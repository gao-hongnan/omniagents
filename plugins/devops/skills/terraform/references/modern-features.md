# Modern Features (1.3 → 1.15)

This file answers one question: **should this repo adopt language feature X,
and where does it fit?** It covers every HCL/CLI feature shipped between
Terraform 1.3 and 1.15, states a verdict (adopt / adopt-with-caveat /
out-of-scope), and gives the one-line reason. It does not restate module
shape, tagging, or the gate pipeline — see the sibling references indexed in
`../SKILL.md`.

The parent skill's floor is Terraform ≥1.11 OSS CLI (the
S3-native-locking / write-only-arguments release). Features below 1.11 here
are already available at that floor. Where the source digest gives no
version number for a row, this file states none rather than guessing.

Read `## Adoption table` for the verdict, then its note below for mechanics
and citation. `## Testing` and `## Config-driven refactoring` are workflows,
not single features, so they get their own sections; `## OpenTofu` and `##
Out of scope: Stacks` are read-once orientation.

## Adoption table

| Feature | Since | Verdict | When to use |
| --- | --- | --- | --- |
| `optional()` object attributes | 1.3 | Adopt | Any object-typed variable where some callers won't set every attribute — replaces `lookup()`/`coalesce()` null-juggling. |
| `check` blocks | 1.5 | Adopt (non-blocking) | Continuous, non-blocking invariants — endpoint health, drift that should warn but not fail a plan already in flight. |
| Pre/postconditions + variable `validation` | not versioned in the source digest | Adopt (blocking) | Contracts that must fail the plan/apply: `precondition` before Terraform creates the block, `postcondition` on the object it produced, `validation` on caller-supplied input. |
| `terraform test` (+ mocks, + parallel) | 1.6 (mocking 1.7, parallel runs 1.12) | Adopt — default | First-line module testing; see `## Testing` below. |
| `moved` / `import` + `-generate-config-out` / `removed` | 1.1 / 1.5 / 1.7 | Adopt — mandatory | Every resource rename, module move, or retirement; never hand-run `terraform state mv`/`rm`. See `## Config-driven refactoring` below. |
| Provider-defined functions (`provider::<name>::fn`) | 1.8 | Adopt where the provider ships one | Replaces bespoke `locals` parsing gymnastics (ARN splitting, CIDR math) with a provider-shipped pure function. |
| `templatestring` | 1.9 | Adopt | Rendering a template that arrives as a *string value* (data-source output, module input) rather than a file on disk — `templatefile` stays correct for on-disk templates. |
| Ephemeral resources + write-only args (`*_wo`/`*_wo_version`) | 1.10 / 1.11 | Adopt — default for secrets | Any argument carrying a credential, token, or password; secrets never enter plan or state. Cross-ref `security-and-gates.md#secrets`. |
| S3 `use_lockfile = true` | 1.10 experimental, 1.11 GA | Adopt — mandatory for new backends | Every new S3 backend; drop `dynamodb_table` once migrated. Cross-ref `state-and-environments.md#backend-baseline`. |
| OCI backend + short-circuit logical operators + import `identity` | 1.12 | Adopt where relevant | OCI backend for OCI-Object-Storage-based state; short-circuit `&&` (see `## 1.12 additions` below for both operators) wherever the un-evaluated branch would otherwise error; `identity` import for providers exposing structured identity instead of a bare string ID. |
| List/search resources + `terraform query` + `actions`/`-invoke` | 1.14 | Adopt for bulk ops | Bulk-discovering and importing unmanaged infrastructure (`terraform query` against `.tfquery.hcl` list blocks) and declarative day-2 operations (`actions` blocks invoked via `-invoke` or a resource lifecycle trigger). |
| Variables in module `source`/`version` + `deprecated` on vars/outputs + typed outputs + `convert()` | 1.15 | Adopt | Environment-parameterized module pins (mark the variable `const = true` so Terraform can resolve it at `init` time); deprecation warnings for variables/outputs mid-migration; explicit output `type`; `convert()` in place of the older per-type `tostring`/`tolist`/`tomap` family. |

### Contracts and assertions

`optional()` replaces the null-juggling pattern for object-typed variables —
give the attribute a default instead of checking for null downstream:
https://developer.hashicorp.com/terraform/language/expressions/type-constraints

```hcl
variable "cache_config" {
  type = object({
    node_type = string
    replicas  = optional(number, 1)
    encrypted = optional(bool, true)
  })
  description = "ElastiCache sizing; replicas/encrypted default when omitted."
}
```

`check` blocks and custom conditions look similar but differ: a `check`
warns and lets the run continue — non-blocking visibility —
https://developer.hashicorp.com/terraform/language/block/check. A
`precondition`/`postcondition` in a `lifecycle` block, or a `validation`
block on a `variable`, fails the plan or apply outright — use those for
contracts that must never be silently violated:
https://developer.hashicorp.com/terraform/language/validate.

```hcl
check "budget_within_limits" {
  assert {
    condition     = local.monthly_estimate <= var.budget_ceiling
    error_message = "monthly estimate exceeds the approved budget ceiling"
  }
}
```

```hcl
resource "aws_instance" "app" {
  ami = var.ami_id

  lifecycle {
    precondition {
      condition     = data.aws_ami.selected.architecture == "x86_64"
      error_message = "ami_id must resolve to an x86_64 image"
    }

    postcondition {
      condition     = self.public_ip != ""
      error_message = "instance must receive a public IP"
    }
  }
}
```

### Extensibility functions

Provider-defined functions (1.8) expose logic the provider author already
wrote and tested — reach for one before writing the equivalent in `locals`:
https://www.hashicorp.com/en/blog/terraform-1-8-improves-extensibility-with-provider-defined-functions

```hcl
locals {
  account_id = provider::aws::arn_parse(var.role_arn).account_id
}
```

`templatestring` (1.9) renders a template that arrives as a string value —
data source, module input — rather than a file on disk; keep `templatefile`
for real files. https://developer.hashicorp.com/terraform/language/functions/templatestring

```hcl
locals {
  rendered = templatestring(data.http.remote_template.response_body, {
    region = var.region
  })
}
```

### Secrets and locking

Ephemeral resources and write-only arguments are the current secrets
mechanism: a write-only argument (`*_wo`) never lands in plan or state, and
its companion `*_wo_version` attribute is the only part Terraform persists —
bump the version to rotate. See `security-and-gates.md#secrets` for the full
pipeline. Ephemeral:
https://developer.hashicorp.com/terraform/language/manage-sensitive-data/ephemeral.
Write-only: https://developer.hashicorp.com/terraform/language/manage-sensitive-data/write-only.

```hcl
resource "aws_db_instance" "this" {
  password_wo          = var.db_password_wo
  password_wo_version  = var.db_password_wo_version
}
```

S3 native locking (`use_lockfile = true`, experimental in 1.10, GA in 1.11)
replaces the DynamoDB lock table for new backends — see
`state-and-environments.md#backend-baseline` for the migration sequence off
an existing table:
https://developer.hashicorp.com/terraform/language/backend/s3

```hcl
terraform {
  backend "s3" {
    bucket       = "acme-tfstate"
    key          = "prod/network/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
  }
}
```

### 1.12 additions

Short-circuit `&&`/`||` stop evaluating the right-hand operand once the
result is already determined — use them wherever the un-evaluated branch
would otherwise raise an error on its own:
https://developer.hashicorp.com/terraform/language/expressions/operators

```hcl
locals {
  is_prod   = var.environment == "prod"
  safe_name = local.is_prod && can(regex("^prod-", var.name)) ? var.name : "unnamed"
}
```

Import by `identity` accepts a provider-defined structured identity object
in place of a bare string ID — use it once the provider supports it, since a
structured identity survives more provider-side changes than a raw ID
string: https://developer.hashicorp.com/terraform/language/block/import

```hcl
import {
  to       = aws_instance.web
  identity = {
    instance_id = "i-0123456789abcdef0"
  }
}
```

The OCI backend stores state in OCI Object Storage with native locking; it
is unrelated to OCI *registries* for provider/module distribution (OpenTofu
only, see `## OpenTofu` below): https://developer.hashicorp.com/terraform/language/backend/oci

### 1.14 additions

`terraform query` runs the `list` blocks in a `.tfquery.hcl` file against
real infrastructure and prints matches — the bulk-discovery front end for
importing resources Terraform doesn't yet manage. Add `-generate-config-out`
to also emit HCL for the matches, the same way the plain `import` block
does for a single resource:
https://developer.hashicorp.com/terraform/cli/commands/query

```hcl
list "aws_instance" "orphaned" {
  provider = aws

  config {
    filter {
      name   = "tag:ManagedBy"
      values = ["none"]
    }
  }
}
```

`actions` blocks declare a provider-defined operation — a Lambda invoke, a
runbook trigger — that runs on a resource lifecycle event or on demand via
`-invoke`, replacing ad hoc `null_resource`/`local-exec` day-2 scripting:
https://developer.hashicorp.com/terraform/language/block/action and
https://developer.hashicorp.com/terraform/language/invoke-actions

```hcl
action "aws_lambda_invoke" "rotate_secret" {
  config {
    function_name = "rotate-db-secret"
  }
}
```

Invoke it with `terraform apply -invoke=action.aws_lambda_invoke.rotate_secret`.

### 1.15 additions

Variables in module `source`/`version` end the workaround of duplicating a
`module` block per environment just to point at a different registry
version. Mark the variable `const = true` so Terraform resolves it at
`init` time: https://developer.hashicorp.com/terraform/language/modules/configuration
(release overview: https://www.hashicorp.com/en/blog/new-in-terraform-115-dynamic-sources-variable-deprecation-and-more).

```hcl
variable "module_version" {
  type  = string
  const = true
}

module "storage" {
  source = "git::https://example.com/terraform-aws-s3.git?ref=${var.module_version}"
}
```

`deprecated` on a variable or output surfaces a warning to every caller —
root-module callers for a deprecated variable, consuming modules for a
deprecated output — the config-driven way to announce a migration window
instead of a comment nobody reads:
https://developer.hashicorp.com/terraform/language/block/variable and
https://developer.hashicorp.com/terraform/language/block/output

```hcl
variable "legacy_region" {
  type       = string
  deprecated = "use region_map instead; removal planned for the next major version"
}
```

Typed outputs (an explicit `type` on an `output` block) and `convert()`
close the same gap: an output can now assert its own shape instead of
silently emitting whatever the expression happens to produce, and
`convert()` replaces the older per-type `tostring`/`tolist`/`tomap` function
family with one call that takes the target type as an argument:
https://developer.hashicorp.com/terraform/language/functions/convert

```hcl
output "vpc_id" {
  type  = string
  value = convert(aws_vpc.this.id, string)
}
```

## Testing

2026 consensus, per the source digest: `terraform test` is the first line of
defense, run on every commit; Terratest (Go) is reserved for cross-system E2E
verification, run pre-release against real deploys.

- Ship `tests/*.tftest.hcl` per module, one file per behavior (naming,
  encryption defaults, feature-flag branching).
- Default CI to `command = plan` with a `mock_provider` block — fast, no
  credentials, no real infrastructure:
  https://developer.hashicorp.com/terraform/language/tests/mocking.
- Reserve `command = apply` for the module's `examples/` directory —
  integration tests against real, disposable infrastructure, run less often
  than the mocked plan suite.
- Mark independent `run` blocks `parallel = true` and pass `-parallelism` to
  `terraform test` once a file grows past a handful of runs (1.12) —
  shortens CI wall-clock time without changing what each run asserts:
  https://developer.hashicorp.com/terraform/language/tests.
- Terratest owns what `terraform test` cannot verify locally — real HTTP,
  real DNS, cross-region behavior — as a pre-release gate, not the default
  per-commit module-testing layer.

A minimal per-module test — one `run` block, mocked provider, `command =
plan`:

```hcl
mock_provider "aws" {}

variables {
  name = "orders-queue"
}

run "creates_encrypted_queue" {
  command = plan

  assert {
    condition     = aws_sqs_queue.this.sqs_managed_sse_enabled
    error_message = "queue must default to SSE-SQS encryption"
  }
}
```

Scale this pattern up with more `run` blocks per file (one per assertion
group) and more files under `tests/` (one per behavior), not with one giant
test file asserting everything about the module at once — the same
composition instinct that keeps `main.tf` from growing into a god module
applies to test files.

## Config-driven refactoring

The rule: **refactors ship as config, reviewed in the PR, not as
out-of-band state surgery.** A `moved` or `removed` block is a diff a
reviewer can read, approve, and re-run; a hand-typed `terraform state mv` or
`state rm` is invisible to the PR and unrepeatable if the apply fails
halfway. Prefer the block every time a resource's address changes or a
resource retires, even when the manual command would be one line shorter.

A rename plus a retirement, in one diff — the `moved` block tells Terraform
`aws_instance.web`'s new address is `aws_instance.app_server`; the `removed`
block hands `aws_instance.legacy_cache` off to another owner without
destroying it:

```hcl
moved {
  from = aws_instance.web
  to   = aws_instance.app_server
}

removed {
  from = aws_instance.legacy_cache

  lifecycle {
    destroy = false
  }
}
```

Both blocks are declarative and idempotent: apply them and Terraform updates
state to match without touching the underlying resource. Keep `moved`
blocks indefinitely — deleting one turns a move into a
destroy-and-recreate for anyone still on the old address. `removed` with
`destroy = false` is the correct shape for a hand-off; omit `lifecycle`, or
set `destroy = true`, when the resource should actually be torn down.

The reverse direction — bringing existing, unmanaged infrastructure under
Terraform — uses `import` blocks with `-generate-config-out` instead of a
manual `terraform import`: define the `import` block, run `terraform plan
-generate-config-out=generated.tf`, review and prune the generated HCL, then
apply. Bulk variants of the same idea (`terraform query` against
`.tfquery.hcl` list blocks) are covered in `## Adoption table` above.

This section covers a single rename, move, or retirement. Campaign-scale
refactors — a provider major-version bump across dozens of modules,
`count`↔`for_each` renumbering at scale, or recovering drifted/corrupted
state — route to `terraform-skill` per the parent `SKILL.md`'s routing
table: this file's blocks are the right primitive either way, but
sequencing a hundred of them safely is a different skill.

## OpenTofu

OpenTofu is a source-compatible fork, not an interchangeable drop-in —
several features diverge from Terraform, and a repo must declare which tool
it targets rather than assume parity:

| Divergence | OpenTofu since | Detail |
| --- | --- | --- |
| State and plan encryption | 1.7+ | Built into the language (`encryption` block, or `TF_ENCRYPTION`/`TOFU_ENCRYPTION` env var), not a Terraform feature at any version. https://opentofu.org/docs/language/state/encryption/ |
| Provider `for_each` | 1.9 | Iterate provider configurations the way `for_each` iterates resources — eliminates hand-duplicated provider blocks per region/account. Requires a static alias and a for_each expression resolvable without data sources or resources. https://opentofu.org/blog/opentofu-1-9-0/ |
| OCI registries for providers/modules | 1.10 | Install providers and modules from an OCI registry via `oci_mirror` configuration — a different mechanism from Terraform's 1.12 OCI *backend* (state storage), not a substitute for it. https://opentofu.org/docs/cli/oci_registries/ |
| Own `use_lockfile` for the S3 backend | 1.10 | Same `use_lockfile = true` attribute name and effect as Terraform's, but shipped and GA'd on OpenTofu's own timeline — do not assume version parity between the two tools' backend docs. https://opentofu.org/docs/language/settings/backends/s3/ |
| Earlier `deprecated` marks on variables/outputs | pre-dates Terraform 1.15 | OpenTofu shipped the `deprecated` argument on `variable`/`output` blocks before Terraform did — the 1.15 row in `## Adoption table` above does not apply to an OpenTofu-only repo's timeline. https://opentofu.org/docs/language/values/variables/ |
| `.tofu` file extension | since the fork | When both `foo.tf` and `foo.tofu` exist in a directory, OpenTofu loads only `foo.tofu` — lets a module author ship tool-specific overrides from one source tree. https://opentofu.org/docs/language/files/ |

The rule: **declare which tool a repo targets**, in the root README or
`versions.tf` — never write config that silently depends on one tool's
divergent behavior while claiming to support both. A module needing
provider `for_each` or native state encryption is an OpenTofu module, full
stop — gate its CI on `tofu`, not `terraform`:

```hcl
terraform {
  required_version = ">= 1.11, < 2.0.0" # this repo targets Terraform, not OpenTofu
}
```

## Out of scope: Stacks

Terraform Stacks (`.tfcomponent.hcl` + `.tfdeploy.hcl`) reached general
availability at HashiConf 2025, but Stacks is HCP-Terraform-only — no
OSS-CLI equivalent exists, and neither `tofu` nor OSS `terraform` can run a
Stacks configuration. This rulebook targets the OSS CLI, so Stacks questions
land outside this plugin; route them to HCP Terraform's own docs instead of
bending a house rule to fit a product this skill does not cover:
https://developer.hashicorp.com/terraform/language/stacks (GA note:
https://developer.hashicorp.com/terraform/language/stacks/update-GA).

_Verified as of 2026-07; sources re-checked against docs/superpowers/research/2026-07-20-*.md._
