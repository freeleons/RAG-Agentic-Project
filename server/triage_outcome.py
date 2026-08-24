"""Post-process a triage agent outcome onto its ticket.

Shared by the JSON and SSE responses of POST /tickets/<id>/triage so both
paths apply identical ticket/draft/status mutations.
"""

from flask import current_app

from server.models import db
from server.utils import clean_draft_text


def apply_triage_outcome(ticket, run, conversation_id, outcome, serialize_ticket):
    """Mutate ticket/run from `outcome`. Return (payload_dict, http_status)."""
    db.session.refresh(run)
    if run.status == "stopped" or outcome.get("status") == "stopped":
        ticket.status = "open"
        run.status = "stopped"
        db.session.commit()
        return {
            "ticket": serialize_ticket(ticket),
            "run": {
                "run_id": run.id,
                "status": "stopped",
                "answer": "Triage was stopped by the user.",
            },
            "conversation_id": conversation_id,
        }, 499

    if outcome.get("status") == "failed":
        current_app.logger.error(f"Agent triage failed for ticket {ticket.id}")
        draft_text = (
            f"Hello {ticket.requester_name.split()[0]},\n\n"
            f"Thank you for contacting ApexCare Support regarding '{ticket.title}'.\n\n"
            f"Our automated triage system is currently experiencing a delay, but your ticket has been securely logged. "
            f"An HR representative will review your request and assist you shortly."
        )
        ticket.draft_reply = draft_text
        ticket.draft_confidence = 0
        ticket.status = "open"
        run.status = "failed"
        db.session.commit()
        outcome = {
            "run_id": run.id,
            "status": "failed",
            "answer": "Triage failed. Applied safe fallback draft.",
        }

    if outcome.get("status") == "completed" and ticket.status != "escalated":
        raw_ans = outcome.get("answer") or ""
        cleaned_ans = clean_draft_text(raw_ans)
        if cleaned_ans:
            ticket.draft_reply = cleaned_ans
            if ticket.status == "open":
                ticket.status = "draft_pending"
            db.session.commit()
    elif (
        outcome.get("status") == "needs_confirmation" or ticket.status == "escalated"
    ) and not ticket.draft_reply:
        requester_first = (ticket.requester_name or "there").split()[0].strip()
        dept_str = ticket.requester_department or "HR Support"
        draft_text = (
            f"Hi {requester_first},\n\n"
            f"Thank you for contacting ApexCare Support regarding '{ticket.title}'. "
            f"I have escalated your request to our {dept_str} specialist team for review.\n\n"
            f"Our team will follow up directly with you shortly with next steps.\n\n"
            f"Best regards,\n"
            f"HR Support Team"
        )
        ticket.draft_reply = draft_text
        if ticket.status == "open":
            ticket.status = "draft_pending"
        db.session.commit()

    db.session.refresh(ticket)
    return {
        "ticket": serialize_ticket(ticket),
        "run": outcome,
        "conversation_id": conversation_id,
    }, 200
