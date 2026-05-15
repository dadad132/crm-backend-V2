"""
Migration script to create ticket system tables
Creates: ticket, ticketcomment, ticketattachment, tickethistory tables
"""

import sqlite3
from datetime import datetime

def migrate():
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    
    print("Starting ticket system migration...")
    
    try:
        # Create ticket table
        print("Creating ticket table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ticket (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_number TEXT UNIQUE NOT NULL,
                subject TEXT NOT NULL,
                description TEXT,
                priority TEXT DEFAULT 'medium',
                status TEXT DEFAULT 'open',
                category TEXT DEFAULT 'general',
                assigned_to_id INTEGER,
                created_by_id INTEGER NOT NULL,
                workspace_id INTEGER NOT NULL,
                related_project_id INTEGER,
                related_task_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP,
                closed_at TIMESTAMP,
                is_archived BOOLEAN DEFAULT 0,
                archived_at TIMESTAMP,
                FOREIGN KEY (assigned_to_id) REFERENCES user(id),
                FOREIGN KEY (created_by_id) REFERENCES user(id),
                FOREIGN KEY (workspace_id) REFERENCES workspace(id),
                FOREIGN KEY (related_project_id) REFERENCES project(id),
                FOREIGN KEY (related_task_id) REFERENCES task(id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ticket_number ON ticket(ticket_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ticket_workspace ON ticket(workspace_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ticket_assigned ON ticket(assigned_to_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ticket_status ON ticket(status)")
        print("✓ Created ticket table")
        
        # Create ticketcomment table
        print("Creating ticketcomment table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ticketcomment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                is_internal BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ticket_id) REFERENCES ticket(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES user(id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ticketcomment_ticket ON ticketcomment(ticket_id)")
        print("✓ Created ticketcomment table")
        
        # Create ticketattachment table
        print("Creating ticketattachment table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ticketattachment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                mime_type TEXT,
                uploaded_by_id INTEGER NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ticket_id) REFERENCES ticket(id) ON DELETE CASCADE,
                FOREIGN KEY (uploaded_by_id) REFERENCES user(id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ticketattachment_ticket ON ticketattachment(ticket_id)")
        print("✓ Created ticketattachment table")
        
        # Create tickethistory table
        print("Creating tickethistory table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickethistory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ticket_id) REFERENCES ticket(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES user(id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickethistory_ticket ON tickethistory(ticket_id)")
        print("✓ Created tickethistory table")
        
        conn.commit()
        print("\n✅ Ticket system migration completed successfully!")
        print("   - ticket table created")
        print("   - ticketcomment table created")
        print("   - ticketattachment table created")
        print("   - tickethistory table created")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
