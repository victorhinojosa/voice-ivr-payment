import json
import os
from datetime import date, timedelta, datetime
from typing import Optional
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from pathlib import Path
from zoneinfo import ZoneInfo
import parsedatetime
from dataclasses import dataclass

env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

LOCAL_TZ = ZoneInfo("America/Mexico_City")
_CAL = parsedatetime.Calendar()  # Shared parser; flexible with EN and ES


# =====================================================================
# Session Config
# =====================================================================

@dataclass
class SessionConfig:
    """Configuration for a single voice negotiation session."""
    language: str = "English"  # "English" or "Spanish"
    company_name: str = "Our Company"
    debt_type: str = "credit_card"  # "credit_card", "mortgage", "insurance_premium"

    def validate(self) -> None:
        """Validate config values."""
        if self.language not in ("English", "Spanish"):
            raise ValueError(f"Unsupported language: {self.language}")
        if self.debt_type not in ("credit_card", "mortgage", "insurance_premium"):
            raise ValueError(f"Unsupported debt_type: {self.debt_type}")


# =====================================================================
# Debt Type Terminology
# =====================================================================

DEBT_TERMINOLOGY = {
    "credit_card": {
        "en": {
            "label": "credit card balance",
            "verb": "pay",
            "article": "your",
            "opening_context": "outstanding credit card balance",
        },
        "es": {
            "label": "saldo de tarjeta de crédito",
            "verb": "pagar",
            "article": "su",
            "opening_context": "saldo pendiente de tarjeta de crédito",
        },
    },
    "mortgage": {
        "en": {
            "label": "mortgage payment",
            "verb": "make a payment on",
            "article": "your",
            "opening_context": "overdue mortgage payment",
        },
        "es": {
            "label": "pago hipotecario",
            "verb": "hacer un pago en",
            "article": "su",
            "opening_context": "pago hipotecario vencido",
        },
    },
    "insurance_premium": {
        "en": {
            "label": "insurance premium",
            "verb": "pay",
            "article": "your",
            "opening_context": "overdue insurance premium",
        },
        "es": {
            "label": "prima de seguros",
            "verb": "pagar",
            "article": "su",
            "opening_context": "prima de seguros vencida",
        },
    },
}


# =====================================================================
# Time & Date Utilities
# =====================================================================

def local_today() -> date:
    return datetime.now(LOCAL_TZ).date()


def _local_now_naive() -> datetime:
    """Naive datetime in local time, used as the reference point for parsedatetime."""
    return datetime.now(LOCAL_TZ).replace(tzinfo=None)


def resolve_date_phrase(phrase: Optional[str], language: str = "English") -> Optional[date]:
    """
    Deterministically resolve a raw natural-language timing phrase into an actual date.
    Supports English and Spanish (parsedatetime is flexible with both).
    """
    if not phrase:
        return None
    
    result, parse_status = _CAL.parseDT(phrase, sourceTime=_local_now_naive())
    
    if parse_status == 0:
        print(f"[DEBUG] resolve_date_phrase: phrase={phrase!r}, language={language}, UNPARSEABLE")
        return None
    
    resolved = result.date()
    print(f"[DEBUG] resolve_date_phrase: phrase={phrase!r}, language={language} → {resolved}")
    return resolved

    
def _ordinal(n: int, language: str = "English") -> str:
    """Convert day number to ordinal (1st, 2nd, 3rd, etc.)."""
    if language == "Spanish":
        # Spanish doesn't use ordinals for dates in the same way; just return the number
        return str(n)
    else:
        # English: 1st, 2nd, 3rd, 21st, 22nd, etc.
        if 10 <= n % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return f"{n}{suffix}"


def format_date_spoken(d: date, language: str = "English") -> str:
    """
    Format a date for spoken/natural language.
    
    English: "Thursday, July 16th"
    Spanish: "jueves, 16 de julio"
    """
    if language == "Spanish":
        # Spanish day name, "de", month name
        # weekday in lowercase for consistency with Spanish convention
        day_name = d.strftime('%A').lower()
        month_name = d.strftime('%B').lower()
        return f"{day_name}, {d.day} de {month_name}"
    else:
        return f"{d.strftime('%A')}, {d.strftime('%B')} {_ordinal(d.day, language)}"


# =====================================================================
# Prompt Generation Functions (Phase 2)
# =====================================================================

def get_agent_system_prompt(config: SessionConfig, amount_owed: float) -> str:
    """
    Generate the agent system prompt dynamically based on config.
    
    Supports:
    - Language: English or Spanish
    - Debt type: credit_card, mortgage, insurance_premium
    - Company name: injected into greeting
    
    The tone and rules remain consistent; only language and context change.
    """
    language = config.language
    debt_type = config.debt_type
    company_name = config.company_name
    
    # Get terminology for this language + debt type
    terms = DEBT_TERMINOLOGY[debt_type][language.lower()]
    
    if language == "Spanish":
        prompt = f"""Eres un agente profesional y empático de recuperación de deuda.

Estás hablando con {{customer_name}}, quien tiene un saldo pendiente.
Objetivo: obtener una Promesa de Pago (PTP) por ${amount_owed:.2f}.

Reglas:
- SIEMPRE responde en español, sin importar qué idioma use el cliente.
  Si cambia de idioma, responde en español y si es necesario, pídele amablemente 
  que continúe en español si lo considera apropiado — nunca cambies de idioma tú mismo.
- Dirige al cliente por su nombre cuando sea natural — no en cada línea.
- Expresa la cantidad exacta solo dos veces en toda la conversación: una vez al 
  proponer o confirmar un plan de pago, y una vez en tu confirmación final de cierre.
  En todas las demás respuestas, refiere simplemente al "pago", "esa cantidad", o "eso" 
  — no repitas la cantidad en dólares en cada turno.
- No repitas información que el cliente ya te dio claramente solo para preguntar 
  "¿te parece bien?" — eso desperdicia un turno. Si su respuesta es vaga 
  (ej. "próxima semana", "pronto"), ve directo a pedir el día específico en la 
  misma respuesta, en lugar de confirmar la versión vaga primero.
- Si el cliente menciona un plazo (ej. "mañana", "próximo jueves", "fin de mes"),
  NO intentes calcular o mencionar la fecha exacta del calendario tú mismo — eres poco confiable en esto
  y no debes intentarlo. En su lugar:
  - Establece "date_phrase" con las propias palabras del cliente describiendo el momento, VERBATIM.
  - En "reply", usa el marcador de posición {{DATE}} donde normalmente dirías la fecha exacta
    (ej. "Solo para confirmar, eso es {{DATE}} para el pago de ${amount_owed:.2f} — ¿te parece bien?").
    Este marcador será reemplazado con la fecha correcta automáticamente. Nunca escribas 
    un nombre de día de la semana específico o una fecha de calendario tú mismo, en ninguna parte de la respuesta.
- Si acceden pero NO dan plazo alguno, solo entonces pregunta: "¿Cuándo podrías hacer eso?"
  (sin marcador de posición aquí, y date_phrase debe ser null)
- Si es vago → haz una pregunta de aclaración enfocada, y establece date_phrase en null.
- Después de un compromiso claro O después de 3 turnos del cliente sin progreso → establece is_terminal: true.
- Mantén las respuestas en menos de 2 oraciones. Sé cortés, profesional, nunca amenazante.

Retorna solo JSON estricto: {{"reply": "...", "date_phrase": "phrase verbatim o null", "is_terminal": false}}"""
    else:
        # English version (original logic, same structure but English)
        prompt = f"""You are a professional, empathetic debt collections agent.

You are speaking with {{customer_name}}, who has an outstanding balance.
Goal: obtain a Promise to Pay (PTP) for ${amount_owed:.2f}.

Rules:
- ALWAYS respond in English, no matter what language the customer speaks or writes in.
  If they use a different language, respond in English and only if needed gently ask them to continue
  in English if needed — never switch languages yourself.
- Address the customer by name when it feels natural — not in every line.
- State the exact dollar amount only twice in the whole conversation: once when
  first proposing or confirming a payment plan, and once in your final closing
  confirmation. In every other reply, refer to it simply as "the payment",
  "that amount", or "it" — do not repeat the full dollar figure each turn.
- Do not restate information the customer already clearly gave you just to ask
  "does that work for you?" — that wastes a turn. If their answer is vague
  (e.g. "next week", "soon"), go straight to asking for the specific day in the
  same reply, rather than confirming the vague version first and asking for
  specifics in a separate later turn.
- If the customer mentions a timeframe (e.g., "tomorrow", "next Thursday", "end of the month"),
  do NOT try to calculate or state the actual calendar date yourself — you are unreliable at this
  and must not attempt it. Instead:
  - Set "date_phrase" to the customer's own words describing the timing, verbatim.
  - In "reply", use the literal placeholder {{DATE}} wherever you would normally say the exact
    date (e.g. "Just to confirm, that's {{DATE}} for the ${amount_owed:.2f} payment — does that work for
    you?"). This placeholder will be substituted with the correct date automatically. Never write
    out a specific weekday name or calendar date yourself, anywhere in the reply.
- If they agree but give NO timeframe at all, only then ask: "When would you be able to do that?"
  (no placeholder needed here, and date_phrase should be null)
- If vague → ask a focused clarifying follow-up, and set date_phrase to null.
- After a clear commitment OR after 3 customer turns without progress → set is_terminal: true.
- Keep replies under 2 sentences. Be polite, professional, never threatening.

Return strict JSON only: {{"reply": "...", "date_phrase": "verbatim phrase or null", "is_terminal": false}}"""
    
    return prompt


def get_ptp_prompt(config: SessionConfig, amount_owed: float, transcript: str) -> str:
    """
    Generate the Promise-to-Pay extraction prompt dynamically.
    
    Supports English and Spanish; instructs the model in the target language.
    """
    language = config.language
    debt_type = config.debt_type
    
    # Get terminology for this language + debt type
    terms = DEBT_TERMINOLOGY[debt_type][language.lower()]
    
    if language == "Spanish":
        prompt = f"""Eres un sistema de análisis de transcripciones de llamadas que determina si el cliente 
hizo una Promesa de Pago (PTP).

Cantidad adeudada: ${amount_owed:.2f}
Transcripción del cliente: {transcript}

Determina el resultado y extrae los detalles del compromiso de pago.

Reglas:
- outcome debe ser exactamente uno de: "promise_made", "refused", "no_commitment"
- "promise_made": el cliente expresa disposición o acuerdo para pagar, incluso sin fecha específica 
  (ej. "sí", "claro", "está bien", "voy a pagar", "me parece bien")
- "refused": el cliente rechaza explícitamente o dice que no puede pagar 
  (ej. "no voy a pagar", "no puedo pagar", "no", "me niego", "no debo nada")
- "no_commitment": genuinamente ambiguo, fuera de tema, o poco claro — el cliente ni acepta ni rechaza
- date_phrase: extrae las propias palabras del cliente describiendo CUÁNDO pagará, VERBATIM como lo dijo 
  (ej. "próximo jueves", "mañana", "en dos semanas", "el 20"). NO resuelvas, calcules, o conviertas esto 
  en una fecha de calendario tú mismo — solo extrae la frase sin procesar exactamente como se habló. 
  Si no se mencionó momento alguno, establece esto en null.
- promise_amount: la cantidad en dólares mencionada por el cliente, o null si no se mencionó ninguna

Responde solo con JSON estricto, sin markdown ni explicación:
{{"outcome": "...", "date_phrase": "frase verbatim o null", "promise_amount": 0.0}}"""
    else:
        # English version
        prompt = f"""You are a debt collection AI analyzing a call transcript to determine if the customer made a Promise to Pay (PTP).

Amount owed: ${amount_owed:.2f}
Customer transcript: {transcript}

Determine the outcome and extract the payment commitment details.

Rules:
- outcome must be exactly one of: "promise_made", "refused", "no_commitment"
- "promise_made": customer expresses willingness or agreement to pay, even without a specific date (e.g. "yes", "sure", "okay", "I'll pay", "sounds good")
- "refused": customer explicitly refuses or says they cannot pay (e.g. "I won't pay", "I can't pay", "no", "I refuse", "I don't owe anything")
- "no_commitment": genuinely ambiguous, off-topic, or unclear — the customer neither agrees nor refuses
- date_phrase: extract the customer's own words describing WHEN they will pay, VERBATIM as they said it (e.g. "next Thursday", "tomorrow", "in two weeks", "the 20th"). Do NOT resolve, calculate, or convert this into an actual calendar date yourself — just extract the raw phrase exactly as spoken. If no timing was mentioned at all, set this to null.
- promise_amount: the dollar amount mentioned by the customer, or null if none was mentioned

Respond with strict JSON only, no markdown, no explanation:
{{"outcome": "...", "date_phrase": "verbatim phrase or null", "promise_amount": 0.0}}"""
    
    return prompt


# =====================================================================
# Agent Functions (Updated to use SessionConfig)
# =====================================================================

async def extract_ptp(transcript: str, amount_owed: float, config: SessionConfig) -> dict:
    """
    Analyze call transcript and extract Promise-to-Pay data.

    Args:
        transcript: The full call transcript (agent + customer turns)
        amount_owed: The debt amount presented during the call
        config: SessionConfig with language + debt_type

    Returns:
        dict with keys: outcome, promise_date (ISO string or None), promise_amount (float or None)
    """
    try:
        prompt = get_ptp_prompt(config, amount_owed, transcript)

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
        date_phrase = result.get("date_phrase")
        promise_amount = result.get("promise_amount")

        if date_phrase in (None, "null", ""):
            date_phrase = None
        if promise_amount in (None, "null", ""):
            promise_amount = None
        else:
            promise_amount = float(promise_amount)

        # Resolve the raw phrase deterministically using language-aware parsing
        promise_date_obj = resolve_date_phrase(date_phrase, language=config.language)
        print(f"[DEBUG] date_phrase={date_phrase!r} resolved to {promise_date_obj}")

        # Apply Python-side defaults for promise_made
        if outcome == "promise_made":
            if promise_date_obj is None:
                promise_date_obj = local_today() + timedelta(days=3)
                print(f"[DEBUG] No usable date_phrase — defaulting to +3 days: {promise_date_obj.isoformat()}")
            if promise_amount is None:
                promise_amount = amount_owed
                print(f"[DEBUG] No promise_amount from Claude — defaulting to amount_owed: {promise_amount}")

        promise_date = promise_date_obj.isoformat() if promise_date_obj else None

        print(f"[DEBUG] extract_ptp result: outcome='{outcome}', date={promise_date}, amount={promise_amount}")
        return {
            "outcome": outcome,
            "promise_date": promise_date,
            "promise_amount": promise_amount
        }

    except Exception as e:
        print(f"[ERROR] extract_ptp failed: {e}")
        return {"outcome": "no_commitment", "promise_date": None, "promise_amount": None}


async def agent_reply(history: list, amount_owed: float, customer_name: str, config: SessionConfig) -> dict:
    """
    Generate the next agent turn in a multi-turn PTP negotiation.

    Args:
        history: list of {"role": "agent"|"customer", "text": "..."} dicts
        amount_owed: the debt amount for this call
        customer_name: name to use in greeting
        config: SessionConfig with language + debt_type

    Returns:
        dict with keys: reply (str), is_terminal (bool)
    """
    try:
        system = get_agent_system_prompt(config, amount_owed)

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
        date_phrase = result.get("date_phrase")
        is_terminal = bool(result.get("is_terminal", False))

        if date_phrase in (None, "null", ""):
            date_phrase = None

        # Resolve the date deterministically and substitute it into the reply
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
        return {"reply": "Someone will follow up with you shortly. Goodbye.", "is_terminal": True}