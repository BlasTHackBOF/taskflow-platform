# TaskFlow application image. One image for Compose, Kubernetes and
# production — only environment variables differ between them.
# Build from the repository root:  docker build -f docker/Dockerfile .

# --- builder: dependencies compile here, nothing from this stage ships
#     except the finished virtualenv ---------------------------------------
FROM python:3.12.12-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

COPY app/requirements.txt /tmp/requirements.txt
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install -r /tmp/requirements.txt

# --- runtime --------------------------------------------------------------
FROM python:3.12.12-slim-bookworm

# Build metadata surfaces in the taskflow_build_info metric.
ARG APP_VERSION=dev
ARG GIT_SHA=unknown
ENV APP_VERSION=${APP_VERSION} \
    GIT_SHA=${GIT_SHA} \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Explicit non-root user with a fixed UID, so Kubernetes securityContext
# rules (runAsUser/runAsNonRoot) can reference a known number.
RUN groupadd --system --gid 10001 taskflow \
    && useradd --system --uid 10001 --gid taskflow --no-create-home taskflow

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY app/taskflow ./taskflow
COPY app/migrations ./migrations
COPY app/wsgi.py app/gunicorn.conf.py ./

USER taskflow
EXPOSE 8000

# python already ships in the image, so the probe needs no curl/wget.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status == 200 else 1)"]

# Exec form: gunicorn runs as PID 1 and receives SIGTERM directly, so
# `docker stop` shuts it down gracefully instead of waiting out the timeout.
# Worker count and bind address live in gunicorn.conf.py.
CMD ["gunicorn", "wsgi:app"]
