# ADR-0010: Helm chart structure and the migration hook

- **Status:** Accepted
- **Date:** 2026-08-05

## Context

The raw manifests of ADR-0009 deploy exactly one configuration. Helm
turns them into a parameterised release: one chart, per-environment
values, an upgrade history, one-command rollback. The packaging forces
decisions worth recording: what one chart contains, where secrets do
not go, how the migration Job becomes a hook, and what the two version
fields mean.

## One chart, no subcharts

The chart contains the application, PostgreSQL and the migration Job
together. The alternative — depending on a community PostgreSQL chart
(e.g. Bitnami's) — was rejected: it imports a values surface an order
of magnitude larger than this project's entire chart, its release
cadence and image choices become upgrade events here, and it replaces
a StatefulSet the project already understands line-by-line with one it
does not. A dependency earns its keep when the wrapped thing is hard;
a single-instance PostgreSQL on local-path is not hard.

Names and labels flow from `_helpers.tpl` (`fullname`, shared label
blocks, the postgres suffix, the image reference). A rename means
changing a helper, not nine files. The `DATABASE_URL` is composed in
the pod spec from `$(POSTGRES_USER)`/`$(POSTGRES_PASSWORD)`/host parts
for the same reason: the vault-created Secret holds only secrets, while
topology (the postgres service name) stays in the chart, so helpers can
rename services without stranding a URL frozen inside a Secret.

## Secrets never pass through Helm

The chart references `taskflow-secrets` and `ghcr-pull` by name and
will never create them. Two mechanical reasons beyond ADR-0002:
values files live in git in plaintext, and Helm stores rendered release
manifests in-cluster where anyone with read access on release storage
can recover them. The Ansible vault remains the store of record;
NOTES.txt prints the exact creation commands so nobody assumes
`helm install` is sufficient — the failure modes of a missing Secret
(`CreateContainerConfigError`, `ImagePullBackOff`) are named there too.

## The migration Job: post-install + pre-upgrade, not pre-install

The manifest comment promised "a pre-upgrade hook"; the requirement
asked for pre-upgrade/pre-install. The install half changed shape for
a mechanical reason: **pre-install hooks run before any release
resource exists.** On a fresh install a pre-install migration would
wait on a PostgreSQL the release had not yet created — a deadlock, not
an ordering. So:

- **post-install** covers the first deploy: resources exist, the
  hook's init container waits for PostgreSQL to answer, migrations
  apply. Nothing serves traffic prematurely regardless — readiness
  (`/readyz`) already gates on the database.
- **pre-upgrade** covers every deploy after: schema migrates before
  the new pods roll, which is the ordering that actually protects a
  running system.

`before-hook-creation` deletion policy keeps the completed Job (and
its log — the migration's record) until the next rollout replaces it.
Job immutability stops being an operational concern: Helm deletes and
recreates the hook each time, which is what the raw-manifest runbook
did by hand.

## Chart version vs appVersion

`version` (chart) and `appVersion` move independently because they
answer different questions: *how the app is deployed* vs *which build
is deployed*. A probe threshold fix bumps the chart with the app
unchanged; a routine deploy ships a new git SHA through `image.tag`
with the chart untouched. Collapsing them would make every deploy a
chart release and every packaging fix look like an app change —
and on rollback you need to know which of the two you are reverting.
`appVersion` doubles as the default image tag, so the chart is
installable as-committed while production pins its exact SHA in
`values-prod.yaml`.

One refinement learned in production: the pipeline stamps `appVersion`
with the deployed SHA in its disposable checkout before `helm upgrade`,
because the APP VERSION column of `helm history` reads from chart
metadata — without the stamp, every revision reports the last
*committed* appVersion rather than the build it deployed, and the
history lies precisely when an incident has you reading it.

## Consequences

- A deploy is `helm upgrade --set image.tag=<sha>`; a rollback is
  `helm rollback` — both verified against the live cluster, with the
  revision history as the deploy log.
- `kubernetes/manifests/` remains in the tree as the pre-Helm record;
  the chart is what deploys from now on, and the Jenkins pipeline
  (next phase) will drive it.
- The namespace is not templated (Helm convention):
  `--create-namespace` or the existing one.
- Per-environment drift is confined to small values files whose entire
  content is the difference between environments.
