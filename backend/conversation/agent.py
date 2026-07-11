import os
import json
import traceback
from datetime import timedelta
from anthropic import AsyncAnthropic
from conversation.prompts import get_agent_system_prompt, get_ptp_prompt
from conversation.dates import resolve_date_phrase, format_date_spoken, local_today
from conversation.schemas import SessionConfig

client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# =====================================================================
# Robust JSON extraction
# =====================================================================

def _extract_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rstrip("`").strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return raw[start:end + 1]
    return raw


# =====================================================================
# Agent Functions
# =====================================================================

async def extract_ptp(transcript: str, amount_owed: float, config: SessionConfig) -> dict:
    try:
        prompt = get_ptp_prompt(config, amount_owed, transcript)

        message = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = message.content[0].text if message.content else ""
        print(f"[DEBUG] extract_ptp raw response: stop_reason={message.stop_reason!r}, content={response_text!r}")
        result = json.loads(_extract_json(response_text))

        outcome = result.get("outcome", "no_commitment")
        date_phrase = result.get("date_phrase")
        promise_amount = result.get("promise_amount")

        if date_phrase in (None, "null", ""):
            date_phrase = None
        if promise_amount in (None, "null", ""):
            promise_amount = None
        else:
            promise_amount = float(promise_amount)

        promise_date_obj = resolve_date_phrase(date_phrase, language=config.language)
        print(f"[DEBUG] date_phrase={date_phrase!r} resolved to {promise_date_obj}")

        if outcome == "promise_made":
            if promise_date_obj is None:
                promise_date_obj = local_today() + timedelta(days=3)
                print(f"[DEBUG] No usable date_phrase — defaulting to +3 days: {promise_date_obj.isoformat()}")
            if promise_amount is None:
                promise_amount = amount_owed
                print(f"[DEBUG] No promise_amount from Claude — defaulting to amount_owed: {promise_amount}")

        promise_date = promise_date_obj.isoformat() if promise_date_obj else None

        print(f"[DEBUG] extract_ptp result: outcome='{outcome}', date={promise_date}, amount={promise_amount}")
        return {"outcome": outcome, "promise_date": promise_date, "promise_amount": promise_amount}

    except Exception as e:
        print(f"[ERROR] extract_ptp failed: {e}")
        traceback.print_exc()
        return {"outcome": "no_commitment", "promise_date": None, "promise_amount": None}


async def agent_reply(history: list, amount_owed: float, customer_name: str, config: SessionConfig) -> dict:
    try:
        system = get_agent_system_prompt(config, amount_owed, customer_name)

        messages = []
        first_customer_seen = False
        for turn in history:
            role = "assistant" if turn["role"] == "agent" else "user"
            if not first_customer_seen:
                if role == "user":
                    first_customer_seen = True
                else:
                    continue
            messages.append({"role": role, "content": turn["text"]})

        if not messages:
            messages = [{"role": "user", "content": "[conversation started]"}]

        message = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system=system,
            messages=messages,
        )

        raw = message.content[0].text if message.content else ""
        print(f"[DEBUG] agent_reply raw response: stop_reason={message.stop_reason!r}, content={raw!r}")
        result = json.loads(_extract_json(raw))
        reply = result.get("reply", "Could you confirm when you'd be able to make a payment?")
        date_phrase = result.get("date_phrase")
        is_terminal = bool(result.get("is_terminal", False))

        if date_phrase in (None, "null", ""):
            date_phrase = None

        if "{DATE}" in reply:
            resolved = resolve_date_phrase(date_phrase, language=config.language)
            if resolved is None:
                resolved = local_today() + timedelta(days=3)
                print(f"[DEBUG] agent_reply: date_phrase={date_phrase!r} unresolvable — defaulting to +3 days")
            spoken = format_date_spoken(resolved, language=config.language)
            reply = reply.replace("{DATE}", spoken)
            print(f"[DEBUG] agent_reply: date_phrase={date_phrase!r} -> {spoken!r}")

        print(f"[DEBUG] agent_reply: is_terminal={is_terminal}, reply='{reply}'")
        return {"reply": reply, "is_terminal": is_terminal}

    except Exception as e:
        print(f"[ERROR] agent_reply failed: {e}")
        traceback.print_exc()
        if config.language == "Spanish":
            return {"reply": "Alguien se pondrá en contacto contigo pronto. Adiós.", "is_terminal": True}
        return {"reply": "Someone will follow up with you shortly. Goodbye.", "is_terminal": True}