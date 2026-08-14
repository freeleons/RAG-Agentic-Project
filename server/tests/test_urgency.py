from server.llm import LLMError
from server.models import Ticket, User, db
from server.urgency import (
    DEFAULT_PRIORITY,
    apply_priority,
    classify_priority,
    parse_priority_response,
)


def test_parse_priority_valid_json():
    priority, reason = parse_priority_response(
        '{"priority": "urgent", "reason": "Payroll blocked today."}'
    )
    assert priority == "urgent"
    assert "Payroll" in reason


def test_parse_priority_markdown_fenced():
    priority, _ = parse_priority_response(
        '```json\n{"priority": "high", "reason": "Deadline Friday"}\n```'
    )
    assert priority == "high"


def test_parse_priority_aliases_and_invalid():
    assert parse_priority_response('{"priority": "critical", "reason": "x"}')[0] == "urgent"
    assert parse_priority_response('{"priority": "nope", "reason": "x"}')[0] == DEFAULT_PRIORITY
    assert parse_priority_response("not json")[0] == DEFAULT_PRIORITY


def test_classify_priority_uses_generate(app, monkeypatch):
    with app.app_context():
        user = User(email="u@test.com", password_hash="x")
        db.session.add(user)
        db.session.commit()
        ticket = Ticket(
            user_id=user.id,
            title="Cannot access payroll",
            description="Payroll system down and payday is tomorrow.",
            priority="low",
        )
        db.session.add(ticket)
        db.session.commit()

        monkeypatch.setattr(
            "server.urgency.generate",
            lambda messages, tools: {
                "type": "final",
                "content": '{"priority": "urgent", "reason": "Payday blocked."}',
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

        result = classify_priority(ticket)
        assert result["priority"] == "urgent"
        assert result["reason"] == "Payday blocked."
        assert result["usage"]["prompt_tokens"] == 10

        apply_priority(ticket, result)
        db.session.refresh(ticket)
        assert ticket.priority == "urgent"


def test_classify_priority_falls_back_on_llm_error(app, monkeypatch):
    with app.app_context():
        user = User(email="u2@test.com", password_hash="x")
        db.session.add(user)
        db.session.commit()
        ticket = Ticket(
            user_id=user.id,
            title="Benefits question",
            description="What is the FSA limit?",
            priority="low",
        )
        db.session.add(ticket)
        db.session.commit()

        def boom(messages, tools):
            raise LLMError("down")

        monkeypatch.setattr("server.urgency.generate", boom)

        result = classify_priority(ticket)
        assert result["priority"] == DEFAULT_PRIORITY
        assert "error" in result

        apply_priority(ticket, result)
        assert ticket.priority == DEFAULT_PRIORITY


def test_triage_classifies_priority_before_agent(client, auth_headers, monkeypatch):
    from server.models import User

    user = User.query.filter_by(email="me@test.com").first()
    ticket = Ticket(
        user_id=user.id,
        title="VPN outage",
        description="Entire team cannot connect to VPN since this morning.",
        priority="medium",
        category="IT Support",
    )
    db.session.add(ticket)
    db.session.commit()
    ticket_id = ticket.id

    monkeypatch.setattr(
        "server.routes.classify_priority",
        lambda t: {"priority": "high", "reason": "Team-wide outage."},
    )
    monkeypatch.setattr(
        "server.routes.run_agent",
        lambda run, goal: {"run_id": run.id, "status": "completed", "answer": "drafted"},
    )

    res = client.post(f"/api/tickets/{ticket_id}/triage", headers=auth_headers)
    assert res.status_code == 200
    body = res.get_json()
    assert body["ticket"]["priority"] == "high"

    db.session.refresh(ticket)
    assert ticket.priority == "high"

    from server.models import Run, RunStep

    run = db.session.get(Run, body["run"]["run_id"])
    steps = RunStep.query.filter_by(run_id=run.id).order_by(RunStep.seq).all()
    assert steps[0].kind == "llm_call"
    assert steps[0].result["priority"] == "high"
