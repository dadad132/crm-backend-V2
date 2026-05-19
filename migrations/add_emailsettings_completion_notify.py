"""
Add completion notification columns to emailsettings table.
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
        cursor.execute("PRAGMA table_info(emailsettings)")
        columns = {row[1] for row in cursor.fetchall()}
        print(f"emailsettings table has {len(columns)} existing columns")

        new_columns = [
            ('completion_notify_enabled', 'INTEGER NOT NULL DEFAULT 0'),
            ('completion_notify_email',   'TEXT'),
            ('completion_notify_task',    'INTEGER NOT NULL DEFAULT 0'),
            ('completion_notify_ticket',  'INTEGER NOT NULL DEFAULT 0'),
            ('completion_email_subject',  'TEXT'),
            ('completion_email_body',     'TEXT'),
        ]

        for col, col_type in new_columns:
            if col not in columns:
                cursor.execute(f"ALTER TABLE emailsettings ADD COLUMN {col} {col_type}")
                print(f"[OK] Added {col}")
            else:
                print(f"[SKIP] {col} already exists")

        conn.commit()
        print("\n[DONE] EmailSettings completion notify migration completed successfully!")

    except Exception as e:
        print(f"[ERROR] {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
