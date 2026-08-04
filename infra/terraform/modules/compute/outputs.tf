output "jenkins_public_ip" {
  value       = aws_instance.jenkins.public_ip
  description = "Public IP of taskflow-prod-ci-01."
}

output "k3s_public_ip" {
  value       = aws_instance.k3s.public_ip
  description = "Public IP of taskflow-prod-k3s-01."
}

output "jenkins_instance_id" {
  value       = aws_instance.jenkins.id
  description = "Instance ID of taskflow-prod-ci-01 (consumed by scripts/env-control.sh)."
}

output "k3s_instance_id" {
  value       = aws_instance.k3s.id
  description = "Instance ID of taskflow-prod-k3s-01 (consumed by scripts/env-control.sh)."
}

output "ami_id" {
  value       = data.aws_ami.ubuntu_noble.id
  description = "Resolved Ubuntu 24.04 AMI (ADR-0001)."
}
