"""
Add missing columns to userbehavior table for AI suggestion features.
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
        cursor.execute("PRAGMA table_info(userbehavior)")
        columns = {row[1] for row in cursor.fetchall()}
        print(f"userbehavior table has {len(columns)} existing columns")

        new_columns = [
            ('category',          'TEXT'),
            ('preference_key',    'TEXT'),
            ('preference_value',  'TEXT'),
            ('confidence',        'REAL DEFAULT 0.0'),
            ('occurrence_count',  'INTEGER DEFAULT 1'),
            ('last_observed',     'TEXT'),
            ('updated_at',        'TEXT'),
            ('suggestion_type',   'TEXT'),
            ('context_type',      'TEXT'),
            ('context_value',     'TEXT'),
            ('suggestion_data',   'TEXT'),
            ('relevance_score',   'REAL DEFAULT 0.0'),
            ('times_shown',       'INTEGER DEFAULT 0'),
            ('times_accepted',    'INTEGER DEFAULT 0'),
            ('times_dismissed',   'INTEGER DEFAULT 0'),
            ('is_active',         'INTEGER DEFAULT 1'),
            ('expires_at',        'TEXT'),
        ]

        for col, col_type in new_columns:
            if col not in columns:
                cursor.execute(f"ALTER TABLE userbehavior ADD COLUMN {col} {col_type}")
                print(f"[OK] Added {col}")
            else:
                print(f"[SKIP] {col} already exists")

        conn.commit()
        print("\n[DONE] UserBehavior columns migration completed successfully!")

    except Exception as e:
        print(f"[ERROR] {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
