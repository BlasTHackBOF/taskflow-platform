"""Model rules tested with no HTTP and no database."""

from __future__ import annotations

import pytest

from taskflow.models import (
    ALLOWED_TRANSITIONS,
    Board,
    InvalidTransitionError,
    Task,
    TaskStatus,
)

_ALL_PAIRS = [(src, dst) for src in TaskStatus for dst in TaskStatus]


def test_every_status_has_a_transition_entry():
    assert set(ALLOWED_TRANSITIONS) == set(TaskStatus)


def test_transition_matrix_is_exactly_the_agreed_workflow():
    """Pins the agreed workflow literally, independent of the production
    mapping — an accidental edit to ALLOWED_TRANSITIONS must fail HERE,
    not only in whichever test happens to hard-code one sample."""
    assert ALLOWED_TRANSITIONS == {
        TaskStatus.TODO: {TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED},
        TaskStatus.IN_PROGRESS: {
            TaskStatus.TODO,
            TaskStatus.BLOCKED,
            TaskStatus.DONE,
        },
        TaskStatus.BLOCKED: {TaskStatus.TODO, TaskStatus.IN_PROGRESS},
        TaskStatus.DONE: {TaskStatus.TODO},
    }


@pytest.mark.parametrize(
    ("src", "dst"), _ALL_PAIRS, ids=[f"{s.value}->{d.value}" for s, d in _ALL_PAIRS]
)
def test_every_transition_pair(src: TaskStatus, dst: TaskStatus):
    """Every one of the 16 (source, target) pairs behaves per the mapping:
    legal moves land, illegal moves raise and leave the status untouched."""
    task = Task(status=src)
    if dst in ALLOWED_TRANSITIONS[src]:
        task.transition_to(dst)
        assert task.status is dst
    else:
        with pytest.raises(InvalidTransitionError) as excinfo:
            task.transition_to(dst)
        assert task.status is src
        assert excinfo.value.current is src
        assert excinfo.value.requested is dst


@pytest.mark.parametrize(
    ("raw", "stored"),
    [("tf", "TF"), (" ops ", "OPS"), ("platform", "PLATFORM"), ("QA", "QA")],
)
def test_board_key_normalised(raw: str, stored: str):
    assert Board(key=raw, name="X").key == stored


@pytest.mark.parametrize("bad", ["x", "toolong99", "ab1", "", "  ", "a b", "TF-"])
def test_board_key_rejected(bad: str):
    with pytest.raises(ValueError):
        Board(key=bad, name="X")


def test_reference_combines_board_key_and_number():
    task = Task(board=Board(key="TF", name="X"), number=7)
    assert task.reference == "TF-7"
