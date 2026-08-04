#!/usr/bin/env bash
#
# env-control.sh — start, stop and inspect the TaskFlow EC2 environment.
#
# The environment is billed by the hour and exists only while someone is
# working. Left running 24/7 it costs ≈$32.50/month; stopped it costs
# ≈$2.40/month (EBS only — the public IPv4 addresses are auto-assigned
# and released on stop). Itemised in infra/terraform/README.md.
#
# Public IPs CHANGE on every stop/start cycle. `start` prints the new
# ones; the addresses in `terraform output` go stale the moment an
# instance stops. Live AWS state, not Terraform state, is the address
# of record — this script never reads IPs from Terraform.
#
# Usage:
#   scripts/env-control.sh start           boot both nodes, wait, print new IPs
#   scripts/env-control.sh stop [--force]  stop both nodes (asks unless --force)
#   scripts/env-control.sh status          state, type, public IP, uptime

set -Eeuo pipefail

trap 'echo "env-control: line $LINENO: command failed: $BASH_COMMAND" >&2' ERR

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TF_DIR="$SCRIPT_DIR/../infra/terraform"

usage() {
  cat >&2 <<'EOF'
Usage: env-control.sh <subcommand>
  start           boot both nodes, wait until running, print the new public IPs
  stop [--force]  stop both nodes; asks for confirmation unless --force
  status          state, instance type, public IP and uptime per node
EOF
}

# die <problem> [<fix>] — every failure path names the problem and the fix.
die() {
  echo "env-control: $1" >&2
  [[ -n "${2:-}" ]] && echo "  fix: $2" >&2
  exit 1
}

check_prereqs() {
  command -v aws >/dev/null ||
    die "aws CLI not found on PATH" \
        "install AWS CLI v2: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
  command -v terraform >/dev/null ||
    die "terraform not found on PATH" \
        "install Terraform >= 1.10: https://developer.hashicorp.com/terraform/install"
  aws sts get-caller-identity --query Account --output text >/dev/null 2>&1 ||
    die "AWS credentials are missing, invalid or expired" \
        "run 'aws configure' (or renew the session token), then retry"
}

# tf_output <name> — read one Terraform output, or explain why state is
# unreachable. Instance IDs come from here and are never hardcoded.
tf_output() {
  local name=$1 val
  if ! val=$(terraform -chdir="$TF_DIR" output -raw "$name" 2>/dev/null) || [[ -z "$val" ]]; then
    die "cannot read Terraform output '$name' — the S3 state backend is not reachable from this checkout" \
        "in infra/terraform: copy backend.hcl.example to backend.hcl, run 'terraform init -backend-config=backend.hcl', and confirm the infrastructure has been applied"
  fi
  printf '%s' "$val"
}

# describe — one tab-separated row per instance:
# name  id  state  type  public-ip(None when stopped)  launch-time
describe() {
  aws ec2 describe-instances --region "$REGION" --instance-ids "${IDS[@]}" \
    --query 'Reservations[].Instances[].[Tags[?Key==`Name`]|[0].Value, InstanceId, State.Name, InstanceType, PublicIpAddress, LaunchTime]' \
    --output text
}

cmd_status() {
  local name id state type ip launch uptime secs
  printf '%-22s %-20s %-10s %-9s %-16s %s\n' NAME ID STATE TYPE "PUBLIC IP" UPTIME
  while IFS=$'\t' read -r name id state type ip launch; do
    uptime="-"
    if [[ "$state" == "running" ]]; then
      secs=$(( $(date +%s) - $(date -d "$launch" +%s) ))
      printf -v uptime '%dh %02dm' $(( secs / 3600 )) $(( secs % 3600 / 60 ))
    fi
    [[ "$ip" == "None" || -z "$ip" ]] && ip="-"
    printf '%-22s %-20s %-10s %-9s %-16s %s\n' "$name" "$id" "$state" "$type" "$ip" "$uptime"
  done < <(describe)
}

print_ips() {
  local name ip _
  echo "Public IPs (new on every start — update anything that holds the old ones):"
  while IFS=$'\t' read -r name _ _ _ ip _; do
    [[ "$ip" == "None" || -z "$ip" ]] && ip="(not assigned yet)"
    printf '  %-22s %s\n' "$name" "$ip"
  done < <(describe)
}

cmd_start() {
  local id state _ to_start=()
  while IFS=$'\t' read -r _ id state _; do
    [[ "$state" == "running" ]] || to_start+=("$id")
  done < <(describe)

  if (( ${#to_start[@]} == 0 )); then
    echo "Both instances are already running."
  else
    echo "Starting: ${to_start[*]}"
    aws ec2 start-instances --region "$REGION" --instance-ids "${to_start[@]}" --output text >/dev/null
    echo "Waiting until they are running (typically under a minute)..."
    aws ec2 wait instance-running --region "$REGION" --instance-ids "${to_start[@]}"
    echo "Running."
  fi
  echo
  print_ips
}

cmd_stop() {
  local force=${1:-} id state _ to_stop=() answer
  [[ -z "$force" || "$force" == "--force" ]] ||
    die "unknown option '$force'" "the only option for stop is --force"

  while IFS=$'\t' read -r _ id state _; do
    [[ "$state" == "stopped" ]] || to_stop+=("$id")
  done < <(describe)

  if (( ${#to_stop[@]} == 0 )); then
    echo "Both instances are already stopped."
    return
  fi

  if [[ "$force" != "--force" ]]; then
    echo "About to stop: ${to_stop[*]}"
    echo "Public IPs will be released; the next start assigns new ones."
    read -r -p "Stop them? [y/N] " answer
    if [[ ! "$answer" =~ ^[Yy]$ ]]; then
      echo "Aborted — nothing was stopped."
      exit 1
    fi
  fi

  aws ec2 stop-instances --region "$REGION" --instance-ids "${to_stop[@]}" --output text >/dev/null
  echo "Waiting until they are stopped..."
  aws ec2 wait instance-stopped --region "$REGION" --instance-ids "${to_stop[@]}"
  echo "Stopped. Billing is now EBS only (≈\$2.40/month)."
}

main() {
  local cmd=${1:-}
  case "$cmd" in
    start|stop|status) ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 1 ;;
  esac

  check_prereqs
  REGION=$(tf_output aws_region)
  IDS=( "$(tf_output jenkins_instance_id)" "$(tf_output k3s_instance_id)" )

  case "$cmd" in
    start)  cmd_start ;;
    stop)   cmd_stop "${2:-}" ;;
    status) cmd_status ;;
  esac
}

main "$@"
