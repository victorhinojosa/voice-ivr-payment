"""
Unit tests for conversation.state.

The point of these: no WebSocket, no Claude, no DB, no mocks. Just call the
function and assert on the string/number it returns. If any of these ever
NEEDS a mock, something impure leaked into state.py and should move back to
the service.
"""
from conversation.schemas import SessionConfig
from conversation.state import (
    count_customer_turns,
    should_force_close,
    build_closing_message,
    MAX_CUSTOMER_TURNS,
)


# --- count_customer_turns ------------------------------------------------

def test_count_customer_turns_empty():
    assert count_customer_turns([]) == 0


def test_count_customer_turns_mixed():
    history = [
        {"role": "agent", "text": "hi"},
        {"role": "customer", "text": "hello"},
        {"role": "agent", "text": "when can you pay?"},
        {"role": "customer", "text": "friday"},
    ]
    assert count_customer_turns(history) == 2


# --- should_force_close --------------------------------------------------

def test_should_force_close_below_limit():
    history = [{"role": "customer", "text": "x"}] * (MAX_CUSTOMER_TURNS - 1)
    assert should_force_close(history) is False


def test_should_force_close_at_limit():
    history = [{"role": "customer", "text": "x"}] * MAX_CUSTOMER_TURNS
    assert should_force_close(history) is True


# --- build_closing_message: promise_made, forced-close (no model reply) --
# This is the acceptance criterion "forced-turn-limit closing logic".

def test_closing_promise_forced_english():
    ptp = {"outcome": "promise_made", "promise_date": "2026-07-17", "promise_amount": 1000.0}
    config = SessionConfig(language="English")
    msg = build_closing_message("promise_made", ptp, None, config, "Alice")
    assert "Alice" in msg
    assert "$1000.00" in msg
    assert "2026-07-17" not in msg   # spoken form, never the raw ISO string
    assert "July" in msg


def test_closing_promise_forced_spanish():
    ptp = {"outcome": "promise_made", "promise_date": "2026-07-17", "promise_amount": 1000.0}
    config = SessionConfig(language="Spanish")
    msg = build_closing_message("promise_made", ptp, None, config, "Alice")
    assert "Alice" in msg
    assert "$1000.00" in msg
    assert "julio" in msg            # Spanish month name
    assert "Gracias" in msg


# --- build_closing_message: promise_made with a natural model reply ------

def test_closing_promise_uses_model_reply_verbatim():
    ptp = {"outcome": "promise_made", "promise_date": "2026-07-17", "promise_amount": 1000.0}
    config = SessionConfig(language="English")
    natural = "Perfect, see you Friday for the payment. Thanks!"
    msg = build_closing_message("promise_made", ptp, natural, config, "Alice")
    assert msg == natural            # passes through untouched


# --- build_closing_message: refused --------------------------------------

def test_closing_refused_english():
    config = SessionConfig(language="English")
    msg = build_closing_message("refused", {}, None, config, "Alice")
    assert "specialist" in msg.lower()


def test_closing_refused_spanish():
    config = SessionConfig(language="Spanish")
    msg = build_closing_message("refused", {}, None, config, "Alice")
    assert "especialista" in msg.lower()


# --- build_closing_message: no_commitment --------------------------------

def test_closing_no_commitment_default_english():
    config = SessionConfig(language="English")
    msg = build_closing_message("no_commitment", {}, None, config, "Alice")
    assert "reach out" in msg.lower()


def test_closing_no_commitment_spanish():
    # The empty-speech bug: Spanish session must NOT get an English closing.
    config = SessionConfig(language="Spanish")
    msg = build_closing_message("no_commitment", {}, None, config, "Alice")
    assert "contacto" in msg.lower()


def test_closing_no_commitment_prefers_model_reply():
    config = SessionConfig(language="English")
    msg = build_closing_message("no_commitment", {}, "See you soon.", config, "Alice")
    assert msg == "See you soon."