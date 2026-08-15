def scripted(*responses):
    it = iter(responses)

    def fake_generate(messages, tools):
        return next(it)

    return fake_generate


from server.loop_guard import LoopGuard


def test_fingerprint_stable_for_same_args_different_key_order():
    guard = LoopGuard()
    a = guard.fingerprint("search_knowledge", {"query": "vpn", "x": 1})
    b = guard.fingerprint("search_knowledge", {"x": 1, "query": "vpn"})
    assert a == b


def test_check_trips_on_third_identical_call():
    guard = LoopGuard(repeat_threshold=3)
    args = {"query": "vpn"}
    assert guard.check("search_knowledge", args) is False  # 1st
    assert guard.check("search_knowledge", args) is False  # 2nd
    assert guard.check("search_knowledge", args) is True   # 3rd → block


def test_different_args_do_not_share_fingerprint():
    guard = LoopGuard(repeat_threshold=2)
    assert guard.check("search_knowledge", {"query": "a"}) is False
    assert guard.check("search_knowledge", {"query": "b"}) is False
    assert guard.check("search_knowledge", {"query": "a"}) is True


def test_agent_skips_handler_after_repeated_identical_calls(app, run, monkeypatch):
    """Third identical search_knowledge call should not invoke the real handler."""
    from server.agent import run_agent
    from server.tools import TOOLS

    app.config["MAX_AGENT_STEPS"] = 12
    calls = {"n": 0}

    def counting_handler(query):
        calls["n"] += 1
        return {"answer": f"hit-{calls['n']}", "sources": []}

    responses = [
        {
            "type": "tool_call",
            "name": "search_knowledge",
            "arguments": {"query": "vpn"},
            "call_id": f"c{i}",
        }
        for i in range(1, 4)
    ] + [{"type": "final", "content": "Trying a different approach."}]

    monkeypatch.setattr("server.agent.generate", scripted(*responses))
    monkeypatch.setitem(TOOLS["search_knowledge"], "handler", counting_handler)

    outcome = run_agent(run, "vpn help")
    assert outcome["status"] == "completed"
    # First two execute; third is fingerprint-blocked
    assert calls["n"] == 2
    # Audit still shows three tool_call steps (two real + one blocked)
    assert [s.kind for s in run.steps].count("tool_call") == 3
    blocked = [s for s in run.steps if s.kind == "tool_call"][2]
    assert blocked.result.get("success") is False
    assert "multiple times" in blocked.result.get("error", "")


