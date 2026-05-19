"""
Public REST API — secured by API key.
External programs call these endpoints using the header:
    X-API-Key: cem_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

All responses are JSON.  Base path: /api/v1/
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.api_key import APIKey
from app.models.ticket import Ticket, TicketComment
from app.models.workspace import Workspace

router = APIRouter(prefix="/v1", tags=["External API"])


# ---------------------------------------------------------------------------
# API-key dependency
# ---------------------------------------------------------------------------

async def require_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_session),
) -> tuple[APIKey, Workspace]:
    """Validate the X-API-Key header and return (api_key_row, workspace)."""
    if not x_api_key or not x_api_key.startswith("cem_"):
        raise HTTPException(status_code=401, detail="Invalid API key format")

    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    api_key = (
        await db.execute(select(APIKey).where(APIKey.key_hash == key_hash))
    ).scalar_one_or_none()

    if not api_key or not api_key.is_active:
        raise HTTPException(status_code=401, detail="API key not found or disabled")

    workspace = (
        await db.execute(select(Workspace).where(Workspace.id == api_key.workspace_id))
    ).scalar_one_or_none()

    if not workspace:
        raise HTTPException(status_code=401, detail="Workspace not found")

    # Update last_used timestamp
    api_key.last_used_at = datetime.utcnow()
    await db.commit()

    return api_key, workspace


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TicketCreateRequest(BaseModel):
    subject: str
    description: Optional[str] = None
    priority: Optional[str] = "medium"   # low | medium | high | urgent
    category: Optional[str] = "general"
    guest_name: Optional[str] = None
    guest_surname: Optional[str] = None
    guest_email: Optional[str] = None
    guest_phone: Optional[str] = None
    guest_company: Optional[str] = None


class TicketUpdateRequest(BaseModel):
    status: Optional[str] = None   # open | in_progress | waiting | resolved | closed
    priority: Optional[str] = None
    category: Optional[str] = None


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _ticket_to_dict(t: Ticket) -> dict:
    return {
        "id": t.id,
        "ticket_number": t.ticket_number,
        "subject": t.subject,
        "description": t.description,
        "status": t.status,
        "priority": t.priority,
        "category": t.category,
        "guest_name": t.guest_name,
        "guest_surname": t.guest_surname,
        "guest_email": t.guest_email,
        "guest_phone": t.guest_phone,
        "guest_company": t.guest_company,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "closed_at": t.closed_at.isoformat() if t.closed_at else None,
    }


# ---------------------------------------------------------------------------
# GET /api/v1/tickets
# ---------------------------------------------------------------------------

@router.get("/tickets")
async def list_tickets(
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    limit: int = Query(50, le=200, description="Max results"),
    offset: int = Query(0, ge=0, description="Skip N results"),
    auth=Depends(require_api_key),
    db: AsyncSession = Depends(get_session),
):
    """List tickets for your workspace. Supports filtering by status and priority."""
    _, workspace = auth
    query = select(Ticket).where(Ticket.workspace_id == workspace.id)
    if status:
        query = query.where(Ticket.status == status)
    if priority:
        query = query.where(Ticket.priority == priority)
    query = query.order_by(Ticket.created_at.desc()).offset(offset).limit(limit)
    tickets = (await db.execute(query)).scalars().all()
    return JSONResponse({
        "count": len(tickets),
        "offset": offset,
        "tickets": [_ticket_to_dict(t) for t in tickets],
    })


# ---------------------------------------------------------------------------
# GET /api/v1/tickets/{ticket_number}
# ---------------------------------------------------------------------------

@router.get("/tickets/{ticket_number}")
async def get_ticket(
    ticket_number: str,
    auth=Depends(require_api_key),
    db: AsyncSession = Depends(get_session),
):
    """Get a single ticket by ticket number (e.g. TKT-2024-00001)."""
    _, workspace = auth
    ticket = (
        await db.execute(
            select(Ticket).where(
                Ticket.workspace_id == workspace.id,
                Ticket.ticket_number == ticket_number,
            )
        )
    ).scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Include comments
    comments = (
        await db.execute(
            select(TicketComment)
            .where(TicketComment.ticket_id == ticket.id)
            .order_by(TicketComment.created_at.asc())
        )
    ).scalars().all()

    data = _ticket_to_dict(ticket)
    data["comments"] = [
        {
            "id": c.id,
            "body": c.body,
            "is_internal": c.is_internal,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in comments
        if not c.is_internal
    ]
    return JSONResponse(data)


# ---------------------------------------------------------------------------
# POST /api/v1/tickets
# ---------------------------------------------------------------------------

@router.post("/tickets", status_code=201)
async def create_ticket(
    payload: TicketCreateRequest,
    auth=Depends(require_api_key),
    db: AsyncSession = Depends(get_session),
):
    """Create a new ticket in your workspace."""
    _, workspace = auth

    # Generate ticket number
    count = (
        await db.execute(
            select(Ticket).where(Ticket.workspace_id == workspace.id)
        )
    ).scalars().all()
    year = datetime.utcnow().year
    ticket_number = f"TKT-{year}-{(len(count) + 1):05d}"

    ticket = Ticket(
        workspace_id=workspace.id,
        ticket_number=ticket_number,
        subject=payload.subject,
        description=payload.description,
        priority=payload.priority or "medium",
        category=payload.category or "general",
        status="open",
        is_guest=True,
        guest_name=payload.guest_name,
        guest_surname=payload.guest_surname,
        guest_email=payload.guest_email,
        guest_phone=payload.guest_phone,
        guest_company=payload.guest_company,
        created_at=datetime.utcnow(),
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    return JSONResponse(_ticket_to_dict(ticket), status_code=201)


# ---------------------------------------------------------------------------
# PATCH /api/v1/tickets/{ticket_number}
# ---------------------------------------------------------------------------

@router.patch("/tickets/{ticket_number}")
async def update_ticket(
    ticket_number: str,
    payload: TicketUpdateRequest,
    auth=Depends(require_api_key),
    db: AsyncSession = Depends(get_session),
):
    """Update ticket status, priority, or category."""
    _, workspace = auth
    ticket = (
        await db.execute(
            select(Ticket).where(
                Ticket.workspace_id == workspace.id,
                Ticket.ticket_number == ticket_number,
            )
        )
    ).scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if payload.status:
        ticket.status = payload.status
        if payload.status == "closed" and not ticket.closed_at:
            ticket.closed_at = datetime.utcnow()
    if payload.priority:
        ticket.priority = payload.priority
    if payload.category:
        ticket.category = payload.category

    await db.commit()
    await db.refresh(ticket)
    return JSONResponse(_ticket_to_dict(ticket))


# ---------------------------------------------------------------------------
# GET /api/v1/ping  — connectivity test (no auth needed)
# ---------------------------------------------------------------------------

@router.get("/ping")
async def ping():
    """Quick connectivity check. No API key required."""
    return JSONResponse({"status": "ok", "message": "CEM API is reachable"})
