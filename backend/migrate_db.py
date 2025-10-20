import sqlite3
import os

DB_PATH = "calls.db"

def migrate():
    """Add new columns to existing database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if columns exist
    cursor.execute("PRAGMA table_info(calls)")
    columns = [col[1] for col in cursor.fetchall()]

    # Add confirmation_response if it doesn't exist
    if 'confirmation_response' not in columns:
        print("Adding confirmation_response column...")
        cursor.execute("ALTER TABLE calls ADD COLUMN confirmation_response TEXT")
        print("✓ confirmation_response added")
    else:
        print("✓ confirmation_response already exists")

    # Add retry_count if it doesn't exist
    if 'retry_count' not in columns:
        print("Adding retry_count column...")
        cursor.execute("ALTER TABLE calls ADD COLUMN retry_count INTEGER DEFAULT 0")
        print("✓ retry_count added")
    else:
        print("✓ retry_count already exists")

    conn.commit()
    conn.close()
    print("\n✅ Database migration complete!")

if __name__ == "__main__":
    if os.path.exists(DB_PATH):
        migrate()
    else:
        print("No database found. It will be created on first run.")
