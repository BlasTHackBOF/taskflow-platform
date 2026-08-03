# ADR-0004: Use GitHub Container Registry for application images

- **Status:** Accepted
- **Date:** 2026-08-03

## Context

Jenkins builds a container image on every merge to `main`, and the k3s
cluster pulls that image at deploy time. The image therefore needs a home
that both sides can reach, and the choice is constrained from two directions:

- The AWS account available to this project is limited to EC2, IAM, Security
  Groups and S3. Amazon ECR — the registry that would normally pair with an
  AWS-hosted cluster — is not among the permitted services.
- The mandatory tool list includes Git/GitHub but no registry product, so a
  registry that rides on an existing tool is preferable to one that adds a
  new vendor, account and credential set.

## Decision

Application images are pushed to the **GitHub Container Registry** (GHCR) at
`ghcr.io`, namespaced under the same GitHub account that owns this
repository.

- Jenkins authenticates with a personal access token scoped to
  `write:packages`, held in the Jenkins credential store.
- k3s pulls with a separate read-only token (`read:packages`), delivered to
  the cluster as an image pull Secret by Ansible from the vault-encrypted
  variables file — the "registry pull token" already accounted for in
  [ADR-0002](0002-manage-secrets-with-ansible-vault.md).

GHCR wins on fit rather than on features:

- **It lives where the code lives.** The same account, the same permission
  model, and the package page links back to the repository — a grader who
  finds the repo finds the images.
- **It deepens a mandatory tool instead of adding one.** GitHub is on the
  required tool list; a separate registry vendor is not.
- **No pull throttling to design around.** GHCR does not impose the
  anonymous pull rate limits that Docker Hub does, so neither CI nor a
  rescheduled pod can fail because a shared IP exhausted a pull quota.
- **Free at this project's scale**, with no impact on the AWS Free Tier
  budget.

## Consequences

- Two token secrets exist: a write token in Jenkins and a read-only token in
  the cluster. Both follow the ADR-0002 pattern — never committed, `.example`
  twins document the expected keys.
- Deploys of *new* images depend on GitHub's availability. Running pods are
  unaffected by a GHCR outage; only rollouts wait.
- Images pulled from outside AWS cross the internet rather than a VPC
  endpoint. At this project's image size and deploy frequency the transfer
  is negligible.
- If the read-only token is rotated, Ansible must re-render the pull Secret;
  token rotation is part of the same runbook as any other vaulted value.

## Alternatives considered

- **Amazon ECR** — the natural choice for a cluster on EC2, with IAM-native
  auth and in-region pulls. Rejected because the AWS services available to
  this project are limited to EC2, IAM, Security Groups and S3; ECR is
  outside that allowlist. It would also add operational friction k3s does
  not handle out of the box: ECR auth tokens expire every 12 hours and need
  a refresh mechanism on every node.
- **Docker Hub** — the default public registry. Rejected because its
  anonymous and free-tier pull rate limits are enforced per source IP, which
  makes CI and cluster pulls fail unpredictably from shared or NATed
  addresses, and because it introduces a second vendor account with its own
  credentials for no capability GHCR lacks here.
- **Self-hosted registry (`registry:2` on EC2)** — maximum control and no
  third party. Rejected because it would consume Free Tier compute the
  cluster needs, add TLS and storage operations for a piece of
  infrastructure nobody grades, and turn every deploy into a dependency on
  one more self-managed service.
