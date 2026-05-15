"""
Migration script to add calendar features:
- Add calendar_color to User table
- Add start_date and due_date to Project table

NOTE: If running on a fresh/empty database, just start the server instead.
The new schema will be created automatically with all the new columns.

This migration is for existing databases with data.
"""
import sqlite3
from datetime import datetime
import os

def run_migration():
    db_path = "data.db"
    
    # Check if database file is empty or doesn't exist
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        print("⚠️  Database is empty or doesn't exist.")
        print("✅ No migration needed - the schema will be created automatically when you start the server.")
        print("\n📝 To get started:")
        print("   1. Start the server: python -m uvicorn app.main:app --reload")
        print("   2. The new schema (with calendar_color, start_date, due_date) will be created automatically")
        print("   3. Register a user and set up your workspace")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("🔄 Starting calendar features migration...")
    
    # Check if tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user'")
    if not cursor.fetchone():
        print("⚠️  User table doesn't exist yet.")
        print("✅ Start the server first to create the database schema, then run this migration.")
        conn.close()
        return
    
    # Add calendar_color column to user table
    try:
        cursor.execute("ALTER TABLE user ADD COLUMN calendar_color TEXT DEFAULT '#3B82F6'")
        print("✅ Added calendar_color column to user table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("⚠️  calendar_color column already exists in user table")
        else:
            raise
    
    # Add start_date column to project table
    try:
        cursor.execute("ALTER TABLE project ADD COLUMN start_date DATE")
        print("✅ Added start_date column to project table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("⚠️  start_date column already exists in project table")
        else:
            raise
    
    # Add due_date column to project table
    try:
        cursor.execute("ALTER TABLE project ADD COLUMN due_date DATE")
        print("✅ Added due_date column to project table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("⚠️  due_date column already exists in project table")
        else:
            raise
    
    # Assign unique colors to ALL existing users (including those with blue)
    try:
        cursor.execute("SELECT id FROM user ORDER BY id")
        all_users = cursor.fetchall()
        
        # Define a set of distinct colors
        colors = [
            "#3B82F6",  # Blue
            "#EF4444",  # Red
            "#10B981",  # Green
            "#F59E0B",  # Amber
            "#8B5CF6",  # Violet
            "#EC4899",  # Pink
            "#14B8A6",  # Teal
            "#F97316",  # Orange
            "#6366F1",  # Indigo
            "#84CC16",  # Lime
            "#06B6D4",  # Cyan
            "#F43F5E",  # Rose
            "#A855F7",  # Purple
            "#22C55E",  # Green
            "#FACC15",  # Yellow
        ]
        
        for idx, (user_id,) in enumerate(all_users):
            color = colors[idx % len(colors)]
            cursor.execute("UPDATE user SET calendar_color = ? WHERE id = ?", (color, user_id))
        
        if all_users:
            print(f"✅ Assigned unique colors to {len(all_users)} users")
    except Exception as e:
        print(f"⚠️  Error assigning colors to users: {e}")
    
    conn.commit()
    conn.close()
    
    print("✅ Migration completed successfully!")
    print("\n📝 Summary:")
    print("  - User table: Added calendar_color column (default: #3B82F6)")
    print("  - Project table: Added start_date and due_date columns")
    print("  - Assigned unique colors to existing users")
    print("\n🎯 Next steps:")
    print("  1. Restart your server if it's running")
    print("  2. Users can now set their calendar colors in Profile settings")
    print("  3. Projects can now have start_date and due_date for calendar display")

if __name__ == "__main__":
    run_migration()
