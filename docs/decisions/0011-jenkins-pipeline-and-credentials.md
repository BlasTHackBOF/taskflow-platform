# ADR-0011: Pipeline structure and credential handling

- **Status:** Accepted
- **Date:** 2026-08-05

## Context

Every deploy before this phase was manual. The pipeline closes the
loop: a push to `main` ends with the new build serving traffic, and a
push anywhere else proves the code without touching production. The
constraints shaping it: Jenkins runs in a container on a 2 GiB
t3.small; the cluster's public address changes on every stop/start;
and this project's standing rule that no secret enters git.

## The pipeline lives in the repository

A declarative `Jenkinsfile` at the repo root, and a Multibranch
Pipeline job that does nothing but point at the repository. Nothing
about the pipeline exists only in the Jenkins UI — a pipeline defined
in the UI is configuration that dies with the instance and reviews
with nobody. The job is Multibranch because the branch/main split *is*
the pipeline's structure:

| Trigger | Stages |
| --- | --- |
| Any branch push / PR | checkout → lint (ruff) → test (pytest, JUnit + coverage archived) → build image → scan (Trivy) |
| Push to `main` | all of the above → push to GHCR → `helm upgrade` → smoke test |

One git SHA flows through the whole run: it tags the image, feeds
`--set image.tag=`, and the smoke test asserts the Deployment is
actually running that exact reference. A failing stage stops the run —
a red test can never reach the deploy stage by construction.

## Where the tools run

Two different answers for two different stage types:

- **Quality stages** (lint, test) run in a disposable
  `python:3.12.12-slim-bookworm` container — the same pinned base the
  production image uses, via the Docker Pipeline plugin against the
  host's daemon through the mounted socket.
- **Shipping stages** (build, scan, push, deploy, smoke) use tools
  baked into the controller image itself: docker CLI, helm, kubectl,
  trivy, each version-pinned in `docker/jenkins/Dockerfile` and built
  on the CI node by the Ansible jenkins role. Baked-in rather than
  tool-containers because Jenkins itself is a container: its workspace
  lives in a named volume, so a nested `docker run -v $WORKSPACE`
  mounts a path that does not exist on the host. Binaries in the
  controller image sidestep the problem instead of working around it.

The Trivy gate fails the build on CRITICAL vulnerabilities that have a
fix available (`--ignore-unfixed`): gate on what is actionable, report
the rest. The gate earned its keep before its first CI run — it caught
four fixable CRITICALs in the base image's Debian packages, which is
why the production Dockerfile now applies security updates instead of
trusting upstream's rebuild cadence.

## Credentials

Two credentials, both in the Jenkins credential store, encrypted at
rest in `jenkins_home` and injected per-stage via `withCredentials` —
never named in the Jenkinsfile as values, never in git in any form:

- **`ghcr-push`** — username + `write:packages` PAT. The write half of
  the token pair ADR-0004 designed; the cluster keeps its separate
  read-only token.
- **`k3s-kubeconfig`** — a kubeconfig whose server address is the app
  node's **private** IP. The private address survives stop/start (the
  public one does not), traffic stays inside the VPC, and the
  CI→k3s-API path is already granted group-to-group in the security
  groups — a rule that holds precisely because it names no address.

The Ansible vault remains the operator's store of record (ADR-0002);
the Jenkins store holds CI's working copies, the same two-store split
ADR-0004 already prescribed for the registry tokens.

## Hygiene on a 2 GiB node

`timeout(30)` bounds every run; `disableConcurrentBuilds` keeps one
build's containers from starving another; the `post` block always
logs out of the registry, prunes dangling build layers, and deletes
the workspace. A hung or hoarding build is a node outage here, not an
inconvenience.

## Known limitation

The GitHub webhook targets the CI node's public IP, which changes on
every stop/start — after restarting the environment the webhook URL
must be updated in the repository settings. Accepted: the alternative
(a stable address) costs an Elastic IP billed while stopped, rejected
in the cost design. The failure mode is loud — pushes stop triggering
builds — and the fix is one field in one settings page.

## Alternatives considered

- **Pipeline defined in the Jenkins UI** — rejected as unreviewable,
  unversioned, and unrecoverable; the "works on my Jenkins" failure.
- **Freestyle/scripted jobs per stage** — rejected: stage graph,
  retries and gating logic belong in one reviewed file.
- **SSH from Jenkins to the k3s node to run helm** — rejected: it
  would put a shell credential where a scoped API credential
  suffices, and the kubeconfig path already crosses no public network.
- **Polling instead of webhook** — rejected: minutes of latency and
  constant API traffic to avoid a one-field fix after restarts.
