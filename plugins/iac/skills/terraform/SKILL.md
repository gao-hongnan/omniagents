---
name: terraform
description: >-
  Use when writing or reviewing Terraform 1.11+ modules with strict
  hygiene enforced: standard module structure, variable/output
  conventions, composition and dependency inversion, feature flags,
  remote state with S3 native locking, directory-per-environment layout,
  version pinning, secrets via ephemeral resources / write-only
  arguments, security-group least privilege, default_tags, and the
  fmt/validate/tflint/trivy gate pipeline.
when_to_use: >-
  Trigger for .tf / .tfvars / .tftest.hcl files, module design reviews,
  terraform init/plan/apply hygiene, backend or state layout decisions,
  environment splitting, provider/module version pinning,
  .terraform.lock.hcl, tagging standards, IaC security gates, tflint or
  trivy config, terraform test authoring, moved/import/removed refactors,
  or "is this module enterprise-grade" tiering questions.
disable-model-invocation: false
user-invocable: true
allowed-tools: []
model: inherit
paths:
  - "**/*.tf"
  - "**/*.tfvars"
  - "**/*.tftest.hcl"
  - "**/.terraform.lock.hcl"
shell: bash
---

# Terraform Module Patterns & Hygiene

House rules for Terraform ≥ 1.11 OSS CLI — the state-locking and
write-only-arguments era. 1.11 is the floor because it is the release
where S3 native locking (`use_lockfile`) and write-only `*_wo`
arguments both went GA; rules below assume both are available. Pin
your actual floor per https://endoflife.date/terraform and raise it
deliberately, never drift it. OpenTofu divergences are flagged inline
where they matter (state/plan encryption, provider `for_each`, its own
`use_lockfile`, earlier `deprecated` marks, the `.tofu` extension).
Terraform Stacks (`.tfcomponent.hcl` / `.tfdeploy.hcl`) are
HCP-Terraform-only and out of scope for this OSS-CLI rulebook.

## Default posture

Surface these ten non-negotiables whenever proposed HCL violates them.
Point at the exact rule rather than re-arguing from first principles —
the reference files below carry the full rationale and source links.

- **Pin everything.** `required_version` in every root; providers `~>`
  (pessimistic minor) in roots, `>=` minimums in reusable modules;
  module sources by exact registry `version` or git `?ref=` tag/SHA —
  never a branch. Commit `.terraform.lock.hcl` for every root. See the
  HashiCorp Style Guide —
  https://developer.hashicorp.com/terraform/language/style
- **Type and describe every variable and output.** Order variable
  fields `type` → `description` → `default` → `sensitive` →
  `validation`; give every output a `description`; keep both blocks
  alphabetized. An undescribed variable is a review-blocking finding,
  not a style nit — see the HashiCorp Style Guide —
  https://developer.hashicorp.com/terraform/language/style

  ```hcl
  variable "node_type" {
    type        = string
    description = "ElastiCache node instance type, e.g. cache.t4g.micro."
    default     = "cache.t4g.micro"
    sensitive   = false

    validation {
      condition     = can(regex("^cache\\.", var.node_type))
      error_message = "node_type must be a valid ElastiCache instance type."
    }
  }
  ```
- **No `provider` blocks inside reusable modules.** Declare only
  `required_providers`; accept configured providers from the caller —
  a child module that hardcodes a `provider "aws" { region = ... }`
  block cannot be composed into a multi-region root. See Standard
  Module Structure —
  https://developer.hashicorp.com/terraform/language/modules/develop/structure
- **Invert dependencies.** Modules receive IDs, ARNs, and objects as
  input variables; never bury a data-source lookup of "assumed"
  infrastructure inside a module — the caller creates-or-queries and
  passes the result in. See Module composition —
  https://developer.hashicorp.com/terraform/language/modules/develop/composition
- **Keep the module tree flat.** One level of child modules, composed
  in the root. No thin single-resource wrapper modules — inline the
  resource instead. No god modules managing unrelated infrastructure.
  Same composition doc as above covers the "flat trees" argument —
  https://developer.hashicorp.com/terraform/language/modules/develop/composition
- **No `0.0.0.0/0` ingress.** Reference security groups, not CIDR
  blocks, wherever the provider supports it; a CIDR-based rule that
  happens to be narrow today has no mechanism to stay narrow as the
  network grows. See AWS Prescriptive Guidance —
  https://docs.aws.amazon.com/prescriptive-guidance/latest/terraform-aws-provider-best-practices/structure.html
- **Set `default_tags` on the root provider.** owner / env /
  cost-center / managed-by at minimum; resource-level tags only for
  genuine per-resource extras — do not repeat the default set on every
  resource block. Same AWS Prescriptive Guidance reference as above.
- **Secrets never enter state.** Use ephemeral resources or
  write-only `*_wo` arguments (TF ≥1.11; bump `*_wo_version` to
  rotate), or reference SSM / Secrets Manager / Vault at runtime.
  `sensitive = true` marks a value for display redaction — it does not
  keep the value out of state. Treat state as secret regardless.
  https://developer.hashicorp.com/terraform/language/manage-sensitive-data/ephemeral
- **Remote state is S3: versioned, encrypted, public-access-blocked,
  `use_lockfile = true`.** Do not create new DynamoDB lock tables —
  `dynamodb_table` is deprecated; an existing table may run alongside
  during migration, then get dropped.
  https://developer.hashicorp.com/terraform/language/backend/s3
- **Run the gate pipeline in order, every time.** `terraform fmt
  -check` → `terraform validate` → TFLint → Trivy (house default —
  one scanner across Terraform and Docker; Checkov is the documented
  alternative) → saved plan artifact → human-reviewed apply. OIDC
  short-lived roles only — zero long-lived cloud keys; keep the
  read-only plan role separate from the apply role. Cross-check
  against Gruntwork's Production-Grade Infrastructure Checklist —
  https://www.gruntwork.io/devops-checklist

## Tiering: name your tier before naming controls

| Control | T1 demo/portfolio | T2 production | T3 regulated |
|---|---|---|---|
| Encryption in transit + AUTH | optional (VPC-scoped SG suffices) | required | required (mandated wrappers) |
| At-rest encryption | provider default | provider default or CMK | CMK + key policy |
| HA / replicas / failover | no | required for stateful path | required |
| Backups / snapshots | no | required (retention named) | required + tested restore |
| Log delivery / audit | no | error+slow logs | full delivery + retention policy |
| Alarms / notifications | no | memory/error alarms | + SNS ops hooks |

Every control names its tier and its pain. A T1 stack passing T1 is
correct, not negligent — enterprise-grade means knowing your tier, not
maximal knobs.

**Worked example: the same single-node Redis cache at three tiers.**

- **T1 — 40-line demo/portfolio module.** One `aws_elasticache_cluster`
  node; security group scoped to the VPC CIDR only; no
  `transit_encryption_enabled`, no `auth_token`, no replica, no
  `snapshot_retention_limit`, no CloudWatch alarm. This is T1-correct
  — every row in the table above allows "no" or "optional" at T1.
  Adding T2 controls here is not extra credit; it is unreviewed scope
  creep nobody asked for.

  ```hcl
  resource "aws_elasticache_cluster" "this" {
    cluster_id         = var.name
    engine             = "redis"
    node_type          = var.node_type
    num_cache_nodes    = 1
    security_group_ids = [aws_security_group.this.id] # VPC-CIDR SG
    # no transit_encryption_enabled, no auth_token, no snapshots
  }
  ```

- **T2 — same workload, production.** Add `transit_encryption_enabled
  = true` plus an `auth_token` (or IAM auth where the engine supports
  it); `automatic_failover_enabled = true` with a replica node; a
  named `snapshot_retention_limit`; a `noeviction` `maxmemory-policy`
  parameter; a CloudWatch alarm on `DatabaseMemoryUsagePercentage` and
  on connection/engine errors.

  ```hcl
  resource "aws_elasticache_replication_group" "this" {
    replication_group_id       = var.name
    engine                     = "redis"
    node_type                  = var.node_type
    num_cache_clusters         = 2
    automatic_failover_enabled = true
    transit_encryption_enabled = true
    auth_token_wo              = var.auth_token_wo # write-only, TF >=1.11
    auth_token_wo_version      = var.auth_token_wo_version
    snapshot_retention_limit   = 7 # named retention
  }

  resource "aws_cloudwatch_metric_alarm" "memory" {
    alarm_name          = "${var.name}-memory-high"
    metric_name         = "DatabaseMemoryUsagePercentage"
    comparison_operator = "GreaterThanThreshold"
    threshold           = 80
  }
  ```

- **T3 — regulated.** Everything in T2, plus a customer-managed KMS
  key (`kms_key_id`) with a key policy scoped to the consuming service
  role; full log delivery (slow-log and engine-log to CloudWatch Logs
  with an explicit retention policy); an SNS topic wired to the
  on-call rotation; and the module itself becomes a mandated wrapper
  (an internal `terraform-aws-elasticache-redis` that hardcodes these
  knobs) rather than a raw resource callers can under-configure.

  ```hcl
  module "redis" {
    source     = "git::https://example.com/terraform-aws-elasticache-redis.git?ref=v3.2.0"
    name       = var.name
    kms_key_id = aws_kms_key.redis.arn # CMK, policy scoped to service role
    log_delivery = [
      { type = "slow-log", destination = aws_cloudwatch_log_group.slow.name },
      { type = "engine-log", destination = aws_cloudwatch_log_group.engine.name },
    ]
    log_retention_days  = 400 # explicit, not provider default
    alarm_sns_topic_arn = aws_sns_topic.ops.arn
  }
  ```

  A raw `aws_elasticache_replication_group` resource at T3 is itself a
  finding: the tier requires the mandated wrapper so the knobs above
  cannot be silently dropped by the next caller.

## Reference index (~1,500–2,000 lines across 4 refs)

| File | Read when… |
| --- | --- |
| [`references/module-design.md`](references/module-design.md) | Structuring or reviewing a module: standard file layout, naming (never echo the resource type in a resource name — `aws_instance.web`, not `aws_instance.web_instance`), variable/output field order, composition + dependency inversion, `create_*`/`enable_*` feature flags, `examples/`/`tests/` shape, terraform-docs, house-style AWS-flavored HCL examples, or diagnosing a god-module / thin-wrapper / hardcoded-literal / output-sprawl smell. |
| [`references/state-and-environments.md`](references/state-and-environments.md) | Choosing or auditing a backend: the bootstrap chicken-and-egg pattern, blast-radius state splitting (env × layer), cross-state data flow, or the CONTESTED directory-per-environment (house rule) vs CLI-workspaces (reserved for ephemeral/PR stacks) question — both positions stated. |
| [`references/security-and-gates.md`](references/security-and-gates.md) | Wiring or reviewing the pinning matrix, secrets mechanics (ephemeral / `_wo` / runtime refs and the `_wo_version` bump), SG least-privilege, encryption defaults, the fmt→validate→tflint→trivy→plan→apply pipeline, OIDC, pre-commit-terraform, drift detection, or Infracost. |
| [`references/modern-features.md`](references/modern-features.md) | Deciding whether to adopt a 1.3–1.15 feature: `terraform test` + mocks + parallelism, check/pre/postconditions, `moved`/`import`/`removed`, provider functions, `templatestring`, `optional()` attributes, 1.14 query/actions, 1.15 dynamic source/`deprecated`, or the OpenTofu divergence list. |

Read only the reference relevant to the current decision. Each file
carries its own headings; cite a specific rule as
`references/<file>.md#<anchor>`, where `<anchor>` is the kebab-case
slug of the heading text exactly as written — for example
`security-and-gates.md#secrets-mechanics` or
`modern-features.md#terraform-test`.

## Routing: deep dives go to terraform-skill

This skill owns authoring conventions: module shape, variable/output
hygiene, tagging, the gate pipeline, and tiering — the four references
above. It does not own failure diagnosis or large-scale surgery.

| Concern | Owner |
| --- | --- |
| Module shape, hygiene, tagging, gates, tiering | **this skill** (`references/*`) |
| Corrupt / locked / drifted state surgery, state disaster recovery | `terraform-skill` |
| Large-scale provider/module version upgrade sweeps | `terraform-skill` |
| `count` ↔ `for_each` refactors at scale (renumber without destroy/recreate) | `terraform-skill` |

Before routing, ask:

1. **Is this a new-code question** ("how should I shape this module /
   variable / backend / gate")? Stay here — read the matching
   reference from the index above.
2. **Is this a broken-state question** ("plan won't unlock", "state
   drifted from reality", "apply half-applied and now nothing
   matches")? Route to `terraform-skill` — do not attempt manual
   `terraform state` surgery from a rule in this file; none is
   documented here on purpose.
3. **Is this a bulk-refactor question** across dozens of resources or
   modules (provider major-version bump, `count`→`for_each` at scale)?
   Route to `terraform-skill` — the mechanical sequencing (`moved`
   blocks, `-generate-config-out`, parallel-safe batching) is his
   domain, not a house convention.
4. **Still unsure?** Prefer this skill for anything a code reviewer
   would flag on a normal PR; prefer `terraform-skill` for anything an
   on-call engineer would page someone about.

`terraform-skill` (Anton Babenko, Apache-2.0,
https://github.com/antonbabenko/terraform-skill) is declared as a
dependency of this plugin. Install it once, then invoke it through the
Skill tool for anything in the second column above — never re-derive
his method into these references:

```
/plugin install terraform-skill@omniagents
```

or, from his own marketplace directly:

```
/plugin marketplace add antonbabenko/agent-plugins
/plugin install terraform-skill@antonbabenko
```

(marketplace source: https://github.com/antonbabenko/agent-plugins)

If `terraform-skill` is not installed, cite the canonical sources
inline instead of guessing at his method — never restate his content
as if it were house material:

- HashiCorp Style Guide —
  https://developer.hashicorp.com/terraform/language/style
- Standard Module Structure —
  https://developer.hashicorp.com/terraform/language/modules/develop/structure
- Module composition —
  https://developer.hashicorp.com/terraform/language/modules/develop/composition
- Google Cloud best practices —
  https://docs.cloud.google.com/docs/terraform/best-practices/general-style-structure
- AWS Prescriptive Guidance —
  https://docs.aws.amazon.com/prescriptive-guidance/latest/terraform-aws-provider-best-practices/structure.html
- Gruntwork Terraform Style Guide —
  https://docs.gruntwork.io/guides/style/terraform-style-guide/

## What this skill does NOT cover

- **Pulumi, CDK, or Kubernetes manifests.** Different tools, different
  rulebooks — this file is Terraform-OSS-CLI only. A CDK-for-Terraform
  (`cdktf`) question is also out of scope; it is a different authoring
  surface even though it emits the same plan/apply model underneath.
- **Failure-mode depth.** State corruption/lock/drift surgery,
  large-scale migrations, and at-scale `count`↔`for_each` refactors
  are routed to `terraform-skill` above, never re-derived here.
- **Provider resource catalogs.** Which `aws_*` / `google_*` /
  `azurerm_*` resource or argument fits a given service is provider
  documentation, not house convention — this skill governs shape and
  hygiene, not which resource block solves a given cloud problem.
- **Cloud-vendor pricing.** Cost modeling belongs to Infracost or the
  vendor calculator — see `security-and-gates.md` — not this file.

If a question lands outside this scope, say so rather than bending one
of the references to fit. If a question lands inside the scope but the
answer isn't in the references yet, that is a signal the catalogue
should be extended — flag it and propose the addition rather than
improvising silently.
