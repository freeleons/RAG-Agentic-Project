import pytest

from server.app import create_app

# Pre-import tools module to ensure monkeypatch can resolve module-level imports
import server.tools.search_knowledge  # noqa: F401


@pytest.fixture
def app():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SECRET_KEY": "test-secret",
            "JWT_EXPIRY_HOURS": 24,
            "AGENT_API_BASE_URL": "",
            "AGENT_API_KEY": "",
            "OLLAMA_BASE_URL": "http://localhost:11434",
        }
    )
    with app.app_context():
        from server.models import db

        db.create_all()
        yield app
        db.session.remove()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_headers(client):
    client.post("/api/auth/register", json={"email": "me@test.com", "password": "password123"})
    token = client.post(
        "/api/auth/login", json={"email": "me@test.com", "password": "password123"}
    ).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(client, app):
    app.config["ADMIN_EMAILS"] = {"admin@test.com"}
    client.post("/api/auth/register", json={"email": "admin@test.com", "password": "password123"})
    token = client.post(
        "/api/auth/login", json={"email": "admin@test.com", "password": "password123"}
    ).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def run(app):
    from server.models import Conversation, Message, Run, User, db

    user = User(email="runner@test.com", password_hash="x")
    db.session.add(user)
    db.session.commit()
    conv = Conversation(user_id=user.id)
    db.session.add(conv)
    db.session.commit()
    msg = Message(conversation_id=conv.id, role="user", content="goal")
    db.session.add(msg)
    db.session.commit()
    r = Run(conversation_id=conv.id, user_message_id=msg.id, model="test-model")
    db.session.add(r)
    db.session.commit()
    return r
