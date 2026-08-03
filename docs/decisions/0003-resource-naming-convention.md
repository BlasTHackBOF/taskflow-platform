# ADR-0003: Adopt a single naming convention across all layers

- **Status:** Accepted
- **Date:** 2026-08-03

## Context

This project spans AWS resources, container images, Kubernetes objects, Helm
releases and Git branches. Each of those tools has its own conventions, its
own character restrictions, and its own community habits. Left alone, they
drift: an EC2 instance called `k3s-server`, an image called `taskflow_app`, a
namespace called `default`, and a Helm release called `my-release`.

The cost of that drift is not aesthetic. When something breaks at the
Kubernetes layer, the first question is which AWS resource is behind it, and
an inconsistent scheme turns that lookup into guesswork. It also makes cost
attribution by tag impossible.

## Decision

Every resource in the project is named with the pattern:

```
taskflow-<environment>-<component>[-<index>]
```

- `taskflow` is the constant project prefix and never varies.
- `<environment>` is `prod`. See "Environments" below.
- `<component>` describes the role, not the technology where the two differ.
- `<index>` is a zero-padded ordinal, present only where more than one
  instance of a component can exist.

Applied across the stack:

| Layer | Name |
| --- | --- |
| EC2 (application node) | `taskflow-prod-k3s-01` |
| EC2 (CI node) | `taskflow-prod-ci-01` |
| Security group | `taskflow-prod-app-sg` |
| S3 (Terraform state) | `taskflow-prod-tfstate` |
| S3 (artifacts, backups) | `taskflow-prod-artifacts` |
| IAM role | `taskflow-prod-node-role` |
| Container image | `ghcr.io/blasthackbof/taskflow-api` |
| Kubernetes namespace | `taskflow-prod` |
| Helm release | `taskflow` |

Two deliberate exceptions:

- **Container images** carry no environment segment. The same image artifact
  is meant to be promotable across environments unchanged; encoding an
  environment in the tag would contradict that.
- **The Helm release** is just `taskflow`, because it is already scoped by the
  namespace it is released into. `taskflow-prod` inside namespace
  `taskflow-prod` is redundant.

### Image tagging

Images are tagged with the **short Git commit SHA** as the immutable
identifier, plus a semantic version tag on release commits. `latest` is
published for convenience but is never referenced by any Kubernetes manifest —
a mutable tag in a deployment makes the running version unknowable.

### Git branches

```
<type>/<short-description>
```

where `<type>` is one of `feat`, `fix`, `docs`, `chore` or `infra`, and the
description is lowercase and hyphenated. Example:
`feat/readiness-probe`.

### AWS tags

Every AWS resource created by Terraform carries `Project=taskflow`,
`Environment=prod`, and `ManagedBy=terraform`, applied through the provider's
`default_tags` block rather than repeated per resource.

## Environments

This project defines **one environment, `prod`**, and still carries the
environment segment in every name.

Two environments would be more representative of a real organisation, but
would roughly double both the AWS spend and the provisioning time, against a
fixed credit budget and deadline. Keeping the segment means adding a second
environment later is a variable change, not a rename of every resource in the
system. This limitation is recorded in the Future Improvements section of the
documentation rather than hidden.

## Consequences

- Any resource can be traced to its project, environment and role from its
  name alone.
- Cost and ownership can be filtered by AWS tag without a lookup table.
- Names are longer than they strictly need to be in a single-environment
  system. This is accepted as the price of not renaming everything later.
- The convention has to be applied by hand; nothing enforces it
  automatically. A future improvement would be a `tflint` rule or a Terraform
  naming module.

## Alternatives considered

- **`<component>-<environment>` ordering** — sorts resources by component
  rather than by project. Rejected because the AWS console lists many
  unrelated resources, and a constant leading prefix makes the project's
  resources contiguous in every listing.
- **No environment segment** — shorter and honest about there being only one
  environment. Rejected because adding a second environment would then require
  renaming every resource, which in Terraform means destroy-and-recreate.
- **Random or generated suffixes** — guarantee global uniqueness, which S3
  bucket names in particular require. Rejected as the default because
  unreadable names defeat the purpose; uniqueness is instead achieved by the
  project prefix, and a suffix will be added only if a specific name collides.
