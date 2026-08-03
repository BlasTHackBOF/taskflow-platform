"""Health probes.

Only liveness (``/healthz``) lives here for now; readiness and startup
probes arrive together with the database layer, since readiness is defined
by the database being reachable.
"""

from __future__ import annotations

from flask import Blueprint

health_bp = Blueprint("health", __name__)


@health_bp.get("/healthz")
def healthz() -> tuple[dict[str, str], int]:
    """Liveness probe.

    Deliberately touches nothing external: a database outage must not make
    the orchestrator restart otherwise-healthy application processes.
    """
    return {"status": "ok"}, 200
