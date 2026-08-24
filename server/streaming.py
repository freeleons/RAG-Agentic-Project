"""Server-Sent Events helpers for live agent/chat traces.

Step-level streaming (not token streaming): the UI learns about each
persisted RunStep as soon as `record_step` commits, instead of polling
GET /runs/<id> every ~700ms.

Wire format (text/event-stream):

    event: <name>
    data: <json>

    (blank line)

Clients should request with `?stream=1` or `Accept: text/event-stream`.
Non-streaming JSON responses stay the default for older clients/tests.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Iterator, Mapping

from flask import Response, request, stream_with_context


EventCallback = Callable[[Mapping[str, Any]], None]


def client_wants_sse() -> bool:
    """True when the caller asked for an event stream."""
    if request.args.get("stream") in {"1", "true", "yes"}:
        return True
    accept = (request.headers.get("Accept") or "").lower()
    return "text/event-stream" in accept


def format_sse(event: str, data: Mapping[str, Any] | list | str | int | float | bool | None) -> str:
    """One SSE message. `data` is JSON-encoded on a single line."""
    payload = json.dumps(data, default=str, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


def sse_response(events: Iterator[str]) -> Response:
    """Wrap an iterator of already-formatted SSE chunks as a Flask response."""
    return Response(
        stream_with_context(events),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx proxy buffering
            "Connection": "keep-alive",
        },
    )


def emit(on_event: EventCallback | None, event_type: str, **payload: Any) -> None:
    """Fire a structured event to an optional callback (no-op if None)."""
    if on_event is None:
        return
    on_event({"type": event_type, **payload})
