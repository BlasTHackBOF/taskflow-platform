terraform {
  # Partial configuration: a backend block cannot read variables, so the
  # bucket name and region live in backend.hcl (copy backend.hcl.example
  # after the bootstrap configuration has created the bucket). Initialise:
  #
  #   terraform init -backend-config=backend.hcl
  backend "s3" {}
}
