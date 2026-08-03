"""One JSON error shape for the whole application.

Every failure — domain errors from the services, illegal status
transitions, and plain HTTP errors such as 404 on an unknown URL — renders
as ``{"error": {"code", "message"}}`` with an optional ``details`` object,
so a client never has to guess how a failure is reported.
"""

from __future__ import annotations

from flask import Flask
from werkzeug.exceptions import HTTPException

from taskflow.models import ALLOWED_TRANSITIONS, InvalidTransitionError
from taskflow.services.errors import ConflictError, NotFoundError, ValidationError


def _payload(code: str, message: str, details: dict | None = None) -> dict:
    body: dict = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return body


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(NotFoundError)
    def not_found(exc: NotFoundError):
        return _payload("not_found", str(exc)), 404

    @app.errorhandler(ValidationError)
    def validation_failed(exc: ValidationError):
        details = {"field": exc.field} if exc.field else None
        return _payload("validation_error", str(exc), details), 422

    @app.errorhandler(ConflictError)
    def conflict(exc: ConflictError):
        return _payload("conflict", str(exc)), 409

    @app.errorhandler(InvalidTransitionError)
    def invalid_transition(exc: InvalidTransitionError):
        details = {
            "current": exc.current.value,
            "requested": exc.requested.value,
            "allowed": sorted(s.value for s in ALLOWED_TRANSITIONS[exc.current]),
        }
        return _payload("invalid_transition", str(exc), details), 409

    @app.errorhandler(HTTPException)
    def http_error(exc: HTTPException):
        code = (exc.name or "error").lower().replace(" ", "_")
        return _payload(code, exc.description or exc.name), exc.code or 500
