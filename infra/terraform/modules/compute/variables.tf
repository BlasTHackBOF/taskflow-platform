variable "name_prefix" {
  type        = string
  description = "ADR-0003 prefix, e.g. taskflow-prod."
}

variable "ssh_public_key" {
  type        = string
  description = "OpenSSH public key for the operator key pair."
}

variable "instance_profile_name" {
  type        = string
  description = "IAM instance profile granting project S3 access."
}

variable "ci_security_group_id" {
  type        = string
  description = "Security group for the Jenkins node."
}

variable "app_security_group_id" {
  type        = string
  description = "Security group for the k3s node."
}

variable "jenkins_instance_type" {
  type        = string
  description = "Instance type for the CI node."
}

variable "k3s_instance_type" {
  type        = string
  description = "Instance type for the application node."
}

variable "jenkins_volume_gb" {
  type        = number
  description = "Root volume size for the CI node, in GB."
}

variable "k3s_volume_gb" {
  type        = number
  description = "Root volume size for the application node, in GB."
}
