# Bootstrap: the one bucket that has to exist before Terraform can store
# remote state anywhere. This configuration deliberately keeps its OWN
# state local, in this directory, committed to git — the state describes
# a single bucket, contains no secrets, and solving its storage with the
# bucket it creates would be circular. See ADR-0006.
#
# Run once per AWS account:
#   terraform init && terraform apply
# then commit the resulting terraform.tfstate (a .gitignore exception
# allows exactly this file).

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

resource "aws_s3_bucket" "tfstate" {
  bucket = "${var.project}-${var.environment}-tfstate"

  # Losing this bucket means losing every workspace's state at once.
  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name = "${var.project}-${var.environment}-tfstate"
  }
}

# Versioning is the recovery story: with no DynamoDB on the permitted
# service list, a corrupted or clobbered state file is rolled back by
# restoring the previous object version.
resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
