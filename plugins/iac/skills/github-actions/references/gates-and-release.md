# Gates & Release

The workflows that guard the workflows, and the shape of the pipeline
that ships. Review rules live in [`smells.md`](smells.md); the security
reasoning behind each gate lives in [`security.md`](security.md).

1. [`## Gate order`](#gate-order)
2. [`## actionlint`](#actionlint)
3. [`## zizmor`](#zizmor)
4. [`## Other scanners`](#other-scanners)
5. [`## Dependabot for actions`](#dependabot-for-actions)
6. [`## Required checks and merge queue`](#required-checks-and-merge-queue)
7. [`## Environments and deployments`](#environments-and-deployments)
8. [`## Release workflows`](#release-workflows)
9. [`## Runtime and cost control`](#runtime-and-cost-control)

## Gate order

Order gates by cost ascending and blast radius descending, so the
cheapest check that can reject the change runs first:

1. **Local, pre-commit** — `actionlint`, `zizmor` (both have pre-commit
   hooks, both run in well under a second on a normal repository).
2. **Pull request** — the same two in CI (pre-commit is advisory;
   someone always skips it), plus `dependency-review-action`, plus
   language linting and tests.
3. **Merge to default branch** — full test matrix, OpenSSF Scorecard,
   CodeQL.
4. **Tag / release** — build, attest provenance, sign, publish through
   OIDC trusted publishing, with an environment gate in front of
   anything irreversible.

The one ordering that matters more than convenience: **workflow linting
runs before anything expensive**, because a broken expression or an
injectable `run:` block is cheaper to catch than a 20-minute matrix is
to run.

## actionlint

Catches what YAML validity does not: unknown runner labels, `needs:`
referencing a nonexistent job, malformed cron, type errors inside
`${{ }}` (dereferencing a property on a string, comparing a boolean to
a string), deprecated workflow commands, and — via bundled shellcheck
and pyflakes — bugs inside every `run:` block. Unquoted `$VAR`,
`cd || exit` omissions, and useless `cat` are found by the same
shellcheck rules you would run on a standalone script, which is the
whole point: `run:` blocks are scripts and nobody lints them.

```yaml
# .github/workflows/lint-workflows.yml
name: lint-workflows
on:
  pull_request:
    paths: [".github/**"]
  push:
    branches: [main]
permissions:
  contents: read
jobs:
  actionlint:
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@REPLACE_WITH_PINNED_SHA # v5.0.0
        with: { persist-credentials: false }
      - name: Run actionlint
        uses: docker://rhysd/actionlint:1.7.12@sha256:REPLACE_WITH_PINNED_DIGEST
        with:
          args: -color
```

Note the `paths:` filter is safe here only because this check is **not**
required — if you make it required, drop the filter
([`workflow-design.md`](workflow-design.md#the-required-check-filter-trap)).

Config lives at `.github/actionlint.yaml`:

```yaml
self-hosted-runner:
  labels:
    - linux-2xlarge
config-variables:
  - DEFAULT_RUNNER
  - DEPLOY_REGION
paths:
  .github/workflows/**/*.{yml,yaml}:
    ignore:
      - 'shellcheck reported issue in this script: SC2086:.+'
```

Declaring `config-variables` turns `vars.*` from an untyped escape hatch
into a checked set — a typo'd `vars.DEPLOY_REGOIN` becomes an error
rather than an empty string. Declaring self-hosted labels stops the
"unknown runner label" noise that otherwise trains people to ignore
output.

Pre-commit:

```yaml
- repo: https://github.com/rhysd/actionlint
  rev: v1.7.12
  hooks:
    - id: actionlint
```

`-shellcheck= -pyflakes=` disables the script integrations if you need
the speed; you almost never do, and disabling them removes most of the
value.

Source: <https://github.com/rhysd/actionlint>.

## zizmor

The security-shaped complement: 40+ audits covering template injection,
excessive permissions, `artipacked` credential persistence, dangerous
triggers, `github-env` writes, `secrets: inherit`, impostor commits,
typosquatted `uses:`, unpinned actions and images, cache poisoning in
release workflows, and unsound `if:` conditions. Most run offline in
milliseconds; the online audits (impostor-commit, known-vulnerable
actions) need a token.

```yaml
  zizmor:
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    permissions:
      contents: read
      security-events: write   # upload SARIF to code scanning
      actions: read
    steps:
      - uses: actions/checkout@REPLACE_WITH_PINNED_SHA # v5.0.0
        with: { persist-credentials: false }
      - uses: zizmorcore/zizmor-action@REPLACE_WITH_PINNED_SHA # v1.0.1
        with:
          format: sarif
          output: zizmor.sarif
      - uses: github/codeql-action/upload-sarif@REPLACE_WITH_PINNED_SHA # v3.29.5
        with:
          sarif_file: zizmor.sarif
```

Routing findings into code scanning rather than a failing log line is
the difference between a gate people fix and a gate people disable:
findings land in the PR's Security tab with dismissal tracking.

Personas set sensitivity: `--persona=regular` (default, high signal),
`--pedantic` (adds smells such as missing `concurrency` and
undocumented `permissions`), `--persona=auditor` (everything, including
likely false positives — for a one-off audit, not a gate). Start at
regular; move to pedantic once the baseline is clean.

Suppression, when a finding is genuinely wrong, should be specific and
annotated:

```yaml
# zizmor.yml
rules:
  template-injection:
    ignore:
      - safe-by-construction.yml:42
```

or inline: `run: | # zizmor: ignore[template-injection]`. A repository
that ignores a whole rule globally has turned the gate off; ignore
*instances*, with the reason in a comment.

Sources: <https://docs.zizmor.sh/audits/>, <https://docs.zizmor.sh/usage/>.

## Other scanners

- **CodeQL** ships queries for Actions workflows (injection, dangerous
  artifact handling) as part of default setup. Free on public
  repositories, and it catches cross-file patterns the linters do not.
- **OpenSSF Scorecard** grades the repository on `Token-Permissions`,
  `Pinned-Dependencies`, `Dangerous-Workflow`, and others, and posts
  results to code scanning. Useful as a trend line and as an external
  standard to argue from; not a substitute for the two linters, since
  it reports a score rather than a location.
- **`actions/dependency-review-action`** blocks PRs that introduce a
  dependency with a known advisory, including action dependencies.
  Requires the dependency graph to be enabled.

Run all three plus actionlint and zizmor — they overlap partially and
each finds things the others miss, and the marginal cost is a minute of
a free runner.

## Dependabot for actions

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"                    # covers .github/workflows/
    schedule:
      interval: "weekly"
      day: "tuesday"
    cooldown:
      default-days: 7
    groups:
      actions-minor:
        update-types: ["minor", "patch"]
    open-pull-requests-limit: 5
```

- `directory: "/"` is correct even though workflows live in
  `.github/workflows/` — Dependabot treats the repository root as the
  manifest location for this ecosystem.
- Add a second entry with `directory: "/.github/actions/<name>"` for
  each composite action in the repository; Dependabot does **not**
  traverse into them from the root entry.
- **Locally-referenced actions (`./.github/actions/x`) are never
  updated** — by definition they are your code.
- **Grouping** minor and patch updates into one PR is the difference
  between a maintained pin set and eight ignored PRs a week.
- **Cooldown** delays taking a release for N days, so a compromised
  publish has time to be discovered before your pipeline consumes it.
  Seven days is a reasonable default; zizmor's `dependabot-cooldown`
  audit flags its absence.
- Dependabot does **not** raise security alerts for SHA-pinned actions,
  since advisories are matched by version range. Version updates are
  therefore the mechanism, not alerts.

Source:
<https://docs.github.com/en/actions/reference/security/secure-use>.

## Required checks and merge queue

Configure required checks on the **aggregator gate job**, not on every
individual job:

- One name to maintain, so adding a matrix leg does not require a
  branch-protection edit.
- No pending-forever failure mode from path filters or skipped jobs,
  provided the gate uses `if: always()` and inspects `needs.*.result`.
- Matrix legs do not appear as separate required checks, which
  otherwise makes the required-check list churn with every version bump.

For the merge queue:

- The workflow must list `merge_group` in `on:`, or the queue waits
  forever for a check nobody will report.
- `merge_group` runs against a temporary queue branch. Anything keyed on
  `github.event.pull_request` is unavailable there — guard with
  `if: github.event_name == 'pull_request'`.
- Path filters and merge queues do not mix
  ([`workflow-design.md`](workflow-design.md#the-required-check-filter-trap)).

Also enable, at the repository level:

- **CODEOWNERS covering `.github/workflows/`** — a workflow change is a
  privilege change.
- **"Require approval for all external contributors"** for workflow
  runs from first-time contributors, so a fork PR cannot spend runner
  minutes or probe the pipeline without a maintainer's click.
- **Restrict who can approve and create PRs from Actions**, unless a
  bot workflow genuinely needs it.

## Environments and deployments

Protection rules live on the environment, not in the workflow file —
which is the point: they cannot be edited by the PR that wants to bypass
them.

| Rule | What it buys | Limits |
|---|---|---|
| Required reviewers | a human between merge and production | up to 6 users/teams; one approval suffices; enable "prevent self-review" |
| Wait timer | a window to notice and cancel | 1–43,200 minutes |
| Deployment branch/tag policy | only `main` or `v*` can deploy here | named patterns, or "protected branches only" |
| Environment secrets | the production key does not exist in PR context | resolves ahead of repository secrets |
| Custom protection rules | change-management or observability gates via a GitHub App | 6 rules per environment total |

Pair every environment with a **matching concurrency group and
`cancel-in-progress: false`** so two merges cannot deploy
simultaneously, and set the environment `url:` so the run page links to
what was deployed. Approvals expire after 30 days.

Source:
<https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments>.

## Release workflows

### Shape

Split build from publish. The build job holds no credentials and
produces an artifact; the publish job holds the credential (or the OIDC
grant), consumes the artifact, and is gated by an environment. This
means the code that produced the artifact never ran in the same process
as the publishing credential.

```yaml
name: release
on:
  push:
    tags: ["v*.*.*"]

permissions:
  contents: read

jobs:
  build:
    runs-on: ubuntu-24.04
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@REPLACE_WITH_PINNED_SHA # v5.0.0
        with: { persist-credentials: false }
      # No cache restore in a release workflow: a PR-writable cache
      # must never reach a published artifact.
      - run: uv build
      - uses: actions/upload-artifact@REPLACE_WITH_PINNED_SHA # v4.6.2
        with:
          name: dist
          path: dist/

  publish:
    needs: [build]
    runs-on: ubuntu-24.04
    timeout-minutes: 15
    environment:
      name: pypi
      url: https://pypi.org/p/my-package
    permissions:
      contents: read
      id-token: write       # trusted publishing; no API token exists
      attestations: write   # provenance
    steps:
      - uses: actions/download-artifact@REPLACE_WITH_PINNED_SHA # v5.0.0
        with:
          name: dist
          path: dist/
      - uses: actions/attest-build-provenance@REPLACE_WITH_PINNED_SHA # v3.0.0
        with:
          subject-path: dist/*
      - uses: pypa/gh-action-pypi-publish@REPLACE_WITH_PINNED_SHA # v1.13.0
```

### Rules

- **Trusted publishing over API tokens.** PyPI, npm, RubyGems, and
  crates.io all accept the OIDC token directly; there is then no
  registry credential in the repository to leak or rotate. Scope the
  publisher to the repository, workflow filename, **and** environment.
- **Tag-triggered, not branch-triggered.** A release that fires on a
  push to `main` ships whatever merged, including the commit that was
  meant to be reverted first.
- **Build provenance attestations** (`actions/attest-build-provenance`)
  bind the artifact to the workflow, repository, and commit that
  produced it, verifiable with `gh attestation verify`. T2+.
- **Never restore a cache in a release workflow**
  ([`security.md`](security.md#cache-and-artifact-poisoning)).
- **Re-run safety.** Publishing is not idempotent on most registries;
  a re-run of a successful publish fails loudly at best. Gate the
  publish job on a version-not-already-published check, or accept that
  re-running the workflow is a manual decision.
- **Rollback is a forward release.** Yanking is registry-specific and
  usually partial; the deployment story is "ship the previous version
  again", which requires that the previous version can still be built
  from its tag.

## Runtime and cost control

Failure modes, cheapest fix first:

- **No cache, or a cache that never hits.** Check the "Cache restored
  from key" line in the log. A key including `github.sha` never hits;
  a key with no `restore-keys` misses on every lockfile change.
- **`fail-fast: false` on a sharded matrix.** Twelve legs keep running
  after the first tells you the build is broken.
- **No `concurrency` on PR CI.** Every push to a branch runs a full
  matrix that the next push obsoletes 30 seconds later.
- **macOS or Windows legs on every PR.** 10× and 2× multipliers. Move
  the full OS matrix to a nightly `schedule` and keep Linux on PRs.
- **Whole-matrix re-runs for one flaky leg.** "Re-run failed jobs"
  exists; so does fixing the flake.
- **Artifact retention at the 90-day default** for artifacts that stop
  mattering when the PR merges. Set `retention-days: 7` on CI
  artifacts.
- **Scheduled workflows nobody reads.** A nightly job whose failures
  nobody is paged for is pure cost. Route it somewhere or delete it.
- **Self-hosted runners adopted to cut cost.** Real savings at scale,
  and a security decision first — [`security.md`](security.md#self-hosted-runners).

For visibility, the repository's Actions usage metrics page breaks
minutes down by workflow; the `workflow_run` API exposes per-run
duration if you want a trend line in your own dashboard.
