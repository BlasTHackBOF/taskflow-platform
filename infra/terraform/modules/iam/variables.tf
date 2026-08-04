variable "name_prefix" {
  type        = string
  description = "ADR-0003 prefix, e.g. taskflow-prod."
}

variable "bucket_arns" {
  type        = list(string)
  description = "ARNs of the project buckets this role may read and write. Nothing outside this list is reachable."
}
