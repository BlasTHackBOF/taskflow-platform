variable "name_prefix" {
  type        = string
  description = "ADR-0003 prefix, e.g. taskflow-prod."
}

variable "operator_cidr" {
  type        = string
  description = "Operator workstation CIDR for SSH, Jenkins UI and k3s API."
}

variable "github_webhook_cidrs" {
  type        = list(string)
  description = "GitHub's published webhook source ranges."
}
