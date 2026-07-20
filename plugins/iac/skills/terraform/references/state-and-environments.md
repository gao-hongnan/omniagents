# State & Environments

Backend layout, bootstrap sequencing, blast-radius splitting, and
environment structure for Terraform ≥ 1.11 OSS CLI. This file expands
the `SKILL.md` default-posture bullets on remote state and secrets
with the mechanics: backend blocks, the bootstrap chicken-and-egg
sequence, and the directory shapes that keep one broken `apply` from
reaching every environment at once. It does not cover state surgery
(corruption, drift, lock recovery) — that is `terraform-skill`'s
domain per the routing table in `SKILL.md`.

## Backend baseline

Every root uses a remote backend. Never commit state to version
control, and never let a root fall back to local state outside the
one-time bootstrap root covered below.

- **Remote, versioned, encrypted, access-logged, public-blocked.** The
  S3 bucket backing state must have versioning enabled (state file
  corruption or a bad apply is recoverable from a prior object
  version), server-side encryption on by default, a public access
  block on all four settings, and access logging turned on so reads of
  state — which can contain secrets — are auditable. See the S3
  backend reference —
  https://developer.hashicorp.com/terraform/language/backend/s3 — and
  AWS Prescriptive Guidance's backend page —
  https://docs.aws.amazon.com/prescriptive-guidance/latest/terraform-aws-provider-best-practices/backend.html.

  ```hcl
  terraform {
    required_version = ">= 1.11"
    backend "s3" {
      bucket       = "acme-tfstate"
      key          = "networking/prod/terraform.tfstate"
      region       = "us-east-1"
      encrypt      = true
      use_lockfile = true
    }
  }

  resource "aws_s3_bucket_versioning" "tfstate" {
    bucket = aws_s3_bucket.tfstate.id
    versioning_configuration {
      status = "Enabled"
    }
  }

  resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
    bucket = aws_s3_bucket.tfstate.id
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "aws:kms"
      }
    }
  }

  resource "aws_s3_bucket_public_access_block" "tfstate" {
    bucket                  = aws_s3_bucket.tfstate.id
    block_public_acls       = true
    block_public_policy     = true
    ignore_public_acls      = true
    restrict_public_buckets = true
  }

  resource "aws_s3_bucket_logging" "tfstate" {
    bucket        = aws_s3_bucket.tfstate.id
    target_bucket = aws_s3_bucket.logs.id
    target_prefix = "tfstate/"
  }
  ```

- **Native locking, no new DynamoDB tables.** `use_lockfile = true`
  shipped experimental in Terraform 1.10 and went GA in 1.11: the S3
  backend writes a `.tflock` companion object next to the state object
  and uses conditional writes for mutual exclusion, so a lock table is
  no longer required. `dynamodb_table` is deprecated on the S3
  backend — do not wire a new one. Same source —
  https://developer.hashicorp.com/terraform/language/backend/s3.

- **Migrating an existing DynamoDB-locked backend.** Do not cut over
  in one step — a mid-migration apply from an un-upgraded Terraform
  binary elsewhere in the fleet must still be able to take the lock.
  Add `use_lockfile = true` while leaving `dynamodb_table` in place,
  run both locking mechanisms for one full deploy cycle across every
  Terraform version touching that state, confirm no caller is still
  on a pre-1.11 binary, then delete the `dynamodb_table` line (and,
  once nothing references the table, the table itself) in a follow-up
  change.

  ```hcl
  terraform {
    backend "s3" {
      bucket         = "acme-tfstate"
      key            = "networking/prod/terraform.tfstate"
      region         = "us-east-1"
      encrypt        = true
      use_lockfile   = true
      dynamodb_table = "acme-tfstate-lock" # run alongside during cutover, then delete this line
    }
  }
  ```

- **Treat state as a secret regardless of what's in it.** Resource
  attributes, including ones never marked `sensitive`, land in plan
  and state in plaintext by default; write-only arguments and
  ephemeral resources (Terraform ≥ 1.11) keep secret values out of
  state entirely, but everything else in that same state file — ARNs,
  hostnames, IDs — is still a reconnaissance map of the environment.
  Bucket encryption and access logging above are the state-file half
  of that control; the ephemeral-resources mechanics are the
  secrets-in-code half, covered in
  `security-and-gates.md#secrets`. See
  https://developer.hashicorp.com/terraform/language/manage-sensitive-data/ephemeral.

## Bootstrap

The state bucket itself cannot be created by a root that depends on
a backend that doesn't exist yet — that's the chicken-and-egg problem
every fresh account or fresh region hits once. Solve it with a tiny,
separate bootstrap root that runs on local state:

1. Write a bootstrap root with no `backend` block (Terraform defaults
   to local state, a `terraform.tfstate` file on disk) that creates
   only the state bucket and its guardrails — versioning, encryption,
   public access block, logging target.
2. Apply it once, by hand or from a bootstrap-only CI job, on
   whatever credentials provision new accounts.
3. Add the `backend "s3" { ... }` block to that same root and run
   `terraform init -migrate-state`; Terraform copies the local
   `terraform.tfstate` into the bucket it just created and the root is
   now self-hosting.
4. Every other root in the account or region points its own
   `backend "s3"` block at that bucket from day one — only the
   bootstrap root ever touches local state, and only once.

```hcl
terraform {
  required_version = ">= 1.11"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
  # no backend block: applies with local state, once
}

provider "aws" { region = "us-east-1" }

resource "aws_s3_bucket" "tfstate" {
  bucket = "acme-tfstate"
}
```

Keep the bootstrap root's own state out of the bucket it creates —
some teams migrate it in after step 3 and accept the small
bootstrapping-its-own-backend oddity, others leave the bootstrap root
permanently on local state (checked into a restricted-access
repository, or held only by the platform team) precisely because it
is the one root that must still apply if the main bucket is ever lost.
Either choice is fine; pick one and document it in the bootstrap
root's own README, because the alternative is an on-call engineer
discovering the answer during an outage. The Google Cloud operations
guide covers the equivalent GCS-bucket bootstrap sequencing —
https://docs.cloud.google.com/docs/terraform/best-practices/operations.

## Blast radius

One state file per environment × service/layer, never a single
mega-state for an account or a whole platform. A state file is the
unit of `plan` time, the unit of lock contention, and — if it
corrupts or an apply half-completes — the unit of blast radius. Small
states plan faster because Terraform only has to refresh and diff the
resources inside that state, not the whole account; they fail smaller
because a bad apply in the `networking/prod` state cannot touch
`billing/prod` or `networking/staging`, whose resources live in
different state files with different lock objects.

- Split first by environment (`prod`, `staging`, `dev`, `pr-preview`),
  then by service or layer within it (`networking`, `data`,
  `app`, `edge`) — the same axis the backend key above already encodes
  (`networking/prod/terraform.tfstate`). Gruntwork's style guide
  argues this split explicitly, live-vs-not-live first, component
  second —
  https://docs.gruntwork.io/guides/style/terraform-style-guide/.
- Layer boundaries should track real change cadence and real blast
  tolerance, not org chart convenience: a VPC changes rarely and an
  unplanned change there is expensive, so it gets its own state; an
  autoscaling group's desired count changes constantly and cheaply, so
  it can share a state with its service. AWS's Prescriptive Guidance
  structure page frames the same layering by lifecycle —
  https://docs.aws.amazon.com/prescriptive-guidance/latest/terraform-aws-provider-best-practices/structure.html.
- At multi-account scale, split by account too — an account boundary
  is already a hard blast-radius wall (separate credentials, separate
  service quotas), so let it also be a state boundary. AWS's I&A team
  standards assume this account-per-state-root shape throughout —
  https://aws-ia.github.io/standards-terraform/.
- Gruntwork's Production-Grade Infrastructure Checklist ties the same
  splitting decision to two operational outcomes worth citing
  directly: faster `plan`/`apply` cycles for the team working in a
  given layer, and a bounded, name-able set of resources anyone can
  reason about when that state's plan comes up for review —
  https://www.gruntwork.io/devops-checklist.
- A single mega-state is not a shortcut, it is deferred cost: every
  `plan` refreshes every resource the account owns, every lock blocks
  every other change in flight, and one `terraform destroy
  aws_instance.oops` typo has the entire account in its diff instead
  of one layer of one environment.

Example layout for one service split this way (each directory is its
own root, own backend key, own state):

```text
live/
├── prod/
│   ├── networking/
│   ├── data/
│   └── app/
├── staging/
│   ├── networking/
│   ├── data/
│   └── app/
└── dev/
    ├── networking/
    ├── data/
    └── app/
```

## Environments

CONTESTED — splitting environments with Terraform CLI workspaces:
the HashiCorp style guide endorses workspace-per-environment as a
legitimate pattern (and HCP Terraform's own "workspaces" are a
different, separate-state-per-workspace concept, not the CLI feature)
— https://developer.hashicorp.com/terraform/language/style — while
Google's best-practices guide, Gruntwork, and the wider community
distillation at terraform-best-practices.com converge on
directory-per-environment instead, because CLI workspaces share one
backend configuration and one set of caller credentials across every
environment they multiplex, so a `terraform workspace select prod`
that silently fails to stick — wrong shell, stale script, a CI runner
that reused a container — turns into a plan computed against `prod`'s
state but applied with `dev`'s intent, or worse, the reverse. See
https://docs.cloud.google.com/docs/terraform/best-practices/general-style-structure
and
https://docs.gruntwork.io/guides/style/terraform-style-guide/.

House verdict, and the one this skill's examples assume:

- **Directory-per-environment is the default.** Each environment gets
  its own root directory (`live/prod/networking`,
  `live/staging/networking`), its own `backend "s3"` block, its own
  state key, and — where the environments live in separate
  accounts — its own provider credentials. Selecting the wrong
  environment now requires `cd`-ing into the wrong directory or
  pointing CI at the wrong path, both of which show up in the plan
  output's backend summary before anything applies. This is the same
  split the "Blast radius" section above already assumes; environment is the
  outer split, service/layer the inner one. Community consensus on
  this default is summarized at
  https://www.terraform-best-practices.com.
- **CLI workspaces are for ephemeral, same-credential stacks.**
  PR-preview environments, short-lived feature stacks, or anything
  that is created and destroyed inside one CI run against one shared
  backend are a good fit — the blast radius of a wrong-workspace
  apply there is one throwaway stack, not `prod`.

  ```hcl
  terraform {
    backend "s3" {
      bucket       = "acme-tfstate-pr"
      key          = "preview/terraform.tfstate"
      region       = "us-east-1"
      encrypt      = true
      use_lockfile = true
    }
  }

  resource "aws_instance" "preview" {
    ami           = var.ami_id
    instance_type = "t3.micro"
    tags = {
      Name = "pr-${terraform.workspace}"
    }
  }
  ```

- **Terragrunt earns its place above a real DRY threshold, not
  below it.** Terragrunt's `include` blocks and dependency graph pay
  for themselves when the directory-per-environment tree above starts
  repeating the same backend/provider/variable wiring across enough
  roots that a single change (a new required tag, a new provider
  version floor) means editing the same six lines in a dozen places.
  In practice that threshold is roughly 3 environments × 3
  service/layers (about nine roots) and up; below it, the DRY savings
  don't cover the added tool and the extra indirection between
  `terragrunt.hcl` and the underlying module. Introducing it at two
  environments with one layer each is solving a problem the tree
  doesn't have yet.

## Cross-state data flow

A stack never reaches into another stack's resources by resource
address or by guessing a name pattern — that couples the two stacks'
internals together and breaks the moment either one renames or
re-shapes a resource. Read what another stack published as output,
through one of two sanctioned paths:

- **`terraform_remote_state`**, when the consuming stack should read
  another stack's outputs directly and is willing to take on a live
  read dependency on that stack's backend at every plan and apply.

  ```hcl
  data "terraform_remote_state" "networking" {
    backend = "s3"
    config = {
      bucket = "acme-tfstate"
      key    = "networking/prod/terraform.tfstate"
      region = "us-east-1"
    }
  }

  resource "aws_instance" "app" {
    ami           = var.ami_id
    instance_type = var.instance_type
    subnet_id     = data.terraform_remote_state.networking.outputs.private_subnet_ids[0]
  }
  ```

- **Data-only modules**, when the consuming stack wants the same
  facts without a hard dependency on another stack's backend shape —
  the module wraps whatever `data` sources (tags, SSM parameters, a
  `terraform_remote_state` read, or a live AWS API lookup) resolve the
  facts, and exposes only the outputs callers need. This is the
  better default for values that many downstream stacks consume, or
  for looked-up facts that aren't Terraform-managed at all (an
  existing VPC, a shared AMI).

  ```hcl
  module "networking_facts" {
    source   = "../modules/networking-facts" # data-only: no resources, only data sources + outputs
    vpc_name = "acme-prod"
  }

  resource "aws_instance" "app" {
    ami           = var.ami_id
    instance_type = var.instance_type
    subnet_id     = module.networking_facts.private_subnet_ids[0]
  }
  ```

Either path keeps the producing stack free to refactor its own
resource names and internal module structure as long as its published
outputs keep their contract; reaching into another stack's state by
resource address instead has no such contract and breaks silently on
the producer's next refactor. Google's cross-config-communication
guide covers this same producer/consumer split for GCS-backed stacks
— https://docs.cloud.google.com/docs/terraform/best-practices/cross-config-communication
— and the same account/layer boundaries from the "Blast radius" section are
usually exactly where a `terraform_remote_state` read or a data-only
module is the right tool, per
https://docs.aws.amazon.com/prescriptive-guidance/latest/terraform-aws-provider-best-practices/structure.html.

Never let a consumer read a producer's raw resource by guessing its
Terraform address (`data.terraform_remote_state.networking.outputs`
is a contract; `aws_subnet.private[2]` reached at from a different
root's provider block, by ID string copy-pasted out of the console,
is not) — the first survives the producer's next refactor, the second
doesn't.

_Verified as of 2026-07; sources re-checked against docs/superpowers/research/2026-07-20-*.md._
