# Setup guide

How to run TaskFlow from a clean machine, in your own environment.

There are two paths. **Path A** runs the whole application stack locally and needs
nothing but Docker — no cloud account, no credentials, about three minutes.
**Path B** provisions the AWS infrastructure and needs your own AWS account.

No credential in this repository is real. Every secret-bearing file has a committed
`.example` twin listing the exact keys the system reads, with placeholder values. You
supply your own.

---

## Path A — local stack, no cloud account

```bash
git clone https://github.com/BlasTHackBOF/taskflow-platform.git
cd taskflow-platform
cp .env.example .env
docker compose up --build
```

The application is on `http://localhost:8000`.

The placeholder values in `.env.example` work as-is for local use. The database
password is only ever seen by a container on your own machine, and the whole stack is
removed with `docker compose down -v`.

### Verify it works

```bash
curl localhost:8000/healthz          # {"status":"ok"}
curl localhost:8000/readyz           # {"status":"ok","database":"ok"}
curl localhost:8000/metrics | head   # Prometheus exposition format

curl -X POST localhost:8000/api/v1/boards \
     -H 'Content-Type: application/json' \
     -d '{"key":"tf","name":"Platform"}'

curl -X POST localhost:8000/api/v1/tasks \
     -H 'Content-Type: application/json' \
     -d '{"board_id":1,"title":"First task"}'

curl localhost:8000/api/v1/tasks
```

Moving a task straight from `todo` to `done` is rejected, and the error names the
moves that are allowed:

```bash
curl -X PATCH localhost:8000/api/v1/tasks/1 \
     -H 'Content-Type: application/json' \
     -d '{"status":"done"}'
# 409  {"error":{"code":"invalid_transition","details":{"allowed":["blocked","in_progress"], ...
```

### Run the test suite

```bash
cd app
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
FLASK_ENV=testing .venv/bin/python -m pytest
.venv/bin/ruff check .
```

Expect 69 passing tests and coverage above 90%. A JUnit report lands in
`app/reports/junit.xml` — the same file the Jenkins pipeline consumes.

### Tear down

```bash
docker compose down -v      # -v also removes the database volume
```

---

## Path B — AWS infrastructure

### What you need first

| Tool | Minimum | Install |
|---|---|---|
| Terraform | 1.10 | HashiCorp apt repository — 1.10 is required for S3-native state locking |
| AWS CLI | v2 | `awscli-exe-linux-x86_64.zip` from AWS; the Ubuntu apt package is too old |
| Docker | any current | Docker Engine or Docker Desktop with WSL integration |
| Git, Python | 3.12+ | `apt install git python3-venv python3-pip` |

### Ansible

Ubuntu 24.04 blocks `pip install` outside a virtual environment (PEP 668), so
Ansible lives in its own venv:

    python3 -m venv ~/.venvs/ansible
    ~/.venvs/ansible/bin/pip install ansible
    ~/.venvs/ansible/bin/ansible-galaxy collection install -r ansible/requirements.yml

Run playbooks with the full path:

    cd ansible
    ~/.venvs/ansible/bin/ansible-playbook site.yml

### Credentials you supply

Nothing here is in the repository. Each is yours to create.

| What | Where to get it | Where it goes |
|---|---|---|
| AWS access key | IAM → Users → create a user → Security credentials → Create access key (CLI use case) | `aws configure`, stored in `~/.aws/credentials` |
| SSH key pair | `ssh-keygen -t ed25519 -f ~/.ssh/taskflow-operator` | Public half into `terraform.tfvars`; private half never leaves your machine |
| Your public IP | `curl -s ifconfig.me` | `terraform.tfvars` as `operator_cidr`, with `/32` |

Do not use the account root user. Create a dedicated IAM user.

> **Note on IAM scope.** This project's IAM user is given `AdministratorAccess` for
> simplicity. A production setup would scope it to EC2, IAM, S3 and Security Groups —
> the only four services used here. See *Known simplifications* in the README.

### Step 1 — configure the AWS CLI

```bash
aws configure          # access key, secret, region (us-east-1), output (json)
aws sts get-caller-identity
```

The second command must return your account id and the user ARN. If it fails, nothing
below will work.

### Step 2 — create the state bucket

Remote state lives in S3, but the bucket has to exist before Terraform can store state
in it. The `bootstrap` configuration solves that chicken-and-egg: it creates only the
bucket and keeps its own state local and committed.

```bash
cd infra/terraform/bootstrap
terraform init
terraform apply                    # 3 resources, effectively free
terraform output                   # note the bucket name
```

### Step 3 — configure the main stack

```bash
cd ..
cp backend.hcl.example backend.hcl
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:

```hcl
aws_region     = "us-east-1"
operator_cidr  = "YOUR.IP.HERE/32"                    # curl -s ifconfig.me
ssh_public_key = "ssh-ed25519 AAAA... your-comment"   # cat ~/.ssh/taskflow-operator.pub
```

Both files are gitignored. Only their `.example` twins are committed.

Edit `backend.hcl` so `bucket` matches the bootstrap output. If you used the default
project name it will already be correct.

### Step 4 — provision

```bash
terraform init -backend-config=backend.hcl
terraform plan
```

**Read the plan before applying.** Expect 23 resources. Confirm that every SSH rule
carries your own IP and not `0.0.0.0/0` — port 80 is the only thing that should be
open to the world.

```bash
terraform apply
```

Takes about a minute. The outputs include both public IPs.

### Step 5 — verify

```bash
ssh -i ~/.ssh/taskflow-operator ubuntu@$(terraform output -raw jenkins_public_ip)
```

An Ubuntu 24.04 banner means the key pair, the security group and the instance are all
correct. `exit` to leave.

`Connection refused` usually means the instance is still booting — wait a minute.
`Permission denied` means the public key in `terraform.tfvars` does not match the
private key you are offering.

---

## Daily operation

The environment is stopped when nobody is working on it. Compute billing stops with
the instances; EBS bills either way.

```bash
./scripts/env-control.sh start     # boot both nodes, print the new public IPs
./scripts/env-control.sh status    # state, type, IP and uptime
./scripts/env-control.sh stop      # shut down
```

**Public IPs change on every stop/start.** `terraform output` shows whatever was in
state at the last refresh, which is empty or stale the moment an instance stops. The
addresses printed by `start` are the record.

### Cost

| | Running | Stopped |
|---|---|---|
| Full environment | ≈ $32.47/month | ≈ $2.40/month |

Line items are in `infra/terraform/README.md`. The charge most people miss is public
IPv4: $0.005/hour per address, roughly a quarter of these instances' hourly cost.

Set a billing alert before you start: Billing → Budgets → Create budget.

### Tear down completely

```bash
cd infra/terraform
terraform destroy
```

Removes everything including the EBS volumes; the bill goes to zero. The state bucket
lives in the separate `bootstrap` configuration and is untouched.

To remove that too:

```bash
cd bootstrap
terraform destroy
```

---

## Troubleshooting

**`terraform apply` rejected the SSH key.** The value in `terraform.tfvars` must be the
complete contents of the `.pub` file on one line. Check with:

```bash
diff <(cat ~/.ssh/taskflow-operator.pub) \
     <(grep ssh_public_key terraform.tfvars | cut -d'"' -f2)
```

Silence means they match.

**SSH times out after a restart.** The IP changed. Run `./scripts/env-control.sh status`
for the current one. If it still fails, your own IP may have changed — re-run
`curl -s ifconfig.me`, update `operator_cidr`, and `terraform apply` again.

**The application container exits immediately.** Production configuration refuses to
start without an explicit `DATABASE_URL` or with a default `SECRET_KEY`. The error
names which one is missing. This is deliberate: a misconfigured deployment should fail
loudly rather than serve traffic against a throwaway database.

**`terraform init` fills the disk.** Each configuration downloads its own copy of the
AWS provider, around 650 MB. Share one copy:

```bash
mkdir -p ~/.terraform.d/plugin-cache
echo 'export TF_PLUGIN_CACHE_DIR=$HOME/.terraform.d/plugin-cache' >> ~/.bashrc
```

**On WSL, `df` lies.** It reports the virtual disk, not free space on the Windows
drive. Check the real figure from PowerShell with `Get-PSDrive C`.
