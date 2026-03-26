import json
import os
from datetime import date, timedelta
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

PTP_PROMPT = """You are a debt collection AI analyzing a call transcript to determine if the customer made a Promise to Pay (PTP).

Today's date: {today}
Amount owed: ${amount_owed:.2f}
Customer transcript: {transcript}

Determine the outcome and extract any payment commitment details.

Rules:
- outcome must be exactly one of: "promise_made", "refused", "no_commitment"
- "promise_made": customer expresses willingness or agreement to pay, even without a specific date (e.g. "yes", "sure", "okay", "I'll pay", "sounds good")
  - If no date is mentioned, default promise_date to 3 days from today
  - If no amount is mentioned, use amount_owed as promise_amount
  - promise_date and promise_amount must always be non-null when outcome is promise_made
- "refused": customer explicitly refuses or says they cannot pay (e.g. "I won't pay", "I can't pay", "no", "I refuse", "I don't owe anything")
- "no_commitment": genuinely ambiguous, off-topic, or unclear — the customer neither agrees nor refuses
- Resolve relative dates (e.g. "next Friday", "tomorrow") to absolute dates using today's date
- promise_date must be in ISO format "YYYY-MM-DD"
- promise_amount is a float (e.g. 200.0)

Respond with strict JSON only, no markdown, no explanation:
{{"outcome": "...", "promise_date": "YYYY-MM-DD or null", "promise_amount": 0.0}}"""


async def extract_ptp(transcript: str, amount_owed: float) -> dict:
    """
    Analyze call transcript and extract Promise-to-Pay data.

    Args:
        transcript: The customer's spoken response converted to text
        amount_owed: The debt amount presented during the call

    Returns:
        dict with keys: outcome, promise_date (ISO string or None), promise_amount (float or None)
    """
    try:
        prompt = PTP_PROMPT.format(
            today=date.today().isoformat(),
            amount_owed=amount_owed,
            transcript=transcript
        )

        message = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        response_text = message.content[0].text if message.content else ""
        print(f"[DEBUG] extract_ptp raw response: stop_reason={message.stop_reason!r}, content={response_text!r}")
        if response_text.startswith("```"):
            response_text = response_text.split("```", 2)[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.rstrip("`").strip()
        result = json.loads(response_text)

        outcome = result.get("outcome", "no_commitment")
        promise_date = result.get("promise_date")
        promise_amount = result.get("promise_amount")

        # Normalize null-like values
        if promise_date in (None, "null", ""):
            promise_date = None
        if promise_amount in (None, "null", ""):
            promise_amount = None
        else:
            promise_amount = float(promise_amount)

        # Apply Python-side defaults for promise_made
        if outcome == "promise_made":
            if promise_date is None:
                promise_date = (date.today() + timedelta(days=3)).isoformat()
                print(f"[DEBUG] No promise_date from Claude — defaulting to +3 days: {promise_date}")
            if promise_amount is None:
                promise_amount = amount_owed
                print(f"[DEBUG] No promise_amount from Claude — defaulting to amount_owed: {promise_amount}")

        print(f"[DEBUG] extract_ptp result: outcome='{outcome}', date={promise_date}, amount={promise_amount}")
        return {
            "outcome": outcome,
            "promise_date": promise_date,
            "promise_amount": promise_amount
        }

    except Exception as e:
        print(f"[ERROR] extract_ptp failed: {e}")
        return {"outcome": "no_commitment", "promise_date": None, "promise_amount": None}


AGENT_SYSTEM_PROMPT = """You are a professional, empathetic debt collections agent.

Today's date is {today}.
Goal: obtain a Promise to Pay (PTP) for ${amount_owed:.2f}.

Rules:
- If the customer provides a timeframe (e.g., "tomorrow", "Friday", "end of the month"), 
  INTERPRET the date based on {today} and confirm it back to them naturally.
- DO NOT ask for a "specific date" or "time" if the customer's intent is clear. 
- Time of day is irrelevant; do not ask for it.
- If they agree but give NO timeframe at all, only then ask: "When would you be able to do that?"
- If vague → ask a focused clarifying follow-up.
- After a clear commitment OR after 3 customer turns without progress → set is_terminal: true.
- Keep replies under 2 sentences. Be polite, professional, never threatening.

Return strict JSON only: {{"reply": "...", "is_terminal": false}}"""


async def agent_reply(history: list, amount_owed: float) -> dict:
    """
    Generate the next agent turn in a multi-turn PTP negotiation.

    Args:
        history: list of {"role": "agent"|"customer", "text": "..."} dicts
        amount_owed: the debt amount for this call

    Returns:
        dict with keys: reply (str), is_terminal (bool)
    """
    try:
        system = AGENT_SYSTEM_PROMPT.format(amount_owed=amount_owed, today=date.today().isoformat())

        # Convert history to Anthropic message format.
        # Skip leading agent turns — the API requires first message to be "user".
        messages = []
        first_customer_seen = False
        for turn in history:
            role = "assistant" if turn["role"] == "agent" else "user"
            if not first_customer_seen:
                if role == "user":
                    first_customer_seen = True
                else:
                    continue  # skip leading agent turns
            messages.append({"role": role, "content": turn["text"]})

        if not messages:
            messages = [{"role": "user", "content": "[conversation started]"}]

        message = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            system=system,
            messages=messages,
        )

        raw = message.content[0].text if message.content else ""
        print(f"[DEBUG] agent_reply raw response: stop_reason={message.stop_reason!r}, content={raw!r}")
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rstrip("`").strip()
        result = json.loads(raw)
        reply = result.get("reply", "Could you confirm when you'd be able to make a payment?")
        is_terminal = bool(result.get("is_terminal", False))

        print(f"[DEBUG] agent_reply: is_terminal={is_terminal}, reply='{reply}'")
        return {"reply": reply, "is_terminal": is_terminal}

    except Exception as e:
        print(f"[ERROR] agent_reply failed: {e}")
        return {"reply": "Someone will follow up with you shortly. Goodbye.", "is_terminal": True}
