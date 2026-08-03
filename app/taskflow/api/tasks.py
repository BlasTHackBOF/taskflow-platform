"""Task endpoints: parse input, call services, format output."""

from __future__ import annotations

from flask import Blueprint, request

from taskflow.api.request_body import json_object
from taskflow.api.serializers import task_to_dict
from taskflow.services import tasks

tasks_bp = Blueprint("tasks", __name__)


@tasks_bp.get("/tasks")
def list_tasks():
    found = tasks.list_tasks(
        board_id=request.args.get("board_id"),
        status=request.args.get("status"),
        assignee=request.args.get("assignee"),
    )
    return {"tasks": [task_to_dict(t) for t in found]}


@tasks_bp.post("/tasks")
def create_task():
    return task_to_dict(tasks.create_task(json_object())), 201


@tasks_bp.get("/tasks/<int:task_id>")
def get_task(task_id: int):
    return task_to_dict(tasks.get_task(task_id))


@tasks_bp.patch("/tasks/<int:task_id>")
def update_task(task_id: int):
    return task_to_dict(tasks.update_task(task_id, json_object()))


@tasks_bp.delete("/tasks/<int:task_id>")
def delete_task(task_id: int):
    tasks.delete_task(task_id)
    return "", 204
