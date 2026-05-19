"""
Add billable/non-billable line items and closing_notes columns to ticket table.
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
        cursor.execute("PRAGMA table_info(ticket)")
        columns = {row[1] for row in cursor.fetchall()}
        print(f"ticket table has {len(columns)} existing columns")

        new_columns = [
            ('billable_traveling',          'TEXT'),
            ('billable_labour_onsite',      'TEXT'),
            ('billable_remote_labour',      'TEXT'),
            ('billable_equipment_used',     'TEXT'),
            ('non_billable_traveling',      'TEXT'),
            ('non_billable_labour_onsite',  'TEXT'),
            ('non_billable_remote_labour',  'TEXT'),
            ('non_billable_equipment_used', 'TEXT'),
            ('closing_notes',               'TEXT'),
        ]

        for col, col_type in new_columns:
            if col not in columns:
                cursor.execute(f"ALTER TABLE task ADD COLUMN {col} {col_type}" if False
                               else f"ALTER TABLE ticket ADD COLUMN {col} {col_type}")
                print(f"[OK] Added {col}")
            else:
                print(f"[SKIP] {col} already exists")

        conn.commit()
        print("\n[DONE] Ticket billing columns migration completed successfully!")

    except Exception as e:
        print(f"[ERROR] {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
