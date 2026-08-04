#!/usr/bin/env bash
#
# Dynamic inventory: identity from Terraform, addresses from live AWS.
#
# Terraform outputs are the source of WHICH instances belong to the
# project (instance IDs and region — nothing is hardcoded here). The
# public addresses are deliberately NOT read from Terraform: they change
# on every stop/start and the state only holds whatever was true at the
# last refresh. Live DescribeInstances is the address of record — the
# same doctrine as scripts/env-control.sh. Trade-offs in ADR-0007.

set -Eeuo pipefail

die() { echo "inventory/terraform.sh: $*" >&2; exit 1; }

# Ansible calls --host <name> for per-host vars; everything is in _meta.
[[ "${1:---list}" == "--host" ]] && { echo '{}'; exit 0; }

TF_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../infra/terraform" && pwd)"

command -v terraform >/dev/null || die "terraform not found on PATH"
command -v aws >/dev/null || die "aws CLI not found on PATH"

region=$(terraform -chdir="$TF_DIR" output -raw aws_region 2>/dev/null) ||
  die "cannot read Terraform outputs — in infra/terraform run: terraform init -backend-config=backend.hcl"
ci_id=$(terraform -chdir="$TF_DIR" output -raw jenkins_instance_id)
app_id=$(terraform -chdir="$TF_DIR" output -raw k3s_instance_id)

declare -A ip
while read -r id addr; do ip["$id"]="$addr"; done < <(
  aws ec2 describe-instances --region "$region" --instance-ids "$ci_id" "$app_id" \
    --query 'Reservations[].Instances[].[InstanceId, PublicIpAddress]' --output text
)

for id in "$ci_id" "$app_id"; do
  [[ "${ip[$id]:-None}" == "None" || -z "${ip[$id]:-}" ]] &&
    die "instance $id has no public address (stopped?) — start the environment: scripts/env-control.sh start"
done

cat <<EOF
{
  "ci":  { "hosts": ["taskflow-prod-ci-01"] },
  "app": { "hosts": ["taskflow-prod-k3s-01"] },
  "_meta": {
    "hostvars": {
      "taskflow-prod-ci-01":  { "ansible_host": "${ip[$ci_id]}",  "ec2_instance_id": "$ci_id" },
      "taskflow-prod-k3s-01": { "ansible_host": "${ip[$app_id]}", "ec2_instance_id": "$app_id" }
    }
  }
}
EOF
