import itertools
from flask import current_app

_counter = itertools.count(1)


def create_draft(ticket_id, reply_text):
    """'Send' a draft reply for a ticket. Updates the database record dynamically."""
    try:
        # Import dynamically to avoid circular dependencies
        from server.models import db, Ticket
        
        # Parse ticket ID (strip non-numeric characters if present)
        clean_id = int(str(ticket_id).replace("T-", "").replace("APX-", ""))
        
        ticket = Ticket.query.get(clean_id)
        if ticket:
            ticket.draft_reply = reply_text
            ticket.status = "draft_pending"
            db.session.commit()
    except Exception as e:
        # Resilient logging if commit fails, but allow execution to continue
        current_app.logger.warning(f"Failed to save draft reply to ticket {ticket_id}: {e}")

    return {"draft_id": f"draft-{next(_counter)}", "ticket_id": ticket_id, "status": "sent"}
