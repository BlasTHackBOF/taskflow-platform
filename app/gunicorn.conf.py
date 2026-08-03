"""Gunicorn configuration, read from the environment.

gunicorn loads this file automatically from the working directory. Keeping
the tuning here (rather than CLI flags in the Dockerfile CMD) lets the
container run gunicorn as PID 1 in exec form while still taking the worker
count from an environment variable.
"""

import os

bind = "0.0.0.0:8000"
workers = int(os.environ.get("GUNICORN_WORKERS", "2"))

# Process-level logs go to stderr; the application writes its own JSON
# access line per request to stdout, so gunicorn's access log stays off.
errorlog = "-"
accesslog = None

# Give in-flight requests a bounded window on SIGTERM, then exit.
graceful_timeout = 20
