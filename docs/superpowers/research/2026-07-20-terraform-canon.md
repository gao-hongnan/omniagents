# Production Terraform Rulebook Corpus — verified July 2026
(research digest from web-research agent; source material for omniagents-iac terraform skill)

Version baseline: Terraform 1.15 (Apr 2026) / 1.14 (Nov 2025) are the supported lines (endoflife.date/terraform). OpenTofu ~1.10–1.12.

## 1. Official canon (the sources a rulebook must cite)

- HashiCorp Style Guide — file layout, naming, pinning, gitignore, meta-arg order: https://developer.hashicorp.com/terraform/language/style
- Standard Module Structure: https://developer.hashicorp.com/terraform/language/modules/develop/structure · Module composition ("flat trees, dependency inversion"): https://developer.hashicorp.com/terraform/language/modules/develop/composition
- Google Cloud best practices (style/structure, operations, security, testing, cross-config): https://docs.cloud.google.com/docs/terraform/best-practices/general-style-structure (siblings: /operations, /security, /testing, /cross-config-communication)
- AWS Prescriptive Guidance, Terraform AWS Provider best practices: https://docs.aws.amazon.com/prescriptive-guidance/latest/terraform-aws-provider-best-practices/structure.html (siblings: /backend.html, /community.html) · AWS I&A team standards: https://aws-ia.github.io/standards-terraform/
- Gruntwork Terraform Style Guide: https://docs.gruntwork.io/guides/style/terraform-style-guide/ · Production-Grade Infrastructure Checklist: https://www.gruntwork.io/devops-checklist
- Community module reference shape: https://github.com/terraform-aws-modules (Anton Babenko) · distilled conventions: https://www.terraform-best-practices.com

## 2. Module design

- Lay out every module as `main.tf` / `variables.tf` / `outputs.tf` / `versions.tf` (style guide also allows `terraform.tf`, `providers.tf`, `backend.tf`, `locals.tf`); split large configs by logical area (`network.tf`, `compute.tf`), never `resources1.tf`.
- Ship `README.md`, `examples/`, optional `modules/` (nested), `tests/` in every published module; repo name `terraform-<provider>-<name>`.
- Name resources with snake_case descriptive nouns; never repeat the resource type in the name (`aws_instance.web`, not `aws_instance.web_instance`).
- Give every variable a `type` and `description`; order fields type → description → default → sensitive → validation; give every output a `description`; keep variables/outputs alphabetized.
- Create a module only when it raises abstraction over raw resources; do not write thin single-resource wrapper modules — inline the resource instead.
- Keep the module tree flat — one level of child modules, composed in the root; avoid deep nesting.
- Practice dependency inversion: modules receive dependencies (VPC IDs, ARNs) as input variables; do not bury data-source lookups of "assumed" infrastructure inside modules — let callers create-or-query and pass objects in.
- Gate optional sub-features with `count`/`for_each` driven by `create_*` / `enable_*` boolean variables (terraform-aws-modules idiom).
- Never configure `provider` blocks inside reusable modules; declare only `required_providers` and accept providers from the caller.
- Anti-patterns to ban: god modules managing unrelated infrastructure, hardcoded literals, missing descriptions, outputs nobody consumes in root configs; in published modules, do export the useful attributes of every created resource for composability.

## 3. Modern language features (adoption status, July 2026)

- `terraform test` (1.6+, HCL `.tftest.hcl`, mocking 1.7, `-parallelism` + parallel runs 1.12): production-ready, use it. https://developer.hashicorp.com/terraform/language/tests
- `check` blocks (1.5) for non-blocking assertions; variable `validation`, resource `precondition`/`postcondition` for blocking contracts.
- Do refactors in config: `moved` (1.1), `import` blocks + `-generate-config-out` (1.5), `removed` (1.7) — not `terraform state mv/rm` by hand.
- Provider-defined functions (1.8, e.g. `provider::aws::arn_parse`): GA.
- Ephemeral values/resources (1.10) + write-only arguments (`*_wo` + `_wo_version` bump pattern, 1.11): the current secrets mechanism — secrets never touch plan/state. https://developer.hashicorp.com/terraform/language/manage-sensitive-data/ephemeral
- S3 native locking `use_lockfile = true` (1.10 experimental, 1.11 GA); `dynamodb_table` deprecated. https://developer.hashicorp.com/terraform/language/backend/s3
- `templatestring` (1.9); `optional(type, default)` object attributes (1.3) — use instead of null-juggling.
- 1.12: OCI backend, short-circuit `&&`/`||`, import `identity`. 1.14: list/search resources + `terraform query` (bulk discovery/import), `actions` blocks + `-invoke` (declarative day-2 ops). 1.15: variables in module `source`/`version`, `deprecated` attribute on variables/outputs, output `type`, `convert()`.
- Terraform Stacks (`.tfcomponent.hcl` + `.tfdeploy.hcl`): GA since HashiConf 2025 but HCP-Terraform-only — not for OSS-CLI rulebooks.
- OpenTofu divergence: state/plan encryption (1.7+), provider `for_each` (1.9), OCI registries + its own `use_lockfile` (1.10), earlier `deprecated` marks; `.tofu` extension.

## 4. State & environments

- Always use a remote, versioned, encrypted, access-logged backend; never commit state; block public access on the bucket.
- New S3 backends: `use_lockfile = true`, no DynamoDB table; existing ones may run both during migration, then drop the table.
- CONTESTED — envs via CLI workspaces: HashiCorp style guide endorses workspace-per-env (HCP workspaces = separate state/vars/RBAC), but Google, Gruntwork, and community consensus say directory-per-environment (or Terragrunt) because CLI workspaces share backend/credentials and invite wrong-env applies; reserve CLI workspaces for ephemeral/PR stacks.
- Terragrunt remains the DRY orchestrator for large multi-account estates (units + `include`, dependency graph).
- Bootstrap the state bucket with a tiny separate config on local state (run once), then `terraform init` -migrate everything else onto it.
- Split state by blast radius: one state per env × service/layer; small states plan faster and fail smaller; share values across states via remote state or data-only modules, never one mega-state.

## 5. Versioning & pinning

- Set `required_version` (e.g. `>= 1.11`) in every root; reusable modules declare only a minimum.
- Providers: root modules pin tightly (`~>` pessimistic minor, or exact); shared/reusable modules use `>=` minimums only, so callers can converge.
- Pin module sources: registry modules with exact `version`, git sources with `?ref=` tag/SHA (never a branch); tag releases semver `x.y.z`.
- Commit `.terraform.lock.hcl` for every root; run `terraform providers lock` for all CI platforms.
- Automate bumps with Renovate (terraform + terragrunt managers, lockFileMaintenance) or Dependabot; Renovate is the deeper of the two.

## 6. Security & compliance gates

- 2026 default stack: `terraform fmt -check` + `terraform validate` + TFLint (with provider ruleset plugins) + one policy scanner: Trivy (absorbed tfsec — same check IDs) or Checkov.
- Do not adopt tfsec (deprecated → Trivy) or Terrascan (archived by Tenable, Nov 2025).
- Secrets: mark `sensitive = true`; prefer ephemeral resources/write-only args so secrets never enter state; otherwise reference SSM/Secrets Manager/Vault at runtime; never plaintext secrets in committed `.tfvars`; treat state as secret regardless.
- Set `default_tags` on the AWS provider in the root (owner/env/cost-center/managed-by); resource-level tags only for per-resource extras.
- Encrypt by default (state bucket SSE-KMS, EBS/RDS/S3 encryption args) and write least-privilege security groups: no `0.0.0.0/0` ingress, reference SGs not CIDRs; fail CI on high/critical findings.

## 7. CI/CD & hygiene

- Pipeline shape: fmt-check → validate → tflint → scan (trivy/checkov) → plan (saved artifact) → human review → apply the reviewed plan file.
- Run plan-on-PR / apply-on-merge with GitHub Actions OIDC → aws-actions/configure-aws-credentials assuming short-lived roles; zero long-lived cloud keys; separate read-only plan role from apply role.
- Generate module docs with terraform-docs via markers in README; enforce locally with pre-commit-terraform hooks (`terraform_fmt`, `terraform_validate`, `terraform_tflint`, `terraform_docs`, trivy/checkov hooks).
- Detect drift with scheduled plans in CI or HCP Terraform health assessments; surface cost deltas on PRs with Infracost.
- Platforms: Atlantis = self-hosted PR-comment plan/apply (runatlantis.io); HCP Terraform = managed runs/state/RBAC/Sentinel + Stacks; Spacelift = policy-as-code (OPA) multi-IaC; env0 = self-service environments + TTL/cost governance.

## 8. Testing

- 2026 consensus: `terraform test` is the first line — HCL unit/contract tests per module (`tests/*.tftest.hcl`, `command = plan` + mocked providers for fast CI, `command = apply` for integration), run on every commit; Terratest (Go) only for cross-system E2E behavior verification, run pre-release.
- Keep the classic pyramid: fmt/validate → linters/scanners → plan-based unit tests → apply-based integration on `examples/` (every module ships a deployable example) → periodic E2E; real-resource tests use disposable projects/accounts with auto-cleanup.

## What changed 2024 → 2026 (where stale skills go wrong)

1. State locking: DynamoDB lock tables are legacy — S3 `use_lockfile` GA'd in 1.11; `dynamodb_table` deprecated; new backends need no table.
2. Secrets: "secrets always end up in state" is obsolete — ephemeral resources (1.10) + write-only `_wo` arguments (1.11) keep them out entirely.
3. Scanners: tfsec is dead (merged into Trivy) and Terrascan is archived (Nov 2025); the only defensible 2026 picks are Trivy and/or Checkov.
4. Testing: native `terraform test` (1.6, mocks 1.7, parallelism 1.12) displaced Terratest as the default module-testing layer; Terratest is now E2E-only.
5. New surface: Stacks GA (HCP-only), `terraform query` + `actions` (1.14), dynamic module source/version + `deprecated` variables/outputs (1.15).
6. Version floor: current supported Terraform is 1.14/1.15; OpenTofu meaningfully diverges (state encryption, provider `for_each`, OCI registries) so rulebooks must say which tool they target.
