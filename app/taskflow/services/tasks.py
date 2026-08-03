"""Task business rules: creation with reference allocation, filtering,
updates including status transitions, and deletion."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from sqlalchemy import select

from taskflow.extensions import db
from taskflow.models import Board, Task, TaskPriority, TaskStatus
from taskflow.services.errors import NotFoundError, ValidationError
from taskflow.services.fields import optional_string, required_string

_CREATE_FIELDS = {"board_id", "title", "description", "priority", "assignee", "due_date"}
_UPDATE_FIELDS = {"title", "description", "priority", "assignee", "due_date", "status"}


def create_task(data: Mapping) -> Task:
    unknown = set(data) - _CREATE_FIELDS
    if unknown:
        if "status" in unknown:
            raise ValidationError(
                "status cannot be set at creation; new tasks start as 'todo'",
                field="status",
            )
        raise ValidationError(f"unknown fields: {', '.join(sorted(unknown))}")

    board_id = data.get("board_id")
    if not isinstance(board_id, int) or isinstance(board_id, bool):
        raise ValidationError(
            "board_id is required and must be an integer", field="board_id"
        )
    title = required_string(data, "title", max_length=200)
    description = optional_string(data, "description")
    assignee = optional_string(data, "assignee", max_length=120)
    priority = (
        _parse_priority(data["priority"]) if "priority" in data else TaskPriority.MEDIUM
    )
    due_date = _parse_due_date(data["due_date"]) if data.get("due_date") is not None else None

    # The row lock serialises reference allocation: two concurrent creates on
    # the same board queue here instead of both reading the same number.
    board = db.session.execute(
        select(Board).where(Board.id == board_id).with_for_update()
    ).scalar_one_or_none()
    if board is None:
        raise NotFoundError("board", board_id)

    task = Task(
        board=board,
        number=board.allocate_task_number(),
        title=title,
        description=description,
        priority=priority,
        assignee=assignee,
        due_date=due_date,
    )
    db.session.add(task)
    db.session.commit()
    return task


def get_task(task_id: int) -> Task:
    task = db.session.get(Task, task_id)
    if task is None:
        raise NotFoundError("task", task_id)
    return task


def list_tasks(
    *,
    board_id: str | None = None,
    status: str | None = None,
    assignee: str | None = None,
) -> list[Task]:
    """Filters arrive as raw query-parameter strings and are validated here,
    so the rules hold for any caller, not just the HTTP layer."""
    query = select(Task).order_by(Task.id)
    if board_id is not None:
        try:
            query = query.where(Task.board_id == int(board_id))
        except ValueError:
            raise ValidationError(
                "board_id must be an integer", field="board_id"
            ) from None
    if status is not None:
        query = query.where(Task.status == _parse_status(status))
    if assignee is not None:
        query = query.where(Task.assignee == assignee)
    return list(db.session.scalars(query))


def update_task(task_id: int, data: Mapping) -> Task:
    task = get_task(task_id)
    unknown = set(data) - _UPDATE_FIELDS
    if unknown:
        raise ValidationError(f"unknown fields: {', '.join(sorted(unknown))}")
    if not data:
        raise ValidationError("request body must name at least one field to change")

    if "title" in data:
        task.title = required_string(data, "title", max_length=200)
    if "description" in data:
        task.description = optional_string(data, "description")
    if "priority" in data:
        task.priority = _parse_priority(data["priority"])
    if "assignee" in data:
        task.assignee = optional_string(data, "assignee", max_length=120)
    if "due_date" in data:
        task.due_date = (
            _parse_due_date(data["due_date"]) if data["due_date"] is not None else None
        )
    if "status" in data:
        # InvalidTransitionError propagates; the API maps it to 409 and the
        # session teardown rolls back the other half-applied fields.
        task.transition_to(_parse_status(data["status"]))

    db.session.commit()
    return task


def delete_task(task_id: int) -> None:
    task = get_task(task_id)
    db.session.delete(task)
    db.session.commit()


def _parse_status(value: object) -> TaskStatus:
    if isinstance(value, str):
        try:
            return TaskStatus(value)
        except ValueError:
            pass
    raise ValidationError(
        f"status must be one of: {', '.join(s.value for s in TaskStatus)}",
        field="status",
    )


def _parse_priority(value: object) -> TaskPriority:
    if isinstance(value, str):
        try:
            return TaskPriority(value)
        except ValueError:
            pass
    raise ValidationError(
        f"priority must be one of: {', '.join(p.value for p in TaskPriority)}",
        field="priority",
    )


def _parse_due_date(value: object) -> date:
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise ValidationError("due_date must be an ISO date (YYYY-MM-DD)", field="due_date")
