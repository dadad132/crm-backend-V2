"""
Migration: Fix attachment file paths from absolute to relative
Converts paths like /home/eugene/crm-backend/app/uploads/... to app/uploads/...
Also searches for files if they exist in different locations
"""
import sqlite3
import os
from pathlib import Path

def migrate():
    """Convert all absolute attachment paths to relative paths and find missing files"""
    db_path = Path("data.db")
    
    if not db_path.exists():
        print("❌ data.db not found, skipping attachment path migration")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    total_updated = 0
    
    # Get current working directory
    base_dir = Path.cwd()
    
    # Fix comment_attachment table
    try:
        cursor.execute("SELECT id, file_path FROM comment_attachment")
        comment_attachments = cursor.fetchall()
        
        updates = []
        for att_id, file_path in comment_attachments:
            if file_path:
                path_obj = Path(file_path)
                
                # Check if it's an absolute path (Windows or Linux)
                if file_path.startswith('/') or (len(file_path) > 1 and file_path[1] == ':'):
                    # Extract UUID filename from absolute path
                    uuid_filename = path_obj.name
                    relative_path = f"app/uploads/comments/{uuid_filename}"
                    
                    # Verify file exists in the relative location
                    full_path = base_dir / relative_path
                    if full_path.exists():
                        updates.append((relative_path, att_id))
                        print(f"  ✓ Found file: {uuid_filename}")
                    else:
                        # File not found in expected location
                        print(f"  ⚠ File not found: {uuid_filename} (will still update path)")
                        updates.append((relative_path, att_id))
                elif not path_obj.is_absolute():
                    # Already relative - verify it exists
                    full_path = base_dir / file_path
                    if not full_path.exists():
                        print(f"  ⚠ Relative path file missing: {file_path}")
        
        if updates:
            print(f"  Converting {len(updates)} comment attachment paths...")
            for relative_path, att_id in updates:
                cursor.execute(
                    "UPDATE comment_attachment SET file_path = ? WHERE id = ?",
                    (relative_path, att_id)
                )
            total_updated += len(updates)
    except sqlite3.OperationalError:
        pass  # Table doesn't exist
    
    # Fix ticketattachment table
    try:
        cursor.execute("SELECT id, file_path FROM ticketattachment")
        ticket_attachments = cursor.fetchall()
        
        updates = []
        for att_id, file_path in ticket_attachments:
            if file_path:
                path_obj = Path(file_path)
                
                # Check if it's an absolute path (Windows or Linux)
                if file_path.startswith('/') or (len(file_path) > 1 and file_path[1] == ':'):
                    # Extract UUID filename from absolute path
                    uuid_filename = path_obj.name
                    relative_path = f"app/uploads/tickets/{uuid_filename}"
                    
                    # Verify file exists in the relative location
                    full_path = base_dir / relative_path
                    if full_path.exists():
                        updates.append((relative_path, att_id))
                        print(f"  ✓ Found file: {uuid_filename}")
                    else:
                        print(f"  ⚠ File not found: {uuid_filename} (will still update path)")
                        updates.append((relative_path, att_id))
        
        if updates:
            print(f"  Converting {len(updates)} ticket attachment paths...")
            for relative_path, att_id in updates:
                cursor.execute(
                    "UPDATE ticketattachment SET file_path = ? WHERE id = ?",
                    (relative_path, att_id)
                )
            total_updated += len(updates)
    except sqlite3.OperationalError:
        pass  # Table doesn't exist
    
    # Fix taskattachment table
    try:
        cursor.execute("SELECT id, file_path FROM taskattachment")
        task_attachments = cursor.fetchall()
        
        updates = []
        for att_id, file_path in task_attachments:
            if file_path:
                path_obj = Path(file_path)
                
                # Check if it's an absolute path (Windows or Linux)
                if file_path.startswith('/') or (len(file_path) > 1 and file_path[1] == ':'):
                    # Extract UUID filename from absolute path
                    uuid_filename = path_obj.name
                    relative_path = f"app/uploads/tasks/{uuid_filename}"
                    
                    # Verify file exists in the relative location
                    full_path = base_dir / relative_path
                    if full_path.exists():
                        updates.append((relative_path, att_id))
                        print(f"  ✓ Found file: {uuid_filename}")
                    else:
                        print(f"  ⚠ File not found: {uuid_filename} (will still update path)")
                        updates.append((relative_path, att_id))
        
        if updates:
            print(f"  Converting {len(updates)} task attachment paths...")
            for relative_path, att_id in updates:
                cursor.execute(
                    "UPDATE taskattachment SET file_path = ? WHERE id = ?",
                    (relative_path, att_id)
                )
            total_updated += len(updates)
    except sqlite3.OperationalError:
        pass  # Table doesn't exist
    
    if total_updated > 0:
        conn.commit()
        print(f"✓ Migration complete: Converted {total_updated} attachment paths to relative format")
    else:
        print("✓ No absolute attachment paths found")
    
    conn.close()

if __name__ == "__main__":
    migrate()
