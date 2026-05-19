"""
Webhook dispatcher — fires signed HTTP POST requests to configured URLs
when ticket events occur.

Usage in route handlers:
    from app.core.webhooks import fire_webhook
    await fire_webhook(db, workspace_id, "ticket.created", {"ticket_number": ...})
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Any

import httpx
from sqlmodel import select

logger = logging.getLogger(__name__)

SUPPORTED_EVENTS = {
    "ticket.created",
    "ticket.updated",
    "ticket.closed",
    "ticket.assigned",
}


async def fire_webhook(db, workspace_id: int, event: str, payload: dict[str, Any]) -> None:
    """
    Find all active webhooks for the workspace that subscribe to `event`,
    then send a signed POST to each URL in the background (non-blocking).
    """
    if event not in SUPPORTED_EVENTS:
        return

    from app.models.webhook import Webhook
    webhooks = (
        await db.execute(
            select(Webhook).where(
                Webhook.workspace_id == workspace_id,
                Webhook.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()

    matching = [w for w in webhooks if event in (w.events or "").split(",")]
    if not matching:
        return

    body = json.dumps({
        "event": event,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "data": payload,
    }, default=str)

    for webhook in matching:
        asyncio.create_task(_send(db, webhook, event, body))


async def _send(db, webhook, event: str, body: str) -> None:
    """Send one webhook request and update its status."""
    from app.models.webhook import Webhook

    headers = {
        "Content-Type": "application/json",
        "X-CEM-Event": event,
        "User-Agent": "CEM-Webhook/1.0",
    }

    # HMAC-SHA256 signature so the receiver can verify authenticity
    if webhook.secret:
        sig = hmac.new(
            webhook.secret.encode(),
            body.encode(),
            hashlib.sha256,
        ).hexdigest()
        headers["X-CEM-Signature"] = f"sha256={sig}"

    status_code = None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(webhook.url, content=body, headers=headers)
            status_code = resp.status_code
            if resp.status_code >= 400:
                logger.warning(
                    f"Webhook {webhook.id} ({webhook.url}) returned {resp.status_code}"
                )
    except Exception as exc:
        logger.warning(f"Webhook {webhook.id} ({webhook.url}) failed: {exc}")
        status_code = 0

    # Persist last result
    try:
        row = (await db.execute(
            select(Webhook).where(Webhook.id == webhook.id)
        )).scalar_one_or_none()
        if row:
            row.last_triggered_at = datetime.utcnow()
            row.last_status_code = status_code
            await db.commit()
    except Exception:
        pass
