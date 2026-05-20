"""
Ticket model for support/help desk system
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class TicketBase(SQLModel):
    ticket_number: str = Field(index=True, unique=True)  # e.g., "TKT-2024-00001"
    subject: str
    description: Optional[str] = None
    priority: str = Field(default="medium", index=True)  # low, medium, high, urgent
    status: str = Field(default="open", index=True)  # open, in_progress, waiting, resolved, closed
    category: str = Field(default="general", index=True)  # support, bug, feature, billing, general
    assigned_to_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)  # Optional for guest tickets
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    
    # Guest submission fields (for clients without accounts)
    is_guest: bool = Field(default=False)
    guest_name: Optional[str] = None
    guest_surname: Optional[str] = None
    guest_email: Optional[str] = Field(default=None, index=True)
    guest_phone: Optional[str] = None
    guest_company: Optional[str] = None
    guest_office_number: Optional[str] = None
    guest_branch: Optional[str] = None
    
    # Related to project/task (optional)
    related_project_id: Optional[int] = Field(default=None, foreign_key="project.id", index=True)
    related_task_id: Optional[int] = Field(default=None, foreign_key="task.id", index=True)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    closed_by_id: Optional[int] = Field(default=None, foreign_key="user.id")  # Track who closed the ticket
    
    # Scheduled date/time for calendar integration
    scheduled_date: Optional[datetime] = None
    # Working days (comma-separated: "0,1,2,3,4" for Mon-Fri, where Mon=0, Sun=6)
    working_days: Optional[str] = Field(default="0,1,2,3,4")
    
    # Archive support
    is_archived: bool = Field(default=False, index=True)
    archived_at: Optional[datetime] = None
    
    # Closing/Billing details (optional, filled when closing ticket)
    # Job card client details
    job_client_name: Optional[str] = None
    job_client_surname: Optional[str] = None
    job_client_phone: Optional[str] = None
    job_client_office_number: Optional[str] = None
    # Billable items
    billable_traveling: Optional[str] = None
    billable_labour_onsite: Optional[str] = None
    billable_remote_labour: Optional[str] = None
    billable_equipment_used: Optional[str] = None
    # Non-billable items (kept for backwards compatibility)
    non_billable_traveling: Optional[str] = None
    non_billable_labour_onsite: Optional[str] = None
    non_billable_remote_labour: Optional[str] = None
    non_billable_equipment_used: Optional[str] = None
    # Closing notes
    closing_notes: Optional[str] = None


class Ticket(TicketBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class TicketComment(SQLModel, table=True):
    """Comments on tickets"""
    id: Optional[int] = Field(default=None, primary_key=True)
    ticket_id: int = Field(foreign_key="ticket.id", ondelete="CASCADE", index=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)  # Optional for guest email comments
    content: str
    is_internal: bool = False  # Internal notes vs public comments
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TicketAttachment(SQLModel, table=True):
    """File attachments for tickets"""
    # TODO: FUTURE FEATURE - Attachment Labels/Categories
    # Add a 'label' or 'category' field to categorize attachments:
    # Examples: "Purchase Order", "PO", "Invoice", "Quote", "Contract", "Receipt", "Screenshot", "Log File"
    # Could be:
    #   - label: Optional[str] = None  # Free-text label
    #   - category: Optional[str] = None  # Predefined categories from a list
    #   - tags: Optional[str] = None  # JSON array of multiple tags
    # UI would need a dropdown or input field when uploading attachments
    # Also consider: description field for additional context about the attachment
    id: Optional[int] = Field(default=None, primary_key=True)
    ticket_id: int = Field(foreign_key="ticket.id", ondelete="CASCADE", index=True)
    comment_id: Optional[int] = Field(default=None, foreign_key="ticketcomment.id", ondelete="CASCADE", index=True)  # Link to specific comment if attached via comment
    filename: str
    file_path: str
    file_size: int  # in bytes
    mime_type: Optional[str] = None
    uploaded_by_id: Optional[int] = Field(default=None, foreign_key="user.id")  # Optional for guest uploads
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)


class TicketHistory(SQLModel, table=True):
    """Track all changes to tickets"""
    id: Optional[int] = Field(default=None, primary_key=True)
    ticket_id: int = Field(foreign_key="ticket.id", ondelete="CASCADE", index=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")  # Nullable for guest actions
    action: str  # created, status_changed, priority_changed, assigned, commented, closed, etc.
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
