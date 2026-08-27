from server.models import (
    Conversation,
    Message,
    PendingAction,
    Run,
    RunStep,
    User,
    db,
)


def test_models_roundtrip(app):
    user = User(email="u@example.com", password_hash="x")
    db.session.add(user)
    db.session.commit()

    conv = Conversation(user_id=user.id, title="VPN issue")
    db.session.add(conv)
    db.session.commit()

    msg = Message(conversation_id=conv.id, role="user", content="hello")
    db.session.add(msg)
    db.session.commit()

    run = Run(conversation_id=conv.id, user_message_id=msg.id, model="llama3.1:8b")
    db.session.add(run)
    db.session.commit()

    step = RunStep(
        run_id=run.id,
        seq=1,
        kind="tool_call",
        tool_name="search_knowledge",
        arguments={"query": "vpn"},
        result={"answer": "reset it"},
        latency_ms=5,
    )
    action = PendingAction(run_id=run.id, tool_name="escalate", arguments={"ticket_id": "T-1"})
    db.session.add_all([step, action])
    db.session.commit()

    assert run.status == "running"
    assert run.steps[0].arguments == {"query": "vpn"}
    assert action.status == "pending"
    assert conv.messages[0].content == "hello"
