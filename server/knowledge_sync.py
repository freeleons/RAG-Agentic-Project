"""Feedback loop into the knowledge base: resolved tickets are pushed to
AnythingLLM as raw-text documents so future search_knowledge() calls can find
answers in past resolutions, not just the static policy PDFs.
"""

import requests
from flask import current_app

from server.models import Ticket, db, utcnow


def _document_text(ticket):
    """Build plain text for embedding from a ticket."""
    lines = [
        f"Ticket #{ticket.id}: {ticket.title}",
        f"Category: {ticket.category}",
        f"Priority: {ticket.priority}",
        "",
        "Description:",
        ticket.description,
    ]
    if ticket.resolution_notes:
        lines += ["", "Resolution:", ticket.resolution_notes]
    return "\n".join(lines)


def sync_one_resolved_ticket(ticket):
    """Push one resolved, unsynced ticket into the knowledge base.

    On success, stamps kb_synced_at. Failures are logged only (non-blocking).
    Returns {"synced": bool, "skipped": bool, "error": str|None}.
    """
    # Only resolved tickets that have not been synced yet
    if ticket.status != "resolved":
        return {"synced": False, "skipped": True, "error": None}
    if ticket.kb_synced_at is not None:
        return {"synced": False, "skipped": True, "error": None}

    cfg = current_app.config
    url = f"{cfg['ANYTHINGLLM_BASE_URL'].rstrip('/')}/api/v1/document/raw-text"
    headers = {"Authorization": f"Bearer {cfg['ANYTHINGLLM_API_KEY']}"}
    payload = {
        "textContent": _document_text(ticket),
        "metadata": {
            "title": f"Resolved Ticket #{ticket.id}: {ticket.title}",
            "docSource": "ticket-history",
        },
        "addToWorkspaces": cfg["ANYTHINGLLM_WORKSPACE"],
    }

    try:
        resp = requests.post(
            url, json=payload, headers=headers, timeout=cfg["TOOL_TIMEOUT_SECONDS"]
        )
    except requests.RequestException as exc:
        current_app.logger.warning("knowledge sync: ticket #%s failed: %s", ticket.id, exc)
        return {"synced": False, "skipped": False, "error": str(exc)}

    try:
        data = resp.json()
    except ValueError:
        data = {}

    if resp.status_code != 200 or not data.get("success"):
        current_app.logger.warning(
            "knowledge sync: ticket #%s rejected (HTTP %s): %s",
            ticket.id,
            resp.status_code,
            resp.text[:200],
        )
        return {
            "synced": False,
            "skipped": False,
            "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
        }

    # Stamp for idempotency so the next run will not re-embed
    ticket.kb_synced_at = utcnow()
    db.session.commit()
    return {"synced": True, "skipped": False, "error": None}


def sync_resolved_tickets(limit=None):
    """Batch-push unsynced resolved tickets (for scripts / manual backfill)."""
    query = (
        Ticket.query.filter_by(status="resolved")
        .filter(Ticket.kb_synced_at.is_(None))
        .order_by(Ticket.id)
    )
    if limit:
        query = query.limit(limit)
    tickets = query.all()

    synced, failed = 0, 0
    for ticket in tickets:
        result = sync_one_resolved_ticket(ticket)
        if result["synced"]:
            synced += 1
        elif not result["skipped"]:
            failed += 1

    return {"synced": synced, "failed": failed, "total": len(tickets)}
