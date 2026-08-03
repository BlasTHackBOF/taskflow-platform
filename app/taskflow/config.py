"""Environment-driven configuration.

Settings are read from environment variables at instantiation time (not at
import time) so tests and deployment tooling can set the environment first
and then build the app. Unknown ``FLASK_ENV`` values resolve to production:
a typo in deployment must fail safe, never silently enable debug behaviour.
"""

from __future__ import annotations

import os

# Sentinel default: fine for local development, refused outright in production.
_DEFAULT_SECRET_KEY = "dev-only-not-a-secret"


class BaseConfig:
    """Settings shared by every environment."""

    DEBUG: bool = False
    TESTING: bool = False
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    def __init__(self) -> None:
        self.SECRET_KEY: str = os.environ.get("SECRET_KEY", _DEFAULT_SECRET_KEY)
        # "json" for production and containers; "console" for local reading.
        self.LOG_FORMAT: str = os.environ.get("LOG_FORMAT", "json")
        # Relative SQLite paths are resolved by Flask-SQLAlchemy into the
        # app instance folder, keeping the working tree free of DB files.
        self.SQLALCHEMY_DATABASE_URI: str = os.environ.get(
            "DATABASE_URL", "sqlite:///taskflow.db"
        )


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestingConfig(BaseConfig):
    TESTING = True

    def __init__(self) -> None:
        super().__init__()
        self.SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class ProductionConfig(BaseConfig):
    def __init__(self) -> None:
        super().__init__()
        if self.SECRET_KEY == _DEFAULT_SECRET_KEY:
            raise RuntimeError(
                "SECRET_KEY is unset or left at its development default; "
                "production refuses to start with a predictable secret."
            )
        if "DATABASE_URL" not in os.environ:
            raise RuntimeError(
                "DATABASE_URL is unset; production refuses to fall back to "
                "a local SQLite file that would silently swallow data. Set "
                "DATABASE_URL to the PostgreSQL connection string."
            )


_CONFIGS: dict[str, type[BaseConfig]] = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(env: str | None = None) -> BaseConfig:
    """Resolve the configuration for ``env`` (default: ``$FLASK_ENV``).

    Anything that is not an exact known name — including a missing variable —
    maps to :class:`ProductionConfig`.
    """
    name = env if env is not None else os.environ.get("FLASK_ENV", "production")
    config_cls = _CONFIGS.get(name.strip().lower(), ProductionConfig)
    return config_cls()
