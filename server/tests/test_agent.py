def scripted(*responses):
    it = iter(responses)

    def fake_generate(messages, tools):
        return next(it)

    return fake_generate


def test_single_tool_then_final_answer(app, run, monkeypatch):
    from server.agent import run_agent
    from server.tools import TOOLS

    monkeypatch.setattr(
        "server.agent.generate",
        scripted(
            {"type": "tool_call", "name": "search_knowledge", "arguments": {"query": "vpn"}, "call_id": "c1"},
            {"type": "final", "content": "Reset it in Settings."},
        ),
    )
    monkeypatch.setitem(
        TOOLS["search_knowledge"], "handler", lambda query: {"answer": "kb says reset", "sources": []}
    )

    outcome = run_agent(run, "How do I reset my VPN?")
    assert outcome["status"] == "completed"
    assert outcome["answer"] == "Reset it in Settings."
    assert [s.kind for s in run.steps] == ["llm_call", "tool_call", "llm_call"]
    from server.models import Message

    saved = Message.query.filter_by(conversation_id=run.conversation_id, role="assistant").one()
    assert saved.content == "Reset it in Settings."


def test_loop_terminates_at_max_steps(app, run, monkeypatch):
    from server.agent import run_agent
    from server.tools import TOOLS

    monkeypatch.setattr(
        "server.agent.generate",
        lambda m, t: {
            "type": "tool_call",
            "name": "search_knowledge",
            "arguments": {"query": "again"},
            "call_id": "c",
        },
    )
    monkeypatch.setitem(TOOLS["search_knowledge"], "handler", lambda query: {"answer": "a", "sources": []})

    outcome = run_agent(run, "loop forever")
    assert outcome["status"] == "failed"
    assert len(run.steps) <= app.config["MAX_AGENT_STEPS"]


def test_invalid_arguments_retry_once_then_fail(app, run, monkeypatch):
    from server.agent import run_agent

    monkeypatch.setattr(
        "server.agent.generate",
        lambda m, t: {"type": "tool_call", "name": "search_knowledge", "arguments": {}, "call_id": "c"},
    )
    outcome = run_agent(run, "bad args forever")
    assert outcome["status"] == "failed"
    # two llm_calls (original + one retry), no tool ever executed
    assert [s.kind for s in run.steps] == ["llm_call", "llm_call"]


def test_llm_failure_fails_gracefully(app, run, monkeypatch):
    from server.agent import run_agent
    from server.llm import LLMError

    def dead(messages, tools):
        raise LLMError("connection refused")

    monkeypatch.setattr("server.agent.generate", dead)
    outcome = run_agent(run, "anything")
    assert outcome["status"] == "failed"
    assert outcome["answer"]  # a human-readable apology, not empty




def test_cap_check_prevents_tool_call_overflow_with_odd_max_steps(app, run, monkeypatch):
    from server.agent import run_agent
    from server.tools import TOOLS

    # Set MAX_AGENT_STEPS to an odd number to test edge case
    app.config["MAX_AGENT_STEPS"] = 5

    # Generate stub that always returns valid non-gated tool calls
    monkeypatch.setattr(
        "server.agent.generate",
        lambda m, t: {
            "type": "tool_call",
            "name": "search_knowledge",
            "arguments": {"query": "test"},
            "call_id": "c",
        },
    )
    monkeypatch.setitem(TOOLS["search_knowledge"], "handler", lambda query: {"answer": "a", "sources": []})

    outcome = run_agent(run, "infinite loop test")
    assert outcome["status"] == "failed"
    # Must not exceed MAX_AGENT_STEPS (5)
    assert len(run.steps) <= 5
