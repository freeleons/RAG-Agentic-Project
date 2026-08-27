"""SSE streaming helpers + triage stream contract."""

import json

from server.streaming import emit, format_sse


def test_format_sse_shape():
    chunk = format_sse("step", {"run_id": 7, "kind": "llm_call"})
    assert chunk.startswith("event: step\n")
    assert "data: {" in chunk
    assert chunk.endswith("\n\n")
    data_line = [l for l in chunk.splitlines() if l.startswith("data: ")][0]
    payload = json.loads(data_line[len("data: "):])
    assert payload == {"run_id": 7, "kind": "llm_call"}


def test_emit_noop_without_callback():
    emit(None, "step", run_id=1)  # must not raise


def test_emit_forwards_type_and_payload():
    seen = []
    emit(seen.append, "step_start", run_id=3, kind="tool_call", tool_name="search_knowledge")
    assert seen == [
        {
            "type": "step_start",
            "run_id": 3,
            "kind": "tool_call",
            "tool_name": "search_knowledge",
        }
    ]


def test_triage_stream_emits_run_started_and_done(client, auth_headers, monkeypatch):
    """POST /tickets/<id>/triage?stream=1 returns an SSE body with run_started + done."""
    from server.models import Ticket, db

    # Seed a ticket owned by the authenticated user (conftest auth_headers user).
    from server.models import User

    user = User.query.filter_by(email="test@example.com").first()
    if user is None:
        # Fall back: any user that auth_headers authenticates as.
        from flask import g
        pass

    # Create ticket via API reset/list
    listed = client.get("/api/tickets", headers=auth_headers)
    assert listed.status_code == 200
    tickets = listed.get_json()
    if isinstance(tickets, dict):
        tickets = tickets.get("tickets") or tickets.get("items") or []
    assert tickets, "expected seeded tickets"
    ticket_id = tickets[0]["id"]

    # Stub the agent loop so we do not need a live LLM.
    def fake_run_agent(run, goal, on_event=None):
        if on_event:
            on_event({"type": "step_start", "run_id": run.id, "seq": 1, "kind": "llm_call"})
            on_event(
                {
                    "type": "step",
                    "run_id": run.id,
                    "seq": 1,
                    "kind": "llm_call",
                    "decision_type": "final",
                    "step": {
                        "seq": 1,
                        "kind": "llm_call",
                        "tool_name": None,
                        "arguments": None,
                        "result": {"type": "final", "content": "done"},
                        "latency_ms": 12,
                    },
                }
            )
            on_event(
                {
                    "type": "done",
                    "run_id": run.id,
                    "status": "completed",
                    "answer": "Hi there,\n\nAll set.\n\nBest regards,\nHR Support Team",
                }
            )
        return {
            "run_id": run.id,
            "status": "completed",
            "answer": "Hi there,\n\nAll set.\n\nBest regards,\nHR Support Team",
        }

    monkeypatch.setattr("server.routes.run_agent", fake_run_agent)

    resp = client.post(
        f"/api/tickets/{ticket_id}/triage?stream=1",
        headers={**auth_headers, "Accept": "text/event-stream"},
    )
    assert resp.status_code == 200
    assert resp.mimetype == "text/event-stream"
    body = resp.get_data(as_text=True)
    assert "event: run_started" in body
    assert "event: done" in body
    assert "event: step_start" in body or "event: step" in body
    assert '"kind": "llm_call"' in body or '"kind":"llm_call"' in body
    assert '"latency_ms": 12' in body or '"latency_ms":12' in body
