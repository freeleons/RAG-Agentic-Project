import requests

from server.models import Ticket, User, db, utcnow
from server.knowledge_sync import sync_resolved_tickets


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.text = str(payload)

    def json(self):
        return self._payload


def _make_ticket(status="resolved", resolution_notes=None, kb_synced_at=None):
    user = User(email=f"u{Ticket.query.count()}@test.com", password_hash="x")
    db.session.add(user)
    db.session.commit()
    ticket = Ticket(
        user_id=user.id,
        title="Broken monitor",
        description="External display stays black on USB-C",
        status=status,
        resolution_notes=resolution_notes,
        kb_synced_at=kb_synced_at,
    )
    db.session.add(ticket)
    db.session.commit()
    return ticket


def test_sync_pushes_unsynced_resolved_tickets_and_stamps_them(app, monkeypatch):
    with app.app_context():
        target = _make_ticket(status="resolved", resolution_notes="Replaced HDMI cable.")
        _make_ticket(status="open")  # not resolved -> skipped
        _make_ticket(status="resolved", kb_synced_at=utcnow())  # already synced -> skipped

        seen = {}

        def fake_post(url, json=None, headers=None, timeout=None):
            seen["url"] = url
            seen["json"] = json
            seen["auth"] = headers["Authorization"]
            return FakeResponse({"success": True, "documents": [{"location": "x"}]})

        monkeypatch.setattr("server.knowledge_sync.requests.post", fake_post)

        result = sync_resolved_tickets()

        assert result == {"synced": 1, "failed": 0, "total": 1}
        assert seen["url"] == "http://localhost:3001/api/v1/document/raw-text"
        assert seen["auth"].startswith("Bearer ")
        assert seen["json"]["addToWorkspaces"] == "apprentice-kb"
        assert f"Ticket #{target.id}" in seen["json"]["textContent"]
        assert "Replaced HDMI cable." in seen["json"]["textContent"]
        assert seen["json"]["metadata"]["title"].startswith(f"Resolved Ticket #{target.id}")

        db.session.refresh(target)
        assert target.kb_synced_at is not None


def test_sync_skips_already_synced_ticket_on_rerun(app, monkeypatch):
    with app.app_context():
        _make_ticket(status="resolved", resolution_notes="Fixed.")

        monkeypatch.setattr(
            "server.knowledge_sync.requests.post",
            lambda *a, **k: FakeResponse({"success": True}),
        )
        first = sync_resolved_tickets()
        assert first["synced"] == 1

        second = sync_resolved_tickets()
        assert second == {"synced": 0, "failed": 0, "total": 0}


def test_sync_leaves_ticket_unsynced_on_http_failure(app, monkeypatch):
    with app.app_context():
        target = _make_ticket(status="resolved")

        monkeypatch.setattr(
            "server.knowledge_sync.requests.post",
            lambda *a, **k: FakeResponse({"success": False, "error": "boom"}, status=500),
        )
        result = sync_resolved_tickets()

        assert result == {"synced": 0, "failed": 1, "total": 1}
        db.session.refresh(target)
        assert target.kb_synced_at is None


def test_sync_leaves_ticket_unsynced_on_network_error(app, monkeypatch):
    with app.app_context():
        target = _make_ticket(status="resolved")

        def fake_post(*a, **k):
            raise requests.Timeout("too slow")

        monkeypatch.setattr("server.knowledge_sync.requests.post", fake_post)
        result = sync_resolved_tickets()

        assert result == {"synced": 0, "failed": 1, "total": 1}
        db.session.refresh(target)
        assert target.kb_synced_at is None


def test_sync_respects_limit(app, monkeypatch):
    with app.app_context():
        _make_ticket(status="resolved")
        _make_ticket(status="resolved")

        monkeypatch.setattr(
            "server.knowledge_sync.requests.post",
            lambda *a, **k: FakeResponse({"success": True}),
        )
        result = sync_resolved_tickets(limit=1)
        assert result == {"synced": 1, "failed": 0, "total": 1}
