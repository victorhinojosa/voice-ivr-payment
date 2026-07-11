"""
Pure conversation-state logic: turn counting, terminal decisions, and
closing-message construction.

No I/O lives here — no sockets, no LLM calls, no DB. That is the whole point:
these are decisions the turn loop makes, pulled out so they can be unit-tested
by calling a function and asserting on the result, with zero mocks.
"""
from datetime import date

from conversation.dates import format_date_spoken
from conversation.schemas import SessionConfig

# Max customer turns before we force the conversation to a close.
MAX_CUSTOMER_TURNS = 6


def count_customer_turns(history: list[dict]) -> int:
    """How many turns the customer has taken so far."""
    return sum(1 for t in history if t["role"] == "customer")


def should_force_close(history: list[dict], max_turns: int = MAX_CUSTOMER_TURNS) -> bool:
    """True once the customer has hit the turn budget and we must close out."""
    return count_customer_turns(history) >= max_turns


def build_closing_message(
    outcome: str,
    ptp: dict,
    model_reply: str | None,
    config: SessionConfig,
    customer_name: str,
) -> str:
    """
    Decide the final spoken line, given the extracted PTP outcome.

    - promise_made + a natural model reply  -> use it verbatim (the model
      already produced a correct confirmation).
    - promise_made + no model reply (forced-close path) -> build a confirmation
      from the extracted date/amount, since the model never got to speak.
    - refused / no_commitment -> language-aware canned closings. `model_reply`
      is used as the no_commitment line when present, otherwise a default.
    """
    es = config.language == "Spanish"

    if outcome == "promise_made":
        if model_reply is not None:
            return model_reply
        promise_date_obj = date.fromisoformat(ptp["promise_date"])
        spoken = format_date_spoken(promise_date_obj, language=config.language)
        if es:
            return (
                f"Perfecto, {customer_name}. Te tengo anotado para {spoken} "
                f"para el pago de ${ptp['promise_amount']:.2f}. Gracias por tu tiempo."
            )
        return (
            f"Perfect, {customer_name}. I have you down for {spoken} for the "
            f"${ptp['promise_amount']:.2f} payment. Thank you for your time."
        )

    if outcome == "refused":
        return (
            "Entiendo. Un especialista se pondrá en contacto contigo. Adiós."
            if es
            else "I understand. A specialist will follow up with you. Goodbye."
        )

    # no_commitment / anything else
    if es:
        return model_reply or (
            "No pudimos confirmar una fecha. Alguien se pondrá en contacto contigo pronto. Adiós."
        )
    return model_reply or (
        "We weren't able to confirm a date. Someone will reach out to you soon. Goodbye."
    )