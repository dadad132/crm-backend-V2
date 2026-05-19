from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Workspace(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Branding settings
    site_title: Optional[str] = Field(default=None)
    logo_url: Optional[str] = Field(default=None)
    favicon_url: Optional[str] = Field(default=None)
    primary_color: Optional[str] = Field(default="#2563eb")  # Default blue
    timezone: Optional[str] = Field(default="UTC")  # Default timezone
    
    # Business hours settings for ticket resolution calculation
    business_hours_start: Optional[str] = Field(default="07:30")  # HH:MM format
    business_hours_end: Optional[str] = Field(default="16:00")  # HH:MM format
    business_hours_exclude_weekends: bool = Field(default=True)  # Skip Sat/Sun

    # GUI theme: "crimson" | "ocean" | "forest" | "midnight" | "ember"
    gui_theme: Optional[str] = Field(default="crimson")

    # AI integration for Bubbles assistant
    # Provider: "anthropic" | "openai" | "gemini" | None (rule-based)
    bubbles_ai_provider: Optional[str] = Field(default=None)
    # Generic key field — stores whichever provider's key is active
    anthropic_api_key: Optional[str] = Field(default=None)

    # Relationships are defined from User/Project side to avoid SQLAlchemy 2.0
    # typing issues with generic list annotations in this minimal setup.
