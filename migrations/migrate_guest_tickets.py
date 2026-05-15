"""
Migration: Add guest ticket support and email settings
- Adds guest submission fields to ticket table
- Creates emailsettings table for admin configuration
"""

import asyncio
import sqlite3
from pathlib import Path


def migrate():
    """Run migration"""
    db_path = Path("data.db")
    
    if not db_path.exists():
        print("❌ Database file not found: data.db")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    print("Starting guest ticket and email settings migration...")
    
    try:
        # 1. Add guest fields to ticket table
        print("\n1. Adding guest fields to ticket table...")
        
        guest_fields = [
            ("is_guest", "INTEGER DEFAULT 0"),
            ("guest_name", "VARCHAR"),
            ("guest_surname", "VARCHAR"),
            ("guest_email", "VARCHAR"),
            ("guest_phone", "VARCHAR"),
            ("guest_company", "VARCHAR"),
            ("guest_branch", "VARCHAR"),
        ]
        
        # Check existing columns
        cursor.execute("PRAGMA table_info(ticket)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        
        for field_name, field_type in guest_fields:
            if field_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE ticket ADD COLUMN {field_name} {field_type}")
                    print(f"  ✓ Added column: {field_name}")
                except sqlite3.OperationalError as e:
                    if "duplicate column" in str(e).lower():
                        print(f"  - Column already exists: {field_name}")
                    else:
                        raise
        
        # 2. Make created_by_id nullable for guest tickets
        print("\n2. Updating created_by_id to be nullable...")
        print("  ℹ Note: SQLite doesn't support modifying column constraints directly")
        print("  ℹ This field will remain required in code but can be NULL for guest tickets")
        
        # 3. Create emailsettings table
        print("\n3. Creating emailsettings table...")
        
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (workspace_id) REFERENCES workspace (id)
            )
        """)
        print("  ✓ Created emailsettings table")
        
        # 4. Set default confirmation body
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
        
        # Check if default settings exist for workspace 1
        cursor.execute("SELECT id FROM emailsettings WHERE workspace_id = 1")
        if not cursor.fetchone():
            print("\n4. Creating default email settings for workspace 1...")
            cursor.execute("""
                INSERT INTO emailsettings (
                    workspace_id,
                    smtp_host,
                    smtp_port,
                    smtp_username,
                    smtp_password,
                    smtp_from_email,
                    smtp_from_name,
                    smtp_use_tls,
                    confirmation_subject,
                    confirmation_body,
                    company_name,
                    auto_reply_enabled
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                1,  # workspace_id
                "smtp.gmail.com",
                587,
                "your-email@gmail.com",  # Admin needs to configure
                "your-app-password",  # Admin needs to configure
                "support@yourdomain.com",  # Admin needs to configure
                "Support Team",
                1,
                "Ticket Confirmation - #{ticket_number}",
                default_body,
                "Support Team",
                1
            ))
            print("  ✓ Created default email settings (admin must configure SMTP credentials)")
        else:
            print("  - Email settings already exist for workspace 1")
        
        conn.commit()
        
        print("\n✅ Migration completed successfully!")
        print("\nNext steps:")
        print("1. Admin should configure email settings at /web/admin/email-settings")
        print("2. Clients can now submit tickets at /web/tickets/guest")
        print("3. Auto-reply emails will be sent when configured")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
