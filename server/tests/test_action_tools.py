def test_create_draft_returns_record(app):
    from server.tools.create_draft import create_draft

    result = create_draft(ticket_id="T-42", reply_text="Please reset your VPN token.")
    assert result["ticket_id"] == "T-42"
    assert result["status"] == "sent"
    assert result["draft_id"].startswith("draft-")


def test_escalate_persists_ticket_state(app):
    """Escalate should persist status / priority / reason on the ticket."""
    from server.models import Ticket, User, db
    from server.tools.escalate import escalate

    with app.app_context():
        user = User(email="esc@test.com", password_hash="x")
        db.session.add(user)
        db.session.commit()
        ticket = Ticket(
            user_id=user.id,
            title="Outage",
            description="VPN down for whole team",
            status="open",
            priority="medium",
        )
        db.session.add(ticket)
        db.session.commit()
        ticket_id = ticket.id

        result = escalate(ticket_id=str(ticket_id), priority="urgent", reason="team-wide outage")
        assert result["status"] == "escalated"
        assert result["priority"] == "urgent"

        db.session.refresh(ticket)
        assert ticket.status == "escalated"
        assert ticket.priority == "urgent"
        assert ticket.escalation_reason == "team-wide outage"


def test_action_tools_registered_with_confirmation(app):
    from server.tools import TOOLS, validate_arguments

    # Design rule: consequential actions must require HITL confirmation
    assert TOOLS["create_draft"]["requires_confirmation"] is True
    assert TOOLS["escalate"]["requires_confirmation"] is True
    assert validate_arguments("escalate", {"ticket_id": "T-1", "priority": "wrong", "reason": "x"}) is not None
    assert validate_arguments(
        "escalate", {"ticket_id": "T-1", "priority": "high", "reason": "x"}
    ) is None
    assert validate_arguments(
        "create_draft", {"ticket_id": "T-1", "reply_text": "hello"}
    ) is None
