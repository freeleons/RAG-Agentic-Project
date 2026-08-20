"""Cheap input sanitization: regex blocklist for obvious prompt-injection probes.

Applied at HTTP entry points (chat / triage) BEFORE any LLM call. This is the
first layer of a two-layer design; a classifier can be added later without
changing the call sites.
"""

from __future__ import annotations

import re

from flask import Response, current_app, jsonify

# Obvious jailbreak / prompt-hijack phrases. Cheap and imperfect — false
# negatives are expected; this only catches the noisiest attempts.
_OBVIOUS_PATTERNS = [
    re.compile(
        r"\b(ignore|disregard|forget)\s+(all\s+|the\s+)?(previous|prior|above|preceding)\s+(instructions?|rules?|commands?|directives?)\b",
        re.I,
    ),
    re.compile(
        r"\b(print|reveal|show|dump|repeat|output|what\s+is)\s+(your\s+|the\s+)?system\s+prompt\b",
        re.I,
    ),
    re.compile(r"\bsystem\s+prompt\b", re.I),
    re.compile(r"\byou\s+are\s+now\s+(a|an)\b", re.I),
    re.compile(r"\boverride\s+(your|the)\s+(instructions?|rules?|system)\b", re.I),
]


def regex_blocked(text: str) -> str | None:
    """Return the matched pattern string if text looks like an injection probe."""
    if not text:
        return None
    for pattern in _OBVIOUS_PATTERNS:
        if pattern.search(text):
            return pattern.pattern
    return None


def reject_if_injection(*texts: str, source: str) -> tuple[Response, int] | None:
    """If any text matches the blocklist, log and return a Flask (json, 400) tuple.

    Returns None when all texts are clean, so callers can write:

        blocked = reject_if_injection(msg, source="chat")
        if blocked is not None:
            return blocked
    """
    for text in texts:
        matched = regex_blocked(text or "")
        if matched is None:
            continue
        current_app.logger.warning(
            "regex_block source=%s pattern=%s preview=%r",
            source,
            matched,
            (text or "")[:120],
        )
        return (
            jsonify(
                {
                    "error": "Request rejected",
                    "reason": "prompt_injection_suspected",
                }
            ),
            400,
        )
    return None
