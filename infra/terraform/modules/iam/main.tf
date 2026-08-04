# One role for the project's EC2 nodes, scoped to the project's own S3
# buckets and nothing else. Instances get AWS access through this profile;
# no static access key is ever placed on a server.

data "aws_iam_policy_document" "assume_ec2" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "node" {
  name               = "${var.name_prefix}-node-role"
  assume_role_policy = data.aws_iam_policy_document.assume_ec2.json

  tags = {
    Name = "${var.name_prefix}-node-role"
  }
}

data "aws_iam_policy_document" "s3_project" {
  statement {
    sid       = "ListProjectBuckets"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = var.bucket_arns
  }

  statement {
    sid       = "ReadWriteProjectObjects"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = [for arn in var.bucket_arns : "${arn}/*"]
  }
}

resource "aws_iam_role_policy" "s3_project" {
  name   = "${var.name_prefix}-s3-project"
  role   = aws_iam_role.node.id
  policy = data.aws_iam_policy_document.s3_project.json
}

resource "aws_iam_instance_profile" "node" {
  name = "${var.name_prefix}-node-profile"
  role = aws_iam_role.node.name

  tags = {
    Name = "${var.name_prefix}-node-profile"
  }
}
