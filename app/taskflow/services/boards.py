"""Board business rules: creation, lookup and listing."""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from taskflow.extensions import db
from taskflow.models import Board
from taskflow.services.errors import ConflictError, NotFoundError, ValidationError
from taskflow.services.fields import optional_string, required_string

_CREATE_FIELDS = {"key", "name", "description"}


def create_board(data: Mapping) -> Board:
    unknown = set(data) - _CREATE_FIELDS
    if unknown:
        raise ValidationError(f"unknown fields: {', '.join(sorted(unknown))}")

    key = required_string(data, "key")
    name = required_string(data, "name", max_length=120)
    description = optional_string(data, "description")
    try:
        board = Board(key=key, name=name, description=description)
    except ValueError as exc:  # the model's key validator rejected it
        raise ValidationError(str(exc), field="key") from exc

    db.session.add(board)
    try:
        db.session.commit()
    except IntegrityError as exc:
        # The unique constraint is the authority; a pre-check would still
        # race against a concurrent insert of the same key.
        db.session.rollback()
        raise ConflictError(f"board key {board.key!r} already exists") from exc
    return board


def get_board(board_id: int) -> Board:
    board = db.session.get(Board, board_id)
    if board is None:
        raise NotFoundError("board", board_id)
    return board


def list_boards() -> list[Board]:
    return list(db.session.scalars(select(Board).order_by(Board.id)))
