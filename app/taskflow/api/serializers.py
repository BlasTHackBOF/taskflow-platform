"""Model-to-dict converters used by the API blueprints."""

from __future__ import annotations

from taskflow.models import Board, Task


def board_to_dict(board: Board) -> dict:
    return {
        "id": board.id,
        "key": board.key,
        "name": board.name,
        "description": board.description,
        "created_at": board.created_at.isoformat(),
    }


def task_to_dict(task: Task) -> dict:
    return {
        "id": task.id,
        "reference": task.reference,
        "board_id": task.board_id,
        "title": task.title,
        "description": task.description,
        "status": task.status.value,
        "priority": task.priority.value,
        "assignee": task.assignee,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }
