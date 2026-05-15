"""
Simple migration script to add profile_picture field to User table
Uses direct SQLite connection (no async required)
"""
import sqlite3
import os

def migrate():
    """Add profile_picture column to user table if it doesn't exist"""
    
    # Find the database file
    db_path = 'data.db'
    if not os.path.exists(db_path):
        db_path = '/home/eugene/crm-backend/data.db'
    
    if not os.path.exists(db_path):
        print("❌ Error: Could not find data.db")
        print("Please run this script from the project root directory")
        return False
    
    print(f"Using database: {db_path}")
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column exists
        cursor.execute("PRAGMA table_info(user)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'profile_picture' in columns:
            print("✓ profile_picture column already exists")
            conn.close()
            return True
        
        print("Adding profile_picture column to user table...")
        cursor.execute("ALTER TABLE user ADD COLUMN profile_picture VARCHAR")
        conn.commit()
        
        # Verify it was added
        cursor.execute("PRAGMA table_info(user)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'profile_picture' in columns:
            print("✓ Migration completed successfully!")
            print("\nColumn details:")
            cursor.execute("PRAGMA table_info(user)")
            for row in cursor.fetchall():
                if row[1] == 'profile_picture':
                    print(f"  - Name: {row[1]}")
                    print(f"  - Type: {row[2]}")
                    print(f"  - Column ID: {row[0]}")
            conn.close()
            return True
        else:
            print("❌ Error: Column was not added")
            conn.close()
            return False
            
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Profile Picture Migration Script")
    print("=" * 60)
    print()
    
    success = migrate()
    
    print()
    print("=" * 60)
    if success:
        print("✓ Migration successful!")
        print("\nNext steps:")
        print("1. Restart your server:")
        print("   sudo systemctl restart crm-backend")
        print("   OR")
        print("   pkill -f start_server; python start_server.py")
    else:
        print("❌ Migration failed!")
        print("\nTroubleshooting:")
        print("1. Make sure you're in the project directory")
        print("2. Check that data.db exists")
        print("3. Verify you have write permissions")
    print("=" * 60)
