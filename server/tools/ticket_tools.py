"""Ticket CRUD tools the agent can call (plus helpers reused by routes).

All of these rely on Flask's `g.user` being set by @require_auth — every
query is scoped to the logged-in user, so the agent can never read or modify
another user's tickets.
"""

from flask import g
from server.models import Ticket, db


def list_tickets(status=None, priority=None, category=None, query=None, q=None):
    """List tickets for current user, filtered optionally by status, priority, category, or search query."""
    # The schema exposes both 'query' and 'q' because small models pick either
    # name; whichever arrived wins.
    q_str = (query or q or "").strip()
    db_query = Ticket.query.filter_by(user_id=g.user.id)
    if status:
        db_query = db_query.filter_by(status=status)
    if priority:
        db_query = db_query.filter_by(priority=priority)
    if category:
        db_query = db_query.filter_by(category=category)
    if q_str:
        # Case-insensitive substring match on title OR description.
        db_query = db_query.filter(
            (Ticket.title.ilike(f"%{q_str}%")) | (Ticket.description.ilike(f"%{q_str}%"))
        )
    tickets = db_query.order_by(Ticket.id.desc()).all()

    # Return a compact dict (not ORM objects): tool results are JSON-serialized
    # into the model's context and the trace, so keep them small and plain.
    return {
        "count": len(tickets),
        "tickets": [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "status": t.status,
                "priority": t.priority,
                "category": t.category,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tickets
        ],
    }


def create_ticket(title=None, description=None, priority="medium", category="General", **kwargs):
    """Create a new support ticket.

    Accepts **kwargs because models phrase the arguments loosely ("issue",
    "problem", "summary", ...) — we scavenge a usable title/description from
    whatever synonyms arrived rather than failing the call.
    """
    raw_title = (
        title
        or kwargs.get("issue")
        or kwargs.get("problem")
        or kwargs.get("summary")
        or kwargs.get("details")
        or ""
    )
    raw_desc = (
        description
        or kwargs.get("details")
        or kwargs.get("text")
        or kwargs.get("problem")
        or raw_title  # last resort: reuse the title as the description
    )

    t_str = str(raw_title).strip() or "Support Request"
    d_str = str(raw_desc).strip() or t_str

    # Silently coerce invalid enum values to safe defaults instead of erroring.
    p_valid = priority if priority in ["low", "medium", "high", "urgent"] else "medium"
    c_valid = category if category in ["IT", "HR", "Billing", "Facilities", "General"] else "General"

    ticket = Ticket(
        user_id=g.user.id,
        title=t_str[:120],  # column limit is String(120)
        description=d_str,
        priority=p_valid,
        category=c_valid,
        status="open",
    )
    db.session.add(ticket)
    db.session.commit()
    return {
        "success": True,
        "message": f"Ticket #{ticket.id} created successfully.",
        "ticket": {
            "id": ticket.id,
            "title": ticket.title,
            "status": ticket.status,
            "priority": ticket.priority,
            "category": ticket.category,
        },
    }


def update_ticket(ticket_id, status=None, priority=None, title=None, description=None, resolution_notes=None):
    """Update an existing support ticket's status, priority, or details.

    Only the fields that were passed (non-None/non-empty) are changed;
    everything else keeps its current value.
    """
    try:
        t_id = int(ticket_id)
    except (ValueError, TypeError):
        # Errors are returned as data, not raised: the agent loop feeds them
        # back to the model as an observation it can correct.
        return {"error": f"Invalid ticket_id: {ticket_id}"}

    ticket = Ticket.query.filter_by(id=t_id, user_id=g.user.id).first()
    if not ticket:
        return {"error": f"Ticket #{ticket_id} not found."}

    if status:
        ticket.status = status
    if priority:
        ticket.priority = priority
    if title:
        ticket.title = title.strip()
    if description:
        ticket.description = description.strip()
    if resolution_notes:
        ticket.resolution_notes = resolution_notes.strip()

    db.session.commit()

    # When marked resolved, auto-embed into the KB (failures are non-blocking)
    if ticket.status == "resolved":
        from server.knowledge_sync import sync_one_resolved_ticket
        sync_one_resolved_ticket(ticket)

    return {
        "success": True,
        "message": f"Ticket #{ticket.id} updated successfully.",
        "ticket": {
            "id": ticket.id,
            "title": ticket.title,
            "status": ticket.status,
            "priority": ticket.priority,
            "resolution_notes": ticket.resolution_notes,
        },
    }


def delete_ticket(ticket_id):
    """Delete a support ticket (hard delete — no undo)."""
    try:
        t_id = int(ticket_id)
    except (ValueError, TypeError):
        return {"error": f"Invalid ticket_id: {ticket_id}"}

    ticket = Ticket.query.filter_by(id=t_id, user_id=g.user.id).first()
    if not ticket:
        return {"error": f"Ticket #{ticket_id} not found."}

    db.session.delete(ticket)
    db.session.commit()
    return {"success": True, "message": f"Ticket #{ticket_id} permanently deleted."}
