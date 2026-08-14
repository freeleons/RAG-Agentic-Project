"""Flask application factory.

This is the entry point of the backend. `create_app()` wires together every
piece of the server:

  - configuration  (server/config.py, loaded from .env)
  - database       (SQLAlchemy models in server/models.py)
  - auth endpoints (server/auth.py  -> /api/auth/*)
  - API endpoints  (server/routes.py -> /api/*)

Run it with:  flask --app server.app run --debug
"""

from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate

from server.config import Config
from server.models import db


def create_app(test_config=None):
    """Build and return a configured Flask app.

    The "app factory" pattern lets tests create their own app with overridden
    settings (e.g. an in-memory SQLite database) by passing `test_config`.
    """
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        # Tests pass a dict here to override config values (DB URI, fake keys, ...)
        app.config.update(test_config)

    # Allow the React dev server (localhost:5173) to call this API from the browser.
    CORS(app)

    # Bind the shared SQLAlchemy instance to this app and enable `flask db` migrations.
    db.init_app(app)
    Migrate(app, db)

    # Blueprints are imported *inside* the factory (not at module top) to avoid
    # circular imports: auth.py and routes.py both import from server.models,
    # which needs `db` to exist first.
    from server.auth import auth_bp, bcrypt

    bcrypt.init_app(app)
    app.register_blueprint(auth_bp)   # /api/auth/register, /login, /me
    from server.routes import api_bp

    app.register_blueprint(api_bp)    # /api/runs, /api/tickets, /api/chat, ...

    with app.app_context():
        # Create any tables that don't exist yet (no-op for existing tables).
        db.create_all()
        # Lightweight "poor man's migration": db.create_all() never alters
        # existing tables, so columns added to the models after the table was
        # first created must be bolted on by hand. Wrapped in try/except so a
        # failure (e.g. column already exists on Postgres) never blocks startup.
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            if "conversations" in inspector.get_table_names():
                columns = [c["name"] for c in inspector.get_columns("conversations")]
                if "updated_at" not in columns:
                    with db.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE conversations ADD COLUMN updated_at DATETIME"))
                        conn.commit()
            if "tickets" in inspector.get_table_names():
                t_cols = [c["name"] for c in inspector.get_columns("tickets")]
                if "replies_json" not in t_cols:
                    with db.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE tickets ADD COLUMN replies_json TEXT"))
                        conn.commit()
        except Exception:
            pass

    # Simple liveness probe used by the frontend and by tests.
    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


# Module-level app instance so `flask --app server.app run` finds it.
app = create_app()