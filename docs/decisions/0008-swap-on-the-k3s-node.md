# ADR-0008: Swap on the k3s node

- **Status:** Accepted
- **Date:** 2026-08-04

## Context

The application node is a t3.micro: 911 MiB of usable RAM, chosen to
stay inside the Free Tier (see infra/terraform/README.md). Measured on
the live node, the k3s control plane and runtime alone cost roughly
600 MiB RSS — `k3s-server` 430 MiB, containerd 60 MiB, Traefik 27 MiB,
CoreDNS 16 MiB, dockerd 19 MiB — on top of a Ubuntu base system. During
provisioning, the first k3s restart pushed the node into memory
exhaustion: 40 MiB available, multi-second datastore queries, apiserver
handler timeouts, and an Ansible run that hung until killed.

Swap on a Kubernetes node is conventionally considered wrong, for real
reasons:

- **kubelet refuses to start** with swap enabled unless
  `fail-swap-on=false` is set. k3s ships with it disabled by default,
  because k3s targets exactly this class of small machine — so no extra
  configuration was needed, but the convention exists and the deviation
  should be recorded.
- **Memory accounting becomes soft.** The scheduler and kubelet reason
  about RAM; a pod at its memory limit can be paged out instead of
  OOM-killed, so limits stop meaning what they say.
- **Latency becomes unpredictable.** A page-in from gp3 EBS costs on
  the order of a millisecond against ~100 ns for RAM — four orders of
  magnitude, and it strikes whichever allocation happens to fault.

## Decision

A 2 GiB swapfile on the node's gp3 root volume, created and persisted
by the k3s role.

The reasoning: on this node the alternative to swap is not "predictable
latency", it is the OOM killer choosing between the apiserver and the
workload — observed as a NotReady node and a hung provisioning run.
Swap converts that hard failure into soft degradation: the node gets
slow instead of gone, SSH and Ansible keep working, and the cluster
keeps answering. On a one-node lab cluster whose SLO is "the operator
can always get in and fix it", that is the right trade. metrics-server
is disabled in the same spirit (Prometheus arrives in the monitoring
phase; a component that duplicates it cannot be afforded here).

**What it costs, measured:** during the initial thrash the datastore
logged multi-second queries; at idle the micro still pages in at
~0.5 MB/s with ~490 MiB swapped — this node is genuinely too small,
and swap is load-bearing rather than precautionary. That fact drives
the pending instance-size decision.

## When to remove it

- **Sizing is being reconsidered now** (the node must still absorb the
  application, PostgreSQL, Prometheus and Grafana). If the node grows
  to 4 GiB (t3.medium), remove the swapfile: the working set fits with
  real headroom and the standard no-swap posture returns.
- **At 2 GiB (t3.small), keep it** — but demoted from load-bearing to
  crash barrier. The monitoring phase should alert on sustained
  swap-in (node-exporter `node_vmstat_pswpin`): steady paging at 2 GiB
  means the sizing decision was wrong, not that swap needs tuning.
- Pod memory limits in the Helm chart are set as if swap did not
  exist; nothing may be sized assuming it can page.
