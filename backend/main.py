import time
import base64
import json
import re
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv
from core.database import close_pool
from calls.repository import create_call, update_call_sid, complete_call,get_all_calls
from datetime import date
from voice.formatting import  format_amount_for_speech
from conversation.agent import extract_ptp, agent_reply
from conversation.schemas import SessionConfig
from conversation.dates import format_date_spoken
from customers.router import router as customers_router
from customers.repository import get_customer_by_id
from voice_io import synthesize_speech, transcribe_speech

# In-memory conversation state: session_id → list of {"role": "agent"|"customer", "text": str}
conversations: dict[str, list] = {}

# Call IDs that have already been persisted, to guard against double-writes
# (e.g. terminal turn followed by the finally-block fallback).
_finalized_calls: set = set()

env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Max customer turns before we force the conversation to a close.
MAX_CUSTOMER_TURNS = 6


def clean_transcript(text: str) -> str:
    """Strip STT sound-caption artifacts like '(clicks mouse)' or '(music playing)'
    before the text enters conversation history or gets sent to the LLM."""
    cleaned = re.sub(r"[\(\[][^\)\]]*[\)\]]", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_pool()
    print("Database connection pool closed")


app = FastAPI(title="Voice IVR PoC", lifespan=lifespan)

app.include_router(customers_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"status": "ok", "service": "Voice IVR"}


# ---------------------------------------------------------------------------
# Browser voice session (WebSocket)
# ---------------------------------------------------------------------------
#
# The browser runs speech-to-text and text-to-speech locally (Web Speech API),
# so the backend only ever exchanges text. One WebSocket == one negotiation
# session == one row in the `calls` table.
#
# Protocol (JSON messages):
#   client → server:
#     {"type": "start", "session_id": "<uuid>"}
#     {"type": "user",  "text": "<recognized speech>"}
#     {"type": "end"}                       # user hung up early
#   server → client:
#     {"type": "agent",    "text": "...", "is_terminal": false}
#     {"type": "complete", "outcome": "...", "promise_date": "...", "promise_amount": 0.0}
#     {"type": "error",    "message": "..."}
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


async def _finalize_session(session_id: str, call_id, amount_owed: float, started_at: float, config: SessionConfig):
    """
    Run PTP extraction over the accumulated transcript and persist the call.
    Reuses the exact transcript format and extraction pipeline from the
    Twilio implementation. Returns the PTP dict (or a no_commitment default).
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
    """Log a turn with language annotation for debugging."""
    prefix = "[AGENT SPEAKS]" if role == "agent" else "[CUSTOMER RESPONDS]"
    print(f"{prefix} [LANG={language}] {text[:80]}...")


@app.websocket("/ws/session")
async def voice_session(websocket: WebSocket):
    await websocket.accept()
    print(f"\n[DEBUG] ========== WEBSOCKET SESSION OPENED ==========")

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
            await websocket.send_json({"type": "error", "message": "expected start message"})
            return

        session_id = first.get("session_id") or f"web-{int(started_at * 1000)}"
        
        # Parse session config from start message with defaults
        from conversation.schemas import SessionConfig
        session_config = SessionConfig(
            language=first.get("language", "English"),
            company_name=first.get("company_name", "Our Company"),
            debt_type=first.get("debt_type", "credit_card"),
        )
        try:
            session_config.validate()
        except ValueError as e:
            await websocket.send_json({"type": "error", "message": f"Invalid config: {e}"})
            return
        print(f"[DEBUG] Session config: language={session_config.language}, company={session_config.company_name}, debt_type={session_config.debt_type}")

        # Identity and debt amount come from the customer record — the source of truth.
        customer_id = first.get("customer_id")
        if customer_id is None:
            await websocket.send_json({"type": "error", "message": "customer_id is required"})
            return

        customer = await get_customer_by_id(int(customer_id))
        if customer is None:
            await websocket.send_json({"type": "error", "message": "customer not found"})
            return

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
        # Opening adapts to debt_type and company_name
        if session_config.language == "Spanish":
            opening = (
                f"Hola {customer_name}, le llamamos de {session_config.company_name} respecto a {session_config.debt_type == 'mortgage' and 'su pago hipotecario vencido' or 'su saldo pendiente'} "
                f"de ${amount_owed:.2f}. ¿Cuándo podrías hacer un pago?"
            )
        else:
            debt_context = {
                "credit_card": "outstanding credit card balance",
                "mortgage": "overdue mortgage payment",
                "insurance_premium": "overdue insurance premium",
            }.get(session_config.debt_type, "outstanding balance")
            opening = (
                f"Hello {customer_name}, this is a courtesy call from {session_config.company_name} regarding your "
                f"{debt_context} of ${amount_owed:.2f}. When would you be able to make a payment?"
            )
        
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

            # echo back so the frontend can render it
            await websocket.send_json({"type": "user", "text": speech})
            
            # Log customer turn with language for debugging
            _log_turn("customer", speech, session_config.language)

            if not speech:
                # No usable speech — close out as no_commitment (mirrors empty-speech path).
                reply_text = "We weren't able to confirm a date. Someone will reach out to you soon. Goodbye."
                history.append({"role": "agent", "text": reply_text})
                conversations[session_id] = history
                ptp = await _finalize_session(session_id, call_id, amount_owed, started_at, session_config)
                finalized = True
                await _send_agent_turn(websocket, reply_text, True, language=session_config.language)
                await websocket.send_json({
                    "type": "complete",
                    "outcome": ptp["outcome"],
                    "promise_date": ptp["promise_date"],
                    "promise_amount": ptp["promise_amount"],
                })
                break

            # Append the customer turn.
            conversations[session_id] = history

            # Max-turns guard.
            customer_turns = sum(1 for t in history if t["role"] == "customer")
            force_terminal = customer_turns >= MAX_CUSTOMER_TURNS

            if force_terminal:
                # Don't decide what to say yet — we don't know the real outcome until
                # extraction runs. Skip the model call for this turn.
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

            # Terminal turn — extract PTP and persist.
            ptp = await _finalize_session(session_id, call_id, amount_owed, started_at, session_config)
            finalized = True

            if ptp["outcome"] == "promise_made":
                if reply_text is not None:
                    closing = reply_text  # natural model-generated confirmation, already correct
                else:
                    # force_terminal path — the model never got to speak a natural closing,
                    # so build one from the actual extracted result instead of guessing.
                    promise_date_obj = date.fromisoformat(ptp["promise_date"])
                    if session_config.language == "Spanish":
                        closing = (
                            f"Perfecto, {customer_name}. Te tengo anotado para "
                            f"{format_date_spoken(promise_date_obj, language='Spanish')} para el "
                            f"pago de ${ptp['promise_amount']:.2f}. Gracias por tu tiempo."
                        )
                    else:
                        closing = (
                            f"Perfect, {customer_name}. I have you down for "
                            f"{format_date_spoken(promise_date_obj)} for the "
                            f"${ptp['promise_amount']:.2f} payment. Thank you for your time."
                        )
            elif ptp["outcome"] == "refused":
                closing = "Entiendo. Un especialista se pondrá en contacto contigo. Adiós." if session_config.language == "Spanish" else "I understand. A specialist will follow up with you. Goodbye."
            else:
                if session_config.language == "Spanish":
                    closing = reply_text or "No pudimos confirmar una fecha. Alguien se pondrá en contacto contigo pronto. Adiós."
                else:
                    closing = reply_text or "We weren't able to confirm a date. Someone will reach out to you soon. Goodbye."

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
    except Exception as e:
        print(f"[ERROR] voice_session failed: {e}")
        try:
            await websocket.send_json({"type": "error", "message": "session error"})
        except Exception:
            pass
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
