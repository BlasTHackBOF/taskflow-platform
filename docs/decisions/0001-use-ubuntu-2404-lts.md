# ADR-0001: Run all servers on Ubuntu 24.04 LTS

- **Status:** Accepted
- **Date:** 2026-08-03

## Context

Every server in this project — the Kubernetes node and the CI node — needs a
Linux distribution. The choice constrains several later phases at once: which
package manager the Ansible playbooks target, which k3s installation path is
supported, and how long the platform stays patchable without a rebuild.

The relevant forces:

- k3s, Docker and the Prometheus node exporter must all be installed from
  first-party sources, not community backports.
- The Ansible roles should use one package manager consistently. Mixing `apt`
  and `dnf` across hosts would mean duplicated task logic for no benefit.
- The project is a portfolio artifact. A distribution whose support window
  closes before a reader looks at the repository sends the wrong signal.

## Decision

All EC2 instances run **Ubuntu Server 24.04 LTS (Noble Numbat)**, x86_64,
using the official Canonical AMI resolved through a Terraform data source
rather than a hardcoded AMI ID.

## Consequences

- Standard support runs to April 2029, so the platform stays patchable well
  beyond the life of this project.
- k3s and Docker both publish and test against this release directly; no
  third-party repositories are required.
- All Ansible roles target `apt` exclusively, which keeps them short and
  readable.
- Resolving the AMI through a data source means the ID is never hardcoded and
  the Terraform stays portable across regions — at the cost of a `terraform
  plan` diff whenever Canonical publishes a new image build.
- Ubuntu ships a broader default package set than a minimal image would. This
  is accepted for now; hardening is handled explicitly in the Ansible layer
  rather than by starting from a smaller base.

## Alternatives considered

- **Amazon Linux 2023** — integrates cleanly with AWS tooling and is tuned for
  EC2. Rejected because k3s documentation and community troubleshooting
  material overwhelmingly assume Debian or Ubuntu, and debugging time is the
  scarcest resource in this project.
- **Debian 12 (Bookworm)** — very stable and a legitimate choice. Rejected
  because its package versions lag further behind, which would likely mean
  adding external repositories for Docker and observability tooling, and
  because Ubuntu was the distribution used throughout the course.
- **Ubuntu 22.04 LTS** — the previous LTS. Rejected only on support window:
  24.04 offers three additional years for no added cost or risk.
