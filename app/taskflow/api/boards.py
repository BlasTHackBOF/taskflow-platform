"""Board endpoints: parse input, call services, format output."""

from __future__ import annotations

from flask import Blueprint

from taskflow.api.request_body import json_object
from taskflow.api.serializers import board_to_dict
from taskflow.services import boards

boards_bp = Blueprint("boards", __name__)


@boards_bp.get("/boards")
def list_boards():
    return {"boards": [board_to_dict(b) for b in boards.list_boards()]}


@boards_bp.post("/boards")
def create_board():
    return board_to_dict(boards.create_board(json_object())), 201


@boards_bp.get("/boards/<int:board_id>")
def get_board(board_id: int):
    return board_to_dict(boards.get_board(board_id))
