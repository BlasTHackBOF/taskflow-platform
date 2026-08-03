"""TaskFlow — a small task-board service built as a deployment target.

The application exists to exercise the surrounding infrastructure: health
probes, metrics, structured logs and database migrations matter more here
than product features.
"""

from __future__ import annotations

from flask import Flask

from taskflow.config import BaseConfig, get_config
from taskflow.extensions import db, migrate


def create_app(config: BaseConfig | None = None) -> Flask:
    """Build and wire the Flask application.

    ``config`` lets tests inject settings directly; otherwise the
    environment decides via :func:`taskflow.config.get_config`.
    """
    app = Flask(__name__)
    app.config.from_object(config if config is not None else get_config())

    db.init_app(app)
    migrate.init_app(app, db)

    from taskflow.api.health import health_bp

    app.register_blueprint(health_bp)

    return app
