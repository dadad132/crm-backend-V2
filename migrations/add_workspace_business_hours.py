"""
Add business_hours columns to workspace table.
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
        print(f"workspace table has {len(columns)} existing columns")

        new_columns = [
            ('business_hours_start',            "TEXT DEFAULT '07:30'"),
            ('business_hours_end',              "TEXT DEFAULT '16:00'"),
            ('business_hours_exclude_weekends', 'INTEGER NOT NULL DEFAULT 1'),
        ]

        for col, col_type in new_columns:
            if col not in columns:
                cursor.execute(f"ALTER TABLE workspace ADD COLUMN {col} {col_type}")
                print(f"[OK] Added {col}")
            else:
                print(f"[SKIP] {col} already exists")

        conn.commit()
        print("\n[DONE] Workspace business hours migration completed successfully!")

    except Exception as e:
        print(f"[ERROR] {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
