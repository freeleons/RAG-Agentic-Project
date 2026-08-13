import pytest


@pytest.fixture
def other_headers(client):
    client.post("/api/auth/register", json={"email": "other@test.com", "password": "password123"})
    token = client.post(
        "/api/auth/login", json={"email": "other@test.com", "password": "password123"}
    ).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _fake_agent(outcome_status="completed", answer="done"):
    def fake(run, goal):
        return {"run_id": run.id, "status": outcome_status, "answer": answer}

    return fake


def _fake_agent_with_message(answer="hello back"):
    def fake(run, goal):
        from server.models import Message, db

        db.session.add(
            Message(conversation_id=run.conversation_id, role="assistant", content=answer)
        )
        db.session.commit()
        return {"run_id": run.id, "status": "completed", "answer": answer}

    return fake


def test_conversations_crud_and_isolation(client, auth_headers, other_headers):
    resp = client.post("/api/conversations", json={"title": "Ticket T-1"}, headers=auth_headers)
    assert resp.status_code == 201
    conv_id = resp.get_json()["id"]

    mine = client.get("/api/conversations", headers=auth_headers).get_json()
    assert [c["id"] for c in mine] == [conv_id]
    assert client.get("/api/conversations", headers=other_headers).get_json() == []

    resp = client.post(
        f"/api/conversations/{conv_id}/messages", json={"content": "hi"}, headers=other_headers
    )
    assert resp.status_code == 404


def test_send_message_runs_agent_and_returns_trace(client, auth_headers, monkeypatch):
    monkeypatch.setattr("server.routes.run_agent", _fake_agent())
    conv_id = client.post("/api/conversations", json={}, headers=auth_headers).get_json()["id"]

    resp = client.post(
        f"/api/conversations/{conv_id}/messages",
        json={"content": "Escalate T-1"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "completed"
    assert body["answer"] == "done"
    assert body["trace"] == []  # fake agent recorded no steps

    resp = client.post(
        f"/api/conversations/{conv_id}/messages", json={"content": "  "}, headers=auth_headers
    )
    assert resp.status_code == 400


def test_confirm_route_guards(client, auth_headers, monkeypatch):
    monkeypatch.setattr("server.routes.run_agent", _fake_agent())
    conv_id = client.post("/api/conversations", json={}, headers=auth_headers).get_json()["id"]
    run_id = client.post(
        f"/api/conversations/{conv_id}/messages", json={"content": "x"}, headers=auth_headers
    ).get_json()["run_id"]

    # run is 'completed' (fake agent doesn't change DB status from 'running'... it stays 'running')
    resp = client.post(f"/api/runs/{run_id}/confirm", json={}, headers=auth_headers)
    assert resp.status_code == 400  # missing 'approved'
    resp = client.post(f"/api/runs/{run_id}/confirm", json={"approved": True}, headers=auth_headers)
    assert resp.status_code == 409  # not in needs_confirmation
    resp = client.post(f"/api/runs/99999/confirm", json={"approved": True}, headers=auth_headers)
    assert resp.status_code == 404


def test_confirm_route_rejects_non_boolean_approved(client, auth_headers, monkeypatch):
    monkeypatch.setattr("server.routes.run_agent", _fake_agent())
    conv_id = client.post("/api/conversations", json={}, headers=auth_headers).get_json()["id"]
    run_id = client.post(
        f"/api/conversations/{conv_id}/messages", json={"content": "x"}, headers=auth_headers
    ).get_json()["run_id"]

    # approved must be a boolean, not a string
    resp = client.post(f"/api/runs/{run_id}/confirm", json={"approved": "false"}, headers=auth_headers)
    assert resp.status_code == 400
    assert "approved" in resp.get_json()["error"].lower()


def test_get_run_observability_view(client, auth_headers, other_headers, monkeypatch):
    monkeypatch.setattr("server.routes.run_agent", _fake_agent())
    conv_id = client.post("/api/conversations", json={}, headers=auth_headers).get_json()["id"]
    run_id = client.post(
        f"/api/conversations/{conv_id}/messages", json={"content": "x"}, headers=auth_headers
    ).get_json()["run_id"]

    resp = client.get(f"/api/runs/{run_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["id"] == run_id
    assert "steps" in resp.get_json()
    assert resp.get_json().get("pending_action") is None  # no pending action for this run

    assert client.get(f"/api/runs/{run_id}", headers=other_headers).status_code == 404


def test_get_run_includes_pending_action_when_awaiting_confirmation(
    client, auth_headers, monkeypatch
):
    def fake_agent_pauses(run, goal):
        from server.models import PendingAction, db

        run.status = "needs_confirmation"
        pending = PendingAction(
            run_id=run.id,
            tool_name="escalate",
            arguments={"ticket_id": "T-1", "priority": "high", "reason": "outage"},
        )
        db.session.add(pending)
        db.session.commit()
        return {"run_id": run.id, "status": "needs_confirmation"}

    monkeypatch.setattr("server.routes.run_agent", fake_agent_pauses)
    conv_id = client.post("/api/conversations", json={}, headers=auth_headers).get_json()["id"]
    run_id = client.post(
        f"/api/conversations/{conv_id}/messages",
        json={"content": "Escalate ticket T-1"},
        headers=auth_headers,
    ).get_json()["run_id"]

    resp = client.get(f"/api/runs/{run_id}", headers=auth_headers)
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


def test_get_conversation_messages_history(client, auth_headers, monkeypatch):
    monkeypatch.setattr("server.routes.run_agent", _fake_agent_with_message())
    conv_id = client.post("/api/conversations", json={}, headers=auth_headers).get_json()["id"]
    run_id = client.post(
        f"/api/conversations/{conv_id}/messages", json={"content": "hi"}, headers=auth_headers
    ).get_json()["run_id"]

    resp = client.get(f"/api/conversations/{conv_id}/messages", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    roles = [m["role"] for m in body["messages"]]
    assert roles == ["user", "assistant"]
    assert body["messages"][0]["content"] == "hi"
    assert body["runs"] == [
        {
            "id": run_id,
            "user_message_id": body["messages"][0]["id"],
            "status": "running",
            "step_count": 0,
            "total_latency_ms": None,
        }
    ]



def test_get_conversation_messages_isolated(client, auth_headers, other_headers):
    conv_id = client.post("/api/conversations", json={}, headers=auth_headers).get_json()["id"]
    resp = client.get(f"/api/conversations/{conv_id}/messages", headers=other_headers)
    assert resp.status_code == 404


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
    monkeypatch.setattr("server.tools.search_knowledge.search_knowledge", mock_search_knowledge_match)

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
    assert "The knowledge base search returned NO_POLICY_MATCH" in system_msg["content"]
    assert "highly witty, playful, and fun way first" in system_msg["content"]

