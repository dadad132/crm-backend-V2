"""
Migration to add comment_id column to ticketattachment table
This links attachments to specific comments when uploaded via comment form
"""
import sqlite3
import os

def migrate():
    # Find the database
    db_paths = [
        'data.db',
        '/root/cem-backend/data.db',
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data.db')
    ]
    
    db_path = None
    for path in db_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print("Database not found!")
        return False
    
    print(f"Using database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(ticketattachment)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'comment_id' in columns:
            print("Column 'comment_id' already exists in ticketattachment table")
            return True
        
        # Add the comment_id column
        print("Adding 'comment_id' column to ticketattachment table...")
        cursor.execute("""
            ALTER TABLE ticketattachment 
            ADD COLUMN comment_id INTEGER REFERENCES ticketcomment(id) ON DELETE CASCADE
        """)
        
        # Create index for better query performance
        print("Creating index on comment_id...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS ix_ticketattachment_comment_id 
            ON ticketattachment(comment_id)
        """)
        
        conn.commit()
        print("Migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
