import json
import os
import re
from datetime import timedelta
import traceback
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from pathlib import Path
from conversation.dates import resolve_date_phrase, local_today, format_date_spoken
from conversation.schemas import SessionConfig

env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# =====================================================================
# TTS-Friendly Amount Formatting (spelled out in words)
# =====================================================================

_AMOUNT_PATTERN = re.compile(r"\$\s?([\d,]+)(?:\.(\d{2}))?")

# --- English number-to-words -----------------------------------------

_EN_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven",
            "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen",
            "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_EN_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def _en_num_to_words(n: int) -> str:
    if n < 0:
        return "minus " + _en_num_to_words(-n)
    if n < 20:
        return _EN_ONES[n]
    if n < 100:
        tens, rem = divmod(n, 10)
        return _EN_TENS[tens] + (f"-{_EN_ONES[rem]}" if rem else "")
    if n < 1000:
        hundreds, rem = divmod(n, 100)
        return _EN_ONES[hundreds] + " hundred" + (f" {_en_num_to_words(rem)}" if rem else "")
    for divisor, name in [(1_000_000_000, "billion"), (1_000_000, "million"), (1_000, "thousand")]:
        if n >= divisor:
            hi, rem = divmod(n, divisor)
            return _en_num_to_words(hi) + f" {name}" + (f" and {_en_num_to_words(rem)}" if rem else "")
    return str(n)


# --- Spanish number-to-words -----------------------------------------

_ES_UNITS = ["", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve"]
_ES_TEENS = ["diez", "once", "doce", "trece", "catorce", "quince", "dieciséis",
             "diecisiete", "dieciocho", "diecinueve"]
_ES_TWENTIES = ["veinte", "veintiuno", "veintidós", "veintitrés", "veinticuatro",
                "veinticinco", "veintiséis", "veintisiete", "veintiocho", "veintinueve"]
_ES_TENS = ["", "", "veinte", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa"]
_ES_HUNDREDS = ["", "ciento", "doscientos", "trescientos", "cuatrocientos", "quinientos",
                "seiscientos", "setecientos", "ochocientos", "novecientos"]


def _es_two_digits(n: int) -> str:
    if n < 10:
        return _ES_UNITS[n]
    if n < 20:
        return _ES_TEENS[n - 10]
    if n < 30:
        return _ES_TWENTIES[n - 20]
    tens, rem = divmod(n, 10)
    if rem == 0:
        return _ES_TENS[tens]
    return f"{_ES_TENS[tens]} y {_ES_UNITS[rem]}"


def _es_three_digits(n: int) -> str:
    if n == 100:
        return "cien"
    hundreds, rem = divmod(n, 100)
    if hundreds == 0:
        return _es_two_digits(rem)
    prefix = _ES_HUNDREDS[hundreds]
    if rem == 0:
        return prefix
    return f"{prefix} {_es_two_digits(rem)}"


def _es_num_to_words(n: int) -> str:
    if n < 0:
        return "menos " + _es_num_to_words(-n)
    if n == 0:
        return "cero"
    if n < 1000:
        return _es_three_digits(n)
    if n < 1_000_000:
        thousands, rem = divmod(n, 1000)
        thousands_str = "mil" if thousands == 1 else f"{_es_three_digits(thousands)} mil"
        if rem == 0:
            return thousands_str
        return f"{thousands_str} {_es_three_digits(rem)}"
    millions, rem = divmod(n, 1_000_000)
    millions_str = "un millón" if millions == 1 else f"{_es_num_to_words(millions)} millones"
    if rem == 0:
        return millions_str
    return f"{millions_str} {_es_num_to_words(rem)}"


def _es_num_to_words_for_noun(n: int) -> str:
    """
    Spanish requires apocope before a masculine noun: 'uno' -> 'un',
    'veintiuno' -> 'veintiún', 'treinta y uno' -> 'treinta y un'.
    Since we always follow the number with 'pesos'/'centavos', apply that
    adjustment here rather than in the base converter (which is also used
    standalone in tests/other contexts).
    """
    words = _es_num_to_words(n)
    if words == "uno":
        return "un"
    if words.endswith("veintiuno"):
        return words[:-len("veintiuno")] + "veintiún"
    if words.endswith(" uno"):
        return words[:-4] + " un"
    return words


def format_amount_for_speech(text: str, language: str = "English") -> str:
    """
    Rewrite dollar-amount substrings like '$1,500.00' into a fully spelled-out
    spoken form (e.g. 'mil quinientos pesos' / 'one thousand five hundred
    dollars') instead of digits — ElevenLabs pronounces spelled-out numbers
    far more consistently than raw numerals, which sometimes get read as a
    year, a code, or split oddly. Only used for the audio synthesis input —
    the original text (with '$' and digits) is still shown in the transcript/UI.
    """
    def _replace(match):
        whole = int(match.group(1).replace(",", ""))
        cents = match.group(2)
        has_cents = cents is not None and cents != "00"
        cents_val = int(cents) if cents else 0

        if language == "Spanish":
            whole_words = _es_num_to_words_for_noun(whole)
            unit = "peso" if whole == 1 else "pesos"
            result = f"{whole_words} {unit}"
            if has_cents:
                cents_words = _es_num_to_words_for_noun(cents_val)
                cents_unit = "centavo" if cents_val == 1 else "centavos"
                result += f" con {cents_words} {cents_unit}"
            return result
        else:
            whole_words = _en_num_to_words(whole)
            unit = "dollar" if whole == 1 else "dollars"
            result = f"{whole_words} {unit}"
            if has_cents:
                cents_words = _en_num_to_words(cents_val)
                cents_unit = "cent" if cents_val == 1 else "cents"
                result += f" and {cents_words} {cents_unit}"
            return result

    return _AMOUNT_PATTERN.sub(_replace, text)


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