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

    # Imported for the side effect of registering tables on db.metadata,
    # which Flask-Migrate reads when autogenerating migrations.
    from taskflow import models  # noqa: F401
    from taskflow.api.boards import boards_bp
    from taskflow.api.errors import register_error_handlers
    from taskflow.api.health import health_bp
    from taskflow.api.tasks import tasks_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(boards_bp, url_prefix="/api/v1")
    app.register_blueprint(tasks_bp, url_prefix="/api/v1")
    register_error_handlers(app)

    return app
