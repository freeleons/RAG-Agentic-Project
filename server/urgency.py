"""LLM-based urgency / priority classification for support tickets."""

import json
import re

from server.llm import LLMError, generate
from server.prompts import URGENCY_SYSTEM_PROMPT, URGENCY_USER_PROMPT

VALID_PRIORITIES = ("urgent", "high", "medium", "low")
DEFAULT_PRIORITY = "medium"


def build_urgency_messages(ticket):
    """Messages passed to generate() for priority classification."""
    user = URGENCY_USER_PROMPT.format(
        requester_name=ticket.requester_name or "Unknown",
        requester_department=ticket.requester_department or "Unknown",
        category=ticket.category or "General",
        title=ticket.title or "",
        description=ticket.description or "",
    )
    return [
        {"role": "system", "content": URGENCY_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def _extract_json_object(text):
    """Pull the first JSON object out of model output (may be wrapped in markdown)."""
    if not text:
        return None
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    raw = match.group(0)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def parse_priority_response(content):
    """Parse model content into (priority, reason). Invalid → (DEFAULT_PRIORITY, reason)."""
    parsed = _extract_json_object(content or "")
    if not parsed:
        return DEFAULT_PRIORITY, "Could not parse model response; defaulted to medium."

    raw_priority = str(parsed.get("priority") or "").strip().lower()
    reason = str(parsed.get("reason") or "").strip() or "No reason provided."

    # Map common aliases from the inbox-style prompt (high/medium/low only)
    aliases = {"critical": "urgent", "p0": "urgent", "p1": "high", "p2": "medium", "p3": "low"}
    priority = aliases.get(raw_priority, raw_priority)

    if priority not in VALID_PRIORITIES:
        return DEFAULT_PRIORITY, f"Invalid priority '{raw_priority}'; defaulted to medium. ({reason})"

    return priority, reason


def classify_priority(ticket):
    """Ask the model for ticket priority. Returns a dict suitable for record_step.

    On LLM failure or unparseable output, falls back to medium so triage can continue.
    """
    messages = build_urgency_messages(ticket)
    try:
        decision = generate(messages, tools=None)
    except LLMError as exc:
        return {
            "priority": DEFAULT_PRIORITY,
            "reason": f"Model unavailable ({exc}); defaulted to medium.",
            "error": str(exc),
        }

    if decision.get("type") != "final":
        return {
            "priority": DEFAULT_PRIORITY,
            "reason": "Unexpected tool_call response; defaulted to medium.",
            "raw": decision,
        }

    content = decision.get("content") or ""
    priority, reason = parse_priority_response(content)
    result = {
        "priority": priority,
        "reason": reason,
        "raw": content,
    }
    if decision.get("usage"):
        result["usage"] = decision["usage"]
    return result


def apply_priority(ticket, classification):
    """Write classification['priority'] onto the ticket and commit."""
    from server.models import db

    priority = classification.get("priority")
    if priority not in VALID_PRIORITIES:
        priority = DEFAULT_PRIORITY
    ticket.priority = priority
    db.session.commit()
    return ticket.priority
