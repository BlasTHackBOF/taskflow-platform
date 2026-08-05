"""Board UI: the page offers exactly the moves ALLOWED_TRANSITIONS permits.

One test on purpose — the page's only rule is that its buttons mirror the
model's transition table, so that is the thing pinned here. Layout and
styling are not asserted.
"""

from __future__ import annotations

import re

from taskflow.models import ALLOWED_TRANSITIONS, TaskStatus

_CARD_RE = re.compile(r'<li class="card">(.*?)</li>', re.S)


def test_move_buttons_match_allowed_transitions(client):
    client.post("/api/v1/boards", json={"key": "TF", "name": "TaskFlow"})

    # Walk one task into each status via legal API moves.
    paths = {
        1: [],
        2: ["in_progress"],
        3: ["blocked"],
        4: ["in_progress", "done"],
    }
    expected: dict[int, TaskStatus] = {}
    for task_id, moves in paths.items():
        client.post("/api/v1/tasks", json={"board_id": 1, "title": f"Task {task_id}"})
        for status in moves:
            assert (
                client.patch(f"/api/v1/tasks/{task_id}", json={"status": status})
                .status_code
                == 200
            )
        expected[task_id] = TaskStatus(moves[-1]) if moves else TaskStatus.TODO
    assert set(expected.values()) == set(TaskStatus)

    page = client.get("/").data.decode()
    cards = _CARD_RE.findall(page)
    assert len(cards) == len(paths)
    for card in cards:
        task_id = int(re.search(r'data-task-id="(\d+)"', card).group(1))
        offered = {TaskStatus(v) for v in re.findall(r'data-status="([^"]+)"', card)}
        assert offered == ALLOWED_TRANSITIONS[expected[task_id]]
