output "artifacts_bucket_name" {
  value       = aws_s3_bucket.artifacts.bucket
  description = "Bucket the Jenkins pipeline writes build artifacts to."
}

output "artifacts_bucket_arn" {
  value       = aws_s3_bucket.artifacts.arn
  description = "Scopes the IAM instance policy."
}
