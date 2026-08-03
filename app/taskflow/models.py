"""Database models: boards and the tasks that live on them.

Status transitions are data, not control flow: ``ALLOWED_TRANSITIONS`` is
the single authority on which moves are legal. Anything that needs to
validate, render or document the workflow reads that mapping instead of
re-encoding it.
"""

from __future__ import annotations

import enum
import re
from datetime import date, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from taskflow.extensions import db


class TaskStatus(enum.Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"


class TaskPriority(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


#: Legal status moves. BLOCKED describes availability, not work state: a
#: task waiting on an external dependency is blocked whether or not anyone
#: has started it, so it is reachable from TODO as well as IN_PROGRESS, and
#: it leaves to whichever of the two reflects reality — TODO when work never
#: began, IN_PROGRESS when it did. DONE -> TODO is an explicit reopen rather
#: than a silent edit back into the flow.
ALLOWED_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.TODO: frozenset({TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED}),
    TaskStatus.IN_PROGRESS: frozenset(
        {TaskStatus.TODO, TaskStatus.BLOCKED, TaskStatus.DONE}
    ),
    TaskStatus.BLOCKED: frozenset({TaskStatus.TODO, TaskStatus.IN_PROGRESS}),
    TaskStatus.DONE: frozenset({TaskStatus.TODO}),
}


class InvalidTransitionError(ValueError):
    """Raised when a task is asked to make a move not in ALLOWED_TRANSITIONS."""

    def __init__(self, current: TaskStatus, requested: TaskStatus) -> None:
        super().__init__(
            f"cannot move a task from {current.value!r} to {requested.value!r}"
        )
        self.current = current
        self.requested = requested


_BOARD_KEY_RE = re.compile(r"^[A-Z]{2,8}$")

# Stored as VARCHAR + CHECK rather than a native PG enum type: adding a value
# later is then an ordinary column constraint change, not an ALTER TYPE.
_status_column = Enum(
    TaskStatus,
    name="task_status",
    native_enum=False,
    create_constraint=True,
    length=20,
    values_callable=lambda e: [m.value for m in e],
)
_priority_column = Enum(
    TaskPriority,
    name="task_priority",
    native_enum=False,
    create_constraint=True,
    length=20,
    values_callable=lambda e: [m.value for m in e],
)


class Board(db.Model):
    __tablename__ = "boards"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(8), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text())
    # Feeds per-board task references (TF-1, TF-2, ...). Concurrent creators
    # must lock the board row (SELECT ... FOR UPDATE) before reading it.
    next_task_number: Mapped[int] = mapped_column(default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    tasks: Mapped[list[Task]] = relationship(
        back_populates="board", cascade="all, delete-orphan"
    )

    @validates("key")
    def _normalise_key(self, _field: str, value: str) -> str:
        value = value.strip().upper()
        if not _BOARD_KEY_RE.match(value):
            raise ValueError("board key must be 2-8 letters (A-Z)")
        return value

    def allocate_task_number(self) -> int:
        """Hand out the next task number and advance the counter."""
        number = self.next_task_number
        self.next_task_number = number + 1
        return number

    def __repr__(self) -> str:
        return f"<Board {self.key}>"


class Task(db.Model):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("board_id", "number", name="uq_tasks_board_id_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    board_id: Mapped[int] = mapped_column(
        ForeignKey("boards.id", ondelete="CASCADE")
    )
    number: Mapped[int]
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text())
    status: Mapped[TaskStatus] = mapped_column(
        _status_column, default=TaskStatus.TODO, server_default=TaskStatus.TODO.value
    )
    priority: Mapped[TaskPriority] = mapped_column(
        _priority_column,
        default=TaskPriority.MEDIUM,
        server_default=TaskPriority.MEDIUM.value,
    )
    assignee: Mapped[str | None] = mapped_column(String(120))
    due_date: Mapped[date | None]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    board: Mapped[Board] = relationship(back_populates="tasks")

    @property
    def reference(self) -> str:
        """Human-facing identifier, e.g. ``TF-1``; unique because board keys are."""
        return f"{self.board.key}-{self.number}"

    def transition_to(self, requested: TaskStatus) -> None:
        """Move to ``requested`` if ALLOWED_TRANSITIONS permits it."""
        if requested not in ALLOWED_TRANSITIONS[self.status]:
            raise InvalidTransitionError(self.status, requested)
        self.status = requested

    def __repr__(self) -> str:
        return f"<Task {self.board.key}-{self.number} {self.status.value}>"
