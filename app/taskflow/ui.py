"""Server-rendered board page.

Reads go through the same service layer as the JSON API and the move
buttons are generated from ALLOWED_TRANSITIONS, so the page can never
offer a move the API would reject. Writes are sent by the browser to the
public API itself (see static/board.js) — the UI owns no rules of its own.
"""

from __future__ import annotations

import os

from flask import Blueprint, render_template

from taskflow.models import ALLOWED_TRANSITIONS, TaskPriority, TaskStatus
from taskflow.services import boards, tasks

ui_bp = Blueprint("ui", __name__)

#: Display names only; the workflow itself lives in the model.
STATUS_LABELS: dict[TaskStatus, str] = {
    TaskStatus.TODO: "To do",
    TaskStatus.IN_PROGRESS: "In progress",
    TaskStatus.BLOCKED: "Blocked",
    TaskStatus.DONE: "Done",
}

# Frozensets iterate in arbitrary order; buttons need a stable one.
_ORDERED_TRANSITIONS: dict[TaskStatus, list[TaskStatus]] = {
    status: [t for t in TaskStatus if t in ALLOWED_TRANSITIONS[status]]
    for status in TaskStatus
}


@ui_bp.get("/")
def board():
    all_tasks = tasks.list_tasks()
    return render_template(
        "board.html",
        columns=[
            (status, [t for t in all_tasks if t.status is status])
            for status in TaskStatus
        ],
        transitions=_ORDERED_TRANSITIONS,
        labels=STATUS_LABELS,
        priorities=list(TaskPriority),
        boards=boards.list_boards(),
        # Same env vars the taskflow_build_info metric reports.
        build={
            "version": os.environ.get("APP_VERSION", "unknown"),
            "git_sha": os.environ.get("GIT_SHA", "unknown"),
        },
    )
