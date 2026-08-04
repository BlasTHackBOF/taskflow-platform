# Terraform — what this stack costs

Design and state-backend decisions live in
[architecture.md](../../docs/architecture.md) and
[ADR-0006](../../docs/decisions/0006-s3-state-backend-with-native-locking.md).
This file records the money, because "Free Tier" does not mean free here.

On-demand rates, us-east-1, at the time of writing. A month is 730 hours.

| Line item | Rate | 24/7 month | Free Tier coverage |
| --- | --- | --- | --- |
| CI node (t3.small) | $0.0208/h | $15.18 | None — 1 GiB does not run Jenkins |
| App node (t3.small) | $0.0208/h | $15.18 | None — grown from the Free Tier t3.micro, whose 911 MiB could not hold k3s (ADR-0008) |
| Public IPv4 × 2 | $0.005/h each | $3.65 each, $7.30 both | 750 IPv4-hours/month — covers roughly one address running 24/7 |
| EBS gp3, 30 GB total | $0.08/GB-month | $2.40 | 30 GB allowance → $0 |
| S3 (tfstate + artifacts) | $0.023/GB-month | cents | 5 GB allowance |

Worst case, 24/7 with no Free Tier at all:
$15.18 + $15.18 + $7.30 + $2.40 = **$40.06/month**, plus S3 cents. On
an account with the legacy Free Tier: $15.18 + $15.18 + $3.65 =
**$34.01/month** — the instance allowance only ever covered t3.micro,
so since the app node grew (ADR-0008) both nodes bill in full and only
one public IPv4 and the EBS remain covered.

## The line most people forget

Since February 2024 AWS charges $0.005/hour for **every** public IPv4
address, including auto-assigned ones. Per running hour this stack costs
$0.0516, and $0.010 of that — about a fifth — is the two public IPs.
Two things follow:

- **Stopping the instances stops the IPv4 charge too**, because both
  nodes use auto-assigned addresses, which are released on stop. This is
  deliberate: an Elastic IP would keep billing $0.005/h *while the
  instance is stopped* — the stable address would cost more than the
  idle compute. The price of that choice is that public IPs change on
  every start, which is why CI→k3s access is granted group-to-group in
  the security groups rather than by address.
- With the stop-between-sessions discipline (architecture.md), the only
  charge that accrues around the clock is EBS: at most $2.40/month.

## Daily workflow

The environment exists only while someone is working:

    scripts/env-control.sh start    # begin a session — boots both nodes, prints the NEW public IPs
    scripts/env-control.sh status   # state, type, public IP and uptime at a glance
    scripts/env-control.sh stop     # end a session — asks first; --force skips the prompt

Every start assigns fresh public IPs, and `terraform output` keeps
showing whatever addresses were in state at the last refresh — empty or
stale the moment an instance stops. Treat the script's printed IPs as
the address of record, and re-point anything that held the old ones
(SSH sessions, the Ansible inventory in the next phase). The CI→k3s
security-group rule is group-to-group precisely so it survives this.

## Free Tier fine print

The 750-hour instance/IPv4 allowances above are the *legacy* Free Tier.
Accounts created after mid-July 2025 are on the credit-based free plan
instead ($100–200 in credits, no hourly allowances) — on such an account
every line above bills at the listed rate against the credits. Check
which plan the account is on before trusting the "→ $0" column.
