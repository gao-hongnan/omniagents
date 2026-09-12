# GitHub Actions Canon — source dossier for `omniagents-iac:github-actions`

Research behind the `github-actions` skill (shipped 2026-09-12, unreleased at
time of writing). This dossier is the **source of truth for edits**: change a
rule here with its citation before changing the skill, the same convention the
docker and terraform canons follow.

## Scope decision

The skill lives in `plugins/iac/`, not in a new plugin and not in
`plugins/workflow/` (which is a byte-exact MIT import and must not be
hand-edited). Rationale: `omniagents-iac` already owns the CI surface —
`docker/references/ci-and-release.md` covers `docker/build-push-action`,
BuildKit `type=gha` cache, multi-arch fan-out, OCI labels, tag strategy, and
registry lifecycle. The new skill cross-references that file rather than
re-deriving it, and `docker`'s `ci-and-release.md` remains the owner of
image-build CI specifics.

## Rule set, with load-bearing sources

| Rule | Source |
|---|---|
| Explicit `permissions:`, read-only default | <https://docs.github.com/en/actions/reference/security/secure-use> |
| SHA pinning is the only immutable action reference | same |
| Mutable tags are exploited in practice (CVE-2025-30066, 23k+ repos; CVE-2025-30154) | <https://github.com/advisories/GHSA-mrrh-fwg8-r2c3>, <https://www.cisa.gov/news-events/alerts/2025/03/18/supply-chain-compromise-third-party-tj-actionschanged-files-cve-2025-30066-and-reviewdogaction> |
| Dependabot raises no alerts for SHA-pinned actions → version updates, not alerts, are the mechanism | <https://docs.github.com/en/actions/reference/security/secure-use> |
| `cooldown: default-days` (1–90; `semver-*-days` variants) | <https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference> |
| Untrusted context list: `body`, `default_branch`, `email`, `head_ref`, `label`, `message`, `name`, `page_name`, `ref`, `title` | <https://docs.github.com/en/actions/concepts/security/script-injections> |
| Fixes: intermediate `env:` var, or action inputs | same + secure-use |
| `pull_request_target` / `workflow_run` must not check out untrusted code; artifacts from other workflows are untrusted | <https://docs.github.com/en/actions/reference/security/secure-use>, <https://securitylab.github.com/resources/github-actions-preventing-pwn-requests/> |
| `::set-env`/`::add-path` removed Nov 2020 (CVE-2020-15228); `GITHUB_ENV` still injectable via unsafe delimiters | <https://github.blog/changelog/2020-11-09-github-actions-removing-set-env-and-add-path-commands-on-november-16/> |
| Caches are repository-scoped; PR-written cache readable from default branch | <https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching> |
| Cache poisoning is exploited (Cacheract; Angular `dev-infra` chain) | <https://adnanthekhan.com/2024/05/06/the-monsters-in-your-build-cache-github-actions-cache-poisoning/>, <https://adnanthekhan.com/posts/angular-compromise-through-dev-infra/> |
| ArtiPACKED: `persist-credentials: true` default → token in `.git/config` → artifact | <https://www.stepsecurity.io/blog/detect-leaked-secrets-in-github-action-workflow-artifacts> |
| Shell defaults: `bash -e {0}` unspecified vs `bash --noprofile --norc -eo pipefail {0}` for `shell: bash` | <https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idstepsshell> |
| Default job `timeout-minutes` 360; 6h/5d/35d caps; 256 matrix jobs; 500 KB workflow file; 10 GB cache | <https://docs.github.com/en/actions/reference/limits> |
| `concurrency.queue` (`single` default / `max` ≤100; `max` incompatible with `cancel-in-progress: true`) | <https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax> |
| Trigger-filter-skipped workflows report no status → required check pends forever; `merge_group` ignores path filters against the PR diff | <https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks>, <https://github.com/community/community/discussions/45899> |
| Reusable workflows: caller job keyword allowlist; `env` crosses neither direction; permissions only narrow; secrets one hop; 10 levels / 50 unique (GHES 4 / 20) | <https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations> |
| `secrets` context unavailable in composite actions; job-level `if:` sees only `github`/`needs`/`vars`/`inputs` | <https://docs.github.com/en/actions/reference/workflows-and-actions/contexts> |
| `action.yml` metadata: `node20`/`node24`, composite `shell:` mandatory, composite outputs need `value:`, output caps 1 MB/job and 50 MB/workflow | <https://docs.github.com/en/actions/reference/workflows-and-actions/metadata-syntax> |
| Immutable actions via OCI publishing to GitHub Packages | <https://github.com/actions/publish-immutable-action>, <https://docs.github.com/en/actions/how-tos/create-and-publish-actions/release-and-maintain-actions> |
| OIDC: `id-token: write` grants only token minting; `sub` claim forms; AWS has no custom claims | <https://docs.github.com/en/actions/concepts/security/openid-connect>, <https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws> |
| Environments: ≤6 reviewers, wait timer 1–43,200 min, branch/tag policy, ≤6 protection rules, 30-day approval expiry | <https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments> |
| Self-hosted: not ephemeral, never public repos, `ps x -w` cross-job secret leak, JIT config | <https://docs.github.com/en/actions/reference/security/secure-use> |
| Artifacts v4+ immutable; no same-name re-upload | <https://github.com/actions/upload-artifact> |
| actionlint: `.github/actionlint.yaml`, `self-hosted-runner`/`config-variables`/`paths`, bundled shellcheck + pyflakes | <https://github.com/rhysd/actionlint> |
| zizmor: 40+ audits, personas regular/pedantic/auditor, `zizmor.yml`, SARIF + `zizmor-action` | <https://docs.zizmor.sh/audits/>, <https://docs.zizmor.sh/usage/> |
| harden-runner egress audit/block modes | <https://github.com/step-security/harden-runner> |

## Contested calls, resolved in-skill with both positions stated

- **`ubuntu-latest` vs pinned OS.** Skill pins, and states the
  counter-position (drift surfaces migration breakage early) as defensible for
  cheap-to-break CI, not for release pipelines.
- **Self-hosted runners.** T3-or-named-pain, ephemeral/JIT only, never public.
  The legitimate cases (GPU, licensed toolchains, VPC access, cost at scale)
  are named rather than dismissed.
- **harden-runner.** Stated as a genuine trade: the only control that catches a
  compromised *transitive* dependency at runtime, versus adding a privileged
  third-party agent to every job. Resolution: audit mode broadly, block mode on
  release/deploy only.
- **`pull_request_target`.** Not banned outright — the legitimate
  label/comment/assign case is described, with the two-workflow
  `pull_request` → `workflow_run` handoff as the pattern when a build must
  happen too.

## Deliberate omissions

Other CI systems (GitLab/Buildkite/CircleCI/Jenkins), Dockerfile authoring
(→ `docker`), the infrastructure a workflow deploys to (→ `terraform`), test
authoring (→ language `testing` skills), and GitHub App/webhook/API
development beyond in-run token usage. Listed in the skill's "does NOT cover"
section so routing is explicit rather than silent.

## Verification performed at authoring time

- All 33 cited URLs return HTTP 200.
- All 58 embedded YAML/JSON examples parse (`yaml.safe_load` / `json.loads`).
  Four illustrative snippets were rewritten because they were themselves
  invalid YAML — a skill about workflow correctness must not ship unparseable
  examples.
- All 40 intra-skill `references/*.md#anchor` cross-links resolve to real
  headings.
- Listing budget: `description` + `when_to_use` = 832 chars (docker is 862;
  ceiling ~1,536/skill, target ≤~800–900) — see
  [skill-quality-audit](2026-07-31-skill-quality-audit.md).
- `claude plugin validate .` passes; markdownlint reports only MD060
  (table-separator spacing), which the already-shipped docker skill also
  reports — pre-existing house style, not a regression.
- No unverified commit SHAs are printed anywhere; examples use
  `REPLACE_WITH_PINNED_SHA` and the skill instructs the reader to resolve SHAs
  themselves.
