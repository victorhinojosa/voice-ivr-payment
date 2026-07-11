"""
Integration tests for the /ws/session WebSocket endpoint.

These hit the *real* FastAPI app through TestClient — the router, the service,
the state machine, the protocol framing all run for real. Only the external
boundaries are mocked: the DB (calls/customers repos), the LLM (agent_reply /
extract_ptp), and TTS/STT (synthesize/transcribe_speech).

KEY DETAIL: we patch each dependency at conversation.service.<name>, i.e. where
the service *looks it up*, not where it's defined. The service did
`from voice.client import synthesize_speech`, so it holds its own reference in
its namespace — patching voice.client.synthesize_speech would not affect it.

Requires httpx (Starlette's TestClient uses it). If TestClient import fails:
    pip install httpx
"""
import base64
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from conversation.state import MAX_CUSTOMER_TURNS


def _audio() -> str:
    # transcribe_speech is mocked, so these bytes are never interpreted —
    # any base64 payload works; the service only needs it to decode cleanly.
    return base64.b64encode(b"fake-audio").decode()


@pytest.fixture
def mocks():
    """Patch every external boundary the session touches, in one place."""
    targets = {
        "get_customer_by_id": AsyncMock(return_value={
            "id": 1, "name": "Alice", "phone": "+521234567890", "amount_owed": 1000.0,
        }),
        "create_call": AsyncMock(return_value=42),
        "update_call_sid": AsyncMock(),
        "complete_call": AsyncMock(),
        "agent_reply": AsyncMock(),
        "extract_ptp": AsyncMock(),
        "transcribe_speech": AsyncMock(),
        "synthesize_speech": AsyncMock(return_value=b"\x00\x01"),
    }
    with ExitStack() as stack:
        for name, mock in targets.items():
            stack.enter_context(patch(f"conversation.service.{name}", mock))
        yield SimpleNamespace(**targets)


def test_ws_reaches_promise(mocks):
    """Happy path: one customer turn, the model ends it, a PTP is extracted
    and returned in the completion frame."""
    mocks.transcribe_speech.return_value = "I can pay next Friday"
    mocks.agent_reply.return_value = {"reply": "Great, all set. Goodbye.", "is_terminal": True}
    mocks.extract_ptp.return_value = {
        "outcome": "promise_made", "promise_date": "2026-07-17", "promise_amount": 1000.0,
    }

    client = TestClient(app)
    with client.websocket_connect("/ws/session") as ws:
        ws.send_json({"type": "start", "customer_id": 1, "language": "English"})

        opening = ws.receive_json()
        assert opening["type"] == "agent"
        assert opening["is_terminal"] is False

        ws.send_json({"type": "user_audio", "audio": _audio()})

        assert ws.receive_json() == {"type": "user", "text": "I can pay next Friday"}

        agent = ws.receive_json()
        assert agent["type"] == "agent"
        assert agent["is_terminal"] is True

        done = ws.receive_json()
        assert done["type"] == "complete"
        assert done["outcome"] == "promise_made"
        assert done["promise_date"] == "2026-07-17"

    mocks.complete_call.assert_awaited_once()


def test_ws_force_close_after_turn_limit(mocks):
    """Turn-limit path: the model keeps replying non-terminal, and the turn-limit
    guard forces the close on the final turn WITHOUT another model call, building
    the closing line from the extracted PTP."""
    mocks.transcribe_speech.return_value = "hmm, not sure yet"
    mocks.agent_reply.return_value = {"reply": "Could you give me a date?", "is_terminal": False}
    mocks.extract_ptp.return_value = {
        "outcome": "promise_made", "promise_date": "2026-07-17", "promise_amount": 1000.0,
    }

    client = TestClient(app)
    with client.websocket_connect("/ws/session") as ws:
        ws.send_json({"type": "start", "customer_id": 1, "language": "English"})
        assert ws.receive_json()["type"] == "agent"  # opening

        # Turns below the limit: model replies, non-terminal.
        for _ in range(MAX_CUSTOMER_TURNS - 1):
            ws.send_json({"type": "user_audio", "audio": _audio()})
            assert ws.receive_json()["type"] == "user"
            agent = ws.receive_json()
            assert agent["type"] == "agent"
            assert agent["is_terminal"] is False

        # The turn that hits the limit: no model call, forced closing from PTP.
        ws.send_json({"type": "user_audio", "audio": _audio()})
        assert ws.receive_json()["type"] == "user"
        agent = ws.receive_json()
        assert agent["type"] == "agent"
        assert agent["is_terminal"] is True
        assert "July" in agent["text"]        # spoke the resolved date, not {DATE}
        assert "$1000.00" in agent["text"]

        done = ws.receive_json()
        assert done["type"] == "complete"
        assert done["outcome"] == "promise_made"

    # The model was consulted only on the sub-limit turns; the final turn skipped it.
    assert mocks.agent_reply.await_count == MAX_CUSTOMER_TURNS - 1


def test_ws_unknown_customer_emits_error(mocks):
    """A missing customer raises NotFoundError, which the service turns into the
    protocol error frame rather than crashing the socket."""
    mocks.get_customer_by_id.return_value = None

    client = TestClient(app)
    with client.websocket_connect("/ws/session") as ws:
        ws.send_json({"type": "start", "customer_id": 999})
        err = ws.receive_json()
        assert err["type"] == "error"
        assert "customer not found" in err["message"]