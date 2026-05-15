"""
Migration: Make ticket.created_by_id nullable for guest tickets
This allows tickets to be created without a logged-in user
"""
import sqlite3
from datetime import datetime

def migrate():
    """Make created_by_id nullable in ticket table"""
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    
    print("=" * 60)
    print("MIGRATION: Make ticket.created_by_id nullable")
    print("=" * 60)
    
    try:
        # Check current schema
        cursor.execute("PRAGMA table_info(ticket)")
        columns = cursor.fetchall()
        
        print("\n[1] Current ticket table schema:")
        created_by_col = None
        for col in columns:
            if col[1] == 'created_by_id':
                created_by_col = col
                print(f"    {col[1]}: {col[2]} (NOT NULL: {col[3]})")
        
        # Check if already migrated
        if created_by_col and created_by_col[3] == 0:  # 0 means nullable
            print("\n✅ ALREADY MIGRATED: created_by_id is already nullable!")
            print("=" * 60)
            return
        
        # Create new table with nullable created_by_id
        print("\n[2] Creating new ticket table with nullable created_by_id...")
        
        # Drop table if exists from previous failed attempt
        cursor.execute("DROP TABLE IF EXISTS ticket_new")
        
        cursor.execute("""
            CREATE TABLE ticket_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_number VARCHAR NOT NULL UNIQUE,
                subject VARCHAR NOT NULL,
                description TEXT,
                priority VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                category VARCHAR NOT NULL,
                assigned_to_id INTEGER,
                created_by_id INTEGER,  -- Now nullable
                workspace_id INTEGER NOT NULL,
                is_guest INTEGER DEFAULT 0,
                guest_name VARCHAR,
                guest_surname VARCHAR,
                guest_email VARCHAR,
                guest_phone VARCHAR,
                guest_company VARCHAR,
                guest_branch VARCHAR,
                related_project_id INTEGER,
                related_task_id INTEGER,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                resolved_at TIMESTAMP,
                closed_at TIMESTAMP,
                is_archived INTEGER DEFAULT 0,
                archived_at TIMESTAMP,
                FOREIGN KEY (assigned_to_id) REFERENCES user(id),
                FOREIGN KEY (created_by_id) REFERENCES user(id),
                FOREIGN KEY (workspace_id) REFERENCES workspace(id),
                FOREIGN KEY (related_project_id) REFERENCES project(id),
                FOREIGN KEY (related_task_id) REFERENCES task(id)
            )
        """)
        
        # Copy data from old table
        print("[3] Copying data from old table...")
        cursor.execute("""
            INSERT INTO ticket_new 
            SELECT * FROM ticket
        """)
        
        rows_copied = cursor.rowcount
        print(f"    ✓ Copied {rows_copied} tickets")
        
        # Drop old table and rename new one
        print("[4] Replacing old table...")
        cursor.execute("DROP TABLE ticket")
        cursor.execute("ALTER TABLE ticket_new RENAME TO ticket")
        
        # Verify
        cursor.execute("PRAGMA table_info(ticket)")
        columns = cursor.fetchall()
        created_by_col = [col for col in columns if col[1] == 'created_by_id'][0]
        
        print("\n[5] Verification:")
        print(f"    created_by_id: {created_by_col[2]} (NOT NULL: {created_by_col[3]})")
        
        if created_by_col[3] == 0:  # 0 means nullable
            print("\n✅ SUCCESS: created_by_id is now nullable!")
        else:
            print("\n⚠️  WARNING: created_by_id might still be NOT NULL")
        
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
