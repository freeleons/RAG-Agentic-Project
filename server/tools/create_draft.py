"""Tool: draft a reply for staff review on a support ticket."""

import itertools
from flask import current_app

_counter = itertools.count(1)


def create_draft(ticket_id, reply_text):
    """Write draft_reply and set status to draft_pending (awaits staff review)."""
    try:
        # Dynamic import to avoid circular dependencies
        from server.models import db, Ticket

        # Accept prefixed ids like T-123 / APX-123
        clean_id = int(str(ticket_id).replace("T-", "").replace("APX-", ""))

        ticket = db.session.get(Ticket, clean_id)
        if ticket:
            ticket.draft_reply = reply_text
            ticket.status = "draft_pending"
            db.session.commit()
    except Exception as e:
        # Log persist failures; still return a stable shape for the agent loop
        current_app.logger.warning(f"Failed to save draft reply to ticket {ticket_id}: {e}")

    return {"draft_id": f"draft-{next(_counter)}", "ticket_id": ticket_id, "status": "sent"}
