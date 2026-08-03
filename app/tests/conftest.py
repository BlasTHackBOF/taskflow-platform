"""Shared fixtures: every test gets its own application and database.

Each test builds a fresh application, and a fresh app means a fresh
in-memory SQLite engine — no state survives from one test to the next.

The ``app`` fixture deliberately does NOT hold an application context open:
if it did, test-client requests would reuse it instead of pushing their own,
and the per-request teardown (which rolls back a failed request's session,
exactly as in production) would never run. Tests that call services
directly, outside any request, opt into a context via ``app_context``.

KNOWN GAP — this suite runs on SQLite while production runs on PostgreSQL,
and some behaviour is PostgreSQL-only. It passes here without ever being
exercised; Jenkins runs the same suite against real PostgreSQL in a later
phase to close this:

- ``SELECT ... FOR UPDATE`` is silently dropped by the SQLite dialect, so
  the row lock serialising task-reference allocation is never tested —
  ``test_references_allocated_in_order`` proves the counter increments,
  not that concurrent creates queue on the lock.
- ``DateTime(timezone=True)`` is a no-op in SQLite: timestamps come back
  naive, so timezone-aware storage is untested.
- Foreign keys (including ``ON DELETE CASCADE`` on tasks.board_id) are not
  enforced unless ``PRAGMA foreign_keys=ON`` is issued, which we don't do;
  only the ORM-level cascade is exercised.
- ``VARCHAR(n)`` lengths are not enforced by SQLite; the service-layer
  max-length checks are tested, the database backstop is not.
- The schema comes from ``db.create_all()``, not the Alembic migration, so
  drift between the models and the migration would not be caught here.
"""

from __future__ import annotations

import pytest

from taskflow import create_app
from taskflow.config import TestingConfig
from taskflow.extensions import db


@pytest.fixture()
def app():
    application = create_app(TestingConfig())
    with application.app_context():
        db.create_all()
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def app_context(app):
    """For tests that exercise the services directly, with no request."""
    with app.app_context():
        yield


class _BrokenDatabaseConfig(TestingConfig):
    """Points at a database that cannot be opened, for probe failure tests."""

    def __init__(self) -> None:
        super().__init__()
        self.SQLALCHEMY_DATABASE_URI = "sqlite:////nonexistent-dir/broken.db"


@pytest.fixture()
def broken_db_client():
    return create_app(_BrokenDatabaseConfig()).test_client()
