from fastapi import APIRouter, WebSocket

from conversation.service import run_voice_session

router = APIRouter()


@router.websocket("/ws/session")
async def voice_session(websocket: WebSocket):
    """Thin transport layer — all orchestration lives in the service."""
    await run_voice_session(websocket)