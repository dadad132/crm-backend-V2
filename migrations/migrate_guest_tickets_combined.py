"""
Combined Migration: Guest Tickets Support
- Adds guest submission fields to ticket table
- Makes created_by_id nullable for guest tickets
- Creates emailsettings table
- Makes tickethistory.user_id nullable
"""

import sqlite3
from pathlib import Path


def migrate():
    """Run combined migration"""
    db_path = Path("data.db")
    
    if not db_path.exists():
        print("❌ Database file not found: data.db")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    print("=" * 70)
    print("COMBINED MIGRATION: Guest Tickets Support")
    print("=" * 70)
    
    try:
        # PART 1: Check if ticket table needs guest columns
        print("\n[PART 1] Checking ticket table for guest columns...")
        cursor.execute("PRAGMA table_info(ticket)")
        existing_columns = {row[1]: row for row in cursor.fetchall()}
        
        needs_guest_migration = 'is_guest' not in existing_columns
        needs_nullable_migration = (
            'created_by_id' in existing_columns and 
            existing_columns['created_by_id'][3] == 1  # 1 means NOT NULL
        )
        
        if not needs_guest_migration and not needs_nullable_migration:
            print("  ✓ Ticket table already has guest support and nullable created_by_id")
        else:
            # Need to recreate table
            print("\n[STEP 1] Creating new ticket table with guest support...")
            
            # Drop if exists from failed attempt
            cursor.execute("DROP TABLE IF EXISTS ticket_new")
            
            # Create new table
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
                    created_by_id INTEGER,  -- Nullable for guest tickets
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
            print("  ✓ Created ticket_new table")
            
            # Copy data
            print("[STEP 2] Copying data from old table...")
            
            # Get old columns
            old_columns = list(existing_columns.keys())
            
            # Build column list for INSERT (only columns that exist in both)
            new_columns = [
                'id', 'ticket_number', 'subject', 'description', 'priority', 
                'status', 'category', 'assigned_to_id', 'created_by_id', 
                'workspace_id', 'related_project_id', 'related_task_id',
                'created_at', 'updated_at', 'resolved_at', 'closed_at',
                'is_archived', 'archived_at'
            ]
            
            # Add guest columns if they already exist
            guest_cols = ['is_guest', 'guest_name', 'guest_surname', 'guest_email', 
                         'guest_phone', 'guest_company', 'guest_branch']
            
            columns_to_copy = [c for c in new_columns if c in old_columns]
            
            # Add guest columns that already exist
            for gc in guest_cols:
                if gc in old_columns:
                    columns_to_copy.append(gc)
            
            cols_str = ', '.join(columns_to_copy)
            
            cursor.execute(f"""
                INSERT INTO ticket_new ({cols_str})
                SELECT {cols_str} FROM ticket
            """)
            
            rows_copied = cursor.rowcount
            print(f"  ✓ Copied {rows_copied} rows")
            
            # Swap tables
            print("[STEP 3] Swapping tables...")
            cursor.execute("DROP TABLE ticket")
            cursor.execute("ALTER TABLE ticket_new RENAME TO ticket")
            print("  ✓ Table swap complete")
            
            # Verify
            cursor.execute("PRAGMA table_info(ticket)")
            new_schema = {row[1]: row for row in cursor.fetchall()}
            
            if 'is_guest' in new_schema:
                print("  ✓ Guest columns added successfully")
            
            if new_schema['created_by_id'][3] == 0:
                print("  ✓ created_by_id is now nullable")
        
        # PART 2: Check if tickethistory needs nullable user_id
        print("\n[PART 2] Checking tickethistory table...")
        cursor.execute("PRAGMA table_info(tickethistory)")
        history_columns = {row[1]: row for row in cursor.fetchall()}
        
        needs_history_migration = (
            'user_id' in history_columns and 
            history_columns['user_id'][3] == 1  # NOT NULL
        )
        
        if not needs_history_migration:
            print("  ✓ tickethistory.user_id is already nullable")
        else:
            print("\n[STEP 4] Making tickethistory.user_id nullable...")
            
            cursor.execute("DROP TABLE IF EXISTS tickethistory_new")
            
            cursor.execute("""
                CREATE TABLE tickethistory_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER NOT NULL,
                    user_id INTEGER,  -- Nullable for guest actions
                    action VARCHAR NOT NULL,
                    field_name VARCHAR,
                    old_value TEXT,
                    new_value TEXT,
                    comment TEXT,
                    created_at TIMESTAMP NOT NULL,
                    FOREIGN KEY (ticket_id) REFERENCES ticket(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES user(id)
                )
            """)
            
            cursor.execute("""
                INSERT INTO tickethistory_new
                SELECT * FROM tickethistory
            """)
            
            rows_copied = cursor.rowcount
            print(f"  ✓ Copied {rows_copied} history rows")
            
            cursor.execute("DROP TABLE tickethistory")
            cursor.execute("ALTER TABLE tickethistory_new RENAME TO tickethistory")
            print("  ✓ tickethistory.user_id is now nullable")
        
        # PART 3: Create emailsettings table
        print("\n[PART 3] Setting up emailsettings table...")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emailsettings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER NOT NULL UNIQUE,
                smtp_host VARCHAR NOT NULL DEFAULT 'smtp.gmail.com',
                smtp_port INTEGER NOT NULL DEFAULT 587,
                smtp_username VARCHAR NOT NULL,
                smtp_password VARCHAR NOT NULL,
                smtp_from_email VARCHAR NOT NULL,
                smtp_from_name VARCHAR NOT NULL DEFAULT 'Support Team',
                smtp_use_tls INTEGER NOT NULL DEFAULT 1,
                confirmation_subject VARCHAR NOT NULL DEFAULT 'Ticket Confirmation - #{ticket_number}',
                confirmation_body TEXT NOT NULL,
                company_name VARCHAR NOT NULL DEFAULT 'Support Team',
                auto_reply_enabled INTEGER NOT NULL DEFAULT 1,
                incoming_mail_type VARCHAR DEFAULT 'pop3',
                incoming_mail_host VARCHAR,
                incoming_mail_port INTEGER DEFAULT 110,
                incoming_mail_username VARCHAR,
                incoming_mail_password VARCHAR,
                incoming_mail_use_ssl INTEGER DEFAULT 0,
                webmail_url VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (workspace_id) REFERENCES workspace (id)
            )
        """)
        print("  ✓ emailsettings table ready")
        
        # Check if default settings exist
        cursor.execute("SELECT id FROM emailsettings WHERE workspace_id = 1")
        if not cursor.fetchone():
            default_body = """Dear {guest_name} {guest_surname},

Thank you for contacting us. Your support ticket has been successfully created.

Ticket Details:
--------------
Ticket Number: {ticket_number}
Subject: {subject}
Status: Open
Priority: {priority}

Our team will review your request and someone will assist you as soon as possible.

You can reference your ticket number {ticket_number} in any future communication.

Best regards,
{company_name} Support Team

---
This is an automated message. Please do not reply to this email."""
            
            cursor.execute("""
                INSERT INTO emailsettings (
                    workspace_id, smtp_host, smtp_port, 
                    smtp_username, smtp_password, smtp_from_email,
                    smtp_from_name, smtp_use_tls,
                    confirmation_subject, confirmation_body,
                    company_name, auto_reply_enabled
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                1, "smtp.example.com", 587,
                "support@example.com", "CHANGE_ME_IN_ADMIN_SETTINGS",
                "support@example.com", "Support Team", 1,
                "Ticket Confirmation - #{ticket_number}", default_body,
                "Your Company Name", 1
            ))
            print("  ✓ Created default email settings (PLEASE UPDATE IN ADMIN PANEL)")
            print("  ⚠️  WARNING: Default email settings created with placeholder values")
            print("  ⚠️  Go to Admin > Email Settings to configure your actual SMTP details")
        else:
            print("  - Email settings already exist")
        
        conn.commit()
        
        print("\n" + "=" * 70)
        print("✅ MIGRATION COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        print("\nNext steps:")
        print("1. Configure email settings at /web/admin/email-settings")
        print("2. Clients can submit tickets at /web/tickets/guest")
        print("3. Restart your server to apply changes")
        
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
