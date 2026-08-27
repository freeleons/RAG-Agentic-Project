def test_register_login_roundtrip(client):
    resp = client.post(
        "/api/auth/register", json={"email": "a@b.com", "password": "password123"}
    )
    assert resp.status_code == 201
    resp = client.post(
        "/api/auth/login", json={"email": "a@b.com", "password": "password123"}
    )
    assert resp.status_code == 200
    assert "token" in resp.get_json()


def test_register_rejects_short_password(client):
    resp = client.post("/api/auth/register", json={"email": "a@b.com", "password": "short"})
    assert resp.status_code == 400


def test_register_duplicate_email(client):
    client.post("/api/auth/register", json={"email": "a@b.com", "password": "password123"})
    resp = client.post(
        "/api/auth/register", json={"email": "a@b.com", "password": "password123"}
    )
    assert resp.status_code == 409


def test_login_wrong_password(client):
    client.post("/api/auth/register", json={"email": "a@b.com", "password": "password123"})
    resp = client.post("/api/auth/login", json={"email": "a@b.com", "password": "nope-nope"})
    assert resp.status_code == 401


def test_require_auth(app, client):
    from flask import g

    from server.auth import require_auth

    @app.route("/api/probe")
    @require_auth
    def probe():
        return {"email": g.user.email}

    client.post("/api/auth/register", json={"email": "a@b.com", "password": "password123"})
    token = client.post(
        "/api/auth/login", json={"email": "a@b.com", "password": "password123"}
    ).get_json()["token"]

    assert client.get("/api/probe").status_code == 401
    assert (
        client.get("/api/probe", headers={"Authorization": "Bearer garbage"}).status_code
        == 401
    )
    ok = client.get("/api/probe", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200
    assert ok.get_json()["email"] == "a@b.com"


def test_login_reports_admin_flag(app, client):
    app.config["ADMIN_EMAILS"] = {"boss@test.com"}
    for email in ("boss@test.com", "pleb@test.com"):
        client.post("/api/auth/register", json={"email": email, "password": "password123"})
    boss = client.post(
        "/api/auth/login", json={"email": "boss@test.com", "password": "password123"}
    ).get_json()
    pleb = client.post(
        "/api/auth/login", json={"email": "pleb@test.com", "password": "password123"}
    ).get_json()
    assert boss["is_admin"] is True and boss["email"] == "boss@test.com"
    assert pleb["is_admin"] is False
