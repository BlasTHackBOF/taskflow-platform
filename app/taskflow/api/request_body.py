"""Request-body parsing shared by the API blueprints."""

from __future__ import annotations

from flask import request

from taskflow.services.errors import ValidationError


def json_object() -> dict:
    """Return the request body as a dict, or fail with the shared 422 shape.

    Malformed JSON and a wrong Content-Type are raised by Flask itself
    (400/415) and rendered by the HTTPException handler; this only guards
    against valid JSON that is not an object.
    """
    data = request.get_json()
    if not isinstance(data, dict):
        raise ValidationError("request body must be a JSON object")
    return data
