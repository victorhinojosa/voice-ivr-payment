from fastapi import APIRouter
from calls.repository import get_all_calls
from calls.schemas import CallResponse

router = APIRouter(prefix="/api/calls", tags=["calls"])

@router.get("", response_model=list[CallResponse])
async def get_calls():
    """Retrieve all call logs for the dashboard."""
    return await get_all_calls()
