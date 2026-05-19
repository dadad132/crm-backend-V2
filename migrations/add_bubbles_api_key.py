"""
Add anthropic_api_key column to workspace table for Bubbles AI integration
"""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def migrate():
    db_path = 'data.db'

    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA table_info(workspace)")
        columns = {row[1] for row in cursor.fetchall()}
        print(f"Existing workspace columns: {columns}")

        if 'anthropic_api_key' not in columns:
            print("Adding anthropic_api_key column...")
            cursor.execute("ALTER TABLE workspace ADD COLUMN anthropic_api_key TEXT")
            print("[OK] Added anthropic_api_key")
        else:
            print("[OK] anthropic_api_key already exists")

        if 'bubbles_ai_provider' not in columns:
            print("Adding bubbles_ai_provider column...")
            cursor.execute("ALTER TABLE workspace ADD COLUMN bubbles_ai_provider TEXT")
            print("[OK] Added bubbles_ai_provider")
        else:
            print("[OK] bubbles_ai_provider already exists")

        conn.commit()
        print("\n[DONE] Bubbles API key migration completed successfully!")

    except Exception as e:
        print(f"[ERROR] Error during migration: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
