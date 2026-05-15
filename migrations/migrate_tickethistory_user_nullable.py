"""
Migration: Make tickethistory.user_id nullable for guest tickets
This allows history entries to be created without a logged-in user
"""
import sqlite3
from datetime import datetime

def migrate():
    """Make user_id nullable in tickethistory table"""
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    
    print("=" * 60)
    print("MIGRATION: Make tickethistory.user_id nullable")
    print("=" * 60)
    
    try:
        # Check current schema
        cursor.execute("PRAGMA table_info(tickethistory)")
        columns = cursor.fetchall()
        
        print("\n[1] Current tickethistory table schema:")
        user_id_col = None
        for col in columns:
            if col[1] == 'user_id':
                user_id_col = col
                print(f"    {col[1]}: {col[2]} (NOT NULL: {col[3]})")
        
        # Check if already migrated
        if user_id_col and user_id_col[3] == 0:  # 0 means nullable
            print("\n✅ ALREADY MIGRATED: user_id is already nullable!")
            print("=" * 60)
            return
        
        # Create new table with nullable user_id
        print("\n[2] Creating new tickethistory table with nullable user_id...")
        
        # Drop table if exists from previous failed attempt
        cursor.execute("DROP TABLE IF EXISTS tickethistory_new")
        
        cursor.execute("""
            CREATE TABLE tickethistory_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                user_id INTEGER,  -- Now nullable for guest actions
                action VARCHAR NOT NULL,
                old_value VARCHAR,
                new_value VARCHAR,
                created_at TIMESTAMP NOT NULL,
                FOREIGN KEY (ticket_id) REFERENCES ticket(id),
                FOREIGN KEY (user_id) REFERENCES user(id)
            )
        """)
        
        # Copy data from old table
        print("[3] Copying data from old table...")
        cursor.execute("""
            INSERT INTO tickethistory_new 
            SELECT * FROM tickethistory
        """)
        
        rows_copied = cursor.rowcount
        print(f"    ✓ Copied {rows_copied} history entries")
        
        # Drop old table and rename new one
        print("[4] Replacing old table...")
        cursor.execute("DROP TABLE tickethistory")
        cursor.execute("ALTER TABLE tickethistory_new RENAME TO tickethistory")
        
        # Verify
        cursor.execute("PRAGMA table_info(tickethistory)")
        columns = cursor.fetchall()
        user_id_col = [col for col in columns if col[1] == 'user_id'][0]
        
        print("\n[5] Verification:")
        print(f"    user_id: {user_id_col[2]} (NOT NULL: {user_id_col[3]})")
        
        if user_id_col[3] == 0:  # 0 means nullable
            print("\n✅ SUCCESS: user_id is now nullable!")
        else:
            print("\n⚠️  WARNING: user_id might still be NOT NULL")
        
        conn.commit()
        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
