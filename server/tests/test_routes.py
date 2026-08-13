import pytest


@pytest.fixture
def other_headers(client):
    client.post("/api/auth/register", json={"email": "other@test.com", "password": "password123"})
    token = client.post(
        "/api/auth/login", json={"email": "other@test.com", "password": "password123"}
    ).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_get_run_observability_view(client, auth_headers, other_headers):
    from server.models import Conversation, Message, Run, User, db
    user = User.query.filter_by(email="me@test.com").first()
    conv = Conversation(user_id=user.id, title="Test Conv")
    db.session.add(conv)
    db.session.flush()
    msg = Message(conversation_id=conv.id, role="user", content="x")
    db.session.add(msg)
    db.session.flush()
    run = Run(conversation_id=conv.id, user_message_id=msg.id, model="test-model")
    db.session.add(run)
    db.session.commit()
    run_id = run.id

    resp = client.get(f"/api/runs/{run_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["id"] == run_id
    assert "steps" in resp.get_json()
    assert resp.get_json().get("pending_action") is None

    assert client.get(f"/api/runs/{run_id}", headers=other_headers).status_code == 404


def test_get_run_includes_pending_action_when_awaiting_confirmation(
    client, auth_headers
):
    from server.models import Conversation, Message, Run, PendingAction, User, db
    user = User.query.filter_by(email="me@test.com").first()
    conv = Conversation(user_id=user.id)
    db.session.add(conv)
    db.session.flush()
    msg = Message(conversation_id=conv.id, role="user", content="x")
    db.session.add(msg)
    db.session.flush()
    run = Run(conversation_id=conv.id, user_message_id=msg.id, model="test-model", status="needs_confirmation")
    db.session.add(run)
    db.session.flush()

    pending = PendingAction(
        run_id=run.id,
        tool_name="escalate",
        arguments={"ticket_id": "T-1", "priority": "high", "reason": "outage"},
    )
    db.session.add(pending)
    db.session.commit()

    resp = client.get(f"/api/runs/{run.id}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "needs_confirmation"
    assert body["pending_action"]["tool"] == "escalate"
    assert body["pending_action"]["arguments"] == {
        "ticket_id": "T-1",
        "priority": "high",
        "reason": "outage",
    }
    assert isinstance(body["pending_action"]["id"], int)


def test_pip_chat_routes(client, auth_headers, monkeypatch):
    # Test auth requirement
    resp = client.post("/api/chat", json={"message": "hello"})
    assert resp.status_code == 401

    # Test empty message validation
    resp = client.post("/api/chat", json={"message": "   "}, headers=auth_headers)
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "message is required"

    # Test successful chat response with policy match (needs knowledge search)
    mock_called = []
    def mock_generate(messages, tools):
        mock_called.append((messages, tools))
        # If classification prompt, return YES
        if len(messages) == 1 and "routing assistant" in messages[0]["content"]:
            return {"type": "final", "content": "YES"}
        return {"type": "final", "content": "I'm Pip! Let's get back to work!"}

    search_called = []
    def mock_search_knowledge_match(query):
        search_called.append(query)
        return {"answer": "Official PTO policy details...", "sources": ["PTO.pdf"]}

    monkeypatch.setattr("server.routes.generate", mock_generate)
    monkeypatch.setattr("server.routes.search_knowledge", mock_search_knowledge_match)

    resp = client.post("/api/chat", json={"message": "PTO policy"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["reply"] == "I'm Pip! Let's get back to work!"

    # Assert generate called twice: 1 for classification, 1 for final response
    assert len(mock_called) == 2
    # Assert search_knowledge was called
    assert len(search_called) == 1
    assert search_called[0] == "PTO policy"

    # Assert second generate got system prompt with knowledge
    system_msg = mock_called[1][0][0]
    assert "You are Pip" in system_msg["content"]
    assert "AUDITED_POLICY_KNOWLEDGE_RESULT" in system_msg["content"]
    assert "NO_POLICY_MATCH" not in system_msg["content"]

    # Test chat response with off-topic question classified as NO (should skip search_knowledge!)
    mock_called.clear()
    search_called.clear()

    def mock_generate_no_kb(messages, tools):
        mock_called.append((messages, tools))
        if len(messages) == 1 and "routing assistant" in messages[0]["content"]:
            return {"type": "final", "content": "NO"}
        return {"type": "final", "content": "Fun response!"}

    monkeypatch.setattr("server.routes.generate", mock_generate_no_kb)

    resp = client.post("/api/chat", json={"message": "how is the weather"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["reply"] == "Fun response!"

    assert len(mock_called) == 2
    # Assert search_knowledge was SKIPPED (not called!)
    assert len(search_called) == 0
    # Assert second generate got system prompt with no_policy_match instructions
    system_msg = mock_called[1][0][0]
    assert "You are Pip" in system_msg["content"]
    assert "The knowledge base search found no matching policy." in system_msg["content"]
