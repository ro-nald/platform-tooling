# Platform Tooling

A collection of Python CLIs that automate platform engineering workflows — provisioning shared Terraform state backends and onboarding engineering teams to a shared-services AWS environment without manual coordination.

---

## Problem Statement

Scaling infrastructure across multiple teams introduces friction at two well-known points:

1. **Terraform state setup** — every new service needs an S3 bucket configured correctly (versioning, encryption, public-access blocked) and the bucket name wired into CI.
2. **Team onboarding** — teams need to discover shared platform outputs (ECR repositories, IAM roles, state bucket names) and configure their own repositories with the right variables and secrets before they can deploy anything.

This project replaces those manual steps with idempotent, auditable CLI commands.

---

## Tools

### `setup-tf`

Provisions an S3 bucket for Terraform remote state and registers the bucket name as a GitHub Actions variable. Handles the AWS `us-east-1` region special case and enforces consistent bucket naming (`<prefix>-tfstate-<env>`).

### `team-bootstrap`

Reads shared-services outputs directly from AWS SSM Parameter Store and uses them to:

- Generate a `backend.hcl` file scoped to the team's unique state key
- Optionally generate `shared-services.auto.tfvars` with resolved ECR URLs and IAM role ARNs
- Write GitHub Actions variables and secrets to the team's repository

---

## Technologies

| Category | Technology |
| --- | --- |
| Language | Python 3.13+ |
| CLI framework | [Typer](https://typer.tiangolo.com/) |
| AWS SDK | [boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html) |
| GitHub API | [PyGitHub](https://pygithub.readthedocs.io/) |
| Terminal UI | [Rich](https://rich.readthedocs.io/) |
| Package manager | [uv](https://docs.astral.sh/uv/) |
| AWS services | S3, SSM Parameter Store, STS, IAM |
| IaC tooling | Terraform ≥ 1.10 |
| CI platform | GitHub Actions |

---

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) installed
- AWS credentials configured (environment variables, `~/.aws/credentials`, or an instance profile)
- A `GITHUB_TOKEN` with `repo` scope exported in your shell (required for GitHub commands)
- Terraform ≥ 1.10 (required only for `team-bootstrap check`)

---

## Installation

```bash
git clone <repo-url>
cd platform-tooling
uv sync
```

---

## Usage

### setup-tf

#### `backend` — Provision an S3 state bucket

Creates the bucket if it does not exist, enables versioning, and blocks all public access.

```bash
uv run setup-tf/main.py backend <bucket-prefix> [env] [region]
```

| Argument | Default | Description |
| --- | --- | --- |
| `bucket-prefix` | — | Prefix for the bucket name (e.g. `my-org`) |
| `env` | `dev` | Environment name appended to the bucket name |
| `region` | `us-east-1` | AWS region for the bucket |

The resulting bucket name follows the pattern `<bucket-prefix>-tfstate-<env>`.

```bash
# Create my-org-tfstate-dev in us-east-1
uv run setup-tf/main.py backend my-org

# Create my-org-tfstate-prod in eu-west-2
uv run setup-tf/main.py backend my-org prod eu-west-2
```

#### `github` — Register the bucket name in GitHub Actions

Writes the bucket name as a repository variable (`TF_BACKEND_BUCKET_<ENV>`), making it available to CI workflows without hardcoding.

```bash
uv run setup-tf/main.py github <owner/repo> <bucket-prefix> <env>
```

```bash
export GITHUB_TOKEN=<your-token>
uv run setup-tf/main.py github my-org/my-repo my-org dev
```

---

### team-bootstrap

All commands read AWS credentials from the environment and accept `SSM_NAMESPACE`, `TF_STATE_BUCKET`, and `AWS_REGION` as environment variables to avoid repeating them on every invocation.

```bash
export SSM_NAMESPACE=<platform-namespace-guid>
export TF_STATE_BUCKET=<shared-services-state-bucket>
export AWS_REGION=ap-east-1
export GITHUB_TOKEN=<your-token>
```

#### `run` — Full bootstrap sequence

Runs `init` then `configure-github` in one command. The recommended starting point for new teams.

```bash
uv run team-bootstrap/main.py run --team-slug team-payments
```

#### `init` — Generate Terraform backend config

Writes `backend.hcl` with the team's unique, scoped state key. Optionally also writes `shared-services.auto.tfvars`.

```bash
uv run team-bootstrap/main.py init \
  --team-slug team-payments \
  --output-dir ./terraform
```

```bash
# Also generate shared-services.auto.tfvars
uv run team-bootstrap/main.py init \
  --team-slug team-payments \
  --output-dir ./terraform \
  --generate-tfvars
```

After running, initialise Terraform with:

```bash
terraform init -backend-config=backend.hcl
```

#### `configure-github` — Write CI variables and secrets

Reads IAM role ARNs and other values from SSM and writes them to the team's GitHub repository.

| GitHub variable | Value |
| --- | --- |
| `TF_STATE_BUCKET` | Shared state bucket name |
| `SSM_NAMESPACE` | Platform namespace GUID |
| `AWS_REGION` | AWS region |
| `TEAM_STATE_GUID` | Team-scoped state GUID |
| `DEPLOYER_ROLE_ARN` _(secret)_ | IAM role for deployments |
| `ECR_PUSH_ROLE_ARN` _(secret)_ | IAM role for ECR image pushes |

```bash
uv run team-bootstrap/main.py configure-github --team-slug team-payments
```

#### `check` — Verify prerequisites

Checks AWS credentials are valid and that Terraform ≥ 1.10 is installed.

```bash
uv run team-bootstrap/main.py check
```

#### `show-outputs` — Inspect SSM parameters

Displays all shared-services outputs published to the SSM namespace in a formatted table.

```bash
uv run team-bootstrap/main.py show-outputs
```

#### `status` — Show current bootstrap state

Reports which generated files exist locally and whether the SSM namespace is reachable.

```bash
uv run team-bootstrap/main.py status
```
