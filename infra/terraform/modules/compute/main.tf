# Ubuntu 24.04 LTS (ADR-0001), resolved from Canonical's account through a
# data source — the AMI id is never hardcoded, so the configuration stays
# portable across regions at the cost of a plan diff when Canonical
# publishes a new image build.
data "aws_ami" "ubuntu_noble" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_key_pair" "operator" {
  key_name   = "${var.name_prefix}-operator-key"
  public_key = var.ssh_public_key
}

# CI node — Jenkins controller and build executor in one (t3.small: the
# project's one deliberately paid resource; 1 GiB does not run Jenkins).
resource "aws_instance" "jenkins" {
  ami                    = data.aws_ami.ubuntu_noble.id
  instance_type          = var.jenkins_instance_type
  key_name               = aws_key_pair.operator.key_name
  vpc_security_group_ids = [var.ci_security_group_id]
  iam_instance_profile   = var.instance_profile_name

  metadata_options {
    http_tokens = "required" # IMDSv2 only; no unauthenticated metadata reads
  }

  root_block_device {
    volume_type = "gp3"
    volume_size = var.jenkins_volume_gb
    encrypted   = true
  }

  tags = {
    Name = "${var.name_prefix}-ci-01"
  }
}

# Application node — k3s single-node cluster running the app, PostgreSQL
# and the monitoring stack.
resource "aws_instance" "k3s" {
  ami                    = data.aws_ami.ubuntu_noble.id
  instance_type          = var.k3s_instance_type
  key_name               = aws_key_pair.operator.key_name
  vpc_security_group_ids = [var.app_security_group_id]
  iam_instance_profile   = var.instance_profile_name

  metadata_options {
    http_tokens = "required" # IMDSv2 only
  }

  root_block_device {
    volume_type = "gp3"
    volume_size = var.k3s_volume_gb
    encrypted   = true
  }

  tags = {
    Name = "${var.name_prefix}-k3s-01"
  }
}
