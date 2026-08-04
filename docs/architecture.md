# Architecture

TaskFlow is a small task-board service. This document describes the platform
that builds, deploys and operates it — which is where essentially all of the
engineering in this repository lives.

> **Status.** Sections describing the local stack reflect what is built.
> Sections describing AWS, CI/CD and monitoring describe the target design and
> are marked accordingly. This document is updated as each phase lands.

## Overview

```
                     ┌──────────────────────────────────────────────┐
                     │        AWS eu-central-1  ·  VPC              │
                     │                                              │
  ┌──────────┐       │  ┌────────────────┐    ┌──────────────────┐  │
  │  GitHub  │──────►│  │  CI node       │───►│  Application     │  │
  │  (repo)  │webhook│  │  t3.small      │    │  node            │  │
  └──────────┘       │  │                │    │  t3.medium       │  │
       ▲             │  │  Jenkins       │    │                  │  │
       │             │  │  build, test,  │    │  k3s             │  │
       │             │  │  scan, push    │    │  TaskFlow pods   │  │
   git push          │  └────────────────┘    │  PostgreSQL      │  │
       │             │          │             │  Prometheus      │  │
  ┌──────────┐       │          │helm upgrade │  Grafana         │  │
  │ operator │       │          └────────────►│                  │  │
  │  (WSL2)  │       │                        └──────────────────┘  │
  └──────────┘       │                                  │           │
       │             └──────────────────────────────────┼───────────┘
       │                                                │
       │             ┌──────────────────────────────────▼───────────┐
       └────────────►│  S3   tfstate · artifacts · database backups │
         terraform   └──────────────────────────────────────────────┘

  ┌──────────────┐
  │  GHCR        │◄── images pushed by Jenkins, pulled by k3s
  │  registry    │
  └──────────────┘
```

## Components

### Application

A Flask application built around the factory pattern, deliberately small. Its
job is to give the platform something realistic to run, so the parts that
matter operationally — health probes, metrics, structured logs, database
migrations — get more attention than product features.

Configuration is resolved from environment variables at instantiation time
rather than import time, so tests and deployment tooling can set the
environment first. An unrecognised `FLASK_ENV` resolves to production
settings: a typo in a deployment must fail safe rather than silently enable
debug behaviour. Production additionally refuses to start if `SECRET_KEY` is
left at its development default.

### Health probes

Three endpoints, each answering a different question, because Kubernetes acts
differently on each answer.

| Endpoint | Question | Failure consequence |
| --- | --- | --- |
| `/healthz` | Is the process wedged? | Container is restarted |
| `/readyz` | Can it serve traffic now? | Pod is removed from the Service |
| `/metrics` | — | Scraped by Prometheus |

The separation is load-bearing. `/healthz` deliberately touches nothing
external: if it checked the database, a brief database outage would fail
liveness on every pod at once, restart them all, and turn a one-minute
dependency blip into a cluster-wide `CrashLoopBackOff`. `/readyz` does check
the database, so during an outage pods stay alive and simply stop receiving
traffic — and recover the instant the dependency returns.

### Container image *(planned)*

A multi-stage Dockerfile: dependencies are resolved in a build stage and the
runtime stage carries only the application and its installed packages. The
container runs as a non-root user and serves through gunicorn. Logs go to
stdout as structured JSON and are never written to a file inside the
container, so the orchestrator owns log collection.

### Local stack *(planned)*

Docker Compose brings up the application together with PostgreSQL as a single
command, so a new engineer can clone the repository and have a working stack
without reading a setup guide.

### Infrastructure *(planned)*

Two EC2 instances in a purpose-built VPC. Terraform is the only mechanism that
defines infrastructure; the AWS console is used for inspection and debugging,
never for definition. State lives in S3 with native S3 locking rather than a
DynamoDB lock table.

Instances are sized against a fixed credit budget and are stopped between
working sessions by a script in `scripts/`, rather than left running.

### Configuration management *(planned)*

Ansible turns a bare Ubuntu instance into a working node: users and SSH
hardening, package installation, k3s, and the monitoring agents. Roles are
separated by concern and all tasks are idempotent — a second run changes
nothing.

### CI/CD *(planned)*

Jenkins responds differently depending on where a change lands:

| Trigger | Pipeline behaviour |
| --- | --- |
| Push to a feature branch or open PR | lint, secret scan, tests, image build |
| Merge to `main` | the above, plus push to GHCR, `helm upgrade`, smoke test |

A branch that fails any stage cannot be merged, because `main` requires the
check to pass.

### Monitoring *(planned)*

Prometheus scrapes the application's `/metrics` endpoint alongside node and
cluster metrics. Grafana presents a dashboard covering request rate, error
rate and latency for the application, and CPU, memory and pod restarts for the
platform beneath it.

## Request path

1. A request reaches the application node's public IP on port 80.
2. Traefik, bundled with k3s, terminates it and routes by Ingress rule.
3. The Service load-balances across the ready TaskFlow pods — pods failing
   readiness are excluded automatically.
4. The application queries PostgreSQL over the cluster network.

## Security posture

- SSH is reachable only from the operator's IP address, never `0.0.0.0/0`.
- The Jenkins UI is likewise restricted by source address; only GitHub's
  published webhook ranges are permitted to reach the webhook endpoint.
- EC2 instances receive AWS permissions through an IAM instance profile scoped
  to the project's own S3 buckets. No static access keys are placed on any
  server.
- Real secrets never enter the repository; every secret file has a committed
  `.example` twin, and Ansible-layer secrets are encrypted at rest with
  Ansible Vault. See
  [ADR-0002](decisions/0002-manage-secrets-with-ansible-vault.md).

## Decisions

Decisions with lasting consequences are recorded individually in
[`decisions/`](decisions/). Smaller choices are explained inline above.

| ADR | Decision |
| --- | --- |
| [0001](decisions/0001-use-ubuntu-2404-lts.md) | Ubuntu 24.04 LTS on all servers |
| [0002](decisions/0002-manage-secrets-with-ansible-vault.md) | Ansible Vault; only `.example` twins committed |
| [0003](decisions/0003-resource-naming-convention.md) | Single naming convention across layers |
| [0004](decisions/0004-use-ghcr-as-container-registry.md) | GHCR as the container registry |
| [0005](decisions/0005-python-slim-multi-stage-image.md) | python:slim base, multi-stage build |
| [0006](decisions/0006-s3-state-backend-with-native-locking.md) | Terraform state in S3 with native lockfile locking, no DynamoDB |
