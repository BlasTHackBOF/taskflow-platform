output "ci_security_group_id" {
  value       = aws_security_group.ci.id
  description = "Attached to the Jenkins instance."
}

output "app_security_group_id" {
  value       = aws_security_group.app.id
  description = "Attached to the k3s instance."
}
