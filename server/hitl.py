"""Human-in-the-loop gate at the tool-execution layer.

Mirrors a tiered execute_tool_with_hitl wrapper: low-tier tools run immediately;
higher-tier tools create a durable PendingAction and pause for UI confirmation
instead of blocking the request thread.
"""

from dataclasses import dataclass

from server.models import PendingAction, db

# Static risk tiers (1 = auto-run, 2+ = require staff approval).
# Keep in sync with TOOLS[*]["requires_confirmation"] in server/tools/__init__.py.
TOOL_TIERS = {
    "search_knowledge": 1,
    "list_tickets": 1,
    "escalate": 2,
}

# Tools at or above this tier pause for HITL confirmation.
HITL_TIER_THRESHOLD = 2


@dataclass
class HitlOutcome:
    """Result of execute_tool_with_hitl."""

    # "executed" → tool ran; "needs_confirmation" → paused for Approve/Reject
    status: str
    result: dict | None = None
    pending_action: dict | None = None
    tier: int = 1


def tool_tier(tool_name: str) -> int:
    """Look up the static risk tier for a tool (unknown tools default to HITL)."""
    return TOOL_TIERS.get(tool_name, HITL_TIER_THRESHOLD)


def requires_hitl(tool_name: str) -> bool:
    """True when this tool must pause for confirmation before executing."""
    return tool_tier(tool_name) >= HITL_TIER_THRESHOLD


def execute_tool(tool_name: str, args: dict):
    """Run the tool handler with no HITL gate (used after approval)."""
    from server.tools import TOOLS

    tool = TOOLS[tool_name]
    try:
        return tool["handler"](**args)
    except Exception as exc:  # noqa: BLE001 — surface as observation, do not crash the loop
        return {"success": False, "error": str(exc)}


def execute_tool_with_hitl(tool_name: str, args: dict, *, run) -> HitlOutcome:
    """Tool-execution wrapper with a HITL confirmation gate.

    Tier 1: execute immediately and return the tool result.
    Tier 2+: create a PendingAction, mark the run needs_confirmation, and return
    a pause signal. The HTTP handler returns to the client; Approve/Reject later
    resumes via resume_run (we do not block/wait in-process).
    """
    from server.tools import TOOLS

    tier = tool_tier(tool_name)
    if tool_name not in TOOLS:
        return HitlOutcome(
            status="executed",
            result={"success": False, "error": f"unknown tool: {tool_name}"},
            tier=tier,
        )

    # Low tier: run now
    if tier < HITL_TIER_THRESHOLD:
        return HitlOutcome(status="executed", result=execute_tool(tool_name, args), tier=tier)

    # Tier 2+: pause and request approval (durable PendingAction)
    action = PendingAction(run_id=run.id, tool_name=tool_name, arguments=args)
    run.status = "needs_confirmation"
    db.session.add(action)
    db.session.commit()

    return HitlOutcome(
        status="needs_confirmation",
        pending_action={"id": action.id, "tool": tool_name, "arguments": args},
        tier=tier,
    )
