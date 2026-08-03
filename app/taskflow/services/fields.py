"""Field extraction helpers shared by the services."""

from __future__ import annotations

from collections.abc import Mapping

from taskflow.services.errors import ValidationError


def required_string(
    data: Mapping, field: str, *, max_length: int | None = None
) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(
            f"{field} is required and must be a non-empty string", field=field
        )
    value = value.strip()
    if max_length is not None and len(value) > max_length:
        raise ValidationError(
            f"{field} must be at most {max_length} characters", field=field
        )
    return value


def optional_string(
    data: Mapping, field: str, *, max_length: int | None = None
) -> str | None:
    value = data.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a string", field=field)
    if max_length is not None and len(value) > max_length:
        raise ValidationError(
            f"{field} must be at most {max_length} characters", field=field
        )
    return value
