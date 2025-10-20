from fastapi import FastAPI, Form, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from twilio.twiml.voice_response import VoiceResponse, Gather
from contextlib import asynccontextmanager
from pathlib import Path
import os
from dotenv import load_dotenv
import openai

from db import init_db, save_call, get_all_calls, get_pending_clarification, update_call_intent
from claude_agent import process_initial_intent, process_confirmation

env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Initialize OpenAI for Whisper
openai.api_key = os.getenv("OPENAI_API_KEY")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize database
    await init_db()
    print("Database initialized")
    yield
    # Shutdown: cleanup if needed
    print("Shutting down")

app = FastAPI(title="Voice IVR PoC", lifespan=lifespan)

# CORS for React frontend
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

@app.get("/voice")
@app.post("/voice")
async def voice_webhook(request: Request):
    """
    Twilio webhook endpoint - handles incoming calls.
    Returns TwiML to gather speech input from caller.
    """
    response = VoiceResponse()

    # Directly propose payment plan
    gather = Gather(
        input='speech',
        action='/process-response',
        method='POST',
        speech_timeout='3',
        language='en-US'
    )
    gather.say(
        "Hello, this is a courtesy call regarding your outstanding balance of $1,000. "
        "We'd like to propose a payment plan of $200 per month for 5 months. "
        "Would this arrangement work for you?",
        voice="Polly.Joanna"
    )
    response.append(gather)

    # Fallback if no speech detected
    response.say("We didn't receive a response. We'll follow up with you shortly. Goodbye.")

    return Response(content=str(response), media_type="application/xml")

@app.post("/process-response")
async def process_response(
    SpeechResult: str = Form(None),
    From: str = Form(...),
    Confidence: float = Form(0.0)
):
    """
    Process customer's response to the payment plan offer.
    Determine intent and status based on their answer.
    """
    print(f"\n[DEBUG] ========== PROCESSING CUSTOMER RESPONSE ==========")
    print(f"[DEBUG] Customer: {From}")
    print(f"[DEBUG] Response: '{SpeechResult}'")

    response = VoiceResponse()
    offered_plan = "$200/month for 5 months"
    amount_owed = 1000.0

    # Check if this is a follow-up to a clarification request
    pending_call_id = await get_pending_clarification(From)
    if pending_call_id:
        print(f"[DEBUG] Found pending clarification call {pending_call_id} - will update instead of creating new")

    if not SpeechResult:
        response.say("We didn't catch your response. We'll follow up with you shortly. Goodbye.")
        if pending_call_id:
            await update_call_intent(pending_call_id, "", "no_response", "no_response", "no_response", 0)
        else:
            await save_call(
                caller_phone=From,
                transcript="",
                intent="no_response",
                payment_plan=offered_plan,
                reply_text="No response received",
                status="no_response"
            )
        return Response(content=str(response), media_type="application/xml")

    # Analyze the response with Claude
    confirmation = await process_confirmation(SpeechResult)
    print(f"[DEBUG] Claude analysis: answer='{confirmation['answer']}', confidence={confirmation['confidence']}")

    if confirmation["answer"] == "yes":
        # Customer accepted the offer
        intent = "willing_to_pay"
        status = "confirmed"
        reply = "Excellent! We've confirmed your payment plan of $200 per month for 5 months. You'll receive a confirmation by text message shortly. Thank you!"
        print(f"[DEBUG] ✓ Customer ACCEPTED offer → intent='willing_to_pay', status='confirmed'")

    elif confirmation["answer"] == "no":
        # Customer declined - might need negotiation
        intent = "needs_negotiation"
        status = "needs_negotiation"
        reply = "I understand. Let me connect you with a specialist who can discuss alternative payment arrangements. Please hold."
        print(f"[DEBUG] ✓ Customer DECLINED offer → intent='needs_negotiation', status='needs_negotiation'")

    else:
        # Unclear response - repeat the offer and ask again
        intent = "unclear"
        status = "pending_clarification"
        print(f"[DEBUG] ⚠ Unclear response → Repeating offer and asking again")

        # Save the unclear attempt
        await save_call(
            caller_phone=From,
            transcript=SpeechResult,
            intent=intent,
            payment_plan=offered_plan,
            reply_text="Customer asked for clarification - repeating offer",
            confidence=confirmation.get('confidence', 0),
            status=status,
            confirmation_response=confirmation["answer"]
        )
        print(f"[DEBUG] ✓ Saved call: intent='{intent}', status='{status}'")

        # Repeat the offer and gather response again
        gather = Gather(
            input='speech',
            action='/process-response',
            method='POST',
            speech_timeout='3',
            language='en-US'
        )
        gather.say(
            "Of course. You currently owe $1,000. "
            "We're proposing a payment plan of $200 per month for 5 months. "
            "This would clear your balance. Would you like to accept this plan?",
            voice="Polly.Joanna"
        )
        response.append(gather)
        response.say("We'll follow up with you shortly. Goodbye.")
        return Response(content=str(response), media_type="application/xml")

    # Save to database - update if pending, otherwise create new
    if pending_call_id:
        # Update existing clarification call
        print(f"[DEBUG] Updating existing call {pending_call_id}")
        await update_call_intent(
            pending_call_id,
            SpeechResult,
            intent,
            status,
            confirmation["answer"],
            confirmation.get('confidence', 0)
        )
        print(f"[DEBUG] ✓ Updated call {pending_call_id}: intent='{intent}', status='{status}'")
    else:
        # Create new call record
        await save_call(
            caller_phone=From,
            transcript=SpeechResult,
            intent=intent,
            payment_plan=offered_plan,
            reply_text=reply,
            confidence=confirmation.get('confidence', 0),
            status=status,
            confirmation_response=confirmation["answer"]
        )
        print(f"[DEBUG] ✓ Saved new call: intent='{intent}', status='{status}'")

    # Respond to customer
    response.say(reply, voice="Polly.Joanna")

    return Response(content=str(response), media_type="application/xml")


@app.get("/api/calls")
async def get_calls():
    """API endpoint to retrieve all call logs for dashboard."""
    calls = await get_all_calls()
    return {"calls": calls}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
