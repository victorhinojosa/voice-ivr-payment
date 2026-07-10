import asyncpg
import os
import sys
from typing import Optional
from dotenv import load_dotenv
from datetime import datetime

# Fix for Windows asyncpg compatibility
if sys.platform == 'win32':
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

_pool: Optional[asyncpg.Pool] = None

async def get_pool() -> asyncpg.Pool:
    """Get or create the connection pool."""
    global _pool
    if _pool is None:
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL environment variable is not set")
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=60
        )
    return _pool


async def close_pool():
    """Close the connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


# ---------------------------------------------------------------------------
# Call helpers
# ---------------------------------------------------------------------------

async def create_call(
    phone_number: str,
    amount_owed: float,
    customer_id: Optional[int] = None,
    customer_name: Optional[str] = None,
    ) -> int:
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
        """, phone_number, amount_owed, customer_id, customer_name)
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


# async def update_call_duration(call_sid: str, duration_seconds: int) -> None:
#     """Persist call duration received from Twilio's completed status callback."""
#     pool = await get_pool()
#     async with pool.acquire() as conn:
#         await conn.execute("""
#             UPDATE calls SET duration_seconds = $1 WHERE call_sid = $2
#         """, duration_seconds, call_sid)


# async def mark_no_answer(call_id: int) -> None:
#     """Mark a call as no_answer when the customer didn't pick up."""
#     pool = await get_pool()
#     async with pool.acquire() as conn:
#         await conn.execute("""
#             UPDATE calls
#             SET status = 'no_answer', completed_at = $1
#             WHERE id = $2
#         """, datetime.utcnow(), call_id)


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


# async def get_call_by_sid(call_sid: str) -> Optional[dict]:
    """Fetch a single call by Twilio SID — used during webhook processing."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT * FROM calls WHERE call_sid = $1
        """, call_sid)
        return dict(row) if row else None