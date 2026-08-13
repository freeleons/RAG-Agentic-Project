from flask import request

def is_client_disconnected():
    """Check if the HTTP client has closed/aborted the connection."""
    try:
        # Accessing the underlying WSGI socket environment to test connection state
        environ = request.environ
        # Check for socket closing signals or closed stream
        return environ.get("wsgi.input").get_socket()._closed
    except Exception:
        return False
