"""
Migration: Add ProcessedMail table for email-to-ticket tracking
"""
import sqlite3
from pathlib import Path


def migrate():
    """Add processedmail table"""
    db_path = Path("data.db")
    
    if not db_path.exists():
        print("❌ Database file not found: data.db")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    print("=" * 70)
    print("MIGRATION: Add ProcessedMail table")
    print("=" * 70)
    
    try:
        # Check if table already exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='processedmail'")
        if cursor.fetchone():
            print("\n✅ ProcessedMail table already exists!")
            print("=" * 70)
            return
        
        print("\n[1] Creating processedmail table...")
        
        cursor.execute("""
            CREATE TABLE processedmail (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id VARCHAR NOT NULL,
                email_from VARCHAR NOT NULL,
                subject VARCHAR NOT NULL,
                processed_at TIMESTAMP NOT NULL,
                ticket_id INTEGER,
                workspace_id INTEGER NOT NULL,
                FOREIGN KEY (ticket_id) REFERENCES ticket(id),
                FOREIGN KEY (workspace_id) REFERENCES workspace(id)
            )
        """)
        
        print("  ✓ Created processedmail table")
        
        # Create index on message_id for fast lookups
        print("\n[2] Creating index on message_id...")
        cursor.execute("""
            CREATE INDEX idx_processedmail_message_id ON processedmail(message_id)
        """)
        print("  ✓ Created index on message_id")
        
        # Create index on workspace_id
        print("\n[3] Creating index on workspace_id...")
        cursor.execute("""
            CREATE INDEX idx_processedmail_workspace_id ON processedmail(workspace_id)
        """)
        print("  ✓ Created index on workspace_id")
        
        conn.commit()
        
        print("\n" + "=" * 70)
        print("✅ MIGRATION COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        print("\nProcessedMail table created for tracking email-to-ticket conversions.")
        print("This prevents duplicate tickets from the same email.")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ MIGRATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
