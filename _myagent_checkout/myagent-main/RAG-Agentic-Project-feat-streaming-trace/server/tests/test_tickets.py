from server.models import Ticket, db
from server.tools.ticket_tools import create_ticket, list_tickets, update_ticket, delete_ticket

def test_ticket_crud_routes(client, auth_headers):
    from server.models import User
    user = User.query.filter_by(email="me@test.com").first()
    ticket = Ticket(
        user_id=user.id,
        title="Broken Monitor",
        description="External display stays black on USB-C",
        priority="high",
        category="IT",
    )
    db.session.add(ticket)
    db.session.commit()
    ticket_id = ticket.id

    # 1. List tickets via GET /api/tickets
    res = client.get("/api/tickets", headers=auth_headers)
    assert res.status_code == 200
    tickets = res.get_json()
    assert len(tickets) >= 1
    assert any(t["id"] == ticket_id for t in tickets)

    # 2. Filter tickets by status
    res = client.get("/api/tickets?status=open", headers=auth_headers)
    assert res.status_code == 200
    assert len(res.get_json()) >= 1

    # 3. Update ticket via PATCH /api/tickets/<id>
    res = client.patch(
        f"/api/tickets/{ticket_id}",
        headers=auth_headers,
        json={"status": "resolved", "priority": "low"},
    )
    assert res.status_code == 200
    updated = res.get_json()
    assert updated["status"] == "resolved"
    assert updated["priority"] == "low"


def test_reseed_clears_audit_logs(client, auth_headers):
    from server.models import Conversation, Message, Run, RunStep, PendingAction, User
    # Get current user from db
    user = User.query.filter_by(email="me@test.com").first()
    
    # Setup a conversation, message, run, step, and pending action for this user
    conv = Conversation(user_id=user.id, title="Test audit logs")
    db.session.add(conv)
    db.session.flush()
    conv_id = conv.id
    
    msg = Message(conversation_id=conv_id, role="user", content="help")
    db.session.add(msg)
    db.session.flush()
    
    run = Run(conversation_id=conv_id, user_message_id=msg.id, status="running")
    db.session.add(run)
    db.session.flush()
    run_id = run.id
    
    step = RunStep(run_id=run_id, seq=1, kind="llm_call")
    db.session.add(step)
    
    pending = PendingAction(run_id=run_id, tool_name="escalate", arguments={})
    db.session.add(pending)
    
    db.session.commit()
    
    # Verify records exist
    assert Conversation.query.filter_by(user_id=user.id).count() == 1
    assert Message.query.filter_by(conversation_id=conv_id).count() == 1
    assert Run.query.filter_by(conversation_id=conv_id).count() == 1
    assert RunStep.query.filter_by(run_id=run_id).count() == 1
    assert PendingAction.query.filter_by(run_id=run_id).count() == 1
    
    # Call the reset route
    res = client.post("/api/tickets/reset", headers=auth_headers)
    assert res.status_code == 200
    
    # Verify everything was deleted
    assert Conversation.query.filter_by(user_id=user.id).count() == 0
    assert Message.query.filter_by(conversation_id=conv_id).count() == 0
    assert Run.query.filter_by(conversation_id=conv_id).count() == 0
    assert RunStep.query.filter_by(run_id=run_id).count() == 0
    assert PendingAction.query.filter_by(run_id=run_id).count() == 0
    
    # Verify tickets were re-seeded (at least one ticket should exist)
    tickets = Ticket.query.filter_by(user_id=user.id).all()
    assert len(tickets) > 0


def test_patch_resolution_notes_via_rest(client, auth_headers):
    from server.models import User
    user = User.query.filter_by(email="me@test.com").first()
    ticket = Ticket(
        user_id=user.id,
        title="VPN down",
        description="Can't connect to VPN",
    )
    db.session.add(ticket)
    db.session.commit()
    ticket_id = ticket.id

    res = client.patch(
        f"/api/tickets/{ticket_id}",
        headers=auth_headers,
        json={"status": "resolved", "resolution_notes": "Reset VPN token, reconnect worked."},
    )
    assert res.status_code == 200
    assert res.get_json()["resolution_notes"] == "Reset VPN token, reconnect worked."

    res = client.get("/api/tickets", headers=auth_headers)
    ticket_data = next(t for t in res.get_json() if t["id"] == ticket_id)
    assert ticket_data["resolution_notes"] == "Reset VPN token, reconnect worked."


def test_agent_update_ticket_stores_resolution_notes(app):
    from flask import g
    from server.models import User
    with app.test_request_context():
        user = User(email="agent-tool@test.com", password_hash="x")
        db.session.add(user)
        db.session.commit()
        g.user = user

        created = create_ticket(title="Printer jam", description="Paper stuck in tray 2")
        ticket_id = created["ticket"]["id"]

        result = update_ticket(
            ticket_id=ticket_id,
            status="resolved",
            resolution_notes="Cleared jam, replaced pickup roller.",
        )
        assert result["success"] is True

        ticket = db.session.get(Ticket, ticket_id)
        assert ticket.status == "resolved"
        assert ticket.resolution_notes == "Cleared jam, replaced pickup roller."

