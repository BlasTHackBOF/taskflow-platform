# ADR-0006: Terraform state in S3 with native lockfile locking

- **Status:** Accepted
- **Date:** 2026-08-04

## Context

Terraform state is the single source of truth for what exists in AWS. It
cannot live on the operator's workstation: it must survive that machine,
and the Jenkins pipeline will later need to read and write it too. Two or
more writers mean locking is not optional — a plan/apply racing another
apply against the same state silently corrupts it.

The canonical AWS answer is an S3 bucket for the state plus a DynamoDB
table for the lock. DynamoDB is not on this project's permitted service
list (EC2, IAM, Security Groups, S3). Terraform 1.10 removed the need for
it: the S3 backend gained `use_lockfile`, locking implemented entirely
inside S3.

There is also a chicken-and-egg problem: the bucket that stores state
cannot store the state of its own creation.

## Decision

**State lives in S3 (`taskflow-prod-tfstate`), locked with
`use_lockfile = true`.** The backend block is a partial configuration —
backend blocks cannot read variables, so bucket, key and region live in a
gitignored `backend.hcl` with a committed `.example` twin:

    terraform init -backend-config=backend.hcl

**How native locking works.** On every state-mutating operation Terraform
writes a lock object (`<key>.tflock`) next to the state object using an S3
*conditional write* (`If-None-Match`): the PUT succeeds only if the object
does not already exist, and S3 applies that check atomically. A second
Terraform run hits the existing lock object, receives a 412, and reports
the lock holder from the lock object's body (who, when, which operation).
On completion the lock object is deleted; after a crash the leftover lock
is cleared with `terraform force-unlock <id>`. This requires Terraform
>= 1.10, which `versions.tf` pins in both configurations.

**How it honestly differs from DynamoDB locking:**

| | DynamoDB table | S3 `use_lockfile` |
| --- | --- | --- |
| Mechanism | Conditional `PutItem` on a lock table | Conditional `PutObject` next to the state |
| Extra service | Yes — a second service to create, permit and pay for | No |
| State digest check | Stores an MD5 of the state and refuses a mismatched read | None |
| Track record | Battle-tested for a decade | Introduced in 1.10 (late 2024) |
| Direction of travel | The `dynamodb_table` argument is deprecated upstream | The supported path going forward |

The digest row is the real difference. DynamoDB's checksum guarded
against reading a stale state object back when S3 was eventually
consistent. S3 has had strong read-after-write consistency since the end
of 2020, which removes the failure mode the digest existed for — the
check is redundant now, but native locking does lose it, and anyone
running pre-2020 intuitions about S3 should know that is why this is
safe. The shorter track record is also real; the mechanism is simple
enough (one conditional write) that we accept it.

**Bootstrap.** A separate minimal configuration
(`infra/terraform/bootstrap/`) creates the state bucket itself, with
versioning, public access block and `prevent_destroy`. Its own state is
local and **committed to git** — a deliberate, narrow exception in
`.gitignore`. That state describes one bucket and its settings and
contains no secrets. The main configuration's state is never committed:
it will hold instance attributes and anything a provider marks sensitive,
and the project's secrets rule (ADR-0002) is absolute.

**Recovery.** Bucket versioning is the corruption story: a clobbered or
corrupted state file is rolled back by restoring the previous object
version. This replaces nothing DynamoDB provided — it is needed under
either locking scheme.

## Consequences

- Concurrent runs are serialised; the loser sees a "state locked" error
  naming the holder instead of corrupting the state.
- Everything that runs Terraform — operator workstation and later the
  Jenkins pipeline — must be on Terraform >= 1.10. `required_version`
  enforces this at init time.
- A crashed run leaves a stale `.tflock` object; the fix is
  `terraform force-unlock` with the ID from the error message.
- The bootstrap state file must be recommitted on the rare occasion the
  bucket's own configuration changes.
- No lock table appears in any AWS bill or console; the lock is visible,
  when held, as an ordinary object next to the state.

## Alternatives considered

- **DynamoDB lock table** — the long-standing default, rejected twice
  over: DynamoDB is outside the permitted service list, and upstream has
  deprecated the `dynamodb_table` argument in favour of `use_lockfile`.
- **Terraform Cloud / HCP Terraform** — remote state, locking and a UI
  for free, but an external SaaS displacing tools the project is
  required to demonstrate. Rejected.
- **Local state only** — no locking, no sharing, and the pipeline could
  never run Terraform; the state would live and die with one laptop.
- **S3 without `use_lockfile`** — how S3-only backends ran for years.
  Works until two writers race; the flag costs one line and removes the
  risk entirely.
- **Committing state to git** (beyond bootstrap) — rejected outright:
  state embeds every resource attribute including sensitive ones, and
  git history is forever.
