"""Metrics behaviour: exposition format, rule labels, scrape-time gauge."""

from __future__ import annotations

import pytest

from taskflow.services import boards, tasks


def test_metrics_exposes_domain_gauge_with_no_prior_writes(client):
    """A fresh replica must report explicit zeros, not missing series."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.content_type.startswith("text/plain")
    body = response.get_data(as_text=True)
    for status in ("todo", "in_progress", "blocked", "done"):
        assert f'taskflow_tasks{{status="{status}"}} 0.0' in body


def test_domain_gauge_reflects_database_on_scrape(app, client):
    with app.app_context():
        board = boards.create_board({"key": "TF", "name": "X"})
        tasks.create_task({"board_id": board.id, "title": "A"})
        second = tasks.create_task({"board_id": board.id, "title": "B"})
        tasks.update_task(second.id, {"status": "in_progress"})
    body = client.get("/metrics").get_data(as_text=True)
    assert 'taskflow_tasks{status="todo"} 1.0' in body
    assert 'taskflow_tasks{status="in_progress"} 1.0' in body
    assert 'taskflow_tasks{status="done"} 0.0' in body


def test_requests_labelled_by_rule_never_raw_path(client):
    client.get("/healthz")
    client.get("/api/v1/boards/123")  # 404, but the rule still matched
    body = client.get("/metrics").get_data(as_text=True)
    assert 'rule="/healthz"' in body
    assert 'rule="/api/v1/boards/<int:board_id>"' in body
    assert 'rule="/api/v1/boards/123"' not in body


def test_metrics_endpoint_not_counted_in_request_metrics(client):
    client.get("/metrics")
    body = client.get("/metrics").get_data(as_text=True)
    assert 'rule="/metrics"' not in body


def test_in_flight_gauge_drains_after_unhandled_exception(app):
    """A crashing request must not leak a permanent +1 on the gauge.

    With exceptions propagating (as in testing/debug), Flask skips
    after_request entirely, so the decrement has to live in
    teardown_request — the only hook that runs on both paths.
    """

    @app.get("/boom")
    def boom():  # registered here on purpose; the app itself has no such route
        raise RuntimeError("deliberate crash")

    client = app.test_client()
    with pytest.raises(RuntimeError):
        client.get("/boom")

    body = client.get("/metrics").get_data(as_text=True)
    assert "http_requests_in_flight 0.0" in body


def test_build_info_and_core_series_present(client):
    client.get("/healthz")  # labelled series appear after a first observation
    body = client.get("/metrics").get_data(as_text=True)
    assert "taskflow_build_info{" in body
    assert "http_requests_in_flight" in body
    assert 'http_request_duration_seconds_bucket{le="0.05",method="GET",rule="/healthz"}' in body
