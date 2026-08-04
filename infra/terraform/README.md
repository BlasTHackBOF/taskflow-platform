# Terraform — what this stack costs

Design and state-backend decisions live in
[architecture.md](../../docs/architecture.md) and
[ADR-0006](../../docs/decisions/0006-s3-state-backend-with-native-locking.md).
This file records the money, because "Free Tier" does not mean free here.

On-demand rates, us-east-1, at the time of writing. A month is 730 hours.

| Line item | Rate | 24/7 month | Free Tier coverage |
| --- | --- | --- | --- |
| CI node (t3.small) | $0.0208/h | $15.18 | None — 1 GiB does not run Jenkins; this is the project's one deliberately paid resource |
| App node (t3.micro) | $0.0104/h | $7.59 | 750 h/month for 12 months on eligible accounts → $0 |
| Public IPv4 × 2 | $0.005/h each | $3.65 each, $7.30 both | 750 IPv4-hours/month — covers roughly one address running 24/7 |
| EBS gp3, 30 GB total | $0.08/GB-month | $2.40 | 30 GB allowance → $0 |
| S3 (tfstate + artifacts) | $0.023/GB-month | cents | 5 GB allowance |

Worst case, 24/7 with no Free Tier at all:
$15.18 + $7.59 + $7.30 + $2.40 = **$32.47/month**, plus S3 cents. On an
account with the legacy Free Tier: $15.18 + $3.65 = **$18.83/month**
(the t3.small plus the second public IPv4 address).

## The line most people forget

Since February 2024 AWS charges $0.005/hour for **every** public IPv4
address, including auto-assigned ones. Per running hour this stack costs
$0.0412, and $0.010 of that — about a quarter — is the two public IPs.
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

## Free Tier fine print

The 750-hour instance/IPv4 allowances above are the *legacy* Free Tier.
Accounts created after mid-July 2025 are on the credit-based free plan
instead ($100–200 in credits, no hourly allowances) — on such an account
every line above bills at the listed rate against the credits. Check
which plan the account is on before trusting the "→ $0" column.
