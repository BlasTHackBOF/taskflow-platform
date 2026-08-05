# Screenshots

Evidence that each phase actually ran.

## Naming

`<phase>-<what-it-shows>.png` — the numeric prefix sorts them into build order,
so the folder reads as a timeline rather than an unordered pile.

## Captured

| File | Shows |
|---|---|
| `01-tests-passing.png` | 70 tests green, 90.9% coverage, and the JUnit XML the pipeline consumes |
| `02-docker-image-build.png` | A multi-stage build from a clean cache producing a 271 MB image |
| `03-compose-stack-healthy.png` | The local stack: database healthy, migrations run and exited, application healthy |
| `04-terraform-apply-and-ssh.png` | `terraform apply` creating 23 resources, and an SSH session confirming Ubuntu 24.04 |
| `04-aws-console-instances.png` | Both instances running in the EC2 console with all status checks passed |
| `05-bash-env-control-status.png` | `env-control.sh status` listing both instances with state, type and uptime |
| `06-ansible-idempotent.png` | A second playbook run reporting `changed=0` on both nodes |
| `07-kubectl-cluster-ready.png` | The k3s node Ready and all pods running, reached from the operator machine |
| `08-kubernetes-app-running.png` | Application and PostgreSQL pods running in the taskflow namespace |
| `08b-app-in-browser.png` | The API answering through the Ingress from the public internet |
| `09-helm-release.png` | `helm history` showing install, upgrade and rollback |
| `10-jenkins-pipeline.png` | A green pipeline run with test results and archived coverage |
| `10b-jenkins-branches.png` | Both tracked branches green |
| `11-prometheus-targets-up.png` | Prometheus scraping the application target, UP |
| `11b-prometheus-alert-rule.png` | The `NodeSustainedSwapIn` rule loaded and evaluating |
| `12-board-ui.png` | The board UI with the deployed build SHA in the header |

## On Grafana

There is no Grafana screenshot. Grafana has no Ingress by design — it is
reached only through `kubectl port-forward`. What it renders is evidenced
instead by the Prometheus target screenshot, the alert rule loaded and
evaluating, and the dashboard committed as JSON in `monitoring/grafana/`.

## Before adding a screenshot

Check it contains no secrets: tokens, private keys, passwords, AWS access keys.
A public EC2 IP is fine — it changes on every restart anyway.

Capture at the end of each phase, not at the end of the project. Some of these
cannot be recreated without tearing the environment down and rebuilding it.
