output "instance_profile_name" {
  value       = aws_iam_instance_profile.node.name
  description = "Attach to EC2 instances that need the project's S3 access."
}
