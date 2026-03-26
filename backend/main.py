from fastapi import FastAPI, Form, Request, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client as TwilioClient
from pydantic import BaseModel
from contextlib import asynccontextmanager
from pathlib import Path
import os
from dotenv import load_dotenv

import json

from db import (
    init_db, close_pool,
    create_call, update_call_sid, complete_call, mark_no_answer,
    update_call_duration,
    get_all_calls, get_call_by_sid, get_config, set_config,
)
from claude_agent import extract_ptp, agent_reply

# In-memory conversation state: call_sid → list of {"role": "agent"|"customer", "text": str}
conversations: dict[str, list] = {}

env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    print("Database initialized")
    yield
    await close_pool()
    print("Database connection pool closed")


app = FastAPI(title="Voice IVR PoC", lifespan=lifespan)

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
# Outbound call initiation
# ---------------------------------------------------------------------------

@app.post("/api/calls/initiate")
async def initiate_call():
    """
    Read config, create a DB record, place an outbound Twilio call,
    and attach the Twilio SID to the record.
    """
    print(f"\n[DEBUG] ========== INITIATING OUTBOUND CALL ==========")

    config = await get_config()
    debtor_phone = config["debtor_phone"]
    amount_owed = float(config["amount_owed"])

    print(f"[DEBUG] Calling {debtor_phone}, amount_owed={amount_owed}")

    call_id = await create_call(phone_number=debtor_phone, amount_owed=amount_owed)
    print(f"[DEBUG] Created call record id={call_id}")

    twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    call = twilio_client.calls.create(
        to=debtor_phone,
        from_=TWILIO_PHONE_NUMBER,
        url=f"{BASE_URL}/voice",
        status_callback=f"{BASE_URL}/call-status",
        status_callback_method="POST",
    )

    await update_call_sid(call_id, call.sid)
    print(f"[DEBUG] Twilio call placed: call_sid={call.sid}")

    return {"call_id": call_id, "call_sid": call.sid}


# ---------------------------------------------------------------------------
# Twilio status callback
# ---------------------------------------------------------------------------

@app.post("/call-status")
async def call_status(
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
    CallDuration: int = Form(0),
):
    """
    Twilio status callback. Persists duration on completion; marks no_answer on failure.
    """
    print(f"\n[DEBUG] ========== CALL STATUS CALLBACK ==========")
    print(f"[DEBUG] CallSid={CallSid}, CallStatus={CallStatus}, CallDuration={CallDuration}")

    if CallStatus == "completed" and CallDuration > 0:
        await update_call_duration(CallSid, CallDuration)
        print(f"[DEBUG] Persisted duration={CallDuration}s for call_sid={CallSid}")
    elif CallStatus in ("no-answer", "busy", "failed"):
        call = await get_call_by_sid(CallSid)
        if call:
            await mark_no_answer(call["id"])
            print(f"[DEBUG] Marked call {call['id']} as no_answer (status={CallStatus})")
        else:
            print(f"[WARN] No call record found for sid={CallSid}")

    return Response(status_code=204)


# ---------------------------------------------------------------------------
# IVR voice flow
# ---------------------------------------------------------------------------

@app.get("/voice")
@app.post("/voice")
async def voice_webhook(request: Request):
    """
    Twilio webhook — greet caller and present the payment plan offer.
    Reads amount and plan dynamically from config.
    """
    print(f"\n[DEBUG] ========== INCOMING CALL ==========")

    config = await get_config()
    amount_owed = config.get("amount_owed", "1000.00")

    # Always parse form — works for both POST (Twilio outbound) and GET (direct test)
    try:
        form = await request.form()
    except Exception:
        form = {}
    call_sid = form.get("CallSid") or request.query_params.get("CallSid", "")
    print(f"[DEBUG] CallSid={call_sid}, amount_owed={amount_owed}")

    response = VoiceResponse()

    gather = Gather(
        input="speech",
        action=f"/process-response?call_sid={call_sid}",
        method="POST",
        speech_timeout="3",
        language="en-US",
    )
    opening = (
        f"Hello, this is a courtesy call regarding your outstanding balance of ${amount_owed}. "
        "When would you be able to make a payment?"
    )

    # Seed conversation history for this call
    if call_sid:
        conversations[call_sid] = [{"role": "agent", "text": opening}]
        print(f"[DEBUG] Initialized conversation history for call_sid={call_sid}")

    gather.say(opening, voice="Polly.Joanna")
    response.append(gather)

    response.say("We didn't receive a response. We'll follow up with you shortly. Goodbye.")

    return Response(content=str(response), media_type="application/xml")


@app.post("/process-response")
async def process_response(
    call_sid: str = Query(...),
    SpeechResult: str = Form(None),
    From: str = Form(default="unknown"),
    Confidence: float = Form(0.0),
):
    """
    Process the customer's spoken response.
    Runs a multi-turn agent loop; extracts PTP and persists on terminal turn.
    """
    print(f"\n[DEBUG] ========== PROCESSING CUSTOMER RESPONSE ==========")
    print(f"[DEBUG] call_sid={call_sid}, From={From}")
    print(f"[DEBUG] SpeechResult='{SpeechResult}', Confidence={Confidence}")

    config = await get_config()
    amount_owed = float(config.get("amount_owed", "1000.00"))

    response = VoiceResponse()

    # Retrieve the call record
    call = await get_call_by_sid(call_sid)
    print(f"[DEBUG] get_call_by_sid({call_sid}) returned: {call}")
    if call is None:
        print(f"[ERROR] Cannot persist outcome — call_id is None for call_sid={call_sid}")
    call_id = call["id"] if call else None

    # Load or initialize conversation history
    history = conversations.get(call_sid, [])

    # Handle empty speech
    if not SpeechResult:
        print(f"[DEBUG] No speech detected → no_commitment")
        transcript = json.dumps(history)
        if call_id is None:
            print(f"[ERROR] Cannot persist outcome — call_id is None for call_sid={call_sid}")
        else:
            await complete_call(call_id=call_id, outcome="no_commitment", transcript=transcript)
        conversations.pop(call_sid, None)
        response.say("We weren't able to confirm a date. Someone will reach out to you soon. Goodbye.")
        return Response(content=str(response), media_type="application/xml")

    # Append customer turn
    history.append({"role": "customer", "text": SpeechResult})
    print(f"[DEBUG] Conversation turns so far: {len(history)}")

    # Max-turns guard: customer turns = turns with role "customer"
    customer_turn_count = sum(1 for t in history if t["role"] == "customer")
    force_terminal = customer_turn_count >= 4  # 4 customer turns = 8 total history entries
    print(f"[DEBUG] customer_turns={customer_turn_count}, force_terminal={force_terminal}")

    if not force_terminal:
        ar = await agent_reply(history, amount_owed)
        reply_text = ar["reply"]
        is_terminal = ar["is_terminal"]
    else:
        reply_text = "We weren't able to confirm a date. Someone will reach out to you soon. Goodbye."
        is_terminal = True

    print(f"[DEBUG] is_terminal={is_terminal}, reply='{reply_text}'")

    if not is_terminal:
        # Continue conversation — append agent reply and loop back
        history.append({"role": "agent", "text": reply_text})
        conversations[call_sid] = history

        gather = Gather(
            input="speech",
            action=f"/process-response?call_sid={call_sid}",
            method="POST",
            speech_timeout="3",
            language="en-US",
        )
        gather.say(reply_text, voice="Polly.Joanna")
        response.append(gather)
        response.say("We didn't receive a response. We'll follow up with you shortly. Goodbye.")
        return Response(content=str(response), media_type="application/xml")

    # Terminal turn — extract PTP from full transcript and persist
    history.append({"role": "agent", "text": reply_text})
    full_transcript_text = " | ".join(f"{t['role']}: {t['text']}" for t in history)
    transcript_json = json.dumps(history)

    print(f"[DEBUG] Terminal — extracting PTP from full transcript")
    ptp = await extract_ptp(full_transcript_text, amount_owed)
    outcome = ptp["outcome"]
    promise_date = ptp["promise_date"]
    promise_amount = ptp["promise_amount"]

    print(f"[DEBUG] PTP extraction: outcome='{outcome}', date={promise_date}, amount={promise_amount}")

    if call_id:
        await complete_call(
            call_id=call_id,
            outcome=outcome,
            transcript=transcript_json,
            promise_date=promise_date,
            promise_amount=promise_amount,
        )
        print(f"[DEBUG] ✓ Completed call {call_id}: outcome='{outcome}'")

    conversations.pop(call_sid, None)

    # Voice response by outcome
    if outcome == "promise_made":
        closing = (
            f"Thank you. We've recorded your payment commitment of "
            f"${promise_amount:.2f} on {promise_date}. "
            "You'll receive a confirmation shortly. Goodbye."
        )
    elif outcome == "refused":
        closing = "I understand. A specialist will follow up with you. Goodbye."
    else:
        closing = reply_text  # use the agent's closing line

    response.say(closing, voice="Polly.Joanna")
    return Response(content=str(response), media_type="application/xml")


# ---------------------------------------------------------------------------
# Dashboard API
# ---------------------------------------------------------------------------

@app.get("/api/calls")
async def get_calls():
    """Retrieve all call logs for the dashboard."""
    calls = await get_all_calls()
    return {"calls": calls}


@app.get("/api/config")
async def read_config():
    """Return the current runtime config."""
    config = await get_config()
    return config


class ConfigUpdate(BaseModel):
    key: str
    value: str


@app.put("/api/config")
async def write_config(body: ConfigUpdate):
    """Upsert a single config key."""
    print(f"[DEBUG] Config update: {body.key} = {body.value}")
    await set_config(body.key, body.value)
    return {"key": body.key, "value": body.value}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
