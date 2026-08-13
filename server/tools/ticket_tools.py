from flask import g
from server.models import Ticket, db

def list_tickets(status=None, priority=None, category=None, query=None, q=None):
    """List tickets for current user, filtered optionally by status, priority, category, or search query."""
    q_str = (query or q or "").strip()
    db_query = Ticket.query.filter_by(user_id=g.user.id)
    if status:
        db_query = db_query.filter_by(status=status)
    if priority:
        db_query = db_query.filter_by(priority=priority)
    if category:
        db_query = db_query.filter_by(category=category)
    if q_str:
        db_query = db_query.filter(
            (Ticket.title.ilike(f"%{q_str}%")) | (Ticket.description.ilike(f"%{q_str}%"))
        )
    tickets = db_query.order_by(Ticket.id.desc()).all()

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
    """Create a new support ticket."""
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
        or raw_title
    )

    t_str = str(raw_title).strip() or "Support Request"
    d_str = str(raw_desc).strip() or t_str

    p_valid = priority if priority in ["low", "medium", "high", "urgent"] else "medium"
    c_valid = category if category in ["IT", "HR", "Billing", "Facilities", "General"] else "General"

    ticket = Ticket(
        user_id=g.user.id,
        title=t_str[:120],
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
    """Update an existing support ticket's status, priority, or details."""
    try:
        t_id = int(ticket_id)
    except (ValueError, TypeError):
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
    """Delete a support ticket."""
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
