# Module Design

Read this file when structuring a new module or reviewing one on a PR: file
layout, naming, variable/output hygiene, composition and dependency
inversion, feature flags, the `examples/`/`tests/` shape, and the five
module-shape smells a reviewer should flag on sight. Scope is Terraform
≥ 1.11 OSS CLI, AWS-flavored — the same floor as the parent skill. State,
security/gates, and modern-language-feature adoption live in the sibling
references; do not re-derive them here.

## Standard structure

- Lay out every module with the same four files at minimum: `main.tf`
  (resources), `variables.tf` (inputs), `outputs.tf` (exports), and
  `versions.tf` (`terraform { required_version ...; required_providers
  ... }`). The style guide additionally permits `terraform.tf`,
  `providers.tf`, `backend.tf`, and `locals.tf` as separate files when a
  module's provider or locals surface is large enough to deserve its own
  file — do not cram them all into `main.tf` once the file exceeds a
  screenful. See the HashiCorp Style Guide —
  https://developer.hashicorp.com/terraform/language/style — and Standard
  Module Structure —
  https://developer.hashicorp.com/terraform/language/modules/develop/structure.
  A module with the core septet plus a logical-area split looks like this
  on disk — every filename answers "what lives in here" without opening
  it:

  ```text
  modules/ecs-service/
  ├── README.md
  ├── versions.tf    # required_version + required_providers, no provider block
  ├── variables.tf   # inputs, alphabetized
  ├── locals.tf      # computed values referenced by main.tf
  ├── network.tf     # security group, target group attachment
  ├── compute.tf     # ECS task definition, ECS service
  ├── iam.tf         # task role, execution role, policies
  ├── outputs.tf     # exports, alphabetized
  ├── examples/
  │   └── basic/
  │       └── main.tf
  └── tests/
      └── basic.tftest.hcl
  ```

- Split large configurations by logical area, not by resource count or
  creation order: `network.tf`, `compute.tf`, `iam.tf` are correct splits;
  `resources1.tf`, `resources2.tf`, or `misc.tf` are not — a filename must
  tell a reviewer what subsystem lives inside without opening it. Same
  Style Guide reference as above.
- Never configure a `provider` block inside a reusable module. Declare only
  `required_providers` in `versions.tf` and accept a fully configured
  provider from the caller; a module that hardcodes
  `provider "aws" { region = "us-east-1" }` cannot be instantiated twice in
  the same root (e.g. once per region) and cannot be tested with a mock
  provider. See Standard Module Structure —
  https://developer.hashicorp.com/terraform/language/modules/develop/structure.

  ```hcl
  # versions.tf — reusable module: declare requirements, never configure providers
  terraform {
    required_version = ">= 1.11"

    required_providers {
      aws = {
        source  = "hashicorp/aws"
        version = ">= 5.0"
      }
    }
  }
  ```

  When a root needs a module to run against a non-default provider
  configuration (a second region, a second account), pass it explicitly
  with the `providers` meta-argument at the call site — the module still
  declares no provider block of its own:

  ```hcl
  provider "aws" {
    alias  = "replica"
    region = "us-west-2"
  }

  module "replica_bucket" {
    source    = "./modules/s3-bucket"
    providers = { aws = aws.replica }
    name      = "${var.name}-replica"
  }
  ```

- Every module that is *published* — consumed by more than one root, or by
  people outside the immediate team — ships four extras beyond the four
  core files: a `README.md` (usage, inputs, outputs), an `examples/`
  directory containing at least one deployable configuration, a `tests/`
  directory of `.tftest.hcl` files, and, when the module composes
  sub-modules, a nested `modules/` directory (never siblings at the repo
  root). An internal module consumed only by its own root does not need
  the full septet — the bar is "does anyone other than the author read this
  without asking first." See Standard Module Structure —
  https://developer.hashicorp.com/terraform/language/modules/develop/structure
  — and the community module reference shape at terraform-aws-modules —
  https://github.com/terraform-aws-modules.
- Name the repository of a published module `terraform-<provider>-<name>`
  (for example `terraform-aws-elasticache-redis`) — this is the naming
  convention the Terraform Registry itself expects for auto-discovery, and
  it is the pattern used across terraform-aws-modules and reflected in the
  distilled community conventions at terraform-best-practices.com —
  https://www.terraform-best-practices.com.

## Naming

- Name resources, data sources, and module blocks with descriptive
  snake_case nouns and never repeat the resource type inside the local
  name — the type is already the left-hand side of the label, restating it
  is pure noise every time the address is read (`aws_instance.web`, not
  `aws_instance.web_instance`; `module.cache`, not `module.cache_module`).
  See the HashiCorp Style Guide —
  https://developer.hashicorp.com/terraform/language/style.

  ```hcl
  resource "aws_instance" "web" { # good — noun, no type echo
    ami           = var.ami_id
    instance_type = var.instance_type
  }
  resource "aws_instance" "web_instance" { # bad — repeats "instance" in the name
    ami           = var.ami_id
    instance_type = var.instance_type
  }
  ```

- Apply the same no-type-echo rule to `data` blocks, `locals`, and
  `variable`/`output` identifiers: `data "aws_vpc" "selected"`, not
  `data "aws_vpc" "vpc_data"`; `variable "instance_type"`, not
  `variable "instance_type_var"`. The label already carries the type in
  every one of these block kinds, so the same argument against redundancy
  applies uniformly. Same Style Guide reference as above.
- Prefer singular nouns for the local name even when `count` or `for_each`
  produces many instances (`aws_subnet.private`, addressed as
  `aws_subnet.private[0]` or `aws_subnet.private["us-east-1a"]`) — the
  plurality lives in the index, not in the name; do not write
  `aws_subnet.privates`. Same Style Guide reference.
- Name boolean variables that gate optional behavior with a verb prefix —
  `create_*` or `enable_*` — rather than a bare adjective; `enable_backups`
  reads unambiguously as a toggle at the call site, where `backups = true`
  could be mistaken for a nested configuration object. This is the same
  naming convention the Feature flags section below builds on, and it
  follows from the same no-noise argument: the prefix is signal, not
  decoration. Same Style Guide reference as above.
- Key a `for_each` map or set with a value that is stable across plans —
  a name, an ID, a CIDR — never with a numeric index computed from
  `count.index` translated into a map; an unstable key forces Terraform to
  destroy and recreate every entry after the changed one, defeating the
  reason to prefer `for_each` over `count` in the first place. Same Style
  Guide reference as above.

## Variables and outputs

- Give every variable a `type` and a `description` — an undescribed or
  untyped variable is a review-blocking finding, not a style nit, because
  the next caller has no way to know what to pass without reading the
  module's resource bodies. Order the fields inside every `variable` block
  the same way every time: `type` → `description` → `default` →
  `sensitive` → `validation`. See the HashiCorp Style Guide —
  https://developer.hashicorp.com/terraform/language/style.
- Give every `output` a `description` too — an output without a
  description forces the caller to go read the module internals to learn
  what value they are wiring up. Same Style Guide reference.
- Keep `variables.tf` and `outputs.tf` alphabetized by identifier within
  each file. A reviewer diffing a PR that adds one variable should see one
  new block in roughly the right place, not a reordering of the whole
  file. Same Style Guide reference.
- Prefer `optional(type, default)` object attributes over null-juggling
  when a variable is a structured object with some fields the caller may
  omit — it documents the default inline instead of pushing every caller
  through a `coalesce()`/`try()` dance at every reference site. See Type
  Constraints —
  https://developer.hashicorp.com/terraform/language/expressions/type-constraints.
- In every *published* module, export the useful attributes of every
  resource the module creates — an ID, an ARN, an endpoint, a name — so
  composition with other modules does not require a `data` source lookup
  the module itself could have exported directly. The counter-rule is
  output sprawl: do not add an output to a root configuration (as opposed
  to a published module) that nothing downstream consumes — a root's
  outputs are for CLI/CI consumption or genuine cross-state references,
  and an output nobody reads is dead surface a future refactor has to
  reason about anyway. See the full anti-pattern entry below. Same Style
  Guide reference as above.

  ```hcl
  # variables.tf — field order: type -> description -> default -> sensitive -> validation
  variable "node_type" {
    type        = string
    description = "ElastiCache node instance type, e.g. cache.t4g.micro."
    default     = "cache.t4g.micro"
  }

  variable "tags" {
    type = object({
      owner    = string
      env      = string
      ttl_days = optional(number, 30) # optional(type, default) beats null-juggling
    })
    description = "Resource tags; ttl_days defaults when the caller omits it."
  }

  # outputs.tf — every created resource exports its useful attributes; alphabetized
  output "cluster_arn" {
    description = "ARN of the created cache cluster."
    value       = aws_elasticache_cluster.this.arn
  }

  output "cluster_endpoint" {
    description = "Connection endpoint of the created cache cluster."
    value       = aws_elasticache_cluster.this.cache_nodes[0].address
  }
  ```

- The full field order matters most once a variable also carries
  `sensitive` and `validation` — put `sensitive` before `validation` so a
  reviewer scanning top-to-bottom learns "this value is redacted in plan
  output" before reaching the constraint that governs it:

  ```hcl
  variable "auth_token" {
    type        = string
    description = "Redis AUTH token for in-transit authentication."
    default     = null
    sensitive   = true

    validation {
      condition     = var.auth_token == null || length(var.auth_token) >= 16
      error_message = "auth_token must be at least 16 characters when set."
    }
  }
  ```

  `sensitive = true` only redacts the value from CLI/plan output — it does
  not keep the value out of state; that guarantee belongs to ephemeral
  resources and write-only arguments, covered in the security-and-gates
  reference, not here. Same Style Guide reference as above.

## Composition

- Keep the module tree flat: one level of child modules, composed together
  in the root. A root calling three child modules is flat; a root calling
  a module that itself calls another module that calls another module is
  deep nesting — each extra level is a layer of indirection a reader has
  to tunnel through to find which resource actually gets created:

  ```text
  # GOOD — flat: root composes three child modules directly.
  root/
  ├── main.tf         # module "network" {}, module "cluster" {}, module "database" {}
  ├── modules/
  │   ├── network/
  │   ├── cluster/
  │   └── database/

  # BAD — deep nesting: three hops between the root and the real resource.
  root/
  └── modules/app/                    # module "app"
      └── modules/service/            #   -> module "service"
          └── modules/task/           #     -> module "task"
              └── (aws_ecs_task_definition lives here, three levels down)
  ```

  See Module composition —
  https://developer.hashicorp.com/terraform/language/modules/develop/composition.
- Practice dependency inversion: a module receives the IDs, ARNs, and
  objects it depends on as input variables. Do not bury a `data` source
  lookup of "assumed" infrastructure inside a module — a `data "aws_vpc"`
  filtered by a tag convention breaks silently the day someone renames the
  VPC or the module runs in an account where that tag doesn't exist. The
  rule is simple to state and easy to check in review: create-or-query
  belongs to the caller, not the callee. Same Module composition
  reference as above.

  ```hcl
  # GOOD — dependency inversion: the caller creates-or-queries, the module just consumes.
  module "app_service" {
    source     = "./modules/ecs-service"
    vpc_id     = var.vpc_id
    subnet_ids = var.private_subnet_ids
  }

  variable "vpc_id" {
    type        = string
    description = "ID of the VPC the service deploys into."
  }

  variable "private_subnet_ids" {
    type        = list(string)
    description = "Private subnet IDs for the service's ENIs."
  }

  # BAD — the module buries an "assumed infrastructure" lookup instead of receiving it.
  data "aws_vpc" "assumed" {
    tags = { Name = "prod-vpc" } # fragile: breaks the moment tagging changes
  }
  ```

- Create a module only when it raises the level of abstraction over the
  raw resources it wraps — a module that groups a security group, an
  `aws_elasticache_replication_group`, and a parameter group into "a
  cache" is worth the indirection. A module that wraps exactly one
  resource one-to-one is not: inline the resource in the caller instead.
  See the full thin-wrapper anti-pattern entry below, and Module
  composition — same reference as above.

## Feature flags

- Gate optional sub-features of a module with a boolean variable named
  `create_*` or `enable_*` (for example `create_read_replica`,
  `enable_deletion_protection`), and drive the corresponding resource's
  `count` (0 or 1) or `for_each` (empty set or populated set) from that
  boolean. This is the idiom used throughout terraform-aws-modules and
  lets a caller opt in or out of a sub-feature without forking the module
  or passing a sentinel value through an unrelated variable. See the
  community module reference shape —
  https://github.com/terraform-aws-modules — and the distilled convention
  write-up at terraform-best-practices.com —
  https://www.terraform-best-practices.com.

  ```hcl
  variable "create_read_replica" {
    type        = bool
    description = "Whether to create a read replica for this database."
    default     = false
  }

  resource "aws_db_instance" "replica" {
    count               = var.create_read_replica ? 1 : 0
    identifier          = "${var.name}-replica"
    replicate_source_db = aws_db_instance.primary.identifier
    instance_class      = var.instance_class
  }
  ```

- Prefer `for_each` over `count` whenever the flag gates a *set* of
  optional sub-resources keyed by something stable (a map of
  environments, a set of allowed CIDRs) rather than a single 0/1 toggle —
  `for_each` keeps each instance's state address stable when the set
  changes, where `count` renumbers everything after the changed index.
  Same terraform-aws-modules reference as above.
- The same `create_*`/`enable_*` idiom extends one level down, inside a
  single resource, via `dynamic` blocks: a boolean flag can gate whether a
  repeated nested block is emitted at all, not just whether the whole
  resource exists.

  ```hcl
  variable "enable_lifecycle_rule" {
    type        = bool
    description = "Whether to attach an expiration lifecycle rule to the bucket."
    default     = false
  }

  resource "aws_s3_bucket_lifecycle_configuration" "this" {
    count  = var.enable_lifecycle_rule ? 1 : 0
    bucket = aws_s3_bucket.this.id

    dynamic "rule" {
      for_each = var.enable_lifecycle_rule ? [1] : []
      content {
        id     = "expire-noncurrent"
        status = "Enabled"
        expiration {
          days = 90
        }
      }
    }
  }
  ```

  Same terraform-aws-modules reference as above.

## Module tests and examples

- Every published module ships a deployable `examples/` directory — at
  minimum one example that instantiates the module with realistic values
  and can be `terraform init && terraform apply`'d in a disposable
  account. An example that only exists to satisfy a linter and cannot
  actually be applied is worse than no example: it teaches the wrong
  shape. See Google Cloud's Terraform testing guidance —
  https://docs.cloud.google.com/docs/terraform/best-practices/testing.
- Every published module also ships a `tests/*.tftest.hcl` smoke test
  using `command = plan` against mocked providers (`mock_provider`,
  `override_resource` — available since 1.7) — this is the fast,
  no-cloud-credentials-required test that runs on every commit and catches
  a broken variable reference or a typo'd resource address before a human
  ever runs `terraform plan` for real. Reserve `command = apply` runs
  against real infrastructure for the periodic integration layer described
  in the parent skill's tiering table, not for every-commit CI. See
  Terraform Tests —
  https://developer.hashicorp.com/terraform/language/tests.

  ```hcl
  # tests/basic.tftest.hcl
  mock_provider "aws" {}

  run "creates_cluster_with_expected_node_type" {
    command = plan

    variables {
      name      = "test-cache"
      node_type = "cache.t4g.micro"
    }

    assert {
      condition     = aws_elasticache_cluster.this.node_type == "cache.t4g.micro"
      error_message = "node_type was not passed through to the cluster resource"
    }
  }
  ```

- Wire `terraform-docs` markers into the module's `README.md`
  (`<!-- BEGIN_TF_DOCS -->` / `<!-- END_TF_DOCS -->`) so the inputs and
  outputs tables regenerate from the actual `variables.tf`/`outputs.tf`
  instead of drifting out of sync with hand-written prose the first time
  someone adds a variable and forgets the doc. Run it in pre-commit or CI,
  not as a one-time manual step:

  ```text
  <!-- README.md -->
  ## Inputs
  <!-- BEGIN_TF_DOCS -->
  <!-- fed by `terraform-docs markdown table .` in pre-commit -->
  <!-- END_TF_DOCS -->
  ```

  A minimal `.terraform-docs.yml` pins the format so every module in the
  repo renders the same table shape:

  ```yaml
  formatter: "markdown table"
  sections:
    show: [inputs, outputs]
  output:
    file: "README.md"
    mode: inject
  ```

  See terraform-docs — https://terraform-docs.io/.
- Treat the example under `examples/` as the object of the integration
  test, not a separate artifact: the test pyramid's apply-based layer
  should run `terraform apply` against the example itself, so the example
  a human reads to learn the module is the same configuration CI proves
  still works. Same Google Cloud testing reference as above.

## Anti-patterns

Each entry below is a shape a reviewer should flag on sight in a module
PR — the antidote to each is stated in the section above it; this section
exists to name the smell so it is quick to cite in review comments.

### God module

**What it is.** A single module that manages several unrelated pieces of
infrastructure — a VPC, an ECS cluster, an RDS instance, and an S3 bucket,
all in one `modules/everything` — because it was easier to add "just one
more resource" than to draw a boundary. The module has no coherent
abstraction: its name describes the whole application, not a capability.

```hcl
# BAD — one module doing networking, compute, and data-tier work at once.
module "everything" {
  source = "./modules/everything"

  vpc_cidr          = "10.0.0.0/16"
  cluster_name      = "app"
  db_instance_class = "db.t3.medium"
  bucket_name       = "app-uploads"
}
```

**Telltale signs.**

- The module's variable list spans three or more unrelated AWS service
  namespaces (`vpc_*`, `cluster_*`, `db_*`, `bucket_*` all in one
  `variables.tf`).
- Nobody can describe the module's purpose in one noun phrase — the
  description in the README is a paragraph, not a sentence.

**Why it bites.** Every unrelated change re-plans the whole module, so a
one-line S3 bucket-policy edit produces a plan diff that also touches the
VPC and the database — a reviewer cannot tell what actually changed, and a
`terraform apply` for the trivial edit carries the blast radius of the
whole stack. See Module composition —
https://developer.hashicorp.com/terraform/language/modules/develop/composition.

### Thin single-resource wrapper

**What it is.** A module whose entire body is one resource block passed
through 1:1 — every module variable maps directly to one resource
argument, with no added abstraction, no composition of a second resource,
no policy decision baked in.

**Telltale signs.**

- `main.tf` in the module has exactly one `resource` block, and every one
  of its arguments is a bare `var.*` reference with no derived value.
- The module has never grown a second resource in its history — it was
  never going to raise the abstraction, only rename it.

**Why it bites.** It adds a call boundary, a `source`/`version` pin, and
an extra layer in `terraform plan` output for zero abstraction benefit —
the caller could write the resource directly and get the same behavior
with one less indirection to open when debugging. See Module composition —
https://developer.hashicorp.com/terraform/language/modules/develop/composition.

### Hardcoded literals

**What it is.** Magic values — an AMI ID, a CIDR block, an instance type,
an account number — written directly into a resource argument instead of
promoted to a `variable` or a `locals` entry, so the only way to change
the value is to edit the module's source.

**Telltale signs.**

- A quoted AMI ID, account number, or CIDR block appears inside a
  `resource` block in `main.tf` rather than in `variables.tf` or
  `locals.tf`.
- The only way a second environment gets a different value is a forked
  copy of the module, not a different `.tfvars` file.

**Why it bites.** It silently forks the module the first time a second
caller needs a different value: they either fork the source or send a PR
to parameterize it retroactively, and until then every consumer is stuck
on the original author's literal. See the HashiCorp Style Guide —
https://developer.hashicorp.com/terraform/language/style.

### Output sprawl

**What it is.** A root configuration (not a published module) accumulating
outputs that nothing — no CI step, no remote-state consumer, no operator
running `terraform output` — ever reads. Each one seemed cheap to add at
the time; the module or root now exports more surface than anyone
maintains.

**Telltale signs.**

- `grep`-ing the rest of the repo and any downstream `terraform_remote_state`
  data source for an output's name turns up zero references.
- New outputs get added "just in case" during a PR without a named
  consumer in the PR description.

**Why it bites.** Every unused output is state a future refactor has to
preserve or consciously break, and a wall of outputs hides the few that
actually matter to a reader trying to learn what a config produces. See
the HashiCorp Style Guide —
https://developer.hashicorp.com/terraform/language/style.

### Deep nesting

**What it is.** A root that calls a module that calls another module that
calls another module — three or more levels of indirection between the
root and the resource that actually gets created, rather than the flat,
one-level tree the standard structure calls for.

**Telltale signs.**

- A `terraform state list` address contains two or more `module.` segments
  before the resource type (`module.a.module.b.module.c.aws_instance.this`).
- Changing one leaf resource's argument requires editing variables in every
  intermediate module to thread the value down.

**Why it bites.** A reader tracing a single resource's arguments has to
open N module boundaries in sequence, and a `terraform plan` address like
`module.a.module.b.module.c.aws_instance.this` is both harder to target
with `-target` and harder to reason about during a `moved` block refactor.
See Module composition —
https://developer.hashicorp.com/terraform/language/modules/develop/composition.

_Verified as of 2026-07; sources re-checked against docs/superpowers/research/2026-07-20-*.md._
