"""
Migration script to create subtask table for task breakdown functionality.
Run this script to add the subtask table to your database.
"""

import sqlite3
import os
from datetime import datetime


def column_exists(cursor, table_name, column_name):
    """Check if a column exists in a table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def table_exists(cursor, table_name):
    """Check if a table exists in the database."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", 
        (table_name,)
    )
    return cursor.fetchone() is not None


def run_migration():
    """Create the subtask table if it doesn't exist."""
    
    # Database path
    db_path = os.path.join(os.path.dirname(__file__), "data.db")
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return False
    
    print("=" * 70)
    print("Subtask Migration Script")
    print("=" * 70)
    print(f"\nDatabase: {db_path}\n")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if subtask table already exists
        if table_exists(cursor, "subtask"):
            print("✓ Subtask table already exists - skipping creation")
            conn.close()
            return True
        
        # Create subtask table
        print("Creating subtask table...")
        cursor.execute("""
            CREATE TABLE subtask (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                title VARCHAR NOT NULL,
                is_completed BOOLEAN NOT NULL DEFAULT 0,
                completed_at DATETIME,
                "order" INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES task(id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes for better performance
        print("Creating indexes...")
        cursor.execute("""
            CREATE INDEX ix_subtask_task_id ON subtask(task_id)
        """)
        
        cursor.execute("""
            CREATE INDEX ix_subtask_id ON subtask(id)
        """)
        
        conn.commit()
        print("✓ Subtask table created successfully")
        print("✓ Indexes created successfully")
        
        conn.close()
        
        print("\n" + "=" * 70)
        print("✓ Migration completed successfully!")
        print("=" * 70)
        print("\nYou can now:")
        print("  - Add subtasks to any task")
        print("  - Check off subtasks as you complete them")
        print("  - Track task progress with subtask completion")
        
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        if conn:
            conn.close()
        return False


if __name__ == "__main__":
    success = run_migration()
    exit(0 if success else 1)
