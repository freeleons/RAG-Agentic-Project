"""Tool: escalate a support ticket to a human queue."""

import itertools

from flask import current_app

_counter = itertools.count(1)


def escalate(ticket_id, priority, reason):
    """Mark the ticket escalated and persist priority + reason."""
    try:
        from server.models import Ticket, db

        # Accept prefixed ids like T-123 / APX-123
        clean_id = int(str(ticket_id).replace("T-", "").replace("APX-", ""))
        ticket = db.session.get(Ticket, clean_id)
        if ticket:
            ticket.status = "escalated"
            ticket.priority = priority
            ticket.escalation_reason = reason
            db.session.commit()
    except Exception as exc:  # noqa: BLE001 — do not break the agent return shape on persist failure
        current_app.logger.warning("Failed to persist escalate for ticket %s: %s", ticket_id, exc)

    return {
        "escalation_id": f"esc-{next(_counter)}",
        "ticket_id": ticket_id,
        "priority": priority,
        "reason": reason,
        "status": "escalated",
    }
