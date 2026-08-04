output "state_bucket" {
  value       = aws_s3_bucket.tfstate.bucket
  description = "Goes into backend.hcl of the main configuration."
}

output "state_bucket_region" {
  value       = var.aws_region
  description = "Goes into backend.hcl of the main configuration."
}
