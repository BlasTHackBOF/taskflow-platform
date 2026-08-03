# CLAUDE.md — agent instructions for taskflow-platform

## Project

TaskFlow (use this name consistently) is a Flask task-management app for
small teams, taken to a production-shaped environment as a DevOps final
project. The application itself is not graded — it exists to give the
infrastructure something to run. Do not add features beyond what is asked.

## Hard constraints

- **AWS:** EC2, IAM, Security Groups and S3 only. No RDS/EKS/ECS/ALB/ECR.
  Stay within the Free Tier. k3s is self-managed on EC2; PostgreSQL runs in
  a container.
- **Mandatory tools (all must appear):** Linux, Bash, Git/GitHub, Docker,
  Docker Compose, Terraform, Ansible, Jenkins, Kubernetes, Helm, Prometheus,
  Grafana. Check every tool or service choice against this list and the AWS
  allowlist before proposing it — outside tooling that displaces a mandatory
  tool costs grade points.
- **Secrets:** real secrets never enter git in any form, not even encrypted.
  Only `.example` twins with placeholders are committed. Ansible Vault
  encrypts secrets at rest (ADR-0002). SOPS/age/gitleaks were explicitly
  rejected.

Grading weights: Documentation 15%, Terraform 12%, Docker+Compose 10%,
Jenkins 10%, Kubernetes 10%, Linux 8%, Ansible 8%, Monitoring 8%, GitHub 7%,
Helm 7%, professionalism 5%.

## Git and scope rules

- Never push, merge, or open a pull request — the user does that themselves.
- Stop before every commit: show the diff and wait for the explicit word
  "approved". Never chain a commit onto the end of a fix.
- Never `git add -A`, `git add .`, or `git add --all` — stage explicit paths
  only.
- Do not write documentation, config, or code the user did not ask for. If
  something seems missing, say so and wait.
- Do not work ahead into later project phases — one step at a time.
- Verify before claiming success: run it and show real output; if it was not
  executed, say so plainly.
- Commit messages in imperative mood, saying what changed and why.

## Reporting

After every change, report in this order and then stop:

1. A summary of **at most five lines** — what changed and why.
2. The diff.

No commit until the user approves.
