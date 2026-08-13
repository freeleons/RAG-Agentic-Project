from server.models import Ticket, db
from server.tools.ticket_tools import create_ticket, list_tickets, update_ticket, delete_ticket

def test_ticket_crud_routes(client, auth_headers):
    # 1. Create a ticket via POST /api/tickets
    res = client.post(
        "/api/tickets",
        headers=auth_headers,
        json={
            "title": "Broken Monitor",
            "description": "External display stays black on USB-C",
            "priority": "high",
            "category": "IT",
        },
    )
    assert res.status_code == 201
    data = res.get_json()
    assert data["title"] == "Broken Monitor"
    assert data["priority"] == "high"
    assert data["status"] == "open"
    ticket_id = data["id"]

    # 2. List tickets via GET /api/tickets
    res = client.get("/api/tickets", headers=auth_headers)
    assert res.status_code == 200
    tickets = res.get_json()
    assert len(tickets) >= 1
    assert any(t["id"] == ticket_id for t in tickets)

    # 3. Filter tickets by status
    res = client.get("/api/tickets?status=open", headers=auth_headers)
    assert res.status_code == 200
    assert len(res.get_json()) >= 1

    # 4. Update ticket via PATCH /api/tickets/<id>
    res = client.patch(
        f"/api/tickets/{ticket_id}",
        headers=auth_headers,
        json={"status": "resolved", "priority": "low"},
    )
    assert res.status_code == 200
    updated = res.get_json()
    assert updated["status"] == "resolved"
    assert updated["priority"] == "low"

    # 5. Delete ticket via DELETE /api/tickets/<id>
    res = client.delete(f"/api/tickets/{ticket_id}", headers=auth_headers)
    assert res.status_code == 200
    assert res.get_json()["success"] is True

    # Verify deleted
    res = client.get("/api/tickets", headers=auth_headers)
    assert not any(t["id"] == ticket_id for t in res.get_json())


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
    
    # Call the reseed route
    res = client.post("/api/tickets/seed", headers=auth_headers)
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

