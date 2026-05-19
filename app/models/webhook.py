from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Webhook(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    name: str                          # human label, e.g. "Notify ERP on ticket close"
    url: str                           # destination URL
    secret: Optional[str] = Field(default=None)  # HMAC-SHA256 signing secret
    # Comma-separated event list: ticket.created,ticket.updated,ticket.closed,ticket.assigned
    events: str = Field(default="ticket.created,ticket.closed")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_triggered_at: Optional[datetime] = Field(default=None)
    last_status_code: Optional[int] = Field(default=None)
