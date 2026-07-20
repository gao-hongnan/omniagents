# omniagents-iac Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `omniagents-iac` plugin — a `terraform` house-layer skill that links to antonbabenko/terraform-skill instead of repeating it, and a full-catalogue `docker` skill — per the approved spec at `docs/superpowers/specs/2026-07-20-iac-plugin-design.md`.

**Architecture:** New `plugins/iac/` plugin registered in `.claude-plugin/marketplace.json` with an additional external entry for Anton Babenko's terraform-skill. Skill content is authored FROM the three committed research digests in `docs/superpowers/research/` (2026-07-20) — no rules from memory. House shape mirrors `plugins/design-patterns/skills/system/` (SKILL.md posture+index, deep sibling reference files) with `plugins/python/skills/typings/SKILL.md` frontmatter conventions.

**Tech Stack:** Claude Code plugin marketplace (marketplace.json / plugin.json / SKILL.md), GitHub-flavored markdown, `claude plugin validate`.

## Global Constraints

- Repo: `/Users/gaohn/gaohn/packages/omniagents`, branch `feat/iac-plugin`. All commands run from repo root unless stated.
- NEVER run `make release`, `git push`, or version bumps — user-gated.
- NEVER touch these WIP paths (uncommitted user work): `plugins/design-patterns/skills/software/SKILL.md`, `plugins/design-patterns/skills/codebase-design/`, `plugins/tech-lead/agents/`, `plugins/tech-lead/commands/`, `.claude/`, `docs/superpowers/specs/2026-07-04-blindspot-pass-skill-design.md`. `git add` exact paths only — never `git add -A` / `git add .`.
- Source digests (committed, authoritative): `docs/superpowers/research/2026-07-20-terraform-canon.md`, `docs/superpowers/research/2026-07-20-docker-compose-canon.md`, `docs/superpowers/research/2026-07-20-iac-prior-art.md`. Every imperative rule in a reference file carries a source URL inline, taken from these digests or their primary sources.
- Line budgets (enforced with `wc -l` in each task): terraform SKILL.md 300–400; `module-design.md` 500–700; `state-and-environments.md` 300–400; `security-and-gates.md` 400–500; `modern-features.md` 300–400; terraform skill TOTAL ≤ 2,500. docker SKILL.md 250–350; `dockerfile.md` 1,000–1,500; `compose.md` 1,000–1,400; `hardening-and-supply-chain.md` 1,000–1,400; `ci-and-release.md` 800–1,200.
- House scanner is **Trivy** in BOTH skills (Checkov documented as alternative in terraform; Grype as second opinion in docker). Never recommend tfsec (dead → Trivy) or Terrascan (archived).
- CONTESTED rules carry both positions in one line, prefixed `CONTESTED —`. Required CONTESTED entries: workspaces-for-envs (terraform), distroless-vs-slim and compose-in-prod (docker).
- Every reference file ends with a `_Verified as of 2026-07; sources re-checked against docs/superpowers/research/2026-07-20-*.md._` line.
- No `TODO`, `TBD`, `WIP`, or placeholder text anywhere in shipped files.
- The tiering framework below is canonical; both SKILL.md files reproduce this table VERBATIM:

```markdown
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
```

- Markdown style: follow the `omniagents-writing:markdown-conventions` skill if available to the worker (ATX headings, fenced blocks with language tags, no bare URLs outside link/citation context, tables only for enumerable facts).
- Commit after every task; conventional-commit messages; end every commit body with:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`

---

### Task 1: Plugin scaffold + marketplace registration

**Files:**
- Create: `plugins/iac/.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json` (append one entry to `plugins` array)

**Interfaces:**
- Produces: plugin name `omniagents-iac`; skills directory `plugins/iac/skills/` that Tasks 3–12 fill; marketplace entry other tasks leave untouched.

- [ ] **Step 1: Write plugin.json**

```json
{
  "name": "omniagents-iac",
  "version": "0.8.0",
  "description": "Infrastructure-as-code conventions: Terraform module patterns + hygiene (house layer over antonbabenko/terraform-skill) and production Docker/compose rulebook",
  "author": {
    "name": "GAO Hongnan",
    "email": "hongnangao@gmail.com"
  },
  "homepage": "https://github.com/gao-hongnan/omniagents",
  "repository": "https://github.com/gao-hongnan/omniagents",
  "license": "MIT",
  "keywords": [
    "terraform",
    "docker",
    "compose",
    "iac",
    "aws",
    "conventions"
  ],
  "skills": "./skills/"
}
```

Version `0.8.0` matches the current lockstep version (see `.claude-plugin/marketplace.json` `metadata.version`); `make release` bumps all together later.

- [ ] **Step 2: Create the skills directory skeleton**

Run: `mkdir -p plugins/iac/skills/terraform/references plugins/iac/skills/docker/references`

- [ ] **Step 3: Register in marketplace.json**

Append to the `plugins` array (after the last existing entry, matching the existing entry shape exactly — read the file first to match field order):

```json
{
  "name": "omniagents-iac",
  "source": "./plugins/iac",
  "description": "Infrastructure-as-code conventions: Terraform module patterns + hygiene and production Docker/compose rulebook",
  "category": "infrastructure",
  "keywords": [
    "terraform",
    "docker",
    "compose",
    "iac",
    "aws"
  ]
}
```

- [ ] **Step 4: Validate**

Run: `make validate`
Expected: `claude plugin validate .` exits 0. If it fails on the empty skills dirs, create `plugins/iac/skills/terraform/SKILL.md` and `plugins/iac/skills/docker/SKILL.md` as minimal valid frontmatter-only stubs (name + one-line description) and note that Tasks 3/8 replace them wholesale.

- [ ] **Step 5: Commit**

```bash
git add plugins/iac/.claude-plugin/plugin.json .claude-plugin/marketplace.json
git status -s   # confirm ONLY these two paths staged
git commit -m "feat(iac): scaffold omniagents-iac plugin + marketplace entry"
```

---

### Task 2: External terraform-skill entry + dependency wiring

**Files:**
- Modify: `.claude-plugin/marketplace.json` (second new entry)
- Modify: `plugins/iac/.claude-plugin/plugin.json` (`dependencies` field)

**Interfaces:**
- Consumes: Task 1's marketplace entry.
- Produces: external plugin name `terraform-skill` that the terraform SKILL.md (Task 3) routing table names; a recorded RESOLUTION OUTCOME (A, B, or C below) that Task 3 Step 1 reads before writing the routing section.

- [ ] **Step 1: Inspect Babenko's marketplace layout**

Run: `curl -s https://raw.githubusercontent.com/antonbabenko/agent-plugins/main/.claude-plugin/marketplace.json | head -60`

Identify: his marketplace `name`, the `terraform-skill` plugin entry, and its `source` shape. If the URL 404s, try the default branch via `curl -s https://api.github.com/repos/antonbabenko/agent-plugins | python3 -c "import json,sys; print(json.load(sys.stdin)['default_branch'])"` and retry.

- [ ] **Step 2: Add the external entry (outcome A), or fall back**

Decision ladder — record which outcome applied in the commit message:

- **Outcome A (preferred):** his plugin is exposable via a supported source type. Add to our `plugins` array, mirroring his real source (adjust `repo`/`path` to what Step 1 found — the shapes below are the two legal forms):

```json
{
  "name": "terraform-skill",
  "source": {
    "source": "github",
    "repo": "antonbabenko/agent-plugins",
    "path": "plugins/terraform-skill"
  },
  "description": "Deep Terraform/OpenTofu skill by Anton Babenko (external, Apache-2.0) — failure diagnosis, state surgery, migrations. omniagents-iac:terraform routes deep dives here.",
  "category": "infrastructure",
  "keywords": ["terraform", "opentofu", "external"]
}
```

or, if his skill needs subdirectory extraction from a plain repo:

```json
{
  "name": "terraform-skill",
  "source": {
    "source": "git-subdir",
    "url": "https://github.com/antonbabenko/agent-plugins.git",
    "path": "plugins/terraform-skill"
  },
  "description": "Deep Terraform/OpenTofu skill by Anton Babenko (external, Apache-2.0) — failure diagnosis, state surgery, migrations. omniagents-iac:terraform routes deep dives here.",
  "category": "infrastructure",
  "keywords": ["terraform", "opentofu", "external"]
}
```

- **Outcome B:** `make validate` rejects every external-source shape → no external entry. Instead: (1) append to the `omniagents-iac` marketplace entry description: `" Pairs with terraform-skill: /plugin marketplace add antonbabenko/agent-plugins && /plugin install terraform-skill@antonbabenko."`; (2) create `plugins/iac/README.md` containing exactly:

```markdown
# omniagents-iac

Terraform house-layer + Docker/compose production rulebook skills.

## Recommended companion

The terraform skill routes deep dives (failure diagnosis, state surgery,
migrations) to Anton Babenko's terraform-skill (Apache-2.0). Install it:

    /plugin marketplace add antonbabenko/agent-plugins
    /plugin install terraform-skill@antonbabenko

Without it, the skill falls back to canonical HashiCorp/Google/AWS URLs.
```
- **Outcome C:** validation accepts the entry but the `dependencies` field (Step 3) fails validation → keep the external entry, drop the hard dependency (Step 3 reverts), rely on routing prose.

- [ ] **Step 3: Declare the dependency**

Add to `plugins/iac/.claude-plugin/plugin.json` (top level, after `"license"`):

```json
"dependencies": [
  { "name": "terraform-skill" }
]
```

If `make validate` rejects the field or requires `allowCrossMarketplaceDependenciesOn` in marketplace metadata, first try adding to marketplace.json `metadata`: `"allowCrossMarketplaceDependenciesOn": ["antonbabenko"]` (use his marketplace name from Step 1). If still rejected → Outcome C: remove `dependencies`, keep the external entry.

- [ ] **Step 4: Validate**

Run: `make validate`
Expected: exit 0 under the chosen outcome.

- [ ] **Step 5: Commit (recording the outcome)**

```bash
git add .claude-plugin/marketplace.json plugins/iac/.claude-plugin/plugin.json
git commit -m "feat(iac): wire antonbabenko/terraform-skill as external dependency

External-entry resolution outcome: <A|B|C> — <one line describing what
validate accepted/rejected>. Live /plugin install round-trip remains a
post-release user step (local marketplace name collides with the
installed GitHub-sourced one)."
```

---

### Task 3: terraform SKILL.md

**Files:**
- Create (replace any stub): `plugins/iac/skills/terraform/SKILL.md`

**Interfaces:**
- Consumes: Task 2's recorded outcome (A/B/C) — read `git log -2 --format=%B` to learn it; reference-file names below.
- Produces: the four reference filenames + section anchors Tasks 4–7 must match EXACTLY: `references/module-design.md`, `references/state-and-environments.md`, `references/security-and-gates.md`, `references/modern-features.md`.

- [ ] **Step 1: Author the file** — structure and content, in order:

Frontmatter (exact):

```yaml
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
```

Body sections (H1 `# Terraform Module Patterns & Hygiene`):

1. **Scope line** — targets Terraform ≥ 1.11 OSS CLI (state locking + write-only args era); OpenTofu divergences flagged inline where they matter; Stacks are HCP-only and out of scope.
2. **`## Default posture`** — the ten non-negotiables, verbatim from spec §6 (pin everything; typed+described variables/outputs with field order type → description → default → sensitive → validation; no provider blocks in reusable modules; dependency inversion; flat module tree, no thin wrappers, no god modules; no `0.0.0.0/0` ingress, reference SGs not CIDRs; `default_tags` at root; secrets never enter state — ephemeral/`_wo`/runtime refs, `sensitive = true` is marking not protection; S3 remote state versioned+encrypted+public-blocked+`use_lockfile = true`, no new DynamoDB lock tables; gate pipeline fmt→validate→tflint→trivy→saved plan→reviewed apply with OIDC-only credentials).
3. **`## Tiering: name your tier before naming controls`** — the canonical table from Global Constraints, VERBATIM, plus one worked example: the 40-line VPC-scoped single-node demo redis (T1-correct) vs the same workload at T2 (auth+TLS, snapshots, replica, noeviction params, memory alarm) vs T3 (CMK, log delivery, SNS, mandated wrapper modules).
4. **`## Reference index`** — table of the four reference files with one-line "read when…" each (mirror the `design-patterns:system` SKILL.md index format).
5. **`## Routing: deep dives go to terraform-skill`** — routing table: THIS skill = authoring conventions, module shape, gates, tiering. The `terraform-skill` skill (Anton Babenko, installed separately or via this marketplace per Task 2 outcome) = failure diagnosis, corrupt/locked/drifted state surgery, large-scale migrations, count↔for_each refactors at scale. If it is not installed, cite instead: HashiCorp style guide, standard module structure, module composition, Google best practices, AWS Prescriptive Guidance, Gruntwork style guide (full URLs from the terraform digest §1). Rule: never restate his content — link or route.
6. **`## What this skill does NOT cover`** — Pulumi/CDK/K8s; failure-mode depth (routed); provider resource catalogs; cloud-vendor pricing.

- [ ] **Step 2: Verify**

```bash
wc -l plugins/iac/skills/terraform/SKILL.md          # expect 300–400
grep -c "https://" plugins/iac/skills/terraform/SKILL.md   # expect ≥ 8
grep -n "T1 demo/portfolio" plugins/iac/skills/terraform/SKILL.md  # tiering table present
grep -rn "TODO\|TBD" plugins/iac/skills/terraform/SKILL.md # expect no matches
make validate                                        # exit 0
```

- [ ] **Step 3: Commit**

```bash
git add plugins/iac/skills/terraform/SKILL.md
git commit -m "feat(iac): terraform skill — posture, tiering, routing"
```

---

### Task 4: terraform reference — module-design.md

**Files:**
- Create: `plugins/iac/skills/terraform/references/module-design.md`

**Interfaces:**
- Consumes: section name + filename pinned by Task 3's index.
- Produces: anchors `#standard-structure`, `#naming`, `#variables-and-outputs`, `#composition`, `#feature-flags`, `#module-tests-and-examples`, `#anti-patterns` (kebab-case of H2s below).

- [ ] **Step 1: Author** — H1 `# Module Design`, then H2 sections, each rule imperative with inline source URL. Source material: terraform digest §2 (ALL ten bullets become rules — none dropped) + digest §1 URLs. Required content beyond the digest bullets:
  - `## Standard structure`: the file septet (`main.tf`/`variables.tf`/`outputs.tf`/`versions.tf`, optional `providers.tf`/`locals.tf`/`backend.tf`), logical-area splitting (`network.tf`, `compute.tf`, never `resources1.tf`), published-module extras (`README.md`, `examples/`, `tests/`, nested `modules/`), repo naming `terraform-<provider>-<name>`.
  - `## Naming`: snake_case nouns, no type echo — include a 4-line good/bad HCL pair (`aws_instance.web` vs `aws_instance.web_instance`).
  - `## Variables and outputs`: field order, typed+described always, `optional(type, default)` object attrs over null-juggling, alphabetized files, outputs describe + export useful attributes of every created resource in published modules; output sprawl (outputs nobody consumes in roots) as the counter-rule.
  - `## Composition`: flat tree (one child level), dependency inversion with a ~15-line HCL sketch showing a module receiving `vpc_id`/`subnet_ids` as variables vs the anti-form burying `data "aws_vpc"` lookups inside; "create-or-query belongs to the caller".
  - `## Feature flags`: `create_*`/`enable_*` booleans driving `count`/`for_each`, one ~10-line HCL sketch (terraform-aws-modules idiom).
  - `## Module tests and examples`: every published module ships a deployable `examples/` + `tests/*.tftest.hcl` smoke (`command = plan` with mocked providers); terraform-docs markers in README.
  - `## Anti-patterns`: god module (unrelated infra in one module), thin single-resource wrapper (inline instead), hardcoded literals (promote to variables/locals), output sprawl, deep nesting — each with a one-line "why it bites" and source.

- [ ] **Step 2: Verify**

```bash
wc -l plugins/iac/skills/terraform/references/module-design.md   # 500–700
grep -c "https://" plugins/iac/skills/terraform/references/module-design.md  # ≥ 15
grep -c '```hcl' plugins/iac/skills/terraform/references/module-design.md    # ≥ 3
tail -1 plugins/iac/skills/terraform/references/module-design.md  # the Verified-as-of line
```

- [ ] **Step 3: Commit**

```bash
git add plugins/iac/skills/terraform/references/module-design.md
git commit -m "feat(iac): terraform module-design reference"
```

---

### Task 5: terraform reference — state-and-environments.md

**Files:**
- Create: `plugins/iac/skills/terraform/references/state-and-environments.md`

**Interfaces:**
- Consumes: filename pinned by Task 3.
- Produces: anchors `#backend-baseline`, `#bootstrap`, `#blast-radius`, `#environments`, `#cross-state-data-flow`.

- [ ] **Step 1: Author** — H1 `# State & Environments`. Source: terraform digest §4 (all six bullets) + §3's locking bullet. Required content:
  - `## Backend baseline`: remote always; S3 versioned + SSE + public-access-blocked + access-logged; `use_lockfile = true` (1.10 experimental → 1.11 GA); `dynamodb_table` deprecated — migration note (run both, then drop the table); state is a secret regardless of content.
  - `## Bootstrap`: the chicken-and-egg pattern — tiny separate root on local state creates the bucket once, everything else `terraform init -migrate-state` onto it; include a ~12-line HCL sketch of the bootstrap root.
  - `## Blast radius`: one state per env × service/layer; small states plan faster and fail smaller; never one mega-state.
  - `## Environments`: `CONTESTED —` workspaces-for-envs in ONE line (HashiCorp style guide endorses workspace-per-env; Google/Gruntwork/community: directory-per-env because CLI workspaces share backend+credentials and invite wrong-env applies). House verdict: directory-per-environment; CLI workspaces only for ephemeral/PR stacks; Terragrunt when multi-account DRY orchestration earns it (overkill threshold: don't introduce below ~3 envs × 3 layers).
  - `## Cross-state data flow`: outputs consumed via `terraform_remote_state` or data-only modules; never reach into another stack's resources by name.

- [ ] **Step 2: Verify**

```bash
wc -l plugins/iac/skills/terraform/references/state-and-environments.md  # 300–400
grep -n "CONTESTED" plugins/iac/skills/terraform/references/state-and-environments.md  # ≥ 1
grep -c "https://" plugins/iac/skills/terraform/references/state-and-environments.md   # ≥ 8
tail -1 plugins/iac/skills/terraform/references/state-and-environments.md
```

- [ ] **Step 3: Commit**

```bash
git add plugins/iac/skills/terraform/references/state-and-environments.md
git commit -m "feat(iac): terraform state-and-environments reference"
```

---

### Task 6: terraform reference — security-and-gates.md

**Files:**
- Create: `plugins/iac/skills/terraform/references/security-and-gates.md`

**Interfaces:**
- Consumes: filename pinned by Task 3; Trivy-as-house-scanner Global Constraint.
- Produces: anchors `#pinning-matrix`, `#secrets`, `#network-least-privilege`, `#tags-and-encryption`, `#gate-pipeline`, `#credentials`, `#drift-and-cost`.

- [ ] **Step 1: Author** — H1 `# Security & Gates`. Source: terraform digest §5 + §6 + §7 (every bullet). Required content:
  - `## Pinning matrix`: a table — root `required_version` (floor ≥ 1.11) / root providers `~>` / reusable-module providers `>=` only / registry modules exact `version` / git modules `?ref=` tag-or-SHA never branch / `.terraform.lock.hcl` committed + `terraform providers lock` for all CI platforms; Renovate (terraform manager) over Dependabot, with why.
  - `## Secrets`: ephemeral resources (1.10) + write-only `_wo` args with the `_wo_version` bump pattern (1.11) as the default; a ~10-line HCL sketch of a write-only password arg; runtime SSM/Secrets Manager references as the fallback; `sensitive = true` marks, does not protect; never plaintext secrets in committed `.tfvars`.
  - `## Network least privilege`: no `0.0.0.0/0` ingress; SG-references over CIDRs; egress-all is a smell to justify, not a default.
  - `## Tags and encryption`: `default_tags` at root provider (owner/env/cost-center/managed-by) with a ~8-line HCL sketch; resource tags only for extras; encryption-by-default posture (state bucket SSE-KMS; RDS/EBS/S3 encryption args on).
  - `## Gate pipeline`: fmt-check → validate → TFLint (+provider ruleset) → **Trivy** (house default; absorbed tfsec, same check IDs; Checkov the documented alternative; tfsec dead, Terrascan archived Nov 2025 — never recommend) → plan saved as artifact → human review → apply THE REVIEWED PLAN FILE; pre-commit-terraform hook list (`terraform_fmt`, `terraform_validate`, `terraform_tflint`, `terraform_docs`, trivy hook).
  - `## Credentials`: GitHub Actions OIDC → short-lived roles; zero long-lived cloud keys; read-only plan role split from apply role.
  - `## Drift and cost`: scheduled plans for drift; Infracost on PRs; one line each on Atlantis / HCP Terraform / Spacelift / env0 and when a team graduates to them.

- [ ] **Step 2: Verify**

```bash
wc -l plugins/iac/skills/terraform/references/security-and-gates.md  # 400–500
grep -c "https://" plugins/iac/skills/terraform/references/security-and-gates.md  # ≥ 12
grep -n "tfsec\|Terrascan" plugins/iac/skills/terraform/references/security-and-gates.md  # only in the never-recommend line
tail -1 plugins/iac/skills/terraform/references/security-and-gates.md
```

- [ ] **Step 3: Commit**

```bash
git add plugins/iac/skills/terraform/references/security-and-gates.md
git commit -m "feat(iac): terraform security-and-gates reference"
```

---

### Task 7: terraform reference — modern-features.md

**Files:**
- Create: `plugins/iac/skills/terraform/references/modern-features.md`

**Interfaces:**
- Consumes: filename pinned by Task 3.
- Produces: anchors `#adoption-table`, `#testing`, `#config-driven-refactoring`, `#opentofu`, `#out-of-scope-stacks`.

- [ ] **Step 1: Author** — H1 `# Modern Features (1.3 → 1.15)`. Source: terraform digest §3 + §8 (every bullet). Required content:
  - `## Adoption table`: one row per feature — feature / since / verdict / one-line when-to-use: `optional()` attrs (1.3, use), `check` blocks (1.5, use for non-blocking), pre/postconditions + variable validation (blocking contracts, use), `terraform test` (1.6; mocks 1.7; parallel 1.12 — use, see below), `moved`/`import`+`-generate-config-out`/`removed` (1.1/1.5/1.7 — always over hand `state mv/rm`), provider-defined functions (1.8, use where they delete locals gymnastics), `templatestring` (1.9), ephemeral + write-only (1.10/1.11 — default for secrets, cross-ref security ref), S3 `use_lockfile` (1.11 GA, cross-ref state ref), OCI backend + short-circuit logic + import identity (1.12), list/search resources + `terraform query` + `actions`/`-invoke` (1.14 — bulk import and day-2 ops), variables in module source/version + `deprecated` on variables/outputs + typed outputs + `convert()` (1.15).
  - `## Testing`: 2026 consensus — `terraform test` is the first line (per-module `tests/*.tftest.hcl`, `command = plan` + mocked providers in CI, `command = apply` for integration on `examples/`); Terratest is E2E-only (real deploys, HTTP asserts, pre-release); include a ~15-line `.tftest.hcl` sketch with one `run` block + a mocked provider.
  - `## Config-driven refactoring`: a ~12-line sketch showing `moved` + `removed` blocks for a rename+retirement, and the rule "refactors ship as config, reviewed in the PR, not as out-of-band state surgery" (deep surgery routes to terraform-skill per SKILL.md).
  - `## OpenTofu`: divergence list (state/plan encryption 1.7+, provider `for_each` 1.9, OCI registries + own `use_lockfile` 1.10, earlier `deprecated`, `.tofu` extension); rule: declare which tool a repo targets.
  - `## Out of scope: Stacks`: GA but HCP-only; this rulebook targets OSS CLI.

- [ ] **Step 2: Verify**

```bash
wc -l plugins/iac/skills/terraform/references/modern-features.md  # 300–400
grep -c "https://" plugins/iac/skills/terraform/references/modern-features.md  # ≥ 10
grep -n "1.15\|1.14" plugins/iac/skills/terraform/references/modern-features.md  # present
tail -1 plugins/iac/skills/terraform/references/modern-features.md
```

- [ ] **Step 3: Verify terraform skill total budget**

Run: `wc -l plugins/iac/skills/terraform/SKILL.md plugins/iac/skills/terraform/references/*.md | tail -1`
Expected: total ≤ 2,500. If over, trim the largest reference — cut prose, never rules or citations.

- [ ] **Step 4: Commit**

```bash
git add plugins/iac/skills/terraform/references/modern-features.md
git commit -m "feat(iac): terraform modern-features reference"
```

---

### Task 8: docker SKILL.md

**Files:**
- Create (replace any stub): `plugins/iac/skills/docker/SKILL.md`

**Interfaces:**
- Produces: reference filenames + anchors Tasks 9–12 must match EXACTLY: `references/dockerfile.md`, `references/compose.md`, `references/hardening-and-supply-chain.md`, `references/ci-and-release.md`.

- [ ] **Step 1: Author** — frontmatter (exact):

```yaml
---
name: docker
description: >-
  Use when writing or reviewing Dockerfiles or docker-compose files with
  production discipline: multi-stage builds, BuildKit cache mounts,
  base-image choice and digest pinning, non-root runtime, exec-form and
  PID-1 signal handling, healthchecks, the canonical uv two-phase Python
  install, compose file layering vs profiles, service_healthy dependency
  gating, compose secrets, resource limits, SBOM/provenance, image
  scanning and signing, tag strategy, and CI build-push shape.
when_to_use: >-
  Trigger for Dockerfile*, compose*.yaml, docker-compose*.yml,
  .dockerignore, .hadolint.yaml, image build failures, layer-cache
  misses, container security hardening, uv-in-Docker patterns, Vite
  static-build stages, compose dev/prod splits, healthcheck or
  depends_on design, registry tagging, multi-arch builds, hadolint or
  trivy gates, or "is this image production-grade" tiering questions.
disable-model-invocation: false
user-invocable: true
allowed-tools: []
model: inherit
paths:
  - "**/Dockerfile*"
  - "**/compose*.yml"
  - "**/compose*.yaml"
  - "**/docker-compose*.yml"
  - "**/docker-compose*.yaml"
  - "**/.dockerignore"
  - "**/.hadolint.yaml"
shell: bash
---
```

Body (H1 `# Docker & Compose Production Rulebook`):

1. **`## Default posture`** — the twelve non-negotiables verbatim from spec §7 (`# syntax=docker/dockerfile:1` first line; multi-stage always, no toolchains in final stage; non-root USER with explicit UID/GID; exec-form ENTRYPOINT/CMD + init reaper; COPY not ADD; bases pinned `tag@digest` WITH automated bumps — never digest-pin without automation; `.dockerignore` always; healthcheck on every long-running service; no compose `version:` key; secrets never as env vars; memory+CPU limits everywhere; `--locked`/`--frozen` installs only — the container never resolves).
2. **`## Tiering`** — the canonical table from Global Constraints VERBATIM, plus the container mapping line: SBOM/provenance/signing = T2+; read-only rootfs + cap_drop = T2+; distroless/Wolfi = T3 or named pain; T1 = posture list only.
3. **`## Stack quick-paths`** — two ~20-line annotated sketches: (a) Python+uv canonical two-phase Dockerfile (uv from pinned `ghcr.io/astral-sh/uv` COPY, `python:3.X-slim`, cache-mount + bind-mount lockfiles, `uv sync --locked --no-install-project` deps layer, `COPY . .`, `uv sync --locked --no-editable`, venv-copy runtime stage, `UV_COMPILE_BYTECODE=1`, `UV_LINK_MODE=copy`, non-root, exec-form CMD); (b) Node/Vite build stage → static-server stage (nginx-or-caddy, pinned digest, non-root, healthcheck).
4. **`## Reference index`** — table of the four references with "read when…" lines.
5. **`## What this skill does NOT cover`** — Kubernetes manifests/Helm; orchestrator choice; registry operations beyond lifecycle policy; VM provisioning (→ terraform skill).

- [ ] **Step 2: Verify**

```bash
wc -l plugins/iac/skills/docker/SKILL.md   # 250–350
grep -n "T1 demo/portfolio" plugins/iac/skills/docker/SKILL.md  # tiering table present
grep -c '```dockerfile' plugins/iac/skills/docker/SKILL.md      # ≥ 2
make validate
```

- [ ] **Step 3: Commit**

```bash
git add plugins/iac/skills/docker/SKILL.md
git commit -m "feat(iac): docker skill — posture, tiering, quick-paths"
```

---

### Task 9: docker reference — dockerfile.md

**Files:**
- Create: `plugins/iac/skills/docker/references/dockerfile.md`

**Interfaces:**
- Consumes: filenames/anchors pinned by Task 8.
- Produces: anchors `#layering`, `#cache-and-bind-mounts`, `#copy-discipline`, `#base-images`, `#pinning-and-updates`, `#python-and-uv`, `#node-and-vite`, `#anti-patterns`.

- [ ] **Step 1: Author** — H1 `# Dockerfile`. Source: docker digest §1 + §3 (EVERY bullet becomes a rule with its URL). This is catalogue depth: each H2 uses the house pattern-entry shape (Intent · Rules · Sketch · When NOT to use · Anti-pattern variant · References) where a pattern is catalogued. Required content:
  - `## Layering`: syntax directive, least→most volatile ordering with a worked 10-line example showing dep-install surviving a source edit, heredocs over `&&` chains with `set -o pipefail`, apt one-RUN discipline with `--no-install-recommends` + list cleanup + sorted packages.
  - `## Cache and bind mounts`: `--mount=type=cache` per package manager (apt/uv/npm cache paths), `sharing=locked` rule, bind-mount lockfiles instead of COPY, one full RUN sketch.
  - `## Copy discipline`: COPY over ADD (ADD's two legitimate uses), `--chown/--chmod` at copy time (never a chown layer), `--link` for final-stage `COPY --from`, `--parents` (syntax ≥1.20).
  - `## Base images`: decision table slim (default) / alpine (BANNED for Python — musl wheel rationale, cite pythonspeed) / distroless / Chainguard-Wolfi; `CONTESTED —` distroless-vs-slim one-liner (near-zero CVE + no shell vs debuggability; compromise: slim dev/staging, hardened prod).
  - `## Pinning and updates`: `tag@sha256:digest` pairing, Renovate `docker:pinDigests` / Dependabot docker, the "never digest-pin without automation" rule and why (frozen security patches).
  - `## Python and uv`: the FULL canonical pattern — expand the SKILL.md quick-path to a ~35-line annotated Dockerfile: pinned uv COPY --from, env block (`UV_COMPILE_BYTECODE=1`, `UV_LINK_MODE=copy`, `UV_NO_PROGRESS=1`), two-phase sync with cache+bind mounts, `--locked` mandatory (`--frozen` equivalent note), workspace variant (`--no-install-workspace`), venv-copy runtime with `PATH=/app/.venv/bin:$PATH`, no uv in runtime, `.venv` in `.dockerignore`, dev-loop anonymous-volume note.
  - `## Node and Vite`: build stage (npm ci, pinned node slim) → static stage (nginx/caddy pinned digest, non-root, custom conf path note, healthcheck), ~20-line sketch.
  - `## Anti-patterns`: gallery, each with the failing form + one-line why + fix: mutating dependencies inside a frozen build (e.g. `uv add <pkg> --no-sync` before `uv sync --frozen` — the lockfile no longer matches the manifest); `FROM x:latest`; root runtime; chown-after-copy doubling layers; ADD-for-COPY; secrets via build ARG; missing `.dockerignore` (context bloat + cache busts); single-stage prod images.

- [ ] **Step 2: Verify**

```bash
wc -l plugins/iac/skills/docker/references/dockerfile.md   # 1,000–1,500
grep -c "https://" plugins/iac/skills/docker/references/dockerfile.md  # ≥ 20
grep -c '```dockerfile' plugins/iac/skills/docker/references/dockerfile.md  # ≥ 5
grep -n "CONTESTED" plugins/iac/skills/docker/references/dockerfile.md  # ≥ 1
grep -in "alpine" plugins/iac/skills/docker/references/dockerfile.md | head -3  # ban present
tail -1 plugins/iac/skills/docker/references/dockerfile.md
```

- [ ] **Step 3: Commit**

```bash
git add plugins/iac/skills/docker/references/dockerfile.md
git commit -m "feat(iac): docker dockerfile reference"
```

---

### Task 10: docker reference — compose.md

**Files:**
- Create: `plugins/iac/skills/docker/references/compose.md`

**Interfaces:**
- Consumes: filenames/anchors pinned by Task 8.
- Produces: anchors `#spec-baseline`, `#file-layering`, `#profiles`, `#startup-ordering`, `#secrets`, `#runtime-policies`, `#volumes`, `#dev-loop`, `#env-files`, `#single-host-production`.

- [ ] **Step 1: Author** — H1 `# Compose`. Source: docker digest §5 (EVERY bullet). Required content:
  - `## Spec baseline`: no top-level `version:` (obsolete, warn-only), `name:` for the project.
  - `## File layering`: `compose.yaml` base + auto-loaded `compose.override.yaml` (dev) + explicit `-f compose.yaml -f compose.prod.yaml`; a 3-file worked example (~30 lines total) showing dev binds/ports stripped in prod; `extends`/`include` when merges grow complex.
  - `## Profiles`: optional services within ONE environment (debug tools, admin UIs), never environment splits; the decision rule vs file layering in one line; activation via `--profile`/`COMPOSE_PROFILES`.
  - `## Startup ordering`: long-form `depends_on` with `condition: service_healthy` + `restart: true`; requires healthcheck on the dependency; every long-running service defines a healthcheck; a ~15-line sketch (app + redis + postgres).
  - `## Secrets`: compose `secrets:` (file/environment source, mounted `/run/secrets/<name>`) over env vars — the inspect/logs/child-process leak rationale; ~10-line sketch.
  - `## Runtime policies`: `restart: unless-stopped` prod default (`no` for one-shots); `deploy.resources.limits/reservations` honored by non-Swarm compose up, legacy `mem_limit`/`cpus` superseded; logging driver rotation note.
  - `## Volumes`: named volumes for persistent state; binds only for dev source-sync + host-owned config.
  - `## Dev loop`: `develop.watch` — `action: sync` for source (`ignore: [.venv/]`), `action: rebuild` on manifest/lockfile.
  - `## Env files`: `.env` git-ignored for interpolation; `env_file:` for container env; `environment:` wins; commit only `.env.sample`.
  - `## Single-host production`: `CONTESTED —` one-liner (legitimate per Docker's own docs vs "compose isn't prod" camp); then the closing checklist as a table: digest-pinned images, healthchecks + restart policies, resource limits, secrets, log rotation, protected docker socket, update path; multi-host/self-healing → orchestrator.

- [ ] **Step 2: Verify**

```bash
wc -l plugins/iac/skills/docker/references/compose.md  # 1,000–1,400
grep -c "https://" plugins/iac/skills/docker/references/compose.md  # ≥ 15
grep -c '```yaml' plugins/iac/skills/docker/references/compose.md   # ≥ 5
grep -n "CONTESTED" plugins/iac/skills/docker/references/compose.md # ≥ 1
grep -n "version:" plugins/iac/skills/docker/references/compose.md | head -3  # only in the ban rule
tail -1 plugins/iac/skills/docker/references/compose.md
```

- [ ] **Step 3: Commit**

```bash
git add plugins/iac/skills/docker/references/compose.md
git commit -m "feat(iac): docker compose reference"
```

---

### Task 11: docker reference — hardening-and-supply-chain.md

**Files:**
- Create: `plugins/iac/skills/docker/references/hardening-and-supply-chain.md`

**Interfaces:**
- Consumes: filenames/anchors pinned by Task 8; Trivy house rule.
- Produces: anchors `#runtime-hardening`, `#pid-1-and-signals`, `#process-model`, `#healthchecks`, `#linting`, `#scanning`, `#sbom-and-provenance`, `#signing`, `#audit`.

- [ ] **Step 1: Author** — H1 `# Hardening & Supply Chain`. Source: docker digest §2 + §4 (EVERY bullet). Required content:
  - `## Runtime hardening`: non-root USER with explicit UID/GID; read-only rootfs + tmpfs scratch; `cap_drop: [ALL]` + selective add-back; `security_opt: ["no-new-privileges:true"]`; never `privileged`; cite CIS Docker Benchmark §5; a ~12-line compose hardening block sketch.
  - `## PID 1 and signals`: exec-form only (shell form blocks SIGTERM), init reaper (`init: true` / `--init` / explicit tini), wrapper scripts end `exec "$@"`; a 6-line entrypoint sketch.
  - `## Process model`: uvicorn one-process-per-container under an orchestrator; `--workers N` only single-host/compose; `--proxy-headers` behind TLS proxy; tiangolo/uvicorn-gunicorn images deprecated — do not use.
  - `## Healthchecks`: exec-form, no-curl-on-slim rule (app-native check, e.g. `python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"`), explicit interval/timeout/retries/start_period; Kubernetes ignores Dockerfile HEALTHCHECK — define at the orchestrator layer there.
  - `## Linting`: hadolint in CI (bundles ShellCheck on RUN); key gates DL3006 (untagged FROM), DL3008 (unpinned apt), DL3002 (last USER root); `.hadolint.yaml` config + per-line ignore comments; a ~8-line sample config.
  - `## Scanning`: **Trivy primary** (CVE+IaC+secrets+licenses, offline-capable, house scanner shared with the terraform skill); Grype second opinion on critical images; Docker Scout = Desktop-native complement only; fail CI on HIGH/CRITICAL with `.trivyignore` for accepted findings.
  - `## SBOM and provenance`: `docker buildx build --sbom=true --provenance=mode=max`; provenance defaults min, SBOM opt-in; attestations as in-toto/SLSA in the image index.
  - `## Signing`: cosign keyless (OIDC via Fulcio + Rekor) = 2026 default for GitHub-Actions shops; Notation for enterprise PKI; Docker Content Trust retired.
  - `## Audit`: docker-bench-security for host/daemon CIS checks; cadence note (per-release or monthly).

- [ ] **Step 2: Verify**

```bash
wc -l plugins/iac/skills/docker/references/hardening-and-supply-chain.md  # 1,000–1,400
grep -c "https://" plugins/iac/skills/docker/references/hardening-and-supply-chain.md  # ≥ 15
grep -n "cosign\|CIS" plugins/iac/skills/docker/references/hardening-and-supply-chain.md | head -4
tail -1 plugins/iac/skills/docker/references/hardening-and-supply-chain.md
```

- [ ] **Step 3: Commit**

```bash
git add plugins/iac/skills/docker/references/hardening-and-supply-chain.md
git commit -m "feat(iac): docker hardening-and-supply-chain reference"
```

---

### Task 12: docker reference — ci-and-release.md

**Files:**
- Create: `plugins/iac/skills/docker/references/ci-and-release.md`

**Interfaces:**
- Consumes: filenames/anchors pinned by Task 8; gate-order from Task 11 content.
- Produces: anchors `#build-cache`, `#multi-arch`, `#labels`, `#tag-strategy`, `#registry-hygiene`, `#pipeline`.

- [ ] **Step 1: Author** — H1 `# CI & Release`. Source: docker digest §6 + §7 (EVERY bullet). Required content:
  - `## Build cache`: docker/build-push-action with `cache-from: type=gha` / `cache-to: type=gha,mode=max` (mode=max caches all stages); Buildx ≥ 0.21 floor (GitHub Cache API v2, mandatory since 2025-04-15); `type=registry,mode=max` fallback when GHA limits bite; ~15-line workflow YAML sketch.
  - `## Multi-arch`: native-runner matrix (`ubuntu-24.04` + `ubuntu-24.04-arm`) pushing per-arch digests merged via `buildx imagetools create`; QEMU only for trivial images; arm64 is mainstream (Graviton/Apple).
  - `## Labels`: OCI annotations `org.opencontainers.image.{source,revision,version,created,title,description,licenses}` via docker/metadata-action.
  - `## Tag strategy`: immutable git SHA on every push; semver triplet on release (`1.4.2` immutable, `1.4`/`1` floating); `:latest` BANNED from production deploy manifests (deploy by digest or exact tag); registry immutable-tag enforcement where available.
  - `## Registry hygiene`: lifecycle policies expiring untagged + aged SHA tags, release tags kept indefinitely; ECR lifecycle-rule ~10-line JSON sketch.
  - `## Pipeline`: the full gate order as a numbered list — hadolint → build (`--provenance --sbom`) → Trivy fail-on-HIGH/CRITICAL → cosign sign → push — with tags/labels from metadata-action; cross-reference the hardening reference for gate configs.

- [ ] **Step 2: Verify**

```bash
wc -l plugins/iac/skills/docker/references/ci-and-release.md  # 800–1,200
grep -c "https://" plugins/iac/skills/docker/references/ci-and-release.md  # ≥ 12
grep -c '```yaml' plugins/iac/skills/docker/references/ci-and-release.md   # ≥ 2
tail -1 plugins/iac/skills/docker/references/ci-and-release.md
```

- [ ] **Step 3: Commit**

```bash
git add plugins/iac/skills/docker/references/ci-and-release.md
git commit -m "feat(iac): docker ci-and-release reference"
```

---

### Task 13: Consistency pass, yinglong content smoke, final validation

**Files:**
- Modify (fix-ups only, as findings dictate): any file under `plugins/iac/`

**Interfaces:**
- Consumes: everything from Tasks 1–12.
- Produces: the shippable plugin; a smoke-test verdict recorded in the final commit message.

- [ ] **Step 1: Cross-skill consistency checks**

```bash
# Tiering table identical in both SKILL.mds:
diff <(sed -n '/| Control |/,/maximal knobs/p' plugins/iac/skills/terraform/SKILL.md) \
     <(sed -n '/| Control |/,/maximal knobs/p' plugins/iac/skills/docker/SKILL.md)
# Expected: no output.
# Reference index names match real files:
ls plugins/iac/skills/terraform/references/ plugins/iac/skills/docker/references/
grep -o 'references/[a-z-]*\.md' plugins/iac/skills/terraform/SKILL.md | sort -u
grep -o 'references/[a-z-]*\.md' plugins/iac/skills/docker/SKILL.md | sort -u
# Expected: the two grep sets equal the two ls sets.
# No placeholders anywhere:
grep -rn "TODO\|TBD\|WIP" plugins/iac/ ; echo "exit=$?"   # expect exit=1 (no matches)
# Every reference ends with the Verified line:
for f in plugins/iac/skills/*/references/*.md; do tail -1 "$f" | grep -q "Verified as of 2026-07" || echo "MISSING: $f"; done
```

Fix any finding by editing the offending file.

- [ ] **Step 2: Content smoke against yinglong (spec §9)**

Dispatch a fresh subagent (or perform inline) with EXACTLY this brief: "Read `plugins/iac/skills/terraform/SKILL.md` + its four references, then review `/Users/gaohn/gaohn/yinglong/infra/app/modules/redis/` (main.tf, variables.tf, outputs.tf) and `/Users/gaohn/gaohn/yinglong/infra/app/providers.tf` under those rules, stating tier verdicts. Then read `plugins/iac/skills/docker/SKILL.md` + its four references and review `/Users/gaohn/gaohn/yinglong/backend/docker/Dockerfile.api` and `/Users/gaohn/gaohn/yinglong/backend/docker/docker-compose.yml`. Return the findings list only."

PASS criteria (all three, exactly as the spec's smoke demands):
1. Terraform findings flag the redis default (volatile-lru) parameter group + missing snapshots/replica as T2 gaps while accepting the VPC-scoped SG as T1-correct.
2. Terraform findings audit `providers.tf` pinning (required_version / provider constraints) and name each gap or confirm compliance.
3. Docker findings flag the mutate-deps-inside-frozen-build pattern in `Dockerfile.api` (the `uv add … --no-sync` before `uv sync --frozen`) and the absence of compose resource limits.

If any criterion fails, the corresponding rule is missing or buried — strengthen that rule's wording/placement in the relevant reference and re-run the smoke once.

- [ ] **Step 3: Final validation + budget check**

```bash
make validate    # exit 0
wc -l plugins/iac/skills/terraform/SKILL.md plugins/iac/skills/terraform/references/*.md | tail -1   # ≤ 2,500
wc -l plugins/iac/skills/docker/SKILL.md plugins/iac/skills/docker/references/*.md | tail -1
git -C . status -s   # ONLY plugins/iac/ + .claude-plugin/marketplace.json changes from this plan; WIP paths untouched
```

- [ ] **Step 4: Final commit**

```bash
git add plugins/iac/
git commit -m "feat(iac): consistency pass + yinglong smoke verified

Smoke: redis T2 gaps flagged / providers.tf pinning audited /
Dockerfile.api frozen-build mutation + missing compose limits flagged.
make validate green. Release (make release VERSION=x.y.z + push) is
intentionally NOT run — user-gated."
```

STOP here. Do NOT run `make release`, do NOT push, do NOT open a PR unless the user asks.
