# ADR-0012: Monitoring tuned for a single-node cluster

- **Status:** Accepted
- **Date:** 2026-08-06

## Context

The monitoring phase deploys kube-prometheus-stack (pinned 88.1.5) onto
the same 2 GiB node that runs the workload it monitors. The chart's
defaults assume a fleet: dozens of dashboards, ~150 alert rules,
control-plane scrape jobs, hot-reload sidecars. On this cluster those
defaults are not overhead — they are an outage, and they caused two
before this ADR was written.

Also relevant: the AWS account is on the credits-based free plan, whose
instance ceiling is t3.small. A t3.medium resize was attempted and
refused (`FreeTierRestrictionError`), so the stack had to fit — this
document records how, with measurements rather than estimates.

## What happened first: two incidents, one lesson

**Disk.** ADR-0009 budgeted this phase's *memory* (~500 Mi reserve) and
budgeted disk not at all. The 10 GB root volume was at 83% before
install — OS, the 2 GiB ADR-0008 swapfile, the postgres volume, and one
~250 MB application image per pipeline deploy. The monitoring images
pushed free space under kubelet's eviction threshold and the node
entered an eviction loop that eventually evicted the application
itself. Fixed by growing the volume to 20 GB (+$0.80/month, the first
10 GB over the Free Tier allowance). The image pile has two custodians
now: kubelet's own GC (which works once it has slack to work in) on the
cluster node, and a keep-last-3 prune in the pipeline's cleanup stage
on the CI node, where `docker image prune` alone never touches tagged
images.

**Memory.** The ~500 Mi reserve was a guess. Measured, the lightly
trimmed stack's real working set was **~780 MB** — and on a node with
~700 MB truly free, that meant sustained swap thrash (7–11 MB/s in
both directions), monitoring components in restart loops, and the
application taking six liveness kills because a 2-second probe timeout
cannot be met while the kernel pages. The deciding observation:
**monitoring that damages the thing it monitors is worse than no
monitoring.**

The lesson, stated plainly: both incidents came from budgeting one
resource and assuming the other, twice on the same node. Capacity
decisions from here start from the measured numbers below.

## The tuning: measured before and after

| Component (working set) | Chart-default shape | Tuned |
| --- | --- | --- |
| Prometheus | ~250–300 MB (control-plane + cadvisor jobs) | **41 MB** |
| Grafana + sidecars | ~350 MB (2 sidecars, plugin preinstall) | **165 MB** (no sidecars) |
| Operator | ~80 MB | 25 MB |
| Alertmanager | ~50 MB | 13 MB |
| node-exporter + reloaders | ~50 MB | 26 MB |
| **Stack total** | **~780 MB** | **270 MB** |

Node after tuning, stack running, steady state: swap-in/out ≈ 0 KB/s,
~415 MB available, disk 50% of 19 GB. The stack fits with margin
instead of hoping to.

## What was cut, and why each cut is safe here

- **The stock rule pack** (~150 alerts) — written for fleets; on one
  node it is evaluation cost and alarm noise. Replaced by the one rule
  below.
- **kube-state-metrics** — object-state series no committed panel
  reads.
- **Every control-plane scrape job, kubelet/cadvisor included** — k3s
  runs the control plane in one process (there are no scheduler/etcd
  pods to find; kine speaks no etcd metrics), the apiserver job alone
  is thousands of series, and cadvisor thousands more that no panel
  uses. This is the cut that shrinks Prometheus from ~300 MB to 41 MB.
  Node-level CPU/memory/swap still arrive via node-exporter.
- **Self-monitoring** (Prometheus/Alertmanager/Grafana scraping
  themselves) — self-observability is a luxury this node cannot fund.
- **Both Grafana sidecars** — with exactly one dashboard and one
  datasource, watch-and-reload machinery costs ~200 MB to save one
  `kubectl replace` plus pod restart on dashboard edits. Provisioning
  is static: datasource declared in values, dashboard ConfigMap
  mounted into the provider path.
- **Grafana plugin preinstall** — Grafana 12 downloads app plugins on
  every start; minutes of CPU for features nobody opens.
- **Alert delivery integrations** — Alertmanager runs with the null
  route; firing alerts are read in its UI. Slack/email wiring belongs
  to a project with an on-call rotation.
- **Retention 24 h, scrape 60 s, emptyDir storage** — the dashboard
  answers "what is happening now"; durable history is the S3 backup
  story's job, and a 24 h window already accepts metrics dying with
  the pod.

**What was deliberately kept:** node-exporter (~12 MB) — the one
exporter feeding no panel, kept because it feeds the *alert*, and the
alert watches this node's actual failure mode.

## The one alert

`NodeSustainedSwapIn`: `rate(node_vmstat_pswpin[10m]) > 64` pages/s
(≈256 KiB/s) sustained `for: 15m`. Memory is this node's binding
constraint and ADR-0008's swap converts memory exhaustion from a crash
into silent degradation — this alert is the tripwire that promises the
degradation is never silent. Post-deploy churn stays under the `for`
guard; a quarter hour of steady paging means the budget above has been
outgrown and sizing needs revisiting *before* the OOM killer does it.

## Access and secrets

Grafana's admin password comes from the Ansible vault into a
pre-created Secret (`grafana-admin`) the chart references — never a
chart default, never in values. Grafana is reachable only by
`kubectl port-forward` (operator-only, zero new attack surface, no new
security group rule).

## If the stack must grow

The next capacity step is not more trimming — the fat is gone. It is
either the AWS account leaving the free plan so t3.medium is allowed
(≈+$15/month at 24/7, per infra/terraform/README.md), or monitoring
moving off-node. Both are decisions for the day a second dashboard or
a real retention requirement arrives; the numbers above are the
starting point.
