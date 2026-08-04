variable "aws_region" {
  type        = string
  description = "AWS region for every resource in this configuration."
  default     = "us-east-1"
}

variable "project" {
  type        = string
  description = "Constant project prefix from ADR-0003; never varies."
  default     = "taskflow"
}

variable "environment" {
  type        = string
  description = "Environment segment from ADR-0003."
  default     = "prod"
}

variable "operator_cidr" {
  type        = string
  description = "The operator workstation's IP as a /32 CIDR. Grants SSH, the Jenkins UI and the k3s API. Never a broad range."

  validation {
    condition     = can(cidrhost(var.operator_cidr, 0)) && var.operator_cidr != "0.0.0.0/0"
    error_message = "operator_cidr must be a valid CIDR block and must never be 0.0.0.0/0."
  }
}

variable "ssh_public_key" {
  type        = string
  description = "OpenSSH public key material for the operator key pair. The private key never touches this repository."
}

variable "github_webhook_cidrs" {
  type        = list(string)
  description = "GitHub's published webhook source ranges. Refresh from the `hooks` key of https://api.github.com/meta when deliveries start failing."
  default = [
    "192.30.252.0/22",
    "185.199.108.0/22",
    "140.82.112.0/20",
    "143.55.64.0/20",
  ]
}

variable "jenkins_instance_type" {
  type        = string
  description = "CI node type. t3.small is NOT Free Tier — Jenkins plus a build simply do not fit in 1 GiB. This is the project's main paid resource."
  default     = "t3.small"
}

variable "k3s_instance_type" {
  type        = string
  description = "Application node type. t3.micro sits inside the Free Tier 750 h/month allowance on eligible accounts."
  default     = "t3.micro"
}

variable "jenkins_volume_gb" {
  type        = number
  description = "CI node root volume (gp3). Together with k3s_volume_gb this should stay at or under the 30 GB Free Tier EBS allowance."
  default     = 20
}

variable "k3s_volume_gb" {
  type        = number
  description = "Application node root volume (gp3). See jenkins_volume_gb for the shared 30 GB ceiling."
  default     = 10
}
