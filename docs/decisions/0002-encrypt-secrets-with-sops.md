# ADR-0002: Encrypt secrets in-repository with SOPS and age

- **Status:** Accepted
- **Date:** 2026-08-03

## Context

This project is delivered as a single public GitHub repository, and the
delivery rule is absolute: if something is not in the repository, it does not
exist. At the same time the stack needs real secrets across three different
layers:

| Layer | Secret |
| --- | --- |
| Terraform | AWS-facing variables, SSH public key material |
| Ansible | database password, Grafana admin password |
| Kubernetes | application `SECRET_KEY`, `DATABASE_URL`, registry pull token |

These two requirements pull against each other. Committing secrets in plain
text is unacceptable in a public repository. Leaving them out entirely breaks
the self-contained delivery requirement and leaves a reader with a repository
that cannot be reasoned about.

A third constraint: whatever mechanism is chosen has to work in three tools
that share nothing with each other. A per-tool solution means three
mechanisms, three ways to get it wrong, and three things to document.

## Decision

Secrets are encrypted with **SOPS** using an **age** key pair and the
resulting ciphertext files **are committed** to the repository.

- Encrypted files use the suffixes `*.enc.yaml` and `*.enc.tfvars`, which are
  explicitly un-ignored in `.gitignore`.
- The private age key never enters the repository. It lives on the operator
  machine and, for pipeline runs, in the Jenkins credential store.
- Every encrypted file ships with a committed `*.example` twin carrying the
  same keys and placeholder values, so a reader without the key can still see
  the shape of the configuration.

SOPS encrypts values while leaving keys in clear text, so a diff on an
encrypted file still shows *which* setting changed even when the value stays
opaque.

## Consequences

- The repository is genuinely self-contained and safe to publish.
- One mechanism covers Terraform, Ansible and Kubernetes. Nothing needs a
  second scheme bolted on later.
- A reviewer without the age key cannot decrypt the files. The README states
  this plainly and points at the `*.example` files, which carry every key name
  the system reads.
- The local toolchain grows by two binaries, `sops` and `age`. Their
  installation is automated in the Ansible bootstrap role rather than left to
  a manual step.
- Key loss means all encrypted values must be regenerated. The key is treated
  as an operational asset and backed up outside the repository.

## Alternatives considered

- **Ansible Vault** — familiar from the course and requires no new tooling,
  but is scoped to Ansible. Terraform variables and Kubernetes manifests would
  each still need a separate answer, producing exactly the fragmentation this
  decision set out to avoid.
- **HashiCorp Vault** — the correct answer at organisational scale, and the
  one to reach for if this system grew real users. Rejected here because it
  requires a dedicated always-on server, which the project's budget does not
  justify and whose own unseal secret would recreate the same problem one
  level up.
- **AWS Systems Manager Parameter Store** — a good fit for AWS-hosted
  workloads, but outside the set of services this project is permitted to use,
  and it would leave the local Docker Compose stack with no secrets source at
  all.
- **`.gitignore` alone, secrets kept out of band** — the simplest option and
  the one most projects reach for. Rejected because it directly violates the
  self-contained delivery requirement.

## Enforcement

Prevention is not the same as detection. Two automated checks guard the
decision rather than trusting it to discipline:

- a `gitleaks` pre-commit hook, so a plaintext secret fails before it can be
  committed at all;
- a `gitleaks` stage in the Jenkins pipeline, so the same check runs even if
  the hook is absent on a given machine.
