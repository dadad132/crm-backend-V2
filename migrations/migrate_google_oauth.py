"""
Migration script to add Google OAuth fields to user table
"""
import sqlite3
from pathlib import Path

def migrate():
    db_path = Path(__file__).parent / "data.db"
    
    if not db_path.exists():
        print("[!] Database file not found!")
        print(f"[!] Expected location: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(user)")
        columns = [col[1] for col in cursor.fetchall()]
        
        new_columns = [
            ("google_id", "TEXT"),
            ("google_access_token", "TEXT"),
            ("google_refresh_token", "TEXT"),
            ("google_token_expiry", "TIMESTAMP")
        ]
        
        for col_name, col_type in new_columns:
            if col_name not in columns:
                print(f"[*] Adding column: {col_name}")
                cursor.execute(f"ALTER TABLE user ADD COLUMN {col_name} {col_type}")
            else:
                print(f"[~] Column {col_name} already exists, skipping")
        
        # Create index on google_id for faster lookups
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_user_google_id ON user (google_id)")
            print("[*] Created index on google_id")
        except Exception as e:
            print(f"[~] Index creation note: {e}")
        
        conn.commit()
        print("[+] Migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"[!] Error during migration: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Google OAuth Fields Migration")
    print("=" * 60)
    migrate()
