"""Configuration fail-safe rules.

Production must fail loudly at boot on missing configuration; a
misconfigured deployment that starts anyway and writes to a throwaway
database looks healthy until someone notices the data is gone.
"""

from __future__ import annotations

import pytest

from taskflow.config import (
    DevelopmentConfig,
    ProductionConfig,
    get_config,
)

# TestingConfig is aliased so pytest does not try to collect it as a
# test class (its name matches the Test* pattern).
from taskflow.config import TestingConfig as _TestingConfig


def test_production_refuses_missing_database_url(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "a-real-secret")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL is unset"):
        ProductionConfig()


def test_production_refuses_default_secret_key(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://u:p@db/taskflow")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        ProductionConfig()


def test_production_boots_with_explicit_settings(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "a-real-secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://u:p@db/taskflow")
    config = ProductionConfig()
    assert config.SQLALCHEMY_DATABASE_URI.startswith("postgresql+psycopg2://")


def test_development_and_testing_keep_sqlite_defaults(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert DevelopmentConfig().SQLALCHEMY_DATABASE_URI.startswith("sqlite:")
    assert _TestingConfig().SQLALCHEMY_DATABASE_URI == "sqlite:///:memory:"


def test_unknown_flask_env_resolves_to_production(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "a-real-secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://u:p@db/taskflow")
    assert isinstance(get_config("staging-typo"), ProductionConfig)
