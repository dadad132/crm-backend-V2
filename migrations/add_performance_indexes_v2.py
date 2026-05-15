"""
Migration: Add performance indexes to existing database tables.

This adds indexes that were missing from the original model definitions.
These indexes speed up common queries (list pages, dashboard, lookups by FK).

Run: python migrations/add_performance_indexes_v2.py
"""
import sqlite3
from pathlib import Path


def run_migration():
    db_path = Path("data.db")
    if not db_path.exists():
        print("❌ data.db not found")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # List of (index_name, table, column) tuples
    indexes = [
        # Task indexes
        ("ix_task_project_id", "task", "project_id"),
        ("ix_task_creator_id", "task", "creator_id"),
        ("ix_task_parent_task_id", "task", "parent_task_id"),
        ("ix_task_is_archived", "task", "is_archived"),
        
        # Project indexes
        ("ix_project_owner_id", "project", "owner_id"),
        ("ix_project_workspace_id", "project", "workspace_id"),
        
        # Contact indexes
        ("ix_contact_company_id", "contact", "company_id"),
        ("ix_contact_workspace_id", "contact", "workspace_id"),
        
        # Company indexes
        ("ix_company_workspace_id", "company", "workspace_id"),
        
        # Deal indexes
        ("ix_deal_contact_id", "deal", "contact_id"),
        ("ix_deal_company_id", "deal", "company_id"),
        ("ix_deal_assigned_to", "deal", "assigned_to"),
        ("ix_deal_workspace_id", "deal", "workspace_id"),
        
        # Lead indexes
        ("ix_lead_assigned_to", "lead", "assigned_to"),
        ("ix_lead_workspace_id", "lead", "workspace_id"),
        
        # Activity indexes
        ("ix_activity_contact_id", "activity", "contact_id"),
        ("ix_activity_company_id", "activity", "company_id"),
        ("ix_activity_lead_id", "activity", "lead_id"),
        ("ix_activity_deal_id", "activity", "deal_id"),
        ("ix_activity_workspace_id", "activity", "workspace_id"),
        
        # Ticket indexes
        ("ix_ticket_guest_email", "ticket", "guest_email"),
        ("ix_ticket_related_project_id", "ticket", "related_project_id"),
        ("ix_ticket_related_task_id", "ticket", "related_task_id"),
        ("ix_ticket_is_archived", "ticket", "is_archived"),
        
        # Notification indexes
        ("ix_notification_created_at", "notification", "created_at"),
        ("ix_notification_read_at", "notification", "read_at"),
        
        # User indexes
        ("ix_user_workspace_id", "user", "workspace_id"),
        
        # TaskAttachment indexes
        ("ix_taskattachment_task_id", "taskattachment", "task_id"),
        
        # TimeLog indexes
        ("ix_timelog_task_id", "timelog", "task_id"),
        ("ix_timelog_user_id", "timelog", "user_id"),
        
        # ActivityLog indexes
        ("ix_activitylog_workspace_id", "activitylog", "workspace_id"),
        ("ix_activitylog_user_id", "activitylog", "user_id"),
        
        # ProcessedMail indexes
        ("ix_processedmail_workspace_id", "processedmail", "workspace_id"),
    ]
    
    created = 0
    skipped = 0
    
    for idx_name, table, column in indexes:
        try:
            # Check if table exists first
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            if not cursor.fetchone():
                print(f"  ⏭️  Table '{table}' does not exist, skipping {idx_name}")
                skipped += 1
                continue
            
            cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({column})")
            created += 1
        except Exception as e:
            print(f"  ⚠️  Failed to create {idx_name}: {e}")
            skipped += 1
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ Migration complete: {created} indexes created/verified, {skipped} skipped")


if __name__ == "__main__":
    print("🔧 Adding performance indexes to database...")
    run_migration()
