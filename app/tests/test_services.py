"""Service-layer rules exercised directly — no HTTP involved."""

from __future__ import annotations

import pytest

from taskflow.extensions import db
from taskflow.models import InvalidTransitionError, TaskStatus
from taskflow.services import boards, tasks
from taskflow.services.errors import ConflictError, NotFoundError, ValidationError


@pytest.fixture()
def board(app_context):
    return boards.create_board({"key": "tf", "name": "TaskFlow"})


def test_board_key_normalised_on_create(board):
    assert board.key == "TF"


def test_duplicate_board_key_conflicts(app_context, board):
    with pytest.raises(ConflictError):
        boards.create_board({"key": "TF", "name": "Again"})


def test_invalid_board_key_is_validation_error(app_context):
    with pytest.raises(ValidationError):
        boards.create_board({"key": "x", "name": "Bad"})


def test_get_missing_board_raises(app_context):
    with pytest.raises(NotFoundError):
        boards.get_board(99)


def test_references_allocated_in_order(app_context, board):
    first = tasks.create_task({"board_id": board.id, "title": "First"})
    second = tasks.create_task({"board_id": board.id, "title": "Second"})
    assert (first.reference, second.reference) == ("TF-1", "TF-2")
    assert board.next_task_number == 3


def test_create_task_on_missing_board(app_context):
    with pytest.raises(NotFoundError):
        tasks.create_task({"board_id": 42, "title": "Orphan"})


def test_status_rejected_at_creation(app_context, board):
    with pytest.raises(ValidationError):
        tasks.create_task({"board_id": board.id, "title": "T", "status": "done"})


def test_unknown_field_rejected(app_context, board):
    with pytest.raises(ValidationError):
        tasks.create_task({"board_id": board.id, "title": "T", "points": 5})


def test_bad_due_date_rejected(app_context, board):
    with pytest.raises(ValidationError):
        tasks.create_task({"board_id": board.id, "title": "T", "due_date": "tomorrow"})


def test_legal_transition_persists(app_context, board):
    task = tasks.create_task({"board_id": board.id, "title": "T"})
    tasks.update_task(task.id, {"status": "in_progress"})
    assert tasks.get_task(task.id).status is TaskStatus.IN_PROGRESS


def test_illegal_transition_raises_from_service(app_context, board):
    task = tasks.create_task({"board_id": board.id, "title": "T"})
    with pytest.raises(InvalidTransitionError):
        tasks.update_task(task.id, {"status": "done"})
    db.session.rollback()  # what the request teardown does in the app
    assert tasks.get_task(task.id).status is TaskStatus.TODO


def test_filters(app_context, board):
    tasks.create_task({"board_id": board.id, "title": "A", "assignee": "moshe"})
    second = tasks.create_task({"board_id": board.id, "title": "B"})
    tasks.update_task(second.id, {"status": "in_progress"})
    assert [t.title for t in tasks.list_tasks(assignee="moshe")] == ["A"]
    assert [t.title for t in tasks.list_tasks(status="in_progress")] == ["B"]
    assert len(tasks.list_tasks(board_id=str(board.id))) == 2


def test_invalid_filter_status(app_context):
    with pytest.raises(ValidationError):
        tasks.list_tasks(status="nonsense")


def test_invalid_filter_board_id(app_context):
    with pytest.raises(ValidationError):
        tasks.list_tasks(board_id="abc")


def test_delete_task(app_context, board):
    task = tasks.create_task({"board_id": board.id, "title": "T"})
    tasks.delete_task(task.id)
    with pytest.raises(NotFoundError):
        tasks.get_task(task.id)
