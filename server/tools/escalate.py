"""Tool: escalate — hand a ticket off to a human support queue.

Persists status/priority/reason onto the Ticket row when possible. The
RunStep row written by record_step() is still the durable audit trail.
"""

import itertools

from flask import current_app

# Mints esc-1, esc-2, ... per server process; resets on restart.
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
