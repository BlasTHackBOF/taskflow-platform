# ADR-0007: Dynamic inventory from Terraform, and the role split

- **Status:** Accepted
- **Date:** 2026-08-04

## Context

Ansible needs two things Terraform already knows: which servers belong
to this project, and where they are. The two have different lifetimes.
Identity (instance IDs, region) is stable for the life of the
infrastructure. Addresses are not: the instances use auto-assigned
public IPs that change on every stop/start — a deliberate cost choice
(see infra/terraform/README.md) that the environment is stopped and
started daily, so any recorded address is wrong within a day.

A hand-maintained `hosts.ini` is therefore stale by construction. The
question is where the inventory should come from instead.

## Decision

**An executable dynamic inventory, `ansible/inventory/terraform.sh`,
composed from two sources with different authorities:**

- **Identity from Terraform.** Instance IDs and region are read from
  `terraform output` on every invocation. Nothing is hardcoded; if the
  state backend is unreachable the script fails with the init command
  to run, not with a wrong answer.
- **Addresses from live AWS.** Public IPs come from `DescribeInstances`
  at the moment Ansible runs — the same doctrine as
  `scripts/env-control.sh`: Terraform state records what was true at
  the last refresh, the EC2 API records what is true now. If an
  instance has no address (stopped), the inventory refuses to resolve
  and says to start the environment first.

The script is Bash with no dependencies beyond the two CLIs the
operator already needs.

**The trade-off, honestly:** every Ansible invocation now requires
`terraform`, the `aws` CLI, valid AWS credentials and a reachable state
backend, and pays ~2–3 seconds of resolution before the first task. A
static file costs none of that. The price buys the property that
mattered: the inventory cannot be stale, because nothing in it is
remembered.

**Alternatives considered:**

- **Static `hosts.ini`** — free and obvious, and wrong after the first
  stop/start. Rejected: chasing IPs by hand is exactly the failure this
  project's daily workflow would hit most often.
- **`amazon.aws.aws_ec2` inventory plugin** — discovers instances by
  tag query. Needs boto3 and an extra collection, and its authority is
  "whatever in the account matches the tags," which bypasses Terraform
  as the source of what belongs to the project.
- **`cloud.terraform` inventory plugin** — reads addresses out of the
  state file, which is precisely where the stale (or empty — the state
  currently records `""` for both IPs) addresses live. The failure mode
  is silent and this ADR exists because of it.

## The role split

Four roles, split by *which nodes need it*, not by software category:

| Role | Hosts | Why it is separate |
| --- | --- | --- |
| `common` | all | What every node must be before it is anything else: unattended security updates, admin user, hardened SSH, timezone, baseline packages. |
| `docker` | all | Both nodes need the engine for different reasons — CI runs Jenkins in it and builds images; pinned so the two nodes cannot drift apart. |
| `k3s` | app | The cluster, pinned; swapfile for the 1 GiB node; kubeconfig fetched back and rewritten to the public address. |
| `jenkins` | ci | Jenkins in Docker, home on a named volume so the container is disposable and the data is not. |

Scaffolding exists only where it earns its place: `k3s` has the only
template (per-host token and TLS SAN), `common` and `k3s` have the only
handlers (ssh and k3s restarts on config change), `docker` and
`jenkins` have neither because nothing in them reacts to config files.

## Consequences

- `ansible-playbook` and `ansible` commands only work where the
  Terraform backend is initialised and AWS credentials are valid — true
  for the operator machine and, later, the Jenkins node via its
  instance profile.
- Secrets follow ADR-0002: `group_vars/all/vault.yaml` is committed
  only Vault-encrypted with a plaintext `.example` twin; the vault
  password lives in the gitignored `vault_pass.txt` and never enters
  git.
- Version pins (k3s, Jenkins image, Docker Engine) live in role
  defaults and are bumped in review, not discovered in production.
- A second playbook run reports `changed=0`; `--check` is safe and
  clean against a converged environment.
