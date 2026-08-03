"""Structured logging: one JSON object per line, stdout only.

The process never writes log files — the container runtime owns log
collection, and a process managing its own files breaks that contract.

Every request is assigned a request ID, taken from an inbound
``X-Request-ID`` header when present so a trace survives a proxy hop, and
echoed back on the response. ``LOG_FORMAT=console`` switches to a
readable line format for local development; the default is JSON.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone

from flask import Flask, g, has_request_context, request

_METRICS_PATH = "/metrics"

# LogRecord attributes that are bookkeeping, not payload; anything else on
# the record (passed via ``extra=``) belongs in the output line.
_RESERVED_ATTRS = {
    "args", "asctime", "created", "exc_info", "exc_text", "filename",
    "funcName", "levelname", "levelno", "lineno", "message", "module",
    "msecs", "msg", "name", "pathname", "process", "processName",
    "relativeCreated", "stack_info", "taskName", "thread", "threadName",
}


def _record_extras(record: logging.LogRecord) -> dict:
    return {
        key: value
        for key, value in record.__dict__.items()
        if key not in _RESERVED_ATTRS
    }


def _request_fields() -> dict:
    if not has_request_context():
        return {}
    return {
        "request_id": g.get("request_id"),
        "method": request.method,
        "path": request.path,
    }


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        entry.update(_request_fields())
        entry.update(_record_extras(record))
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


class ConsoleFormatter(logging.Formatter):
    """Readable single-line format for local development."""

    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)-8s %(name)s: %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        fields = {**_request_fields(), **_record_extras(record)}
        if fields:
            rendered = " ".join(f"{key}={value}" for key, value in fields.items())
            line = f"{line} ({rendered})"
        return line


def init_logging(app: Flask) -> None:
    handler = logging.StreamHandler(sys.stdout)
    if app.config.get("LOG_FORMAT") == "console":
        handler.setFormatter(ConsoleFormatter())
    else:
        handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    # The dev server's own access lines would duplicate ours; the JSON
    # "request completed" line below is the access log.
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    @app.before_request
    def _assign_request_id():
        g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        g._log_start = time.perf_counter()

    @app.after_request
    def _echo_request_id_and_log(response):
        response.headers["X-Request-ID"] = g.get("request_id", "")
        if request.path != _METRICS_PATH:  # scrapes would drown the log
            started = g.get("_log_start")
            duration_ms = (
                round((time.perf_counter() - started) * 1000, 2)
                if started is not None
                else None
            )
            app.logger.info(
                "request completed",
                extra={"status": response.status_code, "duration_ms": duration_ms},
            )
        return response
