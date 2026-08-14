"""Tool registry: the single catalog of every tool the agent may call.

Each entry in TOOLS bundles three things:

  handler               the Python function that actually does the work
  requires_confirmation True pauses the agent loop for user approval before
                        the tool runs (the "consequential action" guardrail)
  schema                JSON Schema for the arguments; doubles as both the
                        tool definition sent to the model (openai_tool_defs)
                        and the validator input (validate_arguments)

To add a tool: write its handler in a new file in this package, then add one
entry here — agent.py and llm.py need no changes.
"""

# Modules are imported under private aliases so `from server.tools import
# search_knowledge` (the module) doesn't collide with the handler function
# of the same name.
from server.tools import search_knowledge as _search_knowledge_module
from server.tools import create_draft as _create_draft_module
from server.tools import escalate as _escalate_module
from server.tools import ticket_tools as _ticket_tools_module

TOOLS = {
    "search_knowledge": {
        "handler": _search_knowledge_module.search_knowledge,
        "requires_confirmation": False,  # read-only: safe to run freely
        "description": (
            "Search the internal support knowledge base for articles relevant to a "
            "question or ticket. Always try this before answering from memory."
        ),
        "schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The question or topic to look up.",
                }
            },
            "required": ["query"],
        },
    },
    "list_tickets": {
        "handler": _ticket_tools_module.list_tickets,
        "requires_confirmation": False,  # read-only
        "description": "List existing support tickets for the user with optional filters.",
        "schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["open", "in_progress", "resolved", "closed"],
                    "description": "Filter by status.",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "urgent"],
                    "description": "Filter by priority.",
                },
                "category": {
                    "type": "string",
                    "description": "Filter by category (IT, HR, Billing, Facilities, General).",
                },
                # Both spellings accepted because small models use either;
                # list_tickets() merges them.
                "query": {
                    "type": "string",
                    "description": "Optional search term for title or description.",
                },
                "q": {
                    "type": "string",
                    "description": "Optional search term for title or description.",
                },
            },
        },
    },
    "create_draft": {
        "handler": _create_draft_module.create_draft,
        "requires_confirmation": False,
        "description": (
            "Draft and send a reply to a support ticket. Requires user confirmation "
            "before it is sent."
        ),
        "schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "The ticket to reply to."},
                "reply_text": {"type": "string", "description": "The full reply text."},
            },
            "required": ["ticket_id", "reply_text"],
        },
    },
    "escalate": {
        "handler": _escalate_module.escalate,
        "requires_confirmation": False,
        "description": (
            "Escalate a support ticket to a human queue by priority. Requires user "
            "confirmation."
        ),
        "schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "The ticket to escalate."},
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "urgent"],
                    "description": "Escalation priority.",
                },
                "reason": {"type": "string", "description": "Why this needs escalation."},
            },
            "required": ["ticket_id", "priority", "reason"],
        },
    },
}


def openai_tool_defs():
    """Convert TOOLS into the OpenAI 'tools' array shape that generate()
    forwards to the model, so the registry stays the single source of truth."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": tool["description"],
                "parameters": tool["schema"],
            },
        }
        for name, tool in TOOLS.items()
    ]


def validate_arguments(tool_name, arguments):
    """Return a human-readable problem string, or None if the arguments are valid.

    This is the tool-argument guardrail: the agent loop calls it before every
    tool execution, and a non-None result triggers the one-retry-then-fail
    flow instead of crashing into the handler with bad inputs.
    """
    tool = TOOLS.get(tool_name)
    if tool is None:
        return f"unknown tool: {tool_name}"  # model hallucinated a tool name
    if not isinstance(arguments, dict):
        return "arguments must be a JSON object"

    schema = tool["schema"]
    properties = schema["properties"]
    # Required keys must be present AND non-empty.
    for key in schema.get("required", []):
        if key not in arguments or arguments[key] in ("", None):
            return f"missing required argument: {key}"
    # Reject extra keys the schema doesn't know (typos, hallucinated params).
    unknown = set(arguments) - set(properties)
    if unknown:
        return f"unknown arguments: {sorted(unknown)}"
    # Shallow type/enum checks for the keys that were provided.
    for key, spec in properties.items():
        if key not in arguments:
            continue
        if spec.get("type") == "string" and not isinstance(arguments[key], str):
            return f"argument '{key}' must be a string"
        if "enum" in spec and arguments[key] not in spec["enum"]:
            return f"argument '{key}' must be one of {spec['enum']}"
    return None
