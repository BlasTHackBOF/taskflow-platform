"""Prometheus metrics.

Requests are labelled by Flask URL rule, never raw path: a per-path label
would mint one time series per task id and eventually take Prometheus
down. Unmatched requests share the single label value ``<unmatched>`` for
the same reason.

The domain gauge is refreshed on scrape, not on write, so a freshly
started replica reports correct values before it has served a single
request. The scrape endpoint itself is excluded from the request metrics.

Each application instance owns its own CollectorRegistry — tests build
many apps per process, and the library's global registry would reject the
duplicate registrations.
"""

from __future__ import annotations

import os
import time

from flask import Flask, Response, g, request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from sqlalchemy import func, select

from taskflow.extensions import db
from taskflow.models import Task, TaskStatus

_METRICS_PATH = "/metrics"


class Metrics:
    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self.requests_total = Counter(
            "http_requests_total",
            "HTTP requests processed, labelled by URL rule.",
            ["method", "rule", "status"],
            registry=self.registry,
        )
        self.request_duration = Histogram(
            "http_request_duration_seconds",
            "HTTP request latency in seconds, labelled by URL rule.",
            ["method", "rule"],
            registry=self.registry,
        )
        self.in_flight = Gauge(
            "http_requests_in_flight",
            "HTTP requests currently being handled.",
            registry=self.registry,
        )
        self.tasks_by_status = Gauge(
            "taskflow_tasks",
            "Current number of tasks by status, refreshed on scrape.",
            ["status"],
            registry=self.registry,
        )
        build_info = Gauge(
            "taskflow_build_info",
            "Build metadata carried in labels; the value is always 1.",
            ["version", "git_sha"],
            registry=self.registry,
        )
        build_info.labels(
            version=os.environ.get("APP_VERSION", "unknown"),
            git_sha=os.environ.get("GIT_SHA", "unknown"),
        ).set(1)

    def refresh_task_gauge(self) -> None:
        counts = dict(
            db.session.execute(
                select(Task.status, func.count()).group_by(Task.status)
            ).all()
        )
        # Every status is set on every scrape, so absent statuses report an
        # explicit zero instead of a missing series.
        for status in TaskStatus:
            self.tasks_by_status.labels(status=status.value).set(
                counts.get(status, 0)
            )


def init_metrics(app: Flask) -> None:
    metrics = Metrics()
    app.extensions["metrics"] = metrics

    @app.before_request
    def _start_timer():
        if request.path == _METRICS_PATH:
            return
        g._metrics_start = time.perf_counter()
        g._metrics_in_flight = True
        metrics.in_flight.inc()

    @app.after_request
    def _record_request(response):
        start = g.pop("_metrics_start", None)
        if start is None:  # scrape requests carry no timer
            return response
        rule = request.url_rule.rule if request.url_rule else "<unmatched>"
        metrics.requests_total.labels(
            method=request.method, rule=rule, status=response.status_code
        ).inc()
        metrics.request_duration.labels(method=request.method, rule=rule).observe(
            time.perf_counter() - start
        )
        return response

    @app.teardown_request
    def _settle_in_flight(_exc):
        # after_request is skipped when an exception propagates (debug,
        # testing, PROPAGATE_EXCEPTIONS), which would leak a permanent +1
        # on the gauge; teardown runs on the success and failure path both.
        if g.pop("_metrics_in_flight", False):
            metrics.in_flight.dec()

    @app.get(_METRICS_PATH)
    def metrics_endpoint():
        metrics.refresh_task_gauge()
        return Response(
            generate_latest(metrics.registry), mimetype=CONTENT_TYPE_LATEST
        )
