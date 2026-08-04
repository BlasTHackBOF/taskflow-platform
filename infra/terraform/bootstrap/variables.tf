variable "aws_region" {
  type        = string
  description = "Region for the state bucket; must match backend.hcl in the main configuration."
  default     = "us-east-1"
}

variable "project" {
  type        = string
  description = "Constant project prefix from ADR-0003."
  default     = "taskflow"
}

variable "environment" {
  type        = string
  description = "Environment segment from ADR-0003."
  default     = "prod"
}
