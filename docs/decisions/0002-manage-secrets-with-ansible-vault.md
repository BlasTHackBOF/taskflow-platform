# ADR-0002: Manage secrets with Ansible Vault, keep real values out of git

- **Status:** Accepted
- **Date:** 2026-08-03

## Context

This project is delivered as a single public GitHub repository. The work is
graded on what the repository contains, which means every secret-bearing file
must be *represented* in the repository — but real secret values must never
enter git, in plain text or in any other form. The stack needs real secrets
across three different layers:

| Layer | Secret |
| --- | --- |
| Terraform | AWS-facing variables, SSH public key material |
| Ansible | database password, Grafana admin password |
| Kubernetes | application `SECRET_KEY`, `DATABASE_URL`, registry pull token |

The chosen mechanism also has to fit the project's mandatory tool list, which
includes Ansible. A solution from outside that list would add a tool nobody
asked for while leaving a mandated one underused.

## Decision

Real secrets never enter git. Two complementary practices cover the gap:

1. **Every secret file ships a committed `.example` twin.** The twin carries
   the same keys with placeholder values, so a reader without access to any
   secret can still see the exact shape of the configuration. The real file is
   listed in `.gitignore`; the `.example` twin is the artifact that gets
   graded and read.
2. **Ansible Vault encrypts secrets at rest.** Runtime secrets — the database
   password, the Grafana admin password, and the values Ansible injects into
   Kubernetes — live in a vault-encrypted vars file on the operator machine.
   The vault password is kept in `vault_pass.txt`, which is ignored by git,
   and in the Jenkins credential store for pipeline runs.

Per layer:

- **Terraform** reads sensitive variables from `terraform.tfvars`, which is
  ignored by git; `terraform.tfvars.example` is committed.
- **Ansible** keeps its secret variables in a vault-encrypted file with a
  committed plain-text `.example` twin listing every variable name.
- **Kubernetes** receives its Secret objects from Ansible at deploy time,
  templated from the vault-decrypted values. No secret manifest is written to
  the repository; an `.example` manifest documents the expected keys.

The local development stack uses a `.env` file (ignored) with a committed
`.env.example` twin, following the same pattern.

## Consequences

- The repository is safe to publish: no real secret exists in it in any form,
  and no key material can leak through git history.
- A reader can reconstruct the full configuration surface from the `.example`
  files alone — every key name the system reads is visible in plain text.
- Ansible Vault, a mandatory tool for this project, is exercised in its
  intended role instead of being displaced by outside tooling.
- Secrets at rest on the operator machine and the CI node are encrypted;
  losing a laptop does not mean losing the secrets in the clear.
- Losing the vault password means re-creating the vaulted values. The
  password is treated as an operational asset and backed up outside the
  repository.
- The `.example` twins must be kept in sync with the real files by hand.
  A drifted twin misleads the reader, so updating the twin is part of the
  definition of done for any change that touches a secret file.

## Alternatives considered

- **SOPS + age, ciphertext committed** — a solid pattern in industry, and it
  would make the repository self-contained. Rejected because it commits real
  secrets (encrypted) to a public repository against this project's delivery
  rule, adds two binaries outside the mandatory tool list, and sidelines
  Ansible Vault, which is on that list.
- **HashiCorp Vault** — the correct answer at organisational scale. Rejected
  because it requires a dedicated always-on server the project's budget does
  not justify, and its own unseal secret recreates the same problem one level
  up.
- **AWS Systems Manager Parameter Store** — a good fit for AWS-hosted
  workloads, but outside the set of AWS services this project is permitted to
  use, and it would leave the local Docker Compose stack with no secrets
  source at all.
- **`.gitignore` alone, no encryption at rest** — the simplest option.
  Rejected because it leaves secrets in plain text on every machine that
  holds them and demonstrates nothing about secret management.
