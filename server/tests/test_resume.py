def scripted(*responses):
    it = iter(responses)

    def fake_generate(messages, tools):
        return next(it)

    return fake_generate


ESCALATE_CALL = {
    "type": "tool_call",
    "name": "escalate",
    "arguments": {"ticket_id": "T-1", "priority": "high", "reason": "outage"},
    "call_id": "c1",
}


def test_resume_approved_executes_tool_and_completes(app, run, monkeypatch):
    from server.agent import resume_run, run_agent
    from server.models import PendingAction
    from server.tools import TOOLS

    monkeypatch.setattr(
        "server.agent.generate",
        scripted(ESCALATE_CALL, {"type": "final", "content": "Escalated to the on-call queue."}),
    )
    executed = {}
    monkeypatch.setitem(
        TOOLS["escalate"],
        "handler",
        lambda **kwargs: executed.update(kwargs) or {"status": "escalated"},
    )

    assert run_agent(run, "Escalate ticket T-1")["status"] == "needs_confirmation"
    outcome = resume_run(run, approved=True)
    assert outcome["status"] == "completed"
    assert executed["ticket_id"] == "T-1"
    assert PendingAction.query.filter_by(run_id=run.id).one().status == "approved"
    assert [s.kind for s in run.steps] == ["llm_call", "tool_call", "llm_call"]


def test_resume_rejected_skips_tool_and_ends_declined(app, run, monkeypatch):
    from server.agent import resume_run, run_agent
    from server.models import PendingAction
    from server.tools import TOOLS

    monkeypatch.setattr(
        "server.agent.generate",
        scripted(ESCALATE_CALL, {"type": "final", "content": "Understood, I won't escalate."}),
    )
    called = []
    monkeypatch.setitem(TOOLS["escalate"], "handler", lambda **kw: called.append(kw))

    run_agent(run, "Escalate ticket T-1")
    outcome = resume_run(run, approved=False)
    assert outcome["status"] == "declined"
    assert called == []  # the tool never ran
    assert PendingAction.query.filter_by(run_id=run.id).one().status == "rejected"
    assert run.status == "declined"


def test_confirm_endpoint_approves_pending_action(client, auth_headers, monkeypatch):
    """POST /api/runs/<id>/confirm should approve a pending tool."""
    from server.models import Conversation, Message, PendingAction, Run, User, db

    user = User.query.filter_by(email="me@test.com").first()
    conv = Conversation(user_id=user.id)
    db.session.add(conv)
    db.session.flush()
    msg = Message(conversation_id=conv.id, role="user", content="x")
    db.session.add(msg)
    db.session.flush()
    run = Run(
        conversation_id=conv.id,
        user_message_id=msg.id,
        model="test-model",
        status="needs_confirmation",
    )
    db.session.add(run)
    db.session.flush()
    db.session.add(
        PendingAction(
            run_id=run.id,
            tool_name="escalate",
            arguments={"ticket_id": "T-1", "priority": "high", "reason": "outage"},
        )
    )
    # resume_run needs the prior llm_call message context
    from server.models import RunStep
    db.session.add(
        RunStep(
            run_id=run.id,
            seq=1,
            kind="llm_call",
            llm_messages=[{"role": "user", "content": "escalate"}],
            result={"type": "tool_call", "name": "escalate"},
        )
    )
    db.session.commit()
    run_id = run.id

    monkeypatch.setattr(
        "server.agent.generate",
        lambda m, t: {"type": "final", "content": "Done."},
    )

    res = client.post(
        f"/api/runs/{run_id}/confirm",
        headers=auth_headers,
        json={"approved": True},
    )
    assert res.status_code == 200
    assert res.get_json()["status"] == "completed"
