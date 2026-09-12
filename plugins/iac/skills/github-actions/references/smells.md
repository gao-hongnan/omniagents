# Workflow Smells

A review catalogue. Each entry names a smell, shows the shape it takes,
says why it bites, and gives the fix; the reasoning lives in the other
reference files, linked per entry. Use the index to review someone
else's workflow in one pass, then read the family section for anything
that fires.

Severity convention, matching the house review contract: **BLOCKER**
means a live security hole or a check that cannot pass; **IMPORTANT**
means a real defect that will surface; **MINOR** means maintainability
or cost.

## Index

| Smell | Symptom | Severity |
|---|---|---|
| [Ambient permissions](#ambient-permissions) | no `permissions:` block anywhere | BLOCKER |
| [Floating action reference](#floating-action-reference) | `uses: org/action@v4` | BLOCKER |
| [Frozen pin](#frozen-pin) | SHA pins, no `dependabot.yml` | IMPORTANT |
| [Interpolated untrusted input](#interpolated-untrusted-input) | `${{ github.event.* }}` inside `run:` | BLOCKER |
| [Privileged fork checkout](#privileged-fork-checkout) | `pull_request_target` + `head.sha` checkout | BLOCKER |
| [Credential-persisting checkout](#credential-persisting-checkout) | default `actions/checkout` + artifact upload | BLOCKER |
| [Blanket secret inheritance](#blanket-secret-inheritance) | `secrets: inherit` | IMPORTANT |
| [Static cloud key](#static-cloud-key) | `AWS_SECRET_ACCESS_KEY` in secrets | IMPORTANT |
| [Cached release](#cached-release) | `actions/cache` in a tag-triggered workflow | IMPORTANT |
| [Actor as authentication](#actor-as-authentication) | `if: github.actor == '...'` | IMPORTANT |
| [Environment theatre](#environment-theatre) | `environment:` with repo-level secrets | MINOR |
| [Missing pipefail](#missing-pipefail) | `run:` with a pipe and no `shell: bash` | BLOCKER |
| [Suppressed failure](#suppressed-failure) | `continue-on-error: true`, outcome unread | BLOCKER |
| [Unreachable condition](#unreachable-condition) | `if: needs.x.result == 'failure'` alone | IMPORTANT |
| [Required check behind a path filter](#required-check-behind-a-path-filter) | PR stuck on `Expected — Waiting…` | BLOCKER |
| [Unquoted version](#unquoted-version) | `python-version: [3.10]` | IMPORTANT |
| [Unquoted expansion](#unquoted-expansion) | `$VAR` without quotes in `run:` | IMPORTANT |
| [Same-step env read](#same-step-env-read) | `$GITHUB_ENV` write then `${{ env.X }}` | IMPORTANT |
| [Matrix output collision](#matrix-output-collision) | job `outputs:` set from a matrix leg | IMPORTANT |
| [Unbounded job](#unbounded-job) | no `timeout-minutes` | IMPORTANT |
| [Pile-up](#pile-up) | no `concurrency:` | IMPORTANT |
| [Cancelled deploy](#cancelled-deploy) | `cancel-in-progress: true` on a deploy | BLOCKER |
| [Fail-fast compatibility matrix](#fail-fast-compatibility-matrix) | default `fail-fast` across versions | MINOR |
| [Drifting runner](#drifting-runner) | `runs-on: ubuntu-latest` in a release workflow | IMPORTANT |
| [Retry-by-rerun](#retry-by-rerun) | known flake, "just re-run it" | IMPORTANT |
| [Silent scheduled job](#silent-scheduled-job) | `schedule:` with no failure routing | IMPORTANT |
| [Cache that never hits](#cache-that-never-hits) | `key` contains `github.sha`; no `restore-keys` | MINOR |
| [Premium runner by default](#premium-runner-by-default) | macOS/Windows legs on every PR | MINOR |
| [Hoarded artifacts](#hoarded-artifacts) | default 90-day retention on CI output | MINOR |
| [Fourth copy](#fourth-copy) | same job block in several workflows | MINOR |
| [Inline megascript](#inline-megascript) | 60-line `run:` block | MINOR |
| [Flag-driven reusable workflow](#flag-driven-reusable-workflow) | a dozen boolean inputs | MINOR |
| [Wrapper action](#wrapper-action) | composite action wrapping one `uses:` | MINOR |
| [Env across the boundary](#env-across-the-boundary) | called workflow reads caller's `env` | IMPORTANT |
| [Unnamed steps](#unnamed-steps) | log reads `Run echo ...` | MINOR |

## Security smells

### Ambient permissions

```yaml
# no permissions: block anywhere in the file
jobs:
  build:
    steps: [...]
```

The run inherits the repository/organization default, still `write-all`
on any repository predating the 2023 flip. Every third-party action in
the job gets a token that can push to the default branch — including to
`.github/workflows/`.

**Fix:** `permissions: contents: read` at workflow level, widened per
job. → [`security.md`](security.md#permissions)

### Floating action reference

```yaml
- uses: tj-actions/changed-files@v45
```

Tags are mutable. This exact reference was repointed at a
secret-exfiltrating commit in March 2025 across 23,000+ repositories.

**Fix:** full 40-character SHA with the version in a trailing comment.
→ [`security.md`](security.md#supply-chain)

### Frozen pin

Every `uses:` is SHA-pinned and there is no `.github/dependabot.yml`.
The pins were correct the day they were written and now encode
known-vulnerable versions with no mechanism to move.

**Fix:** Dependabot `github-actions` ecosystem, weekly, with grouping
and a cooldown. Pin **and** automate.
→ [`gates-and-release.md`](gates-and-release.md#dependabot-for-actions)

### Interpolated untrusted input

```yaml
- run: echo "Title is ${{ github.event.pull_request.title }}"
```

`${{ }}` is substituted as literal text before the shell parses the
script. A PR title is an attacker-supplied string, so this is remote
code execution with the job's token and secrets.

**Fix:** bind to `env:` and reference `"$TITLE"`.
→ [`security.md`](security.md#script-injection)

### Privileged fork checkout

```yaml
on: pull_request_target
jobs:
  build:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@REPLACE_WITH_PINNED_SHA
        with: { ref: "${{ github.event.pull_request.head.sha }}" }
      - run: npm ci
```

`pull_request_target` runs with full secrets and a writable token;
`npm ci` executes the fork's install scripts. This hands the repository
to anyone who can open a PR.

**Fix:** use plain `pull_request`, or the two-workflow
`pull_request` → `workflow_run` handoff with artifact validation.
→ [`security.md`](security.md#fork-pull-requests)

### Credential-persisting checkout

```yaml
- uses: actions/checkout@REPLACE_WITH_PINNED_SHA  # persist-credentials: true
# ... build steps ...
- uses: actions/upload-artifact@REPLACE_WITH_PINNED_SHA
  with: { path: . }   # ships .git/config, token included
```

**Fix:** `persist-credentials: false` on every checkout that does not
push, and never upload the whole workspace.
→ [`security.md`](security.md#artipacked)

### Blanket secret inheritance

```yaml
jobs:
  deploy:
    uses: ./.github/workflows/deploy.yml
    secrets: inherit
```

Hands the called workflow the entire store, including secrets it has no
reason to see, and propagates down the chain invisibly.

**Fix:** enumerate the secrets the callee needs.
→ [`security.md`](security.md#secrets)

### Static cloud key

```yaml
env:
  AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
  AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

Long-lived, identical across runs, readable by everyone with write
access, rotated when someone remembers.

**Fix:** OIDC with `id-token: write` and a `sub`-constrained trust
policy. → [`security.md`](security.md#oidc)

### Cached release

A tag-triggered publish workflow restores `actions/cache`. Caches are
repository-scoped and writable from PR-triggered runs, so a poisoned
entry can reach a published artifact — the documented Angular
`dev-infra` chain.

**Fix:** no cache in release workflows; if unavoidable,
`actions/cache/restore` keyed on something no PR can produce.
→ [`security.md`](security.md#cache-and-artifact-poisoning)

### Actor as authentication

```yaml
if: github.actor == 'dependabot[bot]'
```

`github.actor` is not an authentication claim; it reflects who triggered
the event, which is influenceable.

**Fix:** check `github.event.pull_request.user.type`, the app identity,
or an environment gate. zizmor's `bot-conditions` audit finds these.
→ [`security.md`](security.md#script-injection)

### Environment theatre

`environment: production` on the job, but the credentials come from
repository secrets. The deployment shows up in the Environments UI and
the gate protects nothing — the secret was already available to any job.

**Fix:** move the credential to an environment secret, so the protection
rule actually stands between the merge and the credential.
→ [`security.md`](security.md#environments-as-a-boundary)

## Correctness smells

### Missing pipefail

```yaml
- run: pytest | tee test.log     # no `shell:` key
```

Without `shell: bash` the runner uses `bash -e {0}` — no `pipefail` —
so the step reports `tee`'s exit status. A failing test suite is a green
build.

**Fix:** `defaults.run.shell: bash` at workflow level, and
`set -euo pipefail` at the top of any non-trivial block.
→ [`workflow-design.md`](workflow-design.md#shell-discipline)

### Suppressed failure

```yaml
- run: ./scripts/scan.sh
  continue-on-error: true
```

The step's failure is discarded and the job reports success. Almost
always written meaning "record it but keep going", which is not what it
does.

**Fix:** delete it, or read `steps.<id>.outcome` in a later step and act
on it. Legitimate only for an experimental matrix leg.
→ [`workflow-design.md`](workflow-design.md#continue-on-error)

### Unreachable condition

```yaml
- if: needs.build.result == 'failure'
```

Every `if:` is implicitly ANDed with `success()`, which is already false
when an upstream job failed — so this never fires.

**Fix:** `if: always() && needs.build.result == 'failure'`, or
`if: failure()`.
→ [`workflow-design.md`](workflow-design.md#conditions-and-result-semantics)

### Required check behind a path filter

```yaml
on:
  pull_request:
    paths: ["src/**"]     # and "test" is a required status check
```

A workflow skipped by a trigger filter reports **nothing**, so the
required check stays `Pending` and the PR can never merge. Merge-queue
`merge_group` events make it worse by evaluating filters against the
queue branch.

**Fix:** filter inside the job with `if:`, or make an always-running
aggregator job the required check.
→ [`workflow-design.md`](workflow-design.md#the-required-check-filter-trap)

### Unquoted version

```yaml
matrix:
  python-version: [3.10, 3.11]     # YAML floats: 3.1 and 3.11
```

`3.10` parses as the number `3.1`. The job runs the wrong interpreter
and the failure looks like a dependency bug.

**Fix:** quote every version string.
→ [`workflow-design.md`](workflow-design.md#matrix)

### Unquoted expansion

```yaml
- env: { TITLE: "${{ github.event.pull_request.title }}" }
  run: grep -q $TITLE file.txt
```

Moving the value into `env:` closed the injection; leaving the expansion
unquoted reopens word splitting and glob expansion.

**Fix:** `"$TITLE"`, always. shellcheck via actionlint catches it.
→ [`security.md`](security.md#script-injection)

### Same-step env read

```yaml
- run: |
    echo "TAG=v1" >> "$GITHUB_ENV"
    echo "${{ env.TAG }}"      # empty
```

Environment-file writes apply to **subsequent** steps, and `${{ }}` was
interpolated before the step ran anyway.

**Fix:** use a shell variable within the step; use `$GITHUB_ENV` only
for cross-step propagation.
→ [`workflow-design.md`](workflow-design.md#environment-files)

### Matrix output collision

A matrix job sets `outputs:`. Each leg overwrites the previous one in
nondeterministic order, so the downstream job reads one arbitrary leg.

**Fix:** upload per-leg artifacts named by the matrix values and
aggregate downstream.
→ [`workflow-design.md`](workflow-design.md#job-outputs)

## Reliability smells

### Unbounded job

No `timeout-minutes`, so the default is 360. A job hung on a network
call or a prompt burns six hours before anything notices.

**Fix:** set it on every job; 10–30 minutes is the normal CI band.
→ [`workflow-design.md`](workflow-design.md#timeouts)

### Pile-up

No `concurrency:` on a PR workflow. Every push runs a full matrix that
the next push obsoletes, and the results arrive out of order.

**Fix:** group on `${{ github.workflow }}-${{ github.ref }}` with
`cancel-in-progress: true`.
→ [`workflow-design.md`](workflow-design.md#concurrency)

### Cancelled deploy

`cancel-in-progress: true` on a deployment workflow. A second merge
kills the first deploy mid-apply, leaving the environment in a state
nothing recorded.

**Fix:** group per environment with `cancel-in-progress: false` —
serialize, never cancel.
→ [`workflow-design.md`](workflow-design.md#concurrency)

### Fail-fast compatibility matrix

Default `fail-fast: true` across language versions. The first failure
cancels the rest, so you learn 3.12 broke and nothing about 3.13 or
3.14 — and repeat the discovery next push.

**Fix:** `fail-fast: false` on compatibility matrices; keep it `true`
on shards of identical work.
→ [`workflow-design.md`](workflow-design.md#matrix)

### Drifting runner

`runs-on: ubuntu-latest` in a release or deploy workflow. The label
moves major versions on GitHub's schedule, so the build environment
changes on a day you did not choose.

**Fix:** pin `ubuntu-24.04`. (On a cheap-to-break CI workflow,
`-latest` is a defensible early-warning signal — but name that as the
reason.) → [`workflow-design.md`](workflow-design.md#runners)

### Retry-by-rerun

A known-flaky job that the team re-runs by hand. The flake is now
invisible in metrics, and the re-run habit hides real failures too.

**Fix:** find the race — usually a `sleep`-based wait, an unseeded
random, or a shared external fixture. If it must be retried, bound the
retry inside the step so the flake rate stays measurable.

### Silent scheduled job

A nightly security scan or dependency check with no failure routing.
Nobody is paged, so it has been red for six weeks. GitHub also disables
scheduled workflows after 60 days of repository inactivity, so it may
not even be running.

**Fix:** route failures somewhere a human reads, or delete the workflow.
An unwatched gate is worse than no gate — it produces false assurance.

## Cost smells

### Cache that never hits

`key:` contains `github.sha` (unique per commit, so never a hit), or
there are no `restore-keys` (so every lockfile change is a full miss).
The log line "Cache not found for input keys" on every run is the tell.

**Fix:** key on `hashFiles('<lockfile>')` plus `runner.os`, with a
prefix `restore-keys` fallback — or use the `setup-*` action's built-in
caching. → [`workflow-design.md`](workflow-design.md#caching)

### Premium runner by default

macOS (10× billing) and Windows (2×) legs on every pull request, for a
project whose users are 95% Linux.

**Fix:** Linux on PRs; full OS matrix nightly or pre-release.
→ [`workflow-design.md`](workflow-design.md#runners)

### Hoarded artifacts

CI artifacts at the default 90-day retention, for output nobody opens
after the PR merges.

**Fix:** `retention-days: 7` on CI artifacts; keep the default only for
release artifacts.
→ [`workflow-design.md`](workflow-design.md#artifacts)

## Maintainability smells

### Fourth copy

The same build-and-test job block in four workflow files. Three are
identical; the fourth diverged eight months ago and nobody noticed.

**Fix:** extract a reusable workflow (whole jobs) or a composite action
(step sequences). → [`reuse.md`](reuse.md#choosing-a-mechanism)

### Inline megascript

A 60-line `run:` block. It cannot be run locally, cannot be unit tested,
reports as one opaque step, and gets edited by pushing to CI.

**Fix:** move it to `scripts/` where a human can run it, and keep the
workflow a thin invocation. Split what remains into named steps.
→ [`workflow-design.md`](workflow-design.md#writing-the-block)

### Flag-driven reusable workflow

A reusable workflow with twelve boolean inputs. Every flag is an
untested branch, and the combinations are untestable by construction.

**Fix:** split into two honest workflows, or accept the duplication.
→ [`reuse.md`](reuse.md#anti-patterns)

### Wrapper action

A composite action whose entire body is one `uses:`. Readers now open
two files to learn what runs, and Dependabot traverses an extra hop.

**Fix:** inline it. → [`reuse.md`](reuse.md#anti-patterns)

### Env across the boundary

A reusable workflow referencing `env.FOO` set by its caller. `env` does
not cross the `workflow_call` boundary in either direction; the value is
an empty string, not an error.

**Fix:** pass it as an input. → [`reuse.md`](reuse.md#constraints-that-bite)

### Unnamed steps

The run log reads `Run echo "::group::..."`. Every failure requires
expanding the step to learn what it was.

**Fix:** `name:` on every step that is not self-evidently trivial, and
write a `$GITHUB_STEP_SUMMARY` for anything a human will want to read
without opening logs.
→ [`workflow-design.md`](workflow-design.md#environment-files)

## Review checklist

Ten questions that catch most of the above in one pass:

1. Is there a `permissions:` block, and is it read-only by default?
2. Is every `uses:` a 40-character SHA with a version comment, and does
   `dependabot.yml` cover the `github-actions` ecosystem?
3. Does any `run:` body interpolate `${{ github.event.* }}`,
   `github.head_ref`, or another untrusted context?
4. Does any `pull_request_target` or `workflow_run` job check out or
   execute PR-controlled code?
5. Does every job have `timeout-minutes`, and does the workflow have
   `concurrency:` with the right `cancel-in-progress` for its kind?
6. Is `shell: bash` (or `defaults.run.shell: bash`) set anywhere a
   `run:` block uses a pipe?
7. Are required checks free of workflow-level `paths:`/`branches:`
   filters — ideally a single always-running aggregator job?
8. Do cloud credentials come from OIDC rather than static secrets, and
   is `secrets: inherit` absent?
9. Does the release workflow avoid caches, trigger on a tag, and sit
   behind an environment gate?
10. Do `actionlint` and `zizmor` run on this repository, and is this
    change clean under both?
