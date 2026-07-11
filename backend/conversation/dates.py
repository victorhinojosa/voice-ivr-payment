import parsedatetime
import re
from zoneinfo import ZoneInfo
from typing import Optional
from datetime import date, timedelta, datetime

LOCAL_TZ = ZoneInfo("America/Mexico_City")
_CAL = parsedatetime.Calendar()

# =====================================================================
# Spanish date vocabulary (parsedatetime only understands English)
# =====================================================================

_WEEKDAYS_ES_TO_EN = {
    "lunes": "monday", "martes": "tuesday",
    "miércoles": "wednesday", "miercoles": "wednesday",
    "jueves": "thursday", "viernes": "friday",
    "sábado": "saturday", "sabado": "saturday",
    "domingo": "sunday",
}

_MONTHS_ES_TO_EN = {
    "enero": "january", "febrero": "february", "marzo": "march", "abril": "april",
    "mayo": "may", "junio": "june", "julio": "july", "agosto": "august",
    "septiembre": "september", "octubre": "october", "noviembre": "november",
    "diciembre": "december",
}

_PHRASES_ES_TO_EN = {
    "pasado mañana": "in 2 days",
    "pasado manana": "in 2 days",
    "próxima semana": "next week",
    "proxima semana": "next week",
}

_WORDS_ES_TO_EN = {
    "mañana": "tomorrow", "manana": "tomorrow",
    "hoy": "today",
    "próximo": "next", "proximo": "next",
    "próxima": "next", "proxima": "next",
    "siguiente": "next",
    "semanas": "weeks", "semana": "week",
    "días": "days", "dias": "days", "día": "day", "dia": "day",
    "meses": "months", "mes": "month",
    "años": "years", "anos": "years", "año": "year", "ano": "year",
    "quincena": "15 days",
}

_SPANISH_WEEKDAY_NAMES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_SPANISH_MONTH_NAMES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

# "End of month" is extremely common in this domain and parsedatetime's
# handling of it is unreliable — resolve it deterministically instead of
# relying on the general-purpose parser.
_END_OF_MONTH_EN = re.compile(r"\bend of (the )?month\b", re.IGNORECASE)
_END_OF_MONTH_ES = re.compile(r"\b(fin|final(es)?)\s+de?l?\s*mes\b", re.IGNORECASE)


def _translate_spanish_date_phrase(phrase: str) -> str:
    result = phrase.lower()

    for es, en in sorted(_PHRASES_ES_TO_EN.items(), key=lambda x: -len(x[0])):
        result = re.sub(rf"\b{re.escape(es)}\b", en, result)

    for es, en in _WORDS_ES_TO_EN.items():
        result = re.sub(rf"\b{re.escape(es)}\b", en, result)

    for es, en in _WEEKDAYS_ES_TO_EN.items():
        result = re.sub(rf"\b{re.escape(es)}\b", en, result)

    for es, en in _MONTHS_ES_TO_EN.items():
        result = re.sub(rf"\b{re.escape(es)}\b", en, result)

    result = re.sub(r"\b(el|la|los|las|de)\b", "", result)
    result = re.sub(r"\s+", " ", result).strip()

    return result


def _end_of_month_date() -> date:
    """Last calendar day of the current month, in local time."""
    today = local_today()
    if today.month == 12:
        return date(today.year, 12, 31)
    return date(today.year, today.month + 1, 1) - timedelta(days=1)


def local_today() -> date:
    return datetime.now(LOCAL_TZ).date()


def _local_now_naive() -> datetime:
    return datetime.now(LOCAL_TZ).replace(tzinfo=None)


def resolve_date_phrase(phrase: Optional[str], language: str = "English") -> Optional[date]:
    """
    Deterministically resolve a raw natural-language timing phrase into an
    actual date. Handles "end of month" as a special case (unreliable in
    parsedatetime), translates common Spanish vocabulary before falling
    back to parsedatetime, and never lets a parser exception escape —
    worst case, it returns None and the caller applies its own default.
    """
    if not phrase:
        return None

    if _END_OF_MONTH_EN.search(phrase) or _END_OF_MONTH_ES.search(phrase):
        resolved = _end_of_month_date()
        print(f"[DEBUG] resolve_date_phrase: matched end-of-month idiom in {phrase!r} -> {resolved}")
        return resolved

    working_phrase = phrase
    if language == "Spanish":
        working_phrase = _translate_spanish_date_phrase(phrase)
        print(f"[DEBUG] resolve_date_phrase: translated {phrase!r} -> {working_phrase!r}")

    try:
        result, parse_status = _CAL.parseDT(working_phrase, sourceTime=_local_now_naive())
    except Exception as e:
        print(f"[ERROR] resolve_date_phrase: parsedatetime raised {e!r} for phrase={working_phrase!r}")
        return None

    if parse_status == 0:
        print(f"[DEBUG] resolve_date_phrase: phrase={phrase!r}, language={language}, UNPARSEABLE")
        return None

    resolved = result.date()
    print(f"[DEBUG] resolve_date_phrase: phrase={phrase!r}, language={language} -> {resolved}")
    return resolved


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def format_date_spoken(d: date, language: str = "English") -> str:
    if language == "Spanish":
        day_name = _SPANISH_WEEKDAY_NAMES[d.weekday()]
        month_name = _SPANISH_MONTH_NAMES[d.month - 1]
        return f"{day_name}, {d.day} de {month_name}"
    else:
        return f"{d.strftime('%A')}, {d.strftime('%B')} {_ordinal(d.day)}"
