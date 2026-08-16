def test_action_tools_registered_with_confirmation(app):
    from server.tools import TOOLS, validate_arguments

    assert "search_knowledge" in TOOLS
    assert "list_tickets" in TOOLS
    assert TOOLS["search_knowledge"]["requires_confirmation"] is False
    assert TOOLS["list_tickets"]["requires_confirmation"] is False
    assert validate_arguments("search_knowledge", {}) is not None
    assert validate_arguments("search_knowledge", {"query": "PTO"}) is None
    assert "create_draft" not in TOOLS
    assert "escalate" not in TOOLS
