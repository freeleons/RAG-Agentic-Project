"""Authentication: register / login / me endpoints + the @require_auth decorator.

Auth scheme in one paragraph: passwords are stored as bcrypt hashes; a
successful login returns a JWT (signed with SECRET_KEY, HS256, 24h expiry)
whose `sub` claim is the user id. Every protected endpoint sends that token as
an `Authorization: Bearer <token>` header, which @require_auth verifies before
the view runs.
"""

from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Blueprint, current_app, g, jsonify, request
from flask_bcrypt import Bcrypt

from server.models import User, db

# Created unbound here, then bound to the app in app.py (bcrypt.init_app).
bcrypt = Bcrypt()
auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.post("/register")
def register():
    """Create a new user account and seed its demo tickets."""
    data = request.get_json(silent=True) or {}
    # Normalize the email so "Foo@Bar.com" and "foo@bar.com" are one account.
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    full_name = (data.get("full_name") or "Support Specialist").strip()
    department = (data.get("department") or "HR Operations").strip()
    role_title = (data.get("role_title") or "Lead Support Specialist").strip()

    if not email or len(password) < 8:
        return jsonify({"error": "email and a password of at least 8 characters are required"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "email already registered"}), 409
    user = User(
        email=email,
        # Only the bcrypt hash is stored; the plaintext password never touches the DB.
        password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
        full_name=full_name,
        department=department,
        role_title=role_title,
    )
    db.session.add(user)
    db.session.commit()

    # Give every fresh account the ApexCare sample tickets so the UI has data.
    # Imported here (not at top) to avoid a circular import with routes.py.
    from server.routes import seed_apexcare_tickets
    seed_apexcare_tickets(user.id)

    return jsonify({
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "department": user.department,
        "role_title": user.role_title
    }), 201


@auth_bp.post("/login")
def login():
    """Verify credentials and hand back a signed JWT plus the user profile."""
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    user = User.query.filter_by(email=email).first()
    # Same error for "no such user" and "wrong password" — don't leak which
    # emails are registered.
    if user is None or not bcrypt.check_password_hash(user.password_hash, password):
        return jsonify({"error": "invalid email or password"}), 401
    token = jwt.encode(
        {
            "sub": str(user.id),  # subject claim: who this token belongs to
            "exp": datetime.now(timezone.utc)
            + timedelta(hours=current_app.config["JWT_EXPIRY_HOURS"]),
        },
        current_app.config["SECRET_KEY"],
        algorithm="HS256",
    )
    return jsonify(
        {
            "token": token,
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name or "Support Specialist",
            "department": user.department or "HR Operations",
            "role_title": user.role_title or "Lead Support Specialist",
            # Admin status is config-driven, not a DB column (see Config.ADMIN_EMAILS).
            "is_admin": user.email in current_app.config["ADMIN_EMAILS"],
        }
    )


@auth_bp.get("/me")
def get_me():
    """Return the profile for the token's user — used by the frontend to
    restore a session on page reload. Duplicates the token check inline
    because @require_auth lives below and would be a circular decoration."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return jsonify({"error": "missing bearer token"}), 401
    try:
        payload = jwt.decode(
            header[len("Bearer ") :],
            current_app.config["SECRET_KEY"],
            algorithms=["HS256"],
        )
    except jwt.InvalidTokenError:
        # Covers bad signature, malformed token, AND expiry (ExpiredSignatureError
        # subclasses InvalidTokenError).
        return jsonify({"error": "invalid or expired token"}), 401
    user = db.session.get(User, int(payload["sub"]))
    if user is None:
        return jsonify({"error": "invalid or expired token"}), 401
    return jsonify({
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name or "Support Specialist",
        "department": user.department or "HR Operations",
        "role_title": user.role_title or "Lead Support Specialist",
        "is_admin": user.email in current_app.config["ADMIN_EMAILS"],
    })


def require_auth(fn):
    """Decorator protecting API endpoints.

    Validates the Bearer JWT, loads the user, and exposes two globals for the
    wrapped view (Flask's `g` is per-request state):

        g.user      -> the authenticated User row
        g.is_admin  -> True if the email is listed in ADMIN_EMAILS

    Any failure short-circuits with 401 before the view runs.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify({"error": "missing bearer token"}), 401
        try:
            payload = jwt.decode(
                header[len("Bearer ") :],
                current_app.config["SECRET_KEY"],
                algorithms=["HS256"],
            )
        except jwt.InvalidTokenError:
            return jsonify({"error": "invalid or expired token"}), 401
        user = db.session.get(User, int(payload["sub"]))
        if user is None:
            return jsonify({"error": "invalid or expired token"}), 401
        g.user = user
        g.is_admin = user.email in current_app.config["ADMIN_EMAILS"]
        return fn(*args, **kwargs)

    return wrapper
