# omniagents-iac plugin — design

- **Date:** 2026-07-20
- **Status:** approved design, pending implementation plan
- **Repo:** gao-hongnan/omniagents, branch `feat/iac-plugin`
- **First consumer:** yinglong (`infra/` Terraform, `backend/docker/` Dockerfiles + compose) — application is a separate phase-2 spec in that repo.

## 1. Problem

The omniagents marketplace enforces a strict house quality bar for Python,
TypeScript, writing, and design patterns — but nothing for infrastructure.
yinglong's IaC (1,340 lines of raw-resource Terraform, three Dockerfiles,
two compose files) has no equivalent rulebook: no conventions to review
against, no tiering language to justify which enterprise controls a given
environment warrants, and no gates (fmt/validate/lint/scan) in CI. The
immediate trigger was comparing a Merck production ElastiCache module
(TLS+AUTH+CMK+logs+failover) against yinglong's 40-line redis module and
having no framework to say which deltas are gaps versus context-appropriate
simplification.

## 2. Goal / non-goals

**Goal:** a new `omniagents-iac` plugin with two skills — `terraform`
(house-layer rulebook that links to deep prior art instead of repeating it)
and `docker` (full-depth catalogue: Dockerfile + compose + hardening +
supply chain + CI). Same voice and rigor as `python:typings` and
`design-patterns:system`: imperative rules, cited sources, overkill
thresholds, CONTESTED flags.

**Non-goals (v1):** applying the skills to yinglong (phase 2, separate
spec); Pulumi/CDK/Kubernetes coverage; skill eval suites (HashiCorp-style
`evals/` noted as a follow-up); running `make release` (version bumps and
pushes stay a human decision).

## 3. Decisions (all user-approved 2026-07-20)

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| D1 | Placement | New `plugins/iac/` plugin, `omniagents-iac` in marketplace.json | Same standing as omniagents-python; installable anywhere; room for k8s later |
| D2 | Scope | `terraform` + `docker` skills from day one | Both stacks are live in yinglong (W4 items pending on each) |
| D3 | Depth | Docker: full catalogue (system-style). Terraform: house layer only | See D4 — prior art absorbs the deep Terraform content |
| D4 | Positioning | Link-don't-repeat: marketplace lists antonbabenko/terraform-skill as an external entry; our plugin declares a dependency; our SKILL.md routes deep dives to it | His skill (★2.2k, Apache-2.0, actively released, by the terraform-aws-modules maintainer) already owns failure-mode/state-surgery depth; the open gap is Docker + the coherent TF+Docker+CI+secrets convention set |

Mechanics verified against code.claude.com plugin docs: git submodules are
NOT a supported distribution mechanism (plugin dirs are copied to cache,
no submodule resolution; outside-symlinks skipped). Marketplace entries MAY
point at third-party GitHub repos as plugin sources, and plugin.json
supports a `dependencies` array incl. cross-marketplace with
`allowCrossMarketplaceDependenciesOn`. Cross-plugin skill invocation has no
formal syntax but prose routing by skill name works (house precedent:
`system` ↔ `software`).

## 4. Research base

Three digests (committed under `docs/superpowers/research/`, 2026-07-20):

- `2026-07-20-iac-prior-art.md` — skill landscape. Terraform side occupied
  by antonbabenko/terraform-skill (~195KB) and hashicorp/agent-skills
  (product-oriented). Docker side fragmented and weak (best candidate ★9).
  No official Anthropic IaC skills. Structures worth borrowing: Babenko's
  routing table + response contract; HashiCorp per-skill evals; assets/
  (templates + validators).
- `2026-07-20-terraform-canon.md` — 2026 rulebook corpus: HashiCorp style
  guide / standard module structure / composition, Google + AWS PG +
  Gruntwork, terraform-aws-modules idioms; modern features 1.3→1.15
  (`terraform test`, ephemeral + write-only args, S3 `use_lockfile`,
  moved/import/removed, 1.14 query/actions, 1.15 dynamic sources); tfsec
  dead → Trivy, Terrascan archived; workspaces-for-envs CONTESTED.
- `2026-07-20-docker-compose-canon.md` — Dockerfile canon (layers, cache
  mounts, COPY flags, base-image tiers, digest pinning), uv two-phase
  pattern, CIS runtime hardening, supply chain (SBOM/provenance/cosign/
  Trivy), compose spec (file layering vs profiles, service_healthy,
  secrets, deploy.resources, watch), tag/OCI-label/CI conventions.

Reference files MUST be authored from these digests plus their primary
sources — no rules from memory; every rule carries its source URL inline.

## 5. Architecture

```
plugins/iac/
├── .claude-plugin/plugin.json          # omniagents-iac; dependencies: [terraform-skill]
└── skills/
    ├── terraform/
    │   ├── SKILL.md                    # posture + tiering + routing (~300–400 lines)
    │   └── references/
    │       ├── module-design.md        # ~500–700
    │       ├── state-and-environments.md  # ~300–400
    │       ├── security-and-gates.md   # ~400–500
    │       └── modern-features.md      # ~300–400
    └── docker/
        ├── SKILL.md                    # posture + index (~250–350)
        └── references/
            ├── dockerfile.md           # ~1,000–1,500
            ├── compose.md              # ~1,000–1,400
            ├── hardening-and-supply-chain.md  # ~1,000–1,400
            └── ci-and-release.md       # ~800–1,200
```

Invocation names: `omniagents-iac:terraform`, `omniagents-iac:docker`.

**marketplace.json** gains:

1. `omniagents-iac` — source `./plugins/iac`, category `infrastructure`,
   keywords terraform/docker/compose/iac/aws.
2. `terraform-skill` — external source pointing at Anton Babenko's repo.
   Resolution procedure during implementation (in order):
   1. Inspect `antonbabenko/agent-plugins`'s own marketplace.json and
      mirror its source stanza (github vs git-subdir + path) into ours.
   2. Verify with a real `/plugin marketplace add` + `/plugin install`
      round-trip from a scratch profile.
   3. If cross-marketplace resolution proves unreliable in practice, drop
      the external entry; README then documents the two-line install of
      his marketplace, and the plugin.json dependency is demoted to a
      documented recommendation. The terraform SKILL.md routing degrades
      gracefully either way (see §6).

**plugin.json** declares `"dependencies": [{"name": "terraform-skill"}]`;
implementation verifies whether our marketplace metadata needs
`allowCrossMarketplaceDependenciesOn` and relaxes to a soft recommendation
if a hard dependency would block installs for users without his
marketplace.

## 6. terraform skill (house layer)

**SKILL.md structure** (mirrors `design-patterns:system`): default posture
→ tiering framework → decision flow → routing table → reference index →
"what this skill does NOT cover".

**Posture (non-negotiables, each with source URL in the reference files):**

- Pin everything: `required_version` per root; providers `~>` in roots,
  `>=` minimums in reusable modules; module sources by exact registry
  version or git `?ref=` tag/SHA (never a branch); `.terraform.lock.hcl`
  committed.
- Every variable and output typed and described; variables ordered
  type → description → default → sensitive → validation.
- No `provider` blocks inside reusable modules; `required_providers` only.
- Dependency inversion: modules receive IDs/ARNs as inputs; no buried
  data-source lookups of assumed infrastructure.
- Flat module tree (one level of children, composed in the root); no thin
  single-resource wrapper modules; no god modules.
- No `0.0.0.0/0` ingress; reference security groups, not CIDRs, wherever
  the provider allows.
- `default_tags` on the root provider (owner/env/cost-center/managed-by).
- Secrets never enter state: ephemeral resources / write-only `_wo` args
  (TF ≥1.11) or runtime SSM/Secrets Manager references; `sensitive = true`
  is marking, not protection; state is secret regardless.
- Remote state: S3 versioned + encrypted + public-access-blocked +
  `use_lockfile = true`; no new DynamoDB lock tables.
- Gates: fmt-check → validate → TFLint → Trivy (house default — one
  scanner across terraform and docker; Checkov documented as the
  alternative) → saved plan → reviewed apply; OIDC short-lived roles,
  zero long-lived cloud keys.

**Tiering framework** (the sample-redis lesson, applied per control):

| Control | T1 demo/portfolio | T2 production | T3 regulated |
|---|---|---|---|
| Encryption in transit + AUTH | optional (VPC-scoped SG suffices) | required | required (mandated wrappers) |
| At-rest encryption | provider default | provider default or CMK | CMK + key policy |
| HA / replicas / failover | no | required for stateful path | required |
| Backups / snapshots | no | required (retention named) | required + tested restore |
| Log delivery / audit | no | error+slow logs | full delivery + retention policy |
| Alarms / notifications | no | memory/error alarms | + SNS ops hooks |

Rule: every control names its tier and its pain; a T1 stack passing T1 is
correct, not negligent — "enterprise-grade means knowing your tier, not
maximal knobs."

**Routing table:** authoring, module shape, conventions, gates → this
skill's references. Failure diagnosis, state surgery (corrupt/locked/
drifted state), large migrations, count↔for_each refactors at scale →
invoke the `terraform-skill` skill when installed; when absent, cite the
canonical URLs (HashiCorp style/structure/composition, Google, AWS PG,
Gruntwork) inline instead. Never re-derive his content into ours.

**References inventory:**

- `module-design.md` — standard structure, naming (no type echo in
  resource names), variables/outputs conventions, composition +
  dependency inversion, `create_*`/`enable_*` feature flags, examples/ +
  tests/ shape, terraform-docs; anti-patterns: god module, thin wrapper,
  hardcoded literals, output sprawl. HCL examples in house style
  (AWS-flavored).
- `state-and-environments.md` — backend baseline, bootstrap
  chicken-and-egg pattern, blast-radius state splitting (env × layer),
  cross-state data flow; CONTESTED verdict: directory-per-env (house
  rule), CLI workspaces reserved for ephemeral/PR stacks, both positions
  stated.
- `security-and-gates.md` — pinning matrix, secrets mechanics (ephemeral/
  `_wo`/runtime refs, with the `_wo_version` bump pattern), SG
  least-privilege, encryption defaults, the full gate pipeline, OIDC,
  pre-commit-terraform, drift detection, Infracost.
- `modern-features.md` — adoption decision tables for 1.3→1.15
  (`terraform test` + mocks + parallelism, check/pre/postconditions,
  moved/import/removed, provider functions, templatestring, optional()
  attrs, 1.14 query/actions, 1.15 dynamic source/deprecated); OpenTofu
  divergence note; Stacks = HCP-only, out of OSS rulebook scope.

## 7. docker skill (full catalogue)

**SKILL.md structure:** posture → tiering (same T1/T2/T3 table applied to
containers: e.g. SBOM/signing = T2+, read-only rootfs = T2+, distroless =
T3-or-named-pain) → stack quick-paths (Python+uv canonical pattern;
Node/Vite build → static-server stage) → decision flow → reference index.

**Posture (non-negotiables):** `# syntax=docker/dockerfile:1` first line;
multi-stage always, toolchains never in the final stage; non-root USER
with explicit UID/GID; exec-form ENTRYPOINT/CMD + init reaper; COPY not
ADD; bases pinned `tag@digest` with automated bumps (never digest-pin
without automation); `.dockerignore` always; healthcheck on every
long-running service; compose files have no `version:` key; secrets never
as environment variables; memory+CPU limits everywhere; `--locked`/
`--frozen` installs only — the container never resolves dependencies.

**References inventory:**

- `dockerfile.md` — layer-ordering canon, cache mounts (+`sharing=locked`),
  bind-mount lockfiles, heredocs, COPY `--chown/--chmod/--link/--parents`,
  base-image decision (slim default; Alpine-for-Python banned with the
  musl rationale; distroless/Wolfi as the hardened tier), digest pinning +
  Renovate, the uv two-phase pattern (`uv sync --locked
  --no-install-project` deps layer → source → `uv sync --locked
  --no-editable`; venv-copy runtime; `UV_COMPILE_BYTECODE`,
  `UV_LINK_MODE=copy`; workspace variant), Vite build → static stage;
  anti-pattern gallery incl. mutating deps inside a frozen build (e.g.
  `uv add --no-sync` before `uv sync --frozen`), `:latest` bases, root
  runtime, chown-after-copy layers, ADD-for-COPY.
- `compose.md` — spec baseline (`name:`, no `version:`), file layering
  (base + auto-loaded dev override + explicit `-f` prod) vs profiles
  (optional services within one env — never env splits), long-form
  `depends_on` + `condition: service_healthy` (+ `restart: true`),
  healthcheck conventions, compose `secrets:` over env vars (inspect/log
  leak rationale), restart policies, `deploy.resources` (legacy
  `mem_limit` superseded), named volumes vs binds, `develop.watch`
  (sync/rebuild split), env_file + `.env.sample` conventions, single-host
  production checklist (CONTESTED framing: legitimate iff the checklist
  closes).
- `hardening-and-supply-chain.md` — CIS-derived runtime hardening
  (read-only rootfs + tmpfs, cap_drop ALL, no-new-privileges, never
  privileged), PID-1/signal discipline (`exec "$@"` wrappers), uvicorn
  process model (one process per container under an orchestrator;
  `--workers` only single-host), hadolint (+key rules DL3006/DL3008/
  DL3002, `.hadolint.yaml`), scanning (Trivy primary, Grype
  second-opinion), SBOM + provenance attestations, cosign keyless
  signing, docker-bench-security.
- `ci-and-release.md` — GHA build-push with `type=gha,mode=max` cache
  (Buildx ≥0.21 requirement), multi-arch via native-runner matrix +
  `imagetools create` (QEMU only for trivial images), metadata-action OCI
  labels, tag strategy (immutable git SHA on every push; semver triplet
  on release; `:latest` banned from prod manifests; registry immutable
  tags + lifecycle policies), gate order hadolint → build (`--provenance
  --sbom`) → Trivy fail-on-HIGH/CRITICAL → cosign → push.

## 8. Conventions (both skills)

- Frontmatter matches house style: `name`, `description` (trigger-rich),
  `when_to_use`, `paths` globs (`**/*.tf`, `**/*.tfvars`,
  `**/.terraform.lock.hcl` / `**/Dockerfile*`, `**/compose*.y*ml`,
  `**/docker-compose*.y*ml`, `**/.dockerignore`, `**/.hadolint.yaml`).
- Every rule cites its source URL inline; CONTESTED rules carry both
  positions in one line (workspaces-for-envs, distroless-vs-slim,
  compose-in-prod).
- Reference entries follow the system-skill shape where a pattern is being
  catalogued: Intent · When to reach for it · Sketch · When NOT to use ·
  Anti-pattern variant · References.
- Overkill thresholds throughout: no control without a named pain/tier.

## 9. Validation & release

- `make validate` (claude plugin validate) green.
- Marketplace registration renders: plugin listed, skills invocable as
  `omniagents-iac:terraform` / `omniagents-iac:docker` in a fresh session.
- Smoke test against yinglong: the terraform skill must (a) flag the
  default (volatile-lru) parameter group + no-snapshot redis as a T2 gap
  while blessing the T1 SG posture, (b) audit the pinning posture of
  `infra/app/providers.tf` + module sources and name each gap; the docker
  skill must flag the `uv add --no-sync`-inside-
  frozen-build pattern in `backend/docker/Dockerfile.api` and the absence
  of compose resource limits.
- External-entry resolution procedure of §5 executed and its outcome
  recorded in the implementation notes.
- Release: work lands on `feat/iac-plugin`; PR to main. `make release
  VERSION=x.y.z` (lockstep bump of every plugin) and `git push` are NOT
  run by the implementation — user-gated, especially since the repo
  carries unrelated uncommitted WIP (`software/SKILL.md` edit,
  `codebase-design/`, `tech-lead/` additions) that must stay untouched.

## 10. Phase 2 (out of scope here)

A separate yinglong spec applies the skills: tier-2 hardening of
`infra/app/modules/*` folding in improvement-plan W4.2 (redis noeviction
parameter group, snapshots, replica, memory alarm), IaC gates in CI
(fmt/validate/tflint/trivy + hadolint), and the W4.6 compose rewrite
reviewed under `omniagents-iac:docker`.

## 11. Risks

- **External-source resolution fails** → mitigated by the §5 fallback
  (README two-liner; routing degrades to canonical URLs).
- **Babenko restructures/renames his plugin** → external entry pins to his
  marketplace name; a rename breaks install, caught by `make validate` /
  install smoke on the next release cycle; routing prose names the skill
  generically ("the terraform-skill skill, if installed").
- **Docker catalogue drifts stale** (the 2024→2026 churn shows the rate)
  → each reference ends with a "verified as of" line + the research digest
  links, making refresh a diff exercise.
- **Depth creep on the terraform side** → hard rule: any content that
  exists in his skill or the official style guide is linked, not
  restated; the house layer caps at ~2.5k lines total.
