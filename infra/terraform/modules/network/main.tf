# Security groups live in the default VPC: creating a dedicated VPC adds
# nothing the project needs, and the permitted service list is EC2, IAM,
# Security Groups and S3 — no NAT gateways, so a private-subnet design is
# out of reach anyway.

data "aws_vpc" "default" {
  default = true
}

# --- CI node (Jenkins) ------------------------------------------------------

resource "aws_security_group" "ci" {
  name        = "${var.name_prefix}-ci-sg"
  description = "Jenkins CI node - operator access and GitHub webhooks only"
  vpc_id      = data.aws_vpc.default.id

  tags = {
    Name = "${var.name_prefix}-ci-sg"
  }
}

# SSH for the operator: Ansible provisioning and break-glass admin access,
# from the operator workstation only — never 0.0.0.0/0.
resource "aws_vpc_security_group_ingress_rule" "ci_ssh_operator" {
  security_group_id = aws_security_group.ci.id
  description       = "SSH from the operator workstation (Ansible, admin)"
  cidr_ipv4         = var.operator_cidr
  from_port         = 22
  to_port           = 22
  ip_protocol       = "tcp"
}

# The Jenkins web UI is for the operator alone; it is not a public service.
resource "aws_vpc_security_group_ingress_rule" "ci_ui_operator" {
  security_group_id = aws_security_group.ci.id
  description       = "Jenkins UI from the operator workstation"
  cidr_ipv4         = var.operator_cidr
  from_port         = 8080
  to_port           = 8080
  ip_protocol       = "tcp"
}

# GitHub webhook deliveries to /github-webhook/ trigger pipeline runs.
# One rule per published GitHub hook range; refresh the list from the
# `hooks` key of https://api.github.com/meta if deliveries start failing.
resource "aws_vpc_security_group_ingress_rule" "ci_webhook_github" {
  for_each = toset(var.github_webhook_cidrs)

  security_group_id = aws_security_group.ci.id
  description       = "GitHub webhook deliveries (api.github.com/meta hooks)"
  cidr_ipv4         = each.value
  from_port         = 8080
  to_port           = 8080
  ip_protocol       = "tcp"
}

# Outbound open: apt mirrors, GitHub checkouts, GHCR image pushes, and the
# k3s API on the application node.
resource "aws_vpc_security_group_egress_rule" "ci_all" {
  security_group_id = aws_security_group.ci.id
  description       = "All outbound (apt, GitHub, GHCR, k3s API)"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

# --- application node (k3s) -------------------------------------------------

resource "aws_security_group" "app" {
  name        = "${var.name_prefix}-app-sg"
  description = "k3s application node - public HTTP, restricted SSH and API"
  vpc_id      = data.aws_vpc.default.id

  tags = {
    Name = "${var.name_prefix}-app-sg"
  }
}

# SSH for the operator: Ansible provisioning and break-glass admin access.
resource "aws_vpc_security_group_ingress_rule" "app_ssh_operator" {
  security_group_id = aws_security_group.app.id
  description       = "SSH from the operator workstation (Ansible, admin)"
  cidr_ipv4         = var.operator_cidr
  from_port         = 22
  to_port           = 22
  ip_protocol       = "tcp"
}

# The application itself, served by Traefik ingress. The one port that is
# deliberately open to the world — this is the product.
resource "aws_vpc_security_group_ingress_rule" "app_http_public" {
  security_group_id = aws_security_group.app.id
  description       = "Public application traffic via Traefik ingress"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
}

# kubectl / helm from the operator workstation.
resource "aws_vpc_security_group_ingress_rule" "app_k3s_api_operator" {
  security_group_id = aws_security_group.app.id
  description       = "k3s API from the operator workstation (kubectl, helm)"
  cidr_ipv4         = var.operator_cidr
  from_port         = 6443
  to_port           = 6443
  ip_protocol       = "tcp"
}

# helm upgrade from the Jenkins pipeline — group-to-group, so it holds
# even when the CI node's public IP changes.
resource "aws_vpc_security_group_ingress_rule" "app_k3s_api_ci" {
  security_group_id            = aws_security_group.app.id
  description                  = "k3s API from the CI node (pipeline deploys)"
  referenced_security_group_id = aws_security_group.ci.id
  from_port                    = 6443
  to_port                      = 6443
  ip_protocol                  = "tcp"
}

# Outbound open: GHCR image pulls, apt, and S3 for database backups.
resource "aws_vpc_security_group_egress_rule" "app_all" {
  security_group_id = aws_security_group.app.id
  description       = "All outbound (GHCR pulls, apt, S3 backups)"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}
