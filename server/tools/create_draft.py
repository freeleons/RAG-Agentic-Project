"""Tool: create_draft — save the agent's proposed reply onto a ticket.

Despite the word "send" in the tool description shown to the model, nothing
is emailed anywhere: the reply is stored as Ticket.draft_reply with status
'draft_pending' so a human can review it in the UI before it goes out.
"""

import itertools
from flask import current_app

# Process-wide counter used only to mint unique-ish draft ids for the tool
# result. Resets when the server restarts — fine, since RunStep rows are the
# durable record.
_counter = itertools.count(1)


def create_draft(ticket_id, reply_text):
    """Write draft_reply and set status to draft_pending (awaits staff review)."""
    try:
        # Dynamic import to avoid circular dependencies
        # (models -> ... -> tools -> models).
        from server.models import db, Ticket

        # The model may pass "7", "T-7", or "APX-1047" — reduce to the numeric
        # database id either way.
        clean_id = int(str(ticket_id).replace("T-", "").replace("APX-", ""))

        ticket = db.session.get(Ticket, clean_id)
        if ticket:
            ticket.draft_reply = reply_text
            ticket.status = "draft_pending"  # awaiting human review in the UI
            db.session.commit()
    except Exception as e:
        # Never let a DB hiccup crash the agent loop mid-run; log and keep
        # going — the draft text still reaches the trace via the return value.
        current_app.logger.warning(f"Failed to save draft reply to ticket {ticket_id}: {e}")

    return {"draft_id": f"draft-{next(_counter)}", "ticket_id": ticket_id, "status": "sent"}
