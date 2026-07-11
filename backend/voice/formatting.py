import re

# This module is pure string work — no env vars are read here, so there is
# deliberately no load_dotenv (the old one pointed at the wrong path anyway
# and loaded nothing this file uses).

# =====================================================================
# STT transcript cleanup
# =====================================================================

def clean_transcript(text: str) -> str:
    """Strip STT sound-caption artifacts like '(clicks mouse)' or
    '(music playing)' before the text enters conversation history or gets
    sent to the LLM."""
    cleaned = re.sub(r"[\(\[][^\)\]]*[\)\]]", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


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