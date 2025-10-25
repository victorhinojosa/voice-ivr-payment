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

async def init_db():
    """Initialize PostgreSQL database with calls table."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS calls (
                id SERIAL PRIMARY KEY,
                timestamp TEXT NOT NULL,
                caller_phone TEXT NOT NULL,
                transcript TEXT,
                intent TEXT,
                payment_plan TEXT,
                reply_text TEXT,
                confidence INTEGER,
                status TEXT DEFAULT 'completed',
                confirmation_response TEXT,
                retry_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

async def save_call(
    caller_phone: str,
    transcript: Optional[str] = None,
    intent: Optional[str] = None,
    payment_plan: Optional[str] = None,
    reply_text: Optional[str] = None,
    confidence: Optional[int] = None,
    status: str = "completed",
    confirmation_response: Optional[str] = None,
    retry_count: int = 0
) -> int:
    """Save call data to database and return call ID."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO calls (timestamp, caller_phone, transcript, intent, payment_plan, reply_text, confidence, status, confirmation_response, retry_count)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING id
        """,
            datetime.utcnow().isoformat(),
            caller_phone,
            transcript,
            intent,
            payment_plan,
            reply_text,
            confidence,
            status,
            confirmation_response,
            retry_count
        )
        return row['id']

async def get_all_calls():
    """Retrieve all calls from database."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, timestamp, caller_phone, transcript, intent, payment_plan, reply_text, confidence, status, confirmation_response, retry_count
            FROM calls
            ORDER BY timestamp DESC
        """)
        return [dict(row) for row in rows]

async def get_pending_clarification(caller_phone: str) -> Optional[int]:
    """Get the most recent pending clarification call ID for a phone number."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT id FROM calls
            WHERE caller_phone = $1 AND status = 'pending_clarification'
            ORDER BY timestamp DESC
            LIMIT 1
        """, caller_phone)
        result = row['id'] if row else None
        print(f"[DEBUG DB] get_pending_clarification({caller_phone}) = {result}")
        return result

async def update_call_intent(
    call_id: int,
    transcript: str,
    intent: str,
    status: str,
    confirmation_response: str,
    confidence: int
):
    """Update an existing call with final intent and status."""
    print(f"[DEBUG DB] Updating call {call_id}: intent='{intent}', status='{status}', confirmation='{confirmation_response}'")
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Append new transcript to existing one
        await conn.execute("""
            UPDATE calls
            SET transcript = transcript || ' → ' || $1,
                intent = $2,
                status = $3,
                confirmation_response = $4,
                confidence = $5
            WHERE id = $6
        """, transcript, intent, status, confirmation_response, confidence, call_id)
        print(f"[DEBUG DB] ✓ Call {call_id} updated successfully")
