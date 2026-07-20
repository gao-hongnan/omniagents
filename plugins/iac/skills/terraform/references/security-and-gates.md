# Security & Gates

Terraform ≥ 1.11 OSS CLI is the floor for every rule in this file. S3
native locking (`use_lockfile`) and write-only `*_wo` arguments both
went GA in 1.11, and the secrets and state posture below assume both
are available. Track the currently supported release line at
https://endoflife.date/terraform and raise the floor deliberately —
never let it drift by omission. This reference expands the Default
posture bullets in the parent `SKILL.md` with the full pinning table,
working HCL sketches, and the exact gate sequence; it does not restate
them.

## Pinning matrix

Every constraint in this table exists to stop one specific failure
mode: an unreviewed provider or module upgrade landing mid-apply. Pin
tighter the closer a config sits to the root, and loosen only in
reusable modules so callers can converge on their own provider
version.

| Layer                             | Constraint            | Syntax                            | Why                                                                   |
| ---------------------------------- | ---------------------- | ----------------------------------- | ----------------------------------------------------------------------- |
| Root `required_version`           | Floor, not a range you drift | `>= 1.11`                    | matches the write-only-args / native-locking floor above             |
| Root provider version              | Pessimistic minor      | `~> 5.60`                          | roots are leaf configs — pin tight, bump on purpose                   |
| Reusable-module provider version   | Minimum only            | `>= 5.0`                           | lets every caller converge on its own provider pin                    |
| Registry module source              | Exact release           | `version = "5.16.0"`               | semver `x.y.z`; never `~>` on a module `version` argument             |
| Git module source                   | Tag or commit SHA       | `?ref=v3.2.0` or `?ref=<full-sha>` | never `?ref=main` — a branch moves under you between plan and apply   |
| Lockfile                            | Commit for every root   | `.terraform.lock.hcl`              | run `terraform providers lock` for every CI platform you deploy from  |

The same two constraints look different depending on which side of the
root/module boundary you're on:

```hcl
# root: environments/prod/versions.tf — pin tight
terraform {
  required_version = ">= 1.11"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }
}

# reusable module: modules/redis/versions.tf — declare a floor only
terraform {
  required_version = ">= 1.11"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0" # no ~>, no provider {} block
    }
  }
}
```

Root `required_version` is a floor, not a target — set it once per
root and only raise it after verifying the new floor's behavior
change, per the HashiCorp Style Guide —
https://developer.hashicorp.com/terraform/language/style. Reusable
modules declare only a minimum `required_version` too, and do not pin
a provider version beyond `>=`: a shared module that pins `~>` blocks
every caller stuck on an older provider release. See Standard Module
Structure —
https://developer.hashicorp.com/terraform/language/modules/develop/structure.

Registry and git module sourcing follow the discipline the community
module ecosystem already enforces — https://github.com/terraform-aws-modules
tags every release semver and expects consumers to pin an exact
`version`; the same org's git-sourced examples always carry a `?ref=`
tag, never a bare branch. The distilled community conventions restate
this as a hard rule — https://www.terraform-best-practices.com.
Gruntwork's style guide adds the operational reason: an unpinned
module source turns `terraform init` into a moving target that
silently changes behavior between two runs of the same pipeline —
https://docs.gruntwork.io/guides/style/terraform-style-guide/.

Commit `.terraform.lock.hcl` for every root — it records the exact
provider version and package hash Terraform resolved, so a second
`init` on a different machine cannot silently pull a different build.
Run `terraform providers lock` (not a bare `init`) whenever CI runs on
a different platform than the machine that generated the lockfile:

```bash
terraform providers lock \
  -platform=linux_amd64 \
  -platform=darwin_arm64 \
  -platform=darwin_amd64
```

A lockfile generated only on a developer's laptop is missing the
hashes CI needs and will fail `terraform init` there — generate it for
every platform in your combined CI-plus-local matrix, not only the one
you happen to run.

Automate the bump cycle with Renovate over Dependabot. Both can open
PRs for provider and module version bumps, but Renovate is the deeper
tool for a Terraform estate: its `terraform` manager reads
`required_providers` and module `source`/`version` blocks together,
its `terragrunt` manager understands `terragrunt.hcl` version pins in
the same run, and `lockFileMaintenance` refreshes `.terraform.lock.hcl`
on a schedule instead of leaving it to drift until the next manual
`providers lock`. Dependabot's Terraform ecosystem support only opens
version-bump PRs for providers and modules — no lockfile-maintenance
mode, no terragrunt awareness — so a Dependabot-only estate still needs
a separate scheduled `providers lock` job. The AWS Prescriptive
Guidance backend and community notes make the same dependency-hygiene
argument from the backend-configuration side —
https://docs.aws.amazon.com/prescriptive-guidance/latest/terraform-aws-provider-best-practices/backend.html
and
https://docs.aws.amazon.com/prescriptive-guidance/latest/terraform-aws-provider-best-practices/community.html.

## Secrets

Ephemeral resources and write-only arguments are the default secrets
mechanism as of 1.10/1.11 — not a hardening option layered on top of
plaintext values. An ephemeral resource's result is never written to
state or plan output, and a write-only `*_wo` argument is accepted by
the provider but never persisted anywhere Terraform reads back from.
See the ephemeral values docs —
https://developer.hashicorp.com/terraform/language/manage-sensitive-data/ephemeral.
Reach for a write-only argument first for any resource that offers one
(RDS/Aurora master passwords, ElastiCache `auth_token`, most
provider-native credential arguments); reach for a full ephemeral
resource when the value itself must come from an ephemeral data source
— a short-lived Vault or SSM token — rather than a static input
variable.

A write-only password argument always ships with a matching
`*_wo_version` counter — bump the counter to force Terraform to accept
a new value, since the write-only value itself never appears in a diff
Terraform can compare against:

```hcl
variable "db_password_wo" {
  type        = string
  description = "RDS master password; write-only, never stored in state."
  sensitive   = true
  ephemeral   = true
}

resource "aws_db_instance" "this" {
  identifier          = var.name
  password_wo         = var.db_password_wo
  password_wo_version = 1 # bump this integer to rotate the password
}
```

The ephemeral half of the same pattern covers the case where the
secret's *source* is itself short-lived — a Vault dynamic credential,
an ephemeral SSM parameter read — rather than a value you pass in
directly:

```hcl
ephemeral "vault_kv_secret_v2" "db" {
  mount = "secret"
  name  = "prod/db/password"
}

resource "aws_db_instance" "this" {
  identifier          = var.name
  password_wo         = ephemeral.vault_kv_secret_v2.db.data["password"]
  password_wo_version = var.db_password_wo_version
}
```

Terraform reads the ephemeral resource during plan and apply, feeds
its value straight into the write-only argument, and discards it
afterward — the secret exists in memory for one operation and in
neither state nor plan output at any point.

Rotation is then a one-line change: bump `password_wo_version` and
supply the new value at apply time (a CI secret, `TF_VAR_`, or an
ephemeral data source) — Terraform recomputes the resource because the
version counter changed, not because it can see the old and new values
differ.

Where a resource has no write-only argument at all, do not fall back
to a plain `variable` marked `sensitive = true` and call it solved.
Reference the secret at runtime instead — an SSM `SecureString`
parameter, a Secrets Manager ARN, or a Vault path the application
resolves at boot — and let Terraform manage only the resource or
policy that grants access, never the secret value itself. `sensitive =
true` redacts a value from CLI output and plan diffs; it does not keep
the value out of state, and it does not stop anyone with `terraform
state show` access from reading it in plain text. Treat the entire
state file as a secret regardless of which individual values inside it
are marked sensitive — the Google Cloud security best practices reach
the same conclusion from the GCP side —
https://docs.cloud.google.com/docs/terraform/best-practices/security.

Never commit a plaintext secret in a `.tfvars` file, including
`terraform.tfvars` — a committed `.tfvars` is source-controlled,
mirrored to every clone, and outlives any later rotation. If a value
must be supplied as a variable rather than a runtime reference, supply
it out-of-band (`TF_VAR_`, a CI secret store, or a gitignored
`*.auto.tfvars`) and keep the tracked `.tfvars.example` free of real
values.

## Network least privilege

No security group or network ACL rule opens ingress on `0.0.0.0/0`
except a public load balancer's `443`/`80` listener you've
deliberately decided should be internet-facing. Every other ingress
rule references a security group, not a CIDR block:

```hcl
resource "aws_security_group_rule" "app_from_lb" {
  type                     = "ingress"
  from_port                = 8080
  to_port                  = 8080
  protocol                 = "tcp"
  security_group_id        = aws_security_group.app.id
  source_security_group_id = aws_security_group.lb.id # not a CIDR
}
```

A CIDR-scoped rule that happens to be narrow today (a single `/32`, a
VPC CIDR) has no mechanism to stay narrow as the network grows —
someone adds a peered VPC or a second subnet and the rule silently
widens. A security-group reference stays correct because it tracks the
actual member instances, not an address range that outlives its
original intent. This is the same load-bearing rule the AWS
Prescriptive Guidance structure doc calls out —
https://docs.aws.amazon.com/prescriptive-guidance/latest/terraform-aws-provider-best-practices/structure.html
— and the AWS Integration & Automation team's standards repo encodes
as a default module convention —
https://aws-ia.github.io/standards-terraform/.

Treat egress-all (`0.0.0.0/0` on every port) as a smell to justify in
a PR description, not a default copied from the last module. Scope
egress to the ports and destinations the workload actually calls —
package registries, the database security group, an external API's
fixed IP range — and widen only when a specific outbound call needs
it. The Google Cloud security best practices reach the same
default-deny posture from the GCP firewall-rule side —
https://docs.cloud.google.com/docs/terraform/best-practices/security.

Lock down the VPC's default security group too — every VPC ships one,
it is attached implicitly to anything that doesn't specify a group,
and it defaults to open. Manage it explicitly with no rules at all so
nothing can accidentally inherit access by omission:

```hcl
resource "aws_default_security_group" "this" {
  vpc_id = aws_vpc.this.id
  # no ingress, no egress — force every workload onto a named SG
}
```

Apply the same reasoning to network ACLs at the subnet layer: NACLs
are stateless and easy to get wrong, so use them as a coarse
defense-in-depth backstop (deny known-bad ranges, deny cross-tier
traffic) rather than the primary enforcement point — security groups
stay the primary control because they are stateful and resource-scoped.

## Tags and encryption

Set `default_tags` on the root AWS provider block, not on every
resource — everything created under that provider inherits the set
without repeating it:

```hcl
provider "aws" {
  default_tags {
    tags = {
      owner       = var.owner
      environment = var.environment
      cost-center = var.cost_center
      managed-by  = "terraform"
    }
  }
}
```

Reserve resource-level `tags` blocks for genuine per-resource extras (a
`Name` tag, a backup-schedule tag specific to one volume) — repeating
`owner`/`environment`/`cost-center`/`managed-by` on individual
resources defeats the point of a provider default and produces drift
the moment one resource's copy falls out of sync with the provider's:

```hcl
resource "aws_ebs_volume" "data" {
  availability_zone = var.az
  size              = 100

  tags = {
    Name = "${var.name}-data" # per-resource extra only
  }
}
```

The AWS Prescriptive Guidance structure doc documents the same
provider-level default —
https://docs.aws.amazon.com/prescriptive-guidance/latest/terraform-aws-provider-best-practices/structure.html.
`cost-center` deserves special care in the default set: it is the tag
billing tooling and Infracost-style cost reports key off, so keep its
value drawn from a small validated set (a `variable` with a
`validation` block, not free text) rather than letting each root
invent its own spelling.

Encrypt by default, not as an opt-in flag reviewers have to remember to
ask for:

- **State bucket** — SSE-KMS, versioning on, public access blocked at
  the bucket and account level. The S3 backend doc covers the
  encryption and locking config together —
  https://developer.hashicorp.com/terraform/language/backend/s3.
- **RDS/Aurora** — `storage_encrypted = true` plus an explicit
  `kms_key_id` once you're past the account default key.
- **EBS** — `encrypted = true` on every `aws_ebs_volume` and launch
  template block device; enable the account-level "encryption by
  default" setting so a bare `aws_instance` cannot accidentally launch
  an unencrypted root volume.
- **S3 data buckets** — a `server_side_encryption_configuration` block
  on every bucket, `aws:kms` unless the workload has no compliance
  reason to need it.

Fail CI on high/critical findings from whichever scanner produced them
— see Gate pipeline below — rather than tracking encryption gaps in a
spreadsheet. The Google Cloud operations best practices make the same
"default, not optional" argument for GCP's equivalent settings —
https://docs.cloud.google.com/docs/terraform/best-practices/operations.

## Gate pipeline

Run every stage, in this order, on every PR — skipping a stage because
"it's just a tag change" is how a real finding reaches `apply`
unreviewed:

1. `terraform fmt -check -recursive` — fails the build on unformatted
   HCL; never a style debate in review.
2. `terraform validate` — catches type errors and broken references
   before anything talks to a provider API.
3. `tflint`, with the provider-specific ruleset plugin loaded (e.g.
   `tflint-ruleset-aws`) — catches provider-specific misuse `validate`
   cannot see: deprecated arguments, invalid instance types.
4. **Trivy** — the house policy scanner, one tool across both
   Terraform and Docker in this repo; Checkov is the documented
   alternative for a team that already standardized on it.
5. `terraform plan -out=tfplan` — save the plan as a build artifact,
   not a throwaway terminal scrollback.
6. Human review of the saved plan — not a re-run of `plan` at review
   time; review the exact artifact step 5 produced.
7. `terraform apply tfplan` — apply the reviewed plan **file**, never
   a fresh `terraform apply` with no `-out` argument. Re-planning at
   apply time reintroduces the exact drift window step 6 exists to
   close.

Never recommend tfsec — Trivy absorbed it and kept the same check IDs — or Terrascan, archived by Tenable in Nov 2025.

Load the provider ruleset explicitly rather than relying on TFLint's
bundled core rules alone:

```hcl
# .tflint.hcl
plugin "aws" {
  enabled = true
  version = "0.35.0"
  source  = "github.com/terraform-linters/tflint-ruleset-aws"
}
```

Treat a scanner suppression the same way you'd treat a `# noqa` in
application code: an inline comment naming the specific check ID and a
tracking ticket, never a blanket ignore file that silences a whole
category. A suppression with no ticket attached is a finding that
someone decided, unilaterally, was fine to skip.

Cross-check the whole sequence against Gruntwork's Production-Grade
Infrastructure Checklist, which enumerates the same gate list from the
operations side — https://www.gruntwork.io/devops-checklist.

Enforce the first four stages locally with `pre-commit-terraform` so a
PR never reaches CI already broken:

```yaml
repos:
  - repo: https://github.com/antonbabenko/pre-commit-terraform
    rev: v1.96.1
    hooks:
      - id: terraform_fmt
      - id: terraform_validate
      - id: terraform_tflint
      - id: terraform_docs
      - id: terraform_trivy
```

`terraform_docs` is not itself a gate so much as a hygiene hook — it
keeps generated module documentation from silently going stale between
reviews, the same README-drift concern the HashiCorp Style Guide
raises — https://developer.hashicorp.com/terraform/language/style.

## Credentials

Authenticate CI to the cloud with GitHub Actions OIDC, not a static
access-key pair stored as a repo secret. A workflow requests a
short-lived token from GitHub's OIDC provider, exchanges it for
temporary cloud credentials scoped to one IAM role, and the credential
is gone by the time the job ends — there is no long-lived key to leak,
rotate, or forget to revoke.

Scope the trust policy's `sub` condition to the specific repo and ref,
not just the OIDC provider — an unscoped trust policy lets any
workflow in the GitHub org assume the role:

```hcl
data "aws_iam_policy_document" "plan_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:my-org/my-repo:ref:refs/heads/main"]
    }
  }
}
```

Split the plan role from the apply role:

- **Plan role** (runs on every PR) — read-only: `iam:Get*`,
  `iam:List*`, and read/describe permissions on the resources the
  config touches. A compromised PR from a fork can request a plan and
  learn nothing it could not already infer from the HCL.
- **Apply role** (runs on merge to the default branch, or via a
  protected environment) — write access scoped to exactly the
  resources this config manages, nothing broader "just in case."

Zero long-lived cloud keys anywhere in the pipeline — no
`AWS_ACCESS_KEY_ID` repo secret, no service-account JSON key file
checked into a secrets manager for CI to fetch. Where a provider or
tool genuinely cannot do OIDC yet, track the long-lived key as a
documented exception with a rotation date, not a permanent fixture.
The AWS Integration & Automation team's standards repo documents the
same OIDC-first posture as a default module and pipeline convention —
https://aws-ia.github.io/standards-terraform/.

## Drift and cost

Detect drift on a schedule, not by waiting for someone to notice a
console change during an incident. Run `terraform plan` on a cron
(nightly, or a few times a day for high-change environments) against
every state and alert on a non-empty diff — a scheduled plan that
comes back non-empty means something changed outside the pipeline and
needs an owner, not necessarily an immediate `apply`. The Google Cloud
best practices for cross-config communication cover the multi-state
version of the same drift concern, where one state's drift cascades
into a consumer state through remote-state data —
https://docs.cloud.google.com/docs/terraform/best-practices/cross-config-communication.

Surface cost deltas on every PR with Infracost, not only at the
monthly bill review — a reviewer approving a plan that adds three
`m5.4xlarge` instances should see the dollar delta in the same PR the
HCL change lives in, not three weeks later on an invoice.

Graduate from raw CI scripts to a dedicated orchestration platform once
plan/apply coordination itself becomes the bottleneck, not before:

- **Atlantis** (https://runatlantis.io) — self-hosted, PR-comment
  driven plan/apply; graduate here first, when you want plan/apply
  tied to PR comments without buying a managed control plane.
- **HCP Terraform** — managed runs, state, RBAC, and Sentinel policy
  (plus Stacks); graduate here when you need centralized state/RBAC
  across many workspaces and are willing to adopt HashiCorp's managed
  platform.
- **Spacelift** — policy-as-code via OPA across multiple IaC tools;
  graduate here when Terraform is one of several IaC tools in the
  estate and you want a single policy engine over all of them.
- **env0** — self-service environments with TTL and cost governance
  built in; graduate here when the bottleneck is developers waiting on
  a platform team to provision throwaway environments, not the gate
  pipeline itself.

_Verified as of 2026-07; sources re-checked against docs/superpowers/research/2026-07-20-*.md._
