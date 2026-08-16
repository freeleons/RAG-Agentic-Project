from server.hitl import (
    HITL_TIER_THRESHOLD,
    TOOL_TIERS,
    execute_tool_with_hitl,
    requires_hitl,
    tool_tier,
)


def test_tiers_match_expected_policy():
    assert tool_tier("search_knowledge") < HITL_TIER_THRESHOLD
    assert tool_tier("list_tickets") < HITL_TIER_THRESHOLD
    assert tool_tier("create_draft") >= HITL_TIER_THRESHOLD
    assert tool_tier("escalate") >= HITL_TIER_THRESHOLD
    assert requires_hitl("escalate") is True
    assert requires_hitl("search_knowledge") is False


def test_execute_low_tier_runs_immediately(app, monkeypatch):
    from server.tools import TOOLS

    monkeypatch.setitem(
        TOOLS["search_knowledge"],
        "handler",
        lambda query: {"answer": "ok", "sources": []},
    )
    # Minimal run stub is not needed for tier-1 path beyond having an object with id
    class _Run:
        id = 1
        status = "running"

    outcome = execute_tool_with_hitl("search_knowledge", {"query": "vpn"}, run=_Run())
    assert outcome.status == "executed"
    assert outcome.result["answer"] == "ok"


def test_execute_high_tier_pauses_with_pending_action(app, run):
    outcome = execute_tool_with_hitl(
        "escalate",
        {"ticket_id": "T-1", "priority": "high", "reason": "outage"},
        run=run,
    )
    assert outcome.status == "needs_confirmation"
    assert outcome.pending_action["tool"] == "escalate"
    assert run.status == "needs_confirmation"
    from server.models import PendingAction

    pending = PendingAction.query.filter_by(run_id=run.id, status="pending").one()
    assert pending.tool_name == "escalate"
