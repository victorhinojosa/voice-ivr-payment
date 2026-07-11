from calls.schemas import CallCreate
from core.database import get_pool
from datetime import datetime
from typing import Optional

async def create_call(call: CallCreate) -> int:
    """
    Insert a new call row when an outbound call is initiated.
    Returns the new call ID.
    """
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO calls (phone_number, amount_owed, status, customer_id, customer_name)
            VALUES ($1, $2, 'initiated', $3, $4)
            RETURNING id
        """, call.phone_number, call.amount_owed, call.customer_id, call.customer_name)
        return row['id']


async def update_call_sid(call_id: int, call_sid: str) -> None:
    """Attach Twilio's call SID once we have it."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE calls SET call_sid = $1 WHERE id = $2
        """, call_sid, call_id)


async def complete_call(
    call_id: int,
    outcome: str,                        # promise_made | refused | no_commitment
    transcript: str,
    duration_seconds: Optional[int] = None,
    promise_date: Optional[str] = None,  # ISO date string "YYYY-MM-DD"
    promise_amount: Optional[float] = None,
) -> None:
    """
    Mark a call as completed with its outcome and extracted PTP data.
    promise_date and promise_amount are only set when outcome == 'promise_made'.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE calls
            SET
                status           = 'completed',
                outcome          = $1,
                transcript       = $2,
                duration_seconds = $3,
                promise_date     = $4,
                promise_amount   = $5,
                completed_at     = $6
            WHERE id = $7
        """,
            outcome,
            transcript,
            duration_seconds,
            datetime.strptime(promise_date, "%Y-%m-%d").date() if promise_date else None,
            promise_amount,
            datetime.utcnow(),
            call_id,
        )


async def get_all_calls() -> list[dict]:
    """Retrieve all calls ordered by most recent first."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                id, call_sid, phone_number, status, outcome,
                amount_owed, promise_date, promise_amount,
                transcript, duration_seconds, initiated_at, completed_at,
                customer_id, customer_name
            FROM calls
            ORDER BY initiated_at DESC
        """)
        return [dict(row) for row in rows]
