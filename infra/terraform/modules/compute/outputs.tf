output "jenkins_public_ip" {
  value       = aws_instance.jenkins.public_ip
  description = "Public IP of taskflow-prod-ci-01."
}

output "k3s_public_ip" {
  value       = aws_instance.k3s.public_ip
  description = "Public IP of taskflow-prod-k3s-01."
}

output "ami_id" {
  value       = data.aws_ami.ubuntu_noble.id
  description = "Resolved Ubuntu 24.04 AMI (ADR-0001)."
}
