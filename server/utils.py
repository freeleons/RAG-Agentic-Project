"""Small request-level helpers shared across the backend."""

from flask import request


def is_client_disconnected():
    """Check if the HTTP client has closed/aborted the connection.

    Agent runs can take many seconds; the loop polls this between steps so a
    closed browser tab stops the run instead of burning model calls nobody
    will see.

    Implementation note: this reaches into private attributes of Werkzeug's
    dev-server socket, so it is best-effort only — on any other WSGI server
    (gunicorn, tests) the attribute chain fails and we conservatively report
    "still connected" (False). The Stop button (run.status='stopped' in the
    DB) is the reliable cancellation path; this is just an optimization.
    """
    try:
        # Accessing the underlying WSGI socket environment to test connection state
        environ = request.environ
        # Check for socket closing signals or closed stream
        return environ.get("wsgi.input").get_socket()._closed
    except Exception:
        return False
