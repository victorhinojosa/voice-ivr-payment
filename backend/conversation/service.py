"""
Voice negotiation session orchestration.

One WebSocket == one negotiation session == one row in the `calls` table.
The browser captures mic audio; this backend transcribes it, runs the LLM
turn loop, extracts a Promise-to-Pay, and persists the outcome.

Pure turn-flow decisions (turn counting, terminal conditions, closing-line
construction) live in conversation.state. This module is the I/O shell that
wires those decisions to the socket, the LLM, TTS/STT, and the DB.

Protocol (JSON messages):
  client -> server:
    {"type": "start", "session_id": "<uuid>", "customer_id": <int>, ...config}
    {"type": "user_audio", "audio": "<base64 webm/opus>"}
    {"type": "end"}                       # user hung up early
  server -> client:
    {"type": "agent",    "text": "...", "audio": "<b64 mp3>", "is_terminal": bool}
    {"type": "user",     "text": "..."}   # echo of recognized speech
    {"type": "complete", "outcome": "...", "promise_date": "...", "promise_amount": 0.0}
    {"type": "error",    "message": "..."}
"""
import time
import base64
import json

from fastapi import WebSocket, WebSocketDisconnect

from calls.repository import create_call, update_call_sid, complete_call
from core.exceptions import AppError, NotFoundError, ValidationError
from customers.repository import get_customer_by_id
from conversation.agent import extract_ptp, agent_reply
from conversation.schemas import SessionConfig
from conversation.state import should_force_close, build_closing_message
from voice.client import synthesize_speech, transcribe_speech
from voice.formatting import format_amount_for_speech, clean_transcript


# In-memory session state. Fine for a single-process PoC; in production this
# becomes a shared store (e.g. Redis) so sessions survive restarts and scale
# across workers. Deliberate choice for now, not an oversight.
conversations: dict[str, list] = {}

# Call IDs already persisted, to guard against double-writes (a terminal turn
# followed by the finally-block fallback).
_finalized_calls: set = set()


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

async def _send_agent_turn(websocket: WebSocket, text: str, is_terminal: bool, language: str = "English"):
    speech_text = format_amount_for_speech(text, language=language)
    audio_bytes = await synthesize_speech(speech_text, language=language)
    await websocket.send_json({
        "type": "agent",
        "text": text,  # keep original with "$" for the transcript/UI
        "audio": base64.b64encode(audio_bytes).decode(),
        "is_terminal": is_terminal,
    })


async def _finalize_session(session_id, call_id, amount_owed, started_at, config: SessionConfig):
    """
    Run PTP extraction over the accumulated transcript and persist the call.
    Idempotent per call_id via _finalized_calls, so the terminal turn and the
    finally-block fallback can't double-write. Returns the PTP dict.
    """
    if call_id is not None and call_id in _finalized_calls:
        return {"outcome": "no_commitment", "promise_date": None, "promise_amount": None}

    history = conversations.get(session_id, [])
    transcript_json = json.dumps(history)
    duration_seconds = max(1, int(time.monotonic() - started_at))

    if not history:
        ptp = {"outcome": "no_commitment", "promise_date": None, "promise_amount": None}
    else:
        full_transcript_text = " | ".join(f"{t['role']}: {t['text']}" for t in history)
        print(f"[DEBUG] Finalizing session {session_id} — extracting PTP (language={config.language})")
        ptp = await extract_ptp(full_transcript_text, amount_owed, config)

    if call_id is not None:
        await complete_call(
            call_id=call_id,
            outcome=ptp["outcome"],
            transcript=transcript_json,
            duration_seconds=duration_seconds,
            promise_date=ptp["promise_date"],
            promise_amount=ptp["promise_amount"],
        )
        _finalized_calls.add(call_id)
        print(f"[DEBUG] Completed call {call_id}: outcome='{ptp['outcome']}'")
    else:
        print(f"[ERROR] Cannot persist outcome — call_id is None for session={session_id}")

    return ptp


def _log_turn(role: str, text: str, language: str = "English"):
    prefix = "[AGENT SPEAKS]" if role == "agent" else "[CUSTOMER RESPONDS]"
    print(f"{prefix} [LANG={language}] {text[:80]}...")


async def _send_error(websocket: WebSocket, message: str):
    """Emit the protocol error frame, tolerating an already-closed socket."""
    try:
        await websocket.send_json({"type": "error", "message": message})
    except Exception:
        pass


def _build_opening(config: SessionConfig, customer_name: str, amount_owed: float) -> str:
    """Agent's first line, adapted to language / company / debt type."""
    if config.language == "Spanish":
        debt_context = (
            "su pago hipotecario vencido"
            if config.debt_type == "mortgage"
            else "su saldo pendiente"
        )
        return (
            f"Hola {customer_name}, le llamamos de {config.company_name} respecto a {debt_context} "
            f"de ${amount_owed:.2f}. ¿Cuándo podrías hacer un pago?"
        )

    debt_context = {
        "credit_card": "outstanding credit card balance",
        "mortgage": "overdue mortgage payment",
        "insurance_premium": "overdue insurance premium",
    }.get(config.debt_type, "outstanding balance")
    return (
        f"Hello {customer_name}, this is a courtesy call from {config.company_name} regarding your "
        f"{debt_context} of ${amount_owed:.2f}. When would you be able to make a payment?"
    )


# ---------------------------------------------------------------------------
# Session driver
# ---------------------------------------------------------------------------

async def run_voice_session(websocket: WebSocket):
    """Drive one full browser voice session over the WebSocket."""
    await websocket.accept()
    print("\n[DEBUG] ========== WEBSOCKET SESSION OPENED ==========")

    session_id = None
    call_id = None
    amount_owed = 1000.0
    started_at = time.monotonic()
    finalized = False
    session_config = None

    try:
        # Wait for the client's "start" message.
        first = await websocket.receive_json()
        if first.get("type") != "start":
            raise ValidationError("expected start message")

        session_id = first.get("session_id") or f"web-{int(started_at * 1000)}"

        # Parse session config from the start message, with defaults.
        session_config = SessionConfig(
            language=first.get("language", "English"),
            company_name=first.get("company_name", "Our Company"),
            debt_type=first.get("debt_type", "credit_card"),
        )
        try:
            session_config.validate()
        except ValueError as e:
            raise ValidationError(f"Invalid config: {e}")
        print(f"[DEBUG] Session config: language={session_config.language}, "
              f"company={session_config.company_name}, debt_type={session_config.debt_type}")

        # Identity and debt amount come from the customer record — the source of truth.
        customer_id = first.get("customer_id")
        if customer_id is None:
            raise ValidationError("customer_id is required")

        customer = await get_customer_by_id(int(customer_id))
        if customer is None:
            raise NotFoundError("customer not found")

        amount_owed = float(customer["amount_owed"])
        debtor_phone = customer["phone"]
        customer_name = customer["name"]

        started_at = time.monotonic()

        # Create the call row, linked to the customer and snapshotting their name.
        call_id = await create_call(
            phone_number=debtor_phone,
            amount_owed=amount_owed,
            customer_id=customer["id"],
            customer_name=customer_name,
        )
        await update_call_sid(call_id, session_id)
        print(f"[DEBUG] Created call id={call_id}, customer_id={customer['id']}, amount_owed={amount_owed}")

        # Seed the conversation with the agent's opening line and speak it.
        opening = _build_opening(session_config, customer_name, amount_owed)
        conversations[session_id] = [{"role": "agent", "text": opening}]
        _log_turn("agent", opening, session_config.language)
        await _send_agent_turn(websocket, opening, False, language=session_config.language)

        # Turn loop.
        while True:
            msg = await websocket.receive_json()
            msg_type = msg.get("type")

            if msg_type == "end":
                print(f"[DEBUG] Client ended session {session_id}")
                break

            if msg_type != "user_audio":
                continue
            audio_b64 = msg.get("audio")
            if not audio_b64:
                continue

            speech = await transcribe_speech(base64.b64decode(audio_b64))
            speech = clean_transcript(speech)

            history = conversations.get(session_id, [])
            history.append({"role": "customer", "text": speech})
            conversations[session_id] = history

            # Echo back so the frontend can render the recognized speech.
            await websocket.send_json({"type": "user", "text": speech})
            _log_turn("customer", speech, session_config.language)

            # No usable speech -> close out as no_commitment. Routed through
            # build_closing_message so the closing respects the session language
            # (this path used to hardcode English).
            if not speech:
                ptp = await _finalize_session(session_id, call_id, amount_owed, started_at, session_config)
                finalized = True
                closing = build_closing_message("no_commitment", ptp, None, session_config, customer_name)
                history.append({"role": "agent", "text": closing})
                conversations[session_id] = history
                await _send_agent_turn(websocket, closing, True, language=session_config.language)
                await websocket.send_json({
                    "type": "complete",
                    "outcome": ptp["outcome"],
                    "promise_date": ptp["promise_date"],
                    "promise_amount": ptp["promise_amount"],
                })
                break

            # Max-turns guard. At the limit we skip the model call — the real
            # outcome isn't known until extraction runs, so we don't let the
            # model improvise a closing line.
            if should_force_close(history):
                reply_text = None
                is_terminal = True
            else:
                ar = await agent_reply(history, amount_owed, customer_name, session_config)
                reply_text = ar["reply"]
                is_terminal = ar["is_terminal"]
                history.append({"role": "agent", "text": reply_text})
                conversations[session_id] = history

                if not is_terminal:
                    await _send_agent_turn(websocket, reply_text, False, language=session_config.language)
                    continue

            # Terminal turn — extract PTP, build the closing line, persist.
            ptp = await _finalize_session(session_id, call_id, amount_owed, started_at, session_config)
            finalized = True

            closing = build_closing_message(
                ptp["outcome"], ptp, reply_text, session_config, customer_name
            )
            history.append({"role": "agent", "text": closing})
            conversations[session_id] = history

            await _send_agent_turn(websocket, closing, True, language=session_config.language)
            await websocket.send_json({
                "type": "complete",
                "outcome": ptp["outcome"],
                "promise_date": ptp["promise_date"],
                "promise_amount": ptp["promise_amount"],
            })
            break

    except WebSocketDisconnect:
        print(f"[DEBUG] WebSocket disconnected (session={session_id})")
    except AppError as e:
        # Expected, client-facing errors (bad start, missing/unknown customer).
        print(f"[DEBUG] voice_session rejected: {e.error_type}: {e.message}")
        await _send_error(websocket, e.message)
    except Exception as e:
        print(f"[ERROR] voice_session failed: {e}")
        await _send_error(websocket, "session error")
    finally:
        # Best-effort persistence if the session ended without a clean terminal turn.
        if session_id is not None and not finalized and call_id is not None:
            try:
                await _finalize_session(session_id, call_id, amount_owed, started_at, session_config)
            except Exception as e:
                print(f"[ERROR] finalize-on-disconnect failed: {e}")
        if session_id is not None:
            conversations.pop(session_id, None)
        if call_id is not None:
            _finalized_calls.discard(call_id)
        try:
            await websocket.close()
        except Exception:
            pass
        print(f"[DEBUG] ========== WEBSOCKET SESSION CLOSED (session={session_id}) ==========")