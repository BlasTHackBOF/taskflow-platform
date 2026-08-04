# Screenshots

Evidence that each phase actually ran. The AWS environment is torn down between
working sessions to control cost, so these are the record that it worked.

## Naming

`<phase>-<what-it-shows>.png` — the numeric prefix sorts them into build order,
so the folder reads as a timeline rather than an unordered pile.

## Captured

| File | Shows |
|---|---|
| `01-tests-passing.png` | 69 tests green, 90.64% coverage, and the JUnit XML the pipeline will consume |
| `02-docker-image-build.png` | A multi-stage build from a clean cache producing a 271 MB image |
| `03-compose-stack-healthy.png` | The full local stack: database healthy, migrations run and exited, application healthy |
| `04-terraform-apply-and-ssh.png` | `terraform apply` creating 23 resources, the outputs, and an SSH session confirming Ubuntu 24.04 |
| `05-bash-env-control-status.png` | `env-control.sh status` listing both instances with state, type and uptime |

## Still needed

- [ ] `04-aws-console-instances.png` — both instances in the EC2 console, showing this exists in the cloud and not only in a terminal
- [ ] `06-ansible-idempotent.png` — a second playbook run reporting `changed=0`
- [ ] `07-kubectl-pods.png` — pods running with probes passing
- [ ] `08-helm-release.png` — `helm list` showing the deployed release
- [ ] `09-jenkins-pipeline.png` — a green pipeline run with every stage visible
- [ ] `10-grafana-dashboard.png` — the dashboard with real data on it

## Before adding a screenshot

Check it contains no secrets: tokens, private keys, passwords, AWS access keys.
A public EC2 IP is fine — it changes on every restart anyway.

Capture at the end of each phase, not at the end of the project. Some of these
cannot be recreated without tearing the environment down and rebuilding it.
