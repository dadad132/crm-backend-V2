"""
Migration script to make user_id nullable in ticketcomment table
This allows guest email comments without requiring a user account
"""
import sqlite3
from pathlib import Path

def migrate():
    db_path = Path(__file__).parent / "data.db"
    
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # SQLite doesn't support ALTER COLUMN directly, so we need to recreate the table
        print("Making user_id nullable in ticketcomment table...")
        
        # Check if the table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ticketcomment'")
        if not cursor.fetchone():
            print("✅ ticketcomment table doesn't exist yet, no migration needed")
            return
        
        # Create new table with nullable user_id
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ticketcomment_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                user_id INTEGER,
                content TEXT NOT NULL,
                is_internal BOOLEAN NOT NULL DEFAULT 0,
                created_at TIMESTAMP NOT NULL,
                FOREIGN KEY (ticket_id) REFERENCES ticket(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES user(id)
            )
        """)
        
        # Copy data from old table
        cursor.execute("""
            INSERT INTO ticketcomment_new (id, ticket_id, user_id, content, is_internal, created_at)
            SELECT id, ticket_id, user_id, content, is_internal, created_at
            FROM ticketcomment
        """)
        
        # Drop old table
        cursor.execute("DROP TABLE ticketcomment")
        
        # Rename new table
        cursor.execute("ALTER TABLE ticketcomment_new RENAME TO ticketcomment")
        
        conn.commit()
        print("✅ Successfully made user_id nullable in ticketcomment table")
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
