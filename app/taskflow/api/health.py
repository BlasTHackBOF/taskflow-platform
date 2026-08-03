"""Health probes.

Liveness (``/healthz``) touches nothing external. Readiness (``/readyz``)
and startup (``/startupz``) are both defined by the database being
reachable — they share one check and differ only in the role the
orchestrator gives them.
"""

from __future__ import annotations

from flask import Blueprint
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from taskflow.extensions import db

health_bp = Blueprint("health", __name__)


def _database_probe() -> tuple[dict[str, str], int]:
    # A dedicated connection, not db.session: a failed probe must not leave
    # a broken transaction behind for whichever request reuses the session.
    try:
        with db.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return {"status": "unavailable", "database": "unreachable"}, 503
    return {"status": "ok", "database": "ok"}, 200


@health_bp.get("/healthz")
def healthz() -> tuple[dict[str, str], int]:
    """Liveness probe.

    Deliberately touches nothing external: a database outage must not make
    the orchestrator restart otherwise-healthy application processes.
    """
    return {"status": "ok"}, 200


@health_bp.get("/readyz")
def readyz() -> tuple[dict[str, str], int]:
    """Readiness probe.

    A pod that cannot reach the database serves nothing useful, so it is
    taken out of Service rotation until the check passes again.
    """
    return _database_probe()


@health_bp.get("/startupz")
def startupz() -> tuple[dict[str, str], int]:
    """Startup probe.

    Same check as readiness, different role: Kubernetes polls it only
    during boot and holds off liveness restarts until the first success,
    so a slow first connection is not mistaken for a hung process.
    """
    return _database_probe()
