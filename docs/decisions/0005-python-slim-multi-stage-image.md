# ADR-0005: Build on python:slim with a multi-stage Dockerfile

- **Status:** Accepted
- **Date:** 2026-08-03

## Context

The application ships as one container image that runs identically in
Docker Compose, in Kubernetes and in production — only environment
variables differ. The image needs the CPython runtime, the pinned
dependencies (including `psycopg2-binary`, which is distributed as a
glibc-linked manylinux wheel), gunicorn, and the application code.
Nothing else: every extra binary in the image is patch surface and pull
time.

Two decisions follow: which base image family, and whether to build in
stages.

## Decision

**Base: `python:3.12.12-slim-bookworm`, pinned to the exact patch
version.** A tag like `latest` or even `3.12-slim` moves underneath the
build; pinning the full version means the same Dockerfile produces the
same runtime until the pin is changed deliberately.

The three candidates and what each costs:

| Base | Size ballpark | Cost |
| --- | --- | --- |
| `python:3.12` (full) | ~1 GB | Ships compilers, headers and a large Debian userland the runtime never uses — slow pulls and needless patch surface. |
| `python:3.12-alpine` | ~50 MB base | musl libc: manylinux wheels do not apply, so `psycopg2-binary` (and any future compiled dependency) must be built from source against musl, adding build-time toolchains and a class of musl-vs-glibc runtime differences that are miserable to debug. Smallest image, highest operational risk. |
| `python:3.12-slim` | ~120 MB base | glibc Debian, so every manylinux wheel installs as-is; no toolchain included. Costs a few tens of MB over alpine and lacks build tools — which is exactly what the builder stage is for. |

Slim wins: the alpine savings are real but small at this scale, and they
are paid for in wheel incompatibility. The full image solves a problem
(missing compilers) that multi-stage solves more cheaply.

**Multi-stage build.** Dependencies install into a virtualenv in a
builder stage; the runtime stage copies the finished `/opt/venv` and the
application code only. pip caches, temporary build artifacts and any
compiler ever needed by a future source-only dependency stay in the
discarded builder layer. The runtime stage also:

- creates an explicit non-root user (`taskflow`, UID 10001) instead of
  trusting a base-image default, so Kubernetes `runAsUser` rules can
  reference a fixed number;
- runs gunicorn in exec form as PID 1, so SIGTERM reaches it directly
  and `docker stop` completes in about a second instead of waiting out
  the kill timeout;
- carries a `HEALTHCHECK` that probes `/healthz` with the Python already
  in the image — no curl or wget added just for the probe.

## Consequences

- The same image is promoted through every environment; configuration
  drift between Compose, Kubernetes and production is limited to
  environment variables by construction.
- Patch updates are explicit: bumping the base means editing the pinned
  tag, and the change is visible in review and in `taskflow_build_info`.
- A future dependency without a prebuilt wheel compiles in the builder
  stage without touching the runtime image.
- Debugging inside the container is barer than on the full image — no
  compilers, no extra tools. The trade is accepted; debugging happens
  against logs, metrics and probes, not by shelling into production.

## Alternatives considered

- **`python:3.12-alpine`** — rejected for musl wheel incompatibility, as
  above; the size advantage does not pay for rebuilding psycopg2 from
  source and carrying the musl behavioural risk.
- **Full `python:3.12`** — rejected: everything it adds over slim exists
  to build software, and building belongs in the builder stage.
- **Distroless (`gcr.io/distroless/python3`)** — attractive hardening,
  but its Python tracks the distro rather than a pinned upstream
  version, there is no shell for the HEALTHCHECK exec probe pattern
  used elsewhere in this stack, and it comes from a registry outside
  the project's decided set (ADR-0004). Worth revisiting if the
  security requirements tighten.
- **Single-stage slim with build tools installed and removed in one
  layer** — the `apt-get install && pip install && apt-get purge` dance.
  Rejected: it recreates multi-stage by hand, is easy to get subtly
  wrong (a forgotten purge silently bloats the layer), and reviews
  worse.
