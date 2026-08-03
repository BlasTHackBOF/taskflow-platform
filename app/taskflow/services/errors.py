"""Domain-level errors raised by the services layer.

These carry no HTTP knowledge. The API layer maps each one to a status
code and the shared JSON error shape in :mod:`taskflow.api.errors`, so the
same rule fails identically whether it is hit through a request or a test.
"""

from __future__ import annotations


class ServiceError(Exception):
    """Base class for errors a service raises on invalid use."""


class NotFoundError(ServiceError):
    def __init__(self, resource: str, identifier: object) -> None:
        super().__init__(f"{resource} {identifier} does not exist")
        self.resource = resource
        self.identifier = identifier


class ValidationError(ServiceError):
    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


class ConflictError(ServiceError):
    """The request is well-formed but collides with existing state."""
