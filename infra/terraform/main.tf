locals {
  # ADR-0003: taskflow-<environment>-<component>[-<index>]
  name_prefix = "${var.project}-${var.environment}"
}

module "network" {
  source = "./modules/network"

  name_prefix          = local.name_prefix
  operator_cidr        = var.operator_cidr
  github_webhook_cidrs = var.github_webhook_cidrs
}

module "storage" {
  source = "./modules/storage"

  name_prefix = local.name_prefix
}

module "iam" {
  source = "./modules/iam"

  name_prefix = local.name_prefix
  bucket_arns = [module.storage.artifacts_bucket_arn]
}

module "compute" {
  source = "./modules/compute"

  name_prefix           = local.name_prefix
  ssh_public_key        = var.ssh_public_key
  instance_profile_name = module.iam.instance_profile_name
  ci_security_group_id  = module.network.ci_security_group_id
  app_security_group_id = module.network.app_security_group_id
  jenkins_instance_type = var.jenkins_instance_type
  k3s_instance_type     = var.k3s_instance_type
  jenkins_volume_gb     = var.jenkins_volume_gb
  k3s_volume_gb         = var.k3s_volume_gb
}
