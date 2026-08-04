# The public IPs feed the Ansible inventory in the next phase.

output "jenkins_public_ip" {
  value       = module.compute.jenkins_public_ip
  description = "CI node (taskflow-prod-ci-01) — Ansible inventory entry."
}

output "k3s_public_ip" {
  value       = module.compute.k3s_public_ip
  description = "Application node (taskflow-prod-k3s-01) — Ansible inventory entry."
}

output "jenkins_instance_id" {
  value       = module.compute.jenkins_instance_id
  description = "CI node instance ID — consumed by scripts/env-control.sh."
}

output "k3s_instance_id" {
  value       = module.compute.k3s_instance_id
  description = "Application node instance ID — consumed by scripts/env-control.sh."
}

output "aws_region" {
  value       = var.aws_region
  description = "Region every resource lives in — consumed by scripts/env-control.sh."
}

output "artifacts_bucket" {
  value       = module.storage.artifacts_bucket_name
  description = "Jenkins build artifact bucket."
}

output "ubuntu_ami_id" {
  value       = module.compute.ami_id
  description = "The Ubuntu 24.04 AMI the data source resolved (ADR-0001)."
}
