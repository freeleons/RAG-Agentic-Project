def test_create_draft_returns_record(app):
    from server.tools.create_draft import create_draft

    result = create_draft(ticket_id="T-42", reply_text="Please reset your VPN token.")
    assert result["ticket_id"] == "T-42"
    assert result["status"] == "sent"
    assert result["draft_id"].startswith("draft-")


def test_escalate_returns_record(app):
    from server.tools.escalate import escalate

    result = escalate(ticket_id="T-42", priority="high", reason="customer outage")
    assert result["ticket_id"] == "T-42"
    assert result["priority"] == "high"
    assert result["status"] == "escalated"


def test_action_tools_registered_with_confirmation(app):
    from server.tools import TOOLS, validate_arguments

    assert TOOLS["create_draft"]["requires_confirmation"] is False
    assert TOOLS["escalate"]["requires_confirmation"] is False
    assert validate_arguments("escalate", {"ticket_id": "T-1", "priority": "wrong", "reason": "x"}) is not None
    assert validate_arguments(
        "escalate", {"ticket_id": "T-1", "priority": "high", "reason": "x"}
    ) is None
    assert validate_arguments(
        "create_draft", {"ticket_id": "T-1", "reply_text": "hello"}
    ) is None
