"""Logging behaviour: request-ID propagation and the JSON line format."""

from __future__ import annotations

import io
import json
import logging

from taskflow.logs import JsonFormatter


def test_inbound_request_id_is_echoed(client):
    response = client.get("/healthz", headers={"X-Request-ID": "trace-me-123"})
    assert response.headers["X-Request-ID"] == "trace-me-123"


def test_request_id_generated_when_absent(client):
    response = client.get("/healthz")
    assert response.headers["X-Request-ID"] != ""


def test_access_log_line_is_json_with_request_id(client):
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        client.get("/healthz", headers={"X-Request-ID": "abc-1"})
    finally:
        root.removeHandler(handler)

    lines = [line for line in stream.getvalue().splitlines() if line.strip()]
    entry = json.loads(lines[-1])  # every line must be one JSON object
    assert entry["message"] == "request completed"
    assert entry["request_id"] == "abc-1"
    assert entry["path"] == "/healthz"
    assert entry["status"] == 200
    assert entry["duration_ms"] >= 0
