"""Gunicorn entrypoint: ``gunicorn wsgi:app``."""

from taskflow import create_app

app = create_app()
