provider "aws" {
  region = var.aws_region

  # ADR-0003: every resource carries these three tags; default_tags means
  # no resource can be created without them.
  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
