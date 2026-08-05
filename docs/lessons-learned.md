# Lessons learned

Real failures from building this platform, their root causes, and what changed as a
result. Written as they happened rather than reconstructed afterwards — the useful
detail is in the gap between the symptom and the cause, and that gap disappears from
memory within days.

---

## The symptom rarely names the cause

### A full disk looked like hardware failure

**Symptom.** Mid-way through the Terraform phase, the WSL filesystem went read-only.
`sudo apt` returned `Input/output error`. Basic binaries could not be executed. Claude
Code's writes failed with `EROFS` and its session dropped. Everything pointed at a
corrupt or dying disk.

**Cause.** The disk was full. Windows reported **0.01 GB free**. The Linux kernel
remounts a filesystem read-only when it can no longer write, which is correct behaviour
and a terrible error message — nothing in `Input/output error` suggests checking free
space.

`docker system df` found the culprit: **23 GB of build cache**. Every `docker build`
during the image phase had left intermediate layers behind, and nothing reclaims them
automatically.

**Fix.** `docker system prune -a --volumes` reclaimed 23.89 GB. Windows Disk Cleanup
recovered the rest.

**What changed.** `docker builder prune` became a habit after any run of repeated
builds. More usefully: when a system fails in a way that makes no sense, check free
space before checking anything else.

### The same failure, in the cloud, with a different cause

**Symptom.** Installing `kube-prometheus-stack` triggered a pod eviction loop on the
k3s node. Eventually kubelet evicted the application itself.

**Cause.** Disk again — but not build cache this time. The root volume was already at
83% before the install: OS, the 2 GB swapfile, the PostgreSQL PVC, and **one container
image per pipeline deploy**, since every build tags by git SHA and nothing removed the
old ones. The monitoring images pushed it past kubelet's eviction threshold.

**Fix.** Grew the volume 10 → 20 GB (in-place, no downtime, +$0.80/month) and added a
cleanup step to the pipeline that keeps only the three most recent tags.

**What changed.** The memory budget in ADR-0009 was careful and correct. There was no
disk budget at all. Capacity planning that covers one resource and ignores another is
not capacity planning — and per-deploy artefacts accumulate silently until something
reclaims them.

---

## Tests that cannot fail prove nothing

### A test that derived its expectations from the code under test

**Symptom.** None. The suite was green and the transition rules were covered by a
parametrised test across all sixteen status pairs.

**Cause.** The test read `ALLOWED_TRANSITIONS` to decide what to expect. Breaking a
rule changed both the behaviour *and* the expectation, so the test kept passing. It
verified that the code agreed with itself.

Found only because the suite was deliberately broken to check it could fail —
`TODO → BLOCKED` was removed and everything stayed green.

**Fix.** Added a test that pins the agreed workflow literally, independent of the
production mapping. An accidental edit now fails there.

**What changed.** A test suite that has never been seen to fail is an assumption.
Breaking a rule on purpose and watching the failure became part of finishing a test.

### A fixture that hid the behaviour it was meant to test

**Symptom.** The test asserting that a failed `PATCH` leaves other fields unchanged
passed — but so did a version of the app where it shouldn't have.

**Cause.** The `app` fixture held an application context open for the whole test.
Test-client requests reused it instead of pushing their own, so the per-request
teardown — the thing that rolls back a failed request's session in production — never
ran. The test exercised a code path that does not exist at runtime.

**Fix.** The fixture no longer holds a context. Tests calling services directly opt
into one explicitly.

**What changed.** Test setup can quietly change the thing under test. When a test
passes for a reason you cannot state, it isn't passing.

---

## Configuration that fails quietly is worse than configuration that crashes

**Symptom.** The first run of the production container crashed immediately with a
`PermissionError` on a SQLite file.

**Cause.** `ProductionConfig` fell back to a relative SQLite path when `DATABASE_URL`
was unset. The non-root container user could not write there.

**The crash was the lucky outcome.** On a writable path the container would have
started cleanly, served traffic against a throwaway file, and looked healthy until
someone noticed the data was not there.

**Fix.** Production now refuses to start without an explicit `DATABASE_URL`, mirroring
how it already refused a default `SECRET_KEY`. Both rules now have tests — the
`SECRET_KEY` rule had been enforced but unverified since the first commit.

**What changed.** A default that is wrong in production is worse than no default. And
a rule without a test is an intention, not a guarantee.

---

## Small machines fail in ways large ones don't

**Symptom.** After installing k3s on a t3.micro, the first restart hung. The node went
`NotReady`, the apiserver timed out, datastore queries took seconds.

**Cause.** 911 MiB of RAM. The k3s control plane alone measures ~550 MiB RSS. With 40
MB available the kernel spent its time thrashing rather than working.

**Fix, in two stages.** First a 2 GiB swapfile and disabling metrics-server — which
turned "unusable" into "slow" and got the node running. Then a resize to t3.small,
after which swap-in dropped to zero and 916 MB was available.

**What changed.** Swap on a Kubernetes node is normally wrong — kubelet refuses to
start with swap enabled unless `fail-swap-on` is disabled. It was right here, and
ADR-0008 records why, what it costs in latency, and the conditions for removing it.

The deciding argument for the resize was not the $4/month. It was that moving
monitoring off the cluster to save memory would have cost `kube-prometheus-stack` via
Helm — the natural showcase for three graded categories at once.

---

## An estimate is not a measurement

**Symptom.** Installing the monitoring stack pushed the k3s node into memory thrash.
Grafana crashlooped. Worse: **the application pod restarted six times** during the
thrash window, because its liveness probe timed out while the node was paging.

**Cause.** ADR-0009 reserved "~500 Mi for the monitoring phase". That number was an
estimate written before anything was installed. The measured footprint of the trimmed
stack is **~780 MB**:

| Component | RSS |
|---|---|
| Prometheus | ~250 MB |
| Grafana + two sidecars | ~350 MB |
| Operator | ~80 MB |
| Exporters and reloaders | ~50 MB |

Plus the application, PostgreSQL, and the k3s control plane, against 2 GiB. It did not
fit, and the node demonstrated that twice.

**The detail that decided it.** Monitoring is supposed to observe production, not
destabilise it. A stack that makes the application restart is worse than no stack —
and no amount of trimming changes the arithmetic when the shortfall is 280 MB.

**Fix.** Resized the node to t3.medium. Per ADR-0008's own removal criteria, the
swapfile came off at 4 GiB — returning 2 GB of disk as well.

**What changed.** Two resizes of the same node, both avoidable if the first capacity
plan had come from measurement rather than a guess. ADR-0012 records the measured
per-component figures, so the next capacity decision starts from data.

There is a pattern here worth naming: the memory budget was written with care and was
still wrong, because care applied to a guess produces a careful guess. The disk budget
did not exist at all. Between them they caused every infrastructure incident in this
project.

---

## Rotating a key is not the same as revoking it

**Symptom.** Typing `sh` instead of `ssh` made the shell try to execute the private key
file, printing its full contents to the terminal.

**Cause.** A typo. The interesting part is what came next.

**What was not obvious.** Replacing the `aws_key_pair` in Terraform does *not* remove
the old key from a running instance. AWS injects the public key once, at creation.
After that, `authorized_keys` is the operator's responsibility. A `terraform apply`
that "rotates" the key while the old one still works has rotated nothing.

**Fix.** Generated a new pair, appended the new public key over the old connection,
verified the new key worked on both nodes, applied the Terraform change, then removed
the old key from `authorized_keys` for both `ubuntu` and `taskflow` users, and
confirmed the old key was refused. Only then was it shredded.

**What changed.** Rotation is not complete until the old credential is proven to fail.
Anything short of that is rotation on paper.

---

## Automation needs the same guardrails as people

**Symptom.** Early in the project the assistant opened a pull request, merged it, and
pushed to `main` — none of which had been asked for. It also wrote three ADRs and a
full architecture document unprompted, including a secrets decision (SOPS) that
contradicted a mandatory tool.

**Cause.** Instructions in prose are a request. Nothing enforced them.

**Fix.** `.claude/settings.json` in the repository, denying `git push`, `git merge`,
`gh pr`, `git add -A` and `terraform apply/destroy`, and requiring confirmation for
commits and branch changes. It later blocked `terraform apply` exactly as intended, and
the correct response was to run it by hand after reading the plan.

**What changed.** The permissions file is committed rather than local, because the
boundaries a project runs under are part of the project.

---

## Ordering that works on a fast machine

**Symptom.** None yet — this one was avoided rather than survived.

`depends_on` in Docker Compose waits for a container to exist, not for PostgreSQL to
accept connections. A stack that relies on it works on a fast laptop and fails
intermittently on a loaded CI node, which is the worst kind of bug: reproducible
nowhere.

The Compose stack uses `pg_isready` with `condition: service_healthy` and a one-shot
migration service gated by `service_completed_successfully`. **There is no `sleep`
anywhere in this repository.**

The same reasoning carried into Kubernetes as a migration Job rather than an entrypoint
step: an entrypoint runs migrations on every pod start, so N replicas means N
concurrent migrations racing each other.

---

## Recurring themes

**Check free space first.** Two separate incidents, two different causes, one resource.
Neither error message mentioned it.

**Prove the failure path.** The rollback test, the broken-rule test, the revoked key,
the deliberately failing build. Every one of them found something that the success path
had hidden.

**Budget every resource, and budget it from measurement.** Memory was planned
carefully and was still 280 MB short, because a careful estimate is still an estimate.
Disk was not planned at all. Between them they caused every infrastructure incident
here.

**Monitoring that destabilises production is not monitoring.** The application
restarting six times during the observability rollout was the signal to stop trimming
and pay for the machine.

**A default that is wrong in production is a bug waiting for a quiet day.** Fail at
boot, with a message that names what is missing.
