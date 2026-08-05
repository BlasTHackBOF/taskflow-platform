# TaskFlow Platform

Infrastructure and delivery pipeline for **TaskFlow**, a lightweight task management
tool for small teams.

The application is small on purpose. This repository is about everything that happens
after the code is written: how it is packaged, provisioned, configured, released, run
and observed.

**Live:** http://34.224.66.237/ — deployed by the pipeline, not by hand. The badge in
the header shows the git SHA of the running build.

---

## Status

| Phase | Tool | State |
|---|---|---|
| Application | Flask, PostgreSQL, pytest | ✅ |
| Container image | Docker | ✅ |
| Local stack | Docker Compose | ✅ |
| Cloud infrastructure | Terraform | ✅ |
| Operational tooling | Bash | ✅ |
| Server configuration | Ansible | ✅ |
| Orchestration | Kubernetes (k3s) | ✅ |
| Packaging | Helm | ✅ |
| CI/CD | Jenkins | ✅ |
| Observability | Prometheus, Grafana | ✅ |
| Interface | Server-rendered board | ✅ |

Evidence for each — pipeline runs, dashboards, running services — is in
[`docs/screenshots/`](docs/screenshots/).

---

## Architecture

```
        workstation (WSL2)
                │ git push
                ▼
          GitHub  ──webhook──┐
                             ▼
   ┌───────────────────────────────────────────┐
   │  AWS  ·  default VPC  ·  us-east-1        │
   │                                           │
   │   ┌──────────────┐    ┌────────────────┐  │
   │   │ EC2 t3.small │    │ EC2 t3.small   │  │
   │   │ taskflow-    │───▶│ taskflow-      │  │
   │   │  prod-ci-01  │6443│  prod-k3s-01   │  │
   │   │              │    │                │  │
   │   │  Jenkins     │    │  k3s           │  │
   │   └──────┬───────┘    │   ├ app pods   │  │
   │          │            │   ├ PostgreSQL │  │
   │          ▼            │   ├ Prometheus │  │
   │   ┌──────────────┐    │   └ Grafana    │  │
   │   │ S3           │    └────────────────┘  │
   │   │  tfstate     │             │          │
   │   │  artifacts   │             ▼ :80      │
   │   └──────────────┘         the internet   │
   └───────────────────────────────────────────┘
                │ push / pull images
                ▼
             GHCR
```

Every security group rule and its justification is in
[`docs/architecture.md`](docs/architecture.md).

### Which tool owns what

These tools overlap, and reaching for the wrong one is the mistake this kind of project
is designed to expose. The boundaries are deliberate.

| Tool | Owns | Deliberately does not |
|---|---|---|
| **Terraform** | Creating AWS resources: EC2, security groups, IAM, S3 | Install or configure anything *inside* a server |
| **Ansible** | Configuring servers that exist: packages, Docker, k3s, Jenkins | Create servers |
| **Docker** | Packaging the application into an image | Decide where that image runs |
| **Kubernetes** | Running, restarting and scaling containers | Know where the image came from |
| **Helm** | Deploying to the cluster with per-environment values | Build images |
| **Jenkins** | Running the pipeline in response to a repository event | Define infrastructure |
| **Prometheus / Grafana** | Observing what is running | Change it |

The seam that matters most: **Terraform stops at the server's door, Ansible starts
there.** Installing Docker through Terraform's `user_data` would blur exactly the
separation this project exists to demonstrate.

### From push to serving traffic

```
git push to main
   → GitHub webhook wakes Jenkins
   → ruff  →  pytest (70 tests)  →  docker build, tagged by git SHA
   → Trivy scan  →  push to GHCR
   → helm upgrade --set image.tag=<sha>
   → smoke test against /healthz
```

A failing test stops the deploy. Branch builds run everything up to the image scan;
only `main` reaches the cluster.

---

## Repository layout

```
taskflow-platform/
├── app/                  Application source, tests, migrations
├── docker/               Three Dockerfiles: app, CI agent, Jenkins
├── docker-compose.yml    Full local stack
├── infra/terraform/      AWS infrastructure as code
├── ansible/              Server configuration, four roles
├── kubernetes/
│   ├── manifests/        Raw manifests
│   └── helm/taskflow/    The chart that supersedes them
├── Jenkinsfile           The pipeline itself, in the repository
├── monitoring/           Prometheus values, alert rule, Grafana dashboard
├── scripts/              Operational Bash tooling
└── docs/                 Architecture, twelve ADRs, screenshots
```

The split is by *lifecycle*, not by technology. Terraform and Ansible are both
infrastructure but change at different rates and for different reasons, so they are
siblings rather than one folder.

**Three Dockerfiles, three jobs.** The application image carries no test tooling; the
CI agent carries no application code; the Jenkins image carries the CLIs the pipeline
drives. Each does one thing.

---

## The application

Boards hold tasks; tasks move through a fixed status workflow. That is all it does.

Its job is to give the infrastructure something real to run: a database dependency, a
health story, meaningful metrics, and a test suite that can fail a build.

| Endpoint | Purpose |
|---|---|
| `GET /` | Board UI |
| `GET /healthz` | Liveness — the process is running |
| `GET /readyz` | Readiness — the database is reachable |
| `GET /startupz` | Startup — slow first boot |
| `GET /metrics` | Prometheus exposition |
| `GET POST /api/v1/boards` | List and create boards |
| `GET /api/v1/boards/<id>` | A board with its tasks |
| `GET POST /api/v1/tasks` | List (filterable) and create tasks |
| `GET PATCH DELETE /api/v1/tasks/<id>` | Read, update, delete |

### Properties that exist for the infrastructure

- **Configuration comes only from the environment.** One image runs unchanged on a
  laptop, in Compose and in Kubernetes. An unrecognised `FLASK_ENV` resolves to
  production, and production refuses to boot on a default `SECRET_KEY` or a missing
  `DATABASE_URL` — a misconfigured deployment fails loudly rather than quietly serving
  traffic against a throwaway database.
- **Three health probes, because Kubernetes asks three different questions.**
  `/healthz` checks nothing external, so a database blip cannot cause a restart loop.
  `/readyz` checks the database, so a broken replica leaves the Service while staying
  alive for diagnosis. `/startupz` covers slow first boots without weakening the
  liveness threshold.
- **Metrics are labelled by Flask URL rule, never raw path.** Labelling by path would
  mint one time series per task id and eventually exhaust Prometheus. Point-in-time
  gauges refresh on scrape, so a fresh replica reports correct values before serving
  traffic.
- **Logs are single-line JSON on stdout,** carrying a request id adopted from an
  inbound `X-Request-ID` when present, so a trace survives a proxy hop.
- **Business rules live in a service layer** and are testable without HTTP — which is
  what makes the pipeline's test stage meaningful rather than decorative. The UI reads
  the same transition table, so it cannot offer a move the API would reject.

**70 tests, 90% coverage.** The suite runs against in-memory SQLite; the
PostgreSQL-specific behaviours it therefore cannot exercise are listed at the top of
`app/tests/conftest.py` rather than left to be discovered later.

---

## Running it locally

No AWS account needed.

```bash
cp .env.example .env
docker compose up --build
```

The board is then on `http://localhost:8000`. The stack starts PostgreSQL, runs
migrations in a one-shot init service, and starts the app only once both have
succeeded — the ordering is healthcheck-based, so it behaves the same on a fast laptop
and a loaded CI node. There is no `sleep` anywhere in this repository.

Full instructions, including the AWS path and the credentials you would need to
supply, are in [`docs/SETUP.md`](docs/SETUP.md).

---

## Secrets and configuration

**No real secret value exists anywhere in this repository.** Every secret-bearing file
has a committed `.example` twin carrying the same keys with placeholder values, so the
full configuration surface is visible without exposing anything.

| Layer | Secret | Where the real value lives |
|---|---|---|
| Local development | `SECRET_KEY`, database password | `.env` (gitignored) |
| Terraform | AWS credentials, SSH public key, operator IP | `terraform.tfvars` (gitignored); credentials in `~/.aws/credentials` |
| Ansible | database, Grafana and registry secrets | Ansible Vault, encrypted at rest |
| Jenkins | GHCR token, kubeconfig | Jenkins credential store |
| Kubernetes | application secrets, image pull | Kubernetes Secrets, created from the vault |

The SSH private key never enters the repository. Its public half is supplied to
Terraform as a variable and installed at instance creation.

Reasoning and rejected alternatives:
[ADR-0002](docs/decisions/0002-manage-secrets-with-ansible-vault.md).

---

## Access

The application is public on port 80. **Management interfaces — Jenkins, Grafana and
SSH — are restricted to the operator's address.** Opening them would mean an
unauthenticated admin console over plain HTTP on a public IP, which is precisely what
security groups exist to prevent. Screenshots in `docs/screenshots/` are the evidence
that they work.

Grafana has no Ingress at all; it is reached by `kubectl port-forward`. Zero public
attack surface, no additional security group rule.

---

## Cost

| | Running | Stopped |
|---|---|---|
| Full environment | ≈ $41/month | ≈ $3.20/month |

The line most people miss is public IPv4: since 2024 AWS charges $0.005/hour per
address, about a fifth of this stack's hourly cost. Stopping the instances stops that
charge too, because both addresses are auto-assigned rather than Elastic.

Line items in [`infra/terraform/README.md`](infra/terraform/README.md).

```bash
./scripts/env-control.sh start     # boot both nodes, print the new public IPs
./scripts/env-control.sh status    # state, type, IP and uptime
./scripts/env-control.sh stop      # shut down
```

---

## Engineering decisions

Twelve numbered, immutable ADRs. Each states the context, the choice, and the
consequences — including the ones we dislike.

| ADR | Decision |
|---|---|
| [0001](docs/decisions/0001-use-ubuntu-2404-lts.md) | Ubuntu 24.04 LTS on all servers |
| [0002](docs/decisions/0002-manage-secrets-with-ansible-vault.md) | Ansible Vault; only `.example` twins committed |
| [0003](docs/decisions/0003-resource-naming-convention.md) | One naming convention across every layer |
| [0004](docs/decisions/0004-use-ghcr-as-container-registry.md) | GHCR as the container registry |
| [0005](docs/decisions/0005-python-slim-multi-stage-image.md) | `python:slim` base, multi-stage build |
| [0006](docs/decisions/0006-s3-state-backend-with-native-locking.md) | S3 state backend with native locking, no DynamoDB |
| [0007](docs/decisions/0007-dynamic-inventory-and-role-split.md) | Ansible inventory resolved from Terraform and live AWS |
| [0008](docs/decisions/0008-swap-on-the-k3s-node.md) | Swap on the k3s node — why, measured cost, removal criteria |
| [0009](docs/decisions/0009-namespace-storage-and-migration-job.md) | Dedicated namespace, local-path storage, migrations as a Job |
| [0010](docs/decisions/0010-helm-chart-structure-and-hooks.md) | Single chart, external secrets, migration hook |
| [0011](docs/decisions/0011-jenkins-pipeline-and-credentials.md) | Declarative pipeline, credentials in the Jenkins store |
| [0012](docs/decisions/0012-monitoring-tuned-for-a-single-node-cluster.md) | Monitoring tuned for one small node — measured 780 → 270 MB |

An ADR that lists only advantages is not finished. Each names what its decision costs.

---

## Conventions

- **Naming** is `taskflow-<environment>-<component>[-<index>]` across AWS tags, Docker
  images, Kubernetes resources and Helm releases. Consistency is what makes a stray
  resource traceable back to this repository at 2 a.m.
- **Branching** is trunk-based with short-lived `<type>/<subject>` branches, merged
  into `main` through pull requests. `git log --first-parent main` reads as a project
  timeline, one entry per phase.
- **Commits** are imperative and say what changed *and why*.
- **Images are tagged by git SHA, never `latest`.** Rollback depends on it, and
  `helm history` names the build each revision actually deployed.

---

## Known simplifications

Recorded here rather than left to be discovered.

- **Public IPs are not stable.** EC2 assigns a new address on every start, so the URL
  above is valid while this environment stays up. Anything holding an address — the
  GitHub webhook, a kubeconfig, a browser tab — needs updating after a restart. Elastic
  IPs would fix it at roughly $3.65/month per address *even while stopped*, which is
  more than a stopped instance costs; for a single-operator project that shuts down
  between sessions, reprinting the address is cheaper. `env-control.sh start` prints
  the current ones for exactly this reason.
- **The Terraform IAM user holds `AdministratorAccess`.** A real deployment would scope
  it to the four services this project uses. The broad policy keeps the focus on the
  delivery pipeline rather than on IAM policy authoring.
- **Tests run against SQLite while deployment uses PostgreSQL.** Five behaviours pass
  locally without being exercised, including `SELECT ... FOR UPDATE` and foreign key
  enforcement. Listed in `app/tests/conftest.py`.
- **No custom VPC.** Resources sit in the default VPC. A private-subnet design needs a
  NAT gateway, which is outside this project's permitted service list and would
  dominate the budget.
- **Single node, single environment.** Everything is `prod`. The environment segment is
  kept in every resource name so adding a second would not require renaming anything.
- **Monitoring retention is 24 hours at a 60-second scrape,** and Prometheus storage is
  `emptyDir`. The dashboard answers "what is happening", not "what happened last week".
  Deliberate, and recorded in ADR-0012.

---

## Lessons learned

Nine real failures, their root causes, and what each changed — including two disk
exhaustions from different causes, a test that could not fail, and a key rotation that
rotated nothing: [`docs/lessons-learned.md`](docs/lessons-learned.md).
