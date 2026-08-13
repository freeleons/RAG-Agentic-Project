from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate

from server.config import Config
from server.models import db


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    CORS(app)
    db.init_app(app)
    Migrate(app, db)
    from server.auth import auth_bp, bcrypt

    bcrypt.init_app(app)
    app.register_blueprint(auth_bp)
    from server.routes import api_bp

    app.register_blueprint(api_bp)

    with app.app_context():
        db.create_all()
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


    @app.get("/api/health")

    def health():
        return {"status": "ok"}

    return app


app = create_app()
