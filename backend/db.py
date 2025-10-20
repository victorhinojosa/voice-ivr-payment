import aiosqlite
import json
from datetime import datetime
from typing import Optional
import os

# Use /app/data for persistence in Docker
DB_PATH = os.getenv("DB_PATH", "data/calls.db")

async def init_db():
    """Initialize SQLite database with calls table."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

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
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO calls (timestamp, caller_phone, transcript, intent, payment_plan, reply_text, confidence, status, confirmation_response, retry_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
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
        ))
        await db.commit()
        return cursor.lastrowid

async def get_all_calls():
    """Retrieve all calls from database."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT id, timestamp, caller_phone, transcript, intent, payment_plan, reply_text, confidence, status, confirmation_response, retry_count
            FROM calls
            ORDER BY timestamp DESC
        """) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def get_pending_clarification(caller_phone: str) -> Optional[int]:
    """Get the most recent pending clarification call ID for a phone number."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT id FROM calls
            WHERE caller_phone = ? AND status = 'pending_clarification'
            ORDER BY timestamp DESC
            LIMIT 1
        """, (caller_phone,)) as cursor:
            row = await cursor.fetchone()
            result = row[0] if row else None
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
    async with aiosqlite.connect(DB_PATH) as db:
        # Append new transcript to existing one
        await db.execute("""
            UPDATE calls
            SET transcript = transcript || ' → ' || ?,
                intent = ?,
                status = ?,
                confirmation_response = ?,
                confidence = ?
            WHERE id = ?
        """, (transcript, intent, status, confirmation_response, confidence, call_id))
        await db.commit()
        print(f"[DEBUG DB] ✓ Call {call_id} updated successfully")

