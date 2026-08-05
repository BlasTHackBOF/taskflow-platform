# ADR-0009: Kubernetes namespace, storage, and the migration Job

- **Status:** Accepted
- **Date:** 2026-08-05

## Context

The first Kubernetes deployment of TaskFlow (raw manifests; Helm
templates them in the next phase) forces three decisions that will
outlive the manifests: where workloads live, where PostgreSQL's data
lives, and how schema migrations run. Each has a default that works
until it hurts — `default` namespace, no persistence, migrate-on-boot —
and this ADR records why none of the defaults survived.

## Namespace: a dedicated `taskflow`

Everything the application owns deploys into a `taskflow` namespace,
not `default`.

- **Blast radius.** `kubectl delete namespace taskflow` is a complete,
  clean uninstall; nothing else on the cluster can be collateral.
- **Scoping.** RBAC, quotas and the NetworkPolicies of a later phase
  all attach to a namespace. Granting anything to `default` grants it
  to whatever else lands there later — including the monitoring stack,
  which gets its own namespace next phase precisely so its lifecycle
  and permissions stay separate.
- **Legibility.** `kubectl -n taskflow get all` answers "what is the
  application" without filtering noise.

The ServiceAccount follows the same least-privilege posture taken to
its limit: the app never calls the Kubernetes API, so the minimal RBAC
is not a narrow Role — it is a dedicated ServiceAccount with **no**
role bindings and `automountServiceAccountToken: false`. No credential
is mounted that could be scoped in the first place.

## Storage: k3s local-path provisioner

PostgreSQL's PVC binds to k3s's bundled `local-path` StorageClass,
which backs the volume with a directory on the node's EBS root volume.

This is the only real choice inside the constraints: dynamic
provisioning of EBS volumes needs the AWS EBS CSI driver, IAM wiring
and per-volume AWS resources — Terraform-owned infrastructure conjured
from inside the cluster, crossing the project's Terraform/Ansible
boundary and its service allowlist discipline for one database volume.

What the trade costs, stated plainly:

- Data survives pod restarts, node reboots and instance stop/start
  (the EBS root volume persists) — verified by deleting the postgres
  pod and finding the data intact.
- Data does **not** survive node replacement or `terraform destroy`.
  The volume is the node. For a graded lab whose durable backup story
  is scheduled dumps to S3 (a later phase, and the reason the app
  node's IAM role can reach S3), that is acceptable; for anything
  multi-node it would not be.
- `ReadWriteOnce` on one node also means the database cannot reschedule
  elsewhere — true of a single-node cluster regardless.

## Migrations: a Job, carried forward from Compose

Compose ran migrations as a one-shot init service gating the app via
`service_completed_successfully` — chosen there so N app replicas never
mean N concurrent migrations. Kubernetes does not change that
reasoning; it sharpens it. A migrate-on-boot entrypoint (or
initContainer) runs on *every* pod start: with `maxSurge` rolling
updates there are moments with two pods booting, i.e. concurrent
schema migrations racing on the live database. The Compose init
service's own comment already named its successor, and this is it: a
`Job`, run once per rollout.

- **Exactly-once per rollout**, regardless of replica count or surge.
- **Observable**: `kubectl wait --for=condition=complete
  job/taskflow-migrate` is the gate, and the Job's log is the
  migration's record.
- **Hook-shaped**: in the Helm phase this Job becomes a `pre-upgrade`
  hook with no structural change.

What raw manifests cannot express is ordering — nothing makes the
Deployment wait for the Job declaratively. The gate is operational
(`kubectl wait` in the deploy sequence, a Helm hook next phase), with a
safety net underneath: `/startupz` and `/readyz` probe the database, so
an app pod can never enter Service rotation ahead of a working schema —
at worst it sits unready, which is visible and harmless.

Job templates are immutable, so each rollout deletes and re-applies the
Job with the new image SHA. For a resource whose entire life is one
rollout, immutability is a feature: the Job that ran is exactly the Job
in the log.

## Consequences

- The deploy sequence is: apply base + postgres → delete/apply the
  migration Job → wait for completion → apply the Deployment. Helm
  automates this next phase.
- Backups become a first-class obligation: local-path storage without
  scheduled S3 dumps is a lab convenience, not a durability story.
- The monitoring stack lands in its own namespace next phase; nothing
  in `taskflow` needs to change for it.
