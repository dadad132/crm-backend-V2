"""
Migration script to add incoming mail fields to EmailSettings table
Run this after pulling the latest code updates
"""
import sqlite3
import sys
from pathlib import Path

def migrate_incoming_mail():
    """Add incoming mail configuration fields to emailsettings table"""
    db_path = Path("data.db")
    
    if not db_path.exists():
        print("❌ Database file 'data.db' not found!")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("📧 Adding incoming mail fields to emailsettings table...")
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(emailsettings)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        
        columns_to_add = {
            'incoming_mail_type': "VARCHAR DEFAULT 'POP3'",
            'incoming_mail_host': "VARCHAR",
            'incoming_mail_port': "INTEGER DEFAULT 110",
            'incoming_mail_username': "VARCHAR",
            'incoming_mail_password': "VARCHAR",
            'incoming_mail_use_ssl': "BOOLEAN DEFAULT 0",
            'webmail_url': "VARCHAR"
        }
        
        added_count = 0
        for column, col_type in columns_to_add.items():
            if column not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE emailsettings ADD COLUMN {column} {col_type}")
                    print(f"  ✓ Added column: {column}")
                    added_count += 1
                except sqlite3.OperationalError as e:
                    if "duplicate column name" not in str(e).lower():
                        raise
                    print(f"  ℹ Column {column} already exists")
            else:
                print(f"  ℹ Column {column} already exists")
        
        conn.commit()
        
        if added_count > 0:
            print(f"\n✅ Successfully added {added_count} new column(s) to emailsettings table")
        else:
            print("\nℹ All columns already exist, no changes needed")
        
        # Show current structure
        cursor.execute("PRAGMA table_info(emailsettings)")
        columns = cursor.fetchall()
        print(f"\n📋 Current emailsettings table structure ({len(columns)} columns):")
        for col in columns:
            print(f"   - {col[1]} ({col[2]})")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("INCOMING MAIL SETTINGS MIGRATION")
    print("=" * 60)
    print()
    
    success = migrate_incoming_mail()
    
    if success:
        print("\n✅ Migration completed successfully!")
        print("\n📝 Next steps:")
        print("   1. Restart the server: python start_server.py")
        print("   2. Go to Admin → Email Settings")
        print("   3. Configure incoming mail (POP3) details")
        sys.exit(0)
    else:
        print("\n❌ Migration failed! Please check the errors above.")
        sys.exit(1)
