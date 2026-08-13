from server.tools import search_knowledge as _search_knowledge_module
from server.tools import create_draft as _create_draft_module
from server.tools import escalate as _escalate_module
from server.tools import ticket_tools as _ticket_tools_module

TOOLS = {
    "search_knowledge": {
        "handler": _search_knowledge_module.search_knowledge,
        "requires_confirmation": False,
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
        "requires_confirmation": False,
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

    "create_ticket": {
        "handler": _ticket_tools_module.create_ticket,
        "requires_confirmation": True,
        "description": "Create a new support ticket. Requires user confirmation.",
        "schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short title describing the issue."},
                "description": {"type": "string", "description": "Detailed problem description."},
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "urgent"],
                    "description": "Ticket priority.",
                },
                "category": {
                    "type": "string",
                    "enum": ["IT", "HR", "Billing", "Facilities", "General"],
                    "description": "Ticket category.",
                },
                "subject": {"type": "string", "description": "Short title or subject alias."},
                "details": {"type": "string", "description": "Problem details alias."},
                "issue": {"type": "string", "description": "Problem issue alias."},
                "problem": {"type": "string", "description": "Problem alias."},
                "summary": {"type": "string", "description": "Problem summary alias."},
                "text": {"type": "string", "description": "Problem text alias."},
                "urgency": {"type": "string", "description": "Priority alias."},
                "requester": {"type": "string", "description": "Category or user alias."},
                "assignee": {"type": "string", "description": "Assignee alias."},
            },
            "required": ["title"],
        },
    },


    "update_ticket": {
        "handler": _ticket_tools_module.update_ticket,
        "requires_confirmation": True,
        "description": "Update an existing support ticket's status or priority. Requires user confirmation.",
        "schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "The ticket ID to update."},
                "status": {
                    "type": "string",
                    "enum": ["open", "in_progress", "resolved", "closed"],
                    "description": "New status.",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "urgent"],
                    "description": "New priority.",
                },
                "title": {"type": "string", "description": "Updated title."},
                "description": {"type": "string", "description": "Updated description."},
                "resolution_notes": {
                    "type": "string",
                    "description": "How the ticket was resolved. Provide when marking a ticket resolved so future lookups can reuse this fix.",
                },
            },
            "required": ["ticket_id"],
        },
    },
    "delete_ticket": {
        "handler": _ticket_tools_module.delete_ticket,
        "requires_confirmation": True,
        "description": "Delete a support ticket. High-risk operation requiring user confirmation.",
        "schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "The ticket ID to delete."},
            },
            "required": ["ticket_id"],
        },
    },
    "create_draft": {
        "handler": _create_draft_module.create_draft,
        "requires_confirmation": True,
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
        "requires_confirmation": True,
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
    """Return a human-readable problem string, or None if the arguments are valid."""
    tool = TOOLS.get(tool_name)
    if tool is None:
        return f"unknown tool: {tool_name}"
    if not isinstance(arguments, dict):
        return "arguments must be a JSON object"

    if tool_name == "create_ticket":
        subject = arguments.get("subject")
        if subject and ("title" not in arguments or not arguments["title"]):
            arguments["title"] = str(subject)

        if "title" not in arguments or not arguments["title"]:
            fallback = (
                arguments.get("description")
                or arguments.get("issue")
                or arguments.get("problem")
                or arguments.get("details")
                or arguments.get("summary")
            )
            if fallback:
                arguments["title"] = str(fallback)

        if "description" not in arguments or not arguments["description"]:
            fallback_desc = (
                arguments.get("title")
                or arguments.get("subject")
                or arguments.get("details")
                or arguments.get("issue")
            )
            if fallback_desc:
                arguments["description"] = str(fallback_desc)

        urgency = arguments.pop("urgency", None)
        if urgency and ("priority" not in arguments or not arguments["priority"]):
            arguments["priority"] = str(urgency).lower()

        if "priority" in arguments and arguments["priority"]:
            p_val = str(arguments["priority"]).lower()
            arguments["priority"] = (
                p_val if p_val in ["low", "medium", "high", "urgent"] else "medium"
            )

        if "category" in arguments and arguments["category"]:
            cat = str(arguments["category"]).upper()
            if cat in ["HARDWARE", "SOFTWARE", "IT", "TECH", "IT DEPARTMENT"]:
                arguments["category"] = "IT"
            elif cat in ["HR", "PERSONNEL"]:
                arguments["category"] = "HR"
            elif cat not in ["IT", "HR", "Billing", "Facilities", "General"]:
                arguments["category"] = "General"

        known = set(tool["schema"]["properties"].keys())
        for k in list(set(arguments.keys()) - known):
            arguments.pop(k, None)


    schema = tool["schema"]


    properties = schema["properties"]
    for key in schema.get("required", []):
        if key not in arguments or arguments[key] in ("", None):
            return f"missing required argument: {key}"
    unknown = set(arguments) - set(properties)
    if unknown:
        return f"unknown arguments: {sorted(unknown)}"
    for key, spec in properties.items():
        if key not in arguments:
            continue
        if spec.get("type") == "string" and not isinstance(arguments[key], str):
            return f"argument '{key}' must be a string"
        if "enum" in spec and arguments[key] not in spec["enum"]:
            return f"argument '{key}' must be one of {spec['enum']}"
    return None
