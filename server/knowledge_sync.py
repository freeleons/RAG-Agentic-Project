import requests
from flask import current_app

from server.models import Ticket, db, utcnow


def _document_text(ticket):
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


def sync_resolved_tickets(limit=None):
    """Push resolved tickets not yet in the knowledge base to AnythingLLM.

    Idempotent: only considers tickets with kb_synced_at IS NULL, and stamps
    each one on success so re-runs don't re-embed it. Best-effort per ticket —
    one failure doesn't stop the rest, and unsynced tickets are retried next run.
    """
    cfg = current_app.config
    query = (
        Ticket.query.filter_by(status="resolved")
        .filter(Ticket.kb_synced_at.is_(None))
        .order_by(Ticket.id)
    )
    if limit:
        query = query.limit(limit)
    tickets = query.all()

    url = f"{cfg['ANYTHINGLLM_BASE_URL'].rstrip('/')}/api/v1/document/raw-text"
    headers = {"Authorization": f"Bearer {cfg['ANYTHINGLLM_API_KEY']}"}
    synced, failed = 0, 0

    for ticket in tickets:
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
            failed += 1
            continue

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
            failed += 1
            continue

        ticket.kb_synced_at = utcnow()
        db.session.commit()
        synced += 1

    return {"synced": synced, "failed": failed, "total": len(tickets)}
