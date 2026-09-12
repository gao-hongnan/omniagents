# Workflow Design

How a workflow is shaped: what triggers it, how its jobs relate, what
bounds its runtime, and how state moves between steps. Security lives in
[`security.md`](security.md) and is cross-referenced here rather than
re-derived; duplication removal lives in [`reuse.md`](reuse.md).

Six decisions this file answers, in the order a new workflow needs them:

1. What events should start this, and what filters are safe? →
   [`## Triggers`](#triggers)
2. How do the jobs relate, and what happens when one fails? →
   [`## Job graph`](#job-graph)
3. What stops runs from piling up or running forever? →
   [`## Concurrency and timeouts`](#concurrency-and-timeouts)
4. How does one job become many? → [`## Matrix`](#matrix)
5. How do I write a `run:` block that fails when it should? →
   [`## Shell discipline`](#shell-discipline)
6. How does data move between steps, jobs, and runs? →
   [`## Expressions and contexts`](#expressions-and-contexts),
   [`## Caching`](#caching), [`## Artifacts`](#artifacts)

[`## Runners`](#runners) and [`## Platform limits`](#platform-limits)
close the file with the constraints everything above is sized against.

## Triggers

### Choosing the event

`on:` accepts most webhook events plus `schedule`, `workflow_dispatch`,
`workflow_call`, `repository_dispatch`, and `merge_group`. The common
mistakes are not exotic:

- **`push` without `branches:`** fires on every branch push including
  ones already covered by `pull_request`, doubling CI spend on every
  feature branch. The standard CI shape is `pull_request:` (all PRs)
  plus `push: branches: [main]` (post-merge verification only).
- **`pull_request` defaults to `types: [opened, synchronize, reopened]`.**
  If you need `ready_for_review` (draft PRs) or `labeled`, name the full
  list — adding one type replaces the default set, it does not extend
  it.
- **`schedule:` uses UTC and offers no jitter.** Everyone picks
  `0 0 * * *`, so the top of the hour is the most contended slot on the
  platform and scheduled runs are routinely delayed. Pick an offset
  minute. GitHub also disables scheduled workflows in public
  repositories after **60 days of repository inactivity** — a nightly
  security scan that silently stops is the failure mode.
- **`workflow_dispatch` inputs** are typed (`string`, `boolean`,
  `choice`, `environment`) and available as `inputs.<name>`. `choice`
  with an explicit `options:` list beats a free-text string that a
  typo turns into a no-op deploy.
- **`merge_group`** must be listed on any workflow whose check is
  required for the merge queue, or the queue will wait for a check that
  will never be reported.

Source:
<https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows>.

### The required-check filter trap

This is the single most common structural bug in GitHub Actions
configuration, and it looks like a cost optimization:

```yaml
# BROKEN if "test" is a required status check.
on:
  pull_request:
    paths: ["src/**"]
```

A workflow skipped because of a workflow-level `paths:`, `branches:`,
or commit-message filter reports **no status at all**. A branch rule
requiring that check sees `Expected — Waiting for status to be
reported`, forever, and the PR cannot merge. A docs-only PR is now
permanently blocked by an optimization intended to speed it up.

Note the asymmetry that makes this confusing: a **job** skipped by a
step/job-level `if:` reports **success**. Only *workflow-level trigger
filters* produce nothing. Two correct shapes:

**Shape 1 — filter inside the job.** The workflow always runs; the
expensive work is conditional.

```yaml
on: [pull_request]

jobs:
  changes:
    runs-on: ubuntu-24.04
    timeout-minutes: 5
    outputs:
      src: ${{ steps.filter.outputs.src }}
    steps:
      - uses: actions/checkout@REPLACE_WITH_PINNED_SHA # v5.0.0
        with: { persist-credentials: false }
      - id: filter
        uses: dorny/paths-filter@REPLACE_WITH_PINNED_SHA # v3.0.2
        with:
          filters: |
            src:
              - 'src/**'

  test:
    needs: [changes]
    if: needs.changes.outputs.src == 'true'
    runs-on: ubuntu-24.04
    timeout-minutes: 20
    steps: [...]
```

**Shape 2 — an aggregator gate.** One always-running job is the required
check; everything else feeds it. This is the more robust option because
it survives matrix changes, and it is what the SKILL.md quick-path
shows. The `if: always()` is mandatory — without it the gate job is
itself skipped when a dependency fails, and the required check goes
pending again.

```yaml
  ci-gate:
    if: always()
    needs: [lint, test, build]
    runs-on: ubuntu-24.04
    timeout-minutes: 5
    steps:
      - name: Fail if any dependency failed
        run: |
          results='${{ join(needs.*.result, " ") }}'
          echo "upstream results: $results"
          for r in $results; do
            [[ "$r" == "success" || "$r" == "skipped" ]] || exit 1
          done
```

The merge queue makes this worse rather than better: `merge_group`
events evaluate path filters against the queue branch, not against the
original PR diff, so a filter that matched on the PR may not match in
the queue. Treat "required check" and "path-filtered workflow" as
mutually exclusive.

Sources:
<https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks>,
<https://github.com/orgs/community/discussions/45899>.

### Filter syntax

`branches`/`branches-ignore`, `tags`/`tags-ignore`, and
`paths`/`paths-ignore` each accept glob patterns and **cannot be paired
with their own negation** (`branches` and `branches-ignore` in the same
`on:` block is a syntax error — use `!` patterns within one list
instead). A `!` pattern requires at least one positive pattern in the
same filter, and order matters: later patterns override earlier ones.

## Job graph

### `needs` and fan-out

Jobs run in parallel unless `needs:` orders them. The default shape most
repositories reach for — `lint → test → build → deploy` in a straight
line — is usually wrong: `lint` and `test` have no data dependency, so
serializing them doubles wall-clock for no benefit. Order by *actual*
dependency, not by narrative order.

```yaml
jobs:
  lint:   { ... }                 # parallel
  test:   { ... }                 # parallel
  build:  { needs: [lint, test] } # genuinely needs both to pass
  deploy: { needs: [build] }
```

### Job outputs

Jobs are separate runners with separate filesystems. The only structured
channel between them is `outputs:`, which is fed by a step's
`GITHUB_OUTPUT` file:

```yaml
jobs:
  version:
    runs-on: ubuntu-24.04
    timeout-minutes: 5
    outputs:
      tag: ${{ steps.compute.outputs.tag }}
    steps:
      - id: compute
        run: echo "tag=v$(date +%Y.%m.%d)" >> "$GITHUB_OUTPUT"

  publish:
    needs: [version]
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - env:
          TAG: ${{ needs.version.outputs.tag }}
        run: echo "publishing $TAG"
```

Three constraints worth knowing before designing around outputs:

- Job outputs are **strings**. A JSON blob round-trips through
  `fromJSON()` but there is no type checking; actionlint will catch
  some misuse.
- Outputs from a **matrix** job are overwritten by each matrix leg in
  nondeterministic order — you get one leg's value, not all of them.
  Use artifacts for per-leg results.
- Job outputs containing secrets are **not** redacted the way step
  output is. Do not pass secrets through `outputs:`.

### Conditions and result semantics

`if:` on a job or step is an expression evaluated without `${{ }}` (the
braces are permitted but redundant). The status functions matter more
than they look:

| Function | True when | Note |
|---|---|---|
| `success()` | all previous steps/needs succeeded | the **implicit default** on every step |
| `failure()` | a previous step/need failed | does not fire if the run was cancelled |
| `cancelled()` | the run was cancelled | pair with `failure()` for cleanup |
| `always()` | unconditionally | **also runs on cancellation** — can make a run unkillable |

Because `success()` is implicit, `if: needs.build.result == 'failure'`
alone never fires — the condition is ANDed with the implicit
`success()`, which is already false. Write
`if: always() && needs.build.result == 'failure'`, or use `failure()`.

Prefer `!cancelled()` over `always()` for cleanup steps unless the
cleanup genuinely must survive a cancel; `always()` on a long step means
pressing "Cancel workflow" does nothing for its duration.

### `continue-on-error`

`continue-on-error: true` on a step marks the step's failure as
non-fatal *and reports the job as successful*. That is almost never what
people want — it is routinely used to mean "record the failure but keep
going", and instead it deletes the signal. The two legitimate uses:

- A step whose `outcome` is then explicitly inspected
  (`steps.<id>.outcome` retains `failure` while `conclusion` becomes
  `success`).
- A matrix leg marked experimental via
  `continue-on-error: ${{ matrix.experimental }}`, where the job's
  failure genuinely should not gate the merge.

Anything else is a suppressed error; see
[`smells.md`](smells.md#correctness-smells).

## Concurrency and timeouts

### Concurrency

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

`cancel-in-progress` defaults to `false`. Only one run per group
proceeds; the rest queue (`queue: single`, the default, keeps at most
one pending and discards older pending runs; `queue: max` allows up to
100 pending and cannot be combined with `cancel-in-progress: true`).

Two group designs, and picking the wrong one is a real outage:

- **CI on pull requests** — group per ref, cancel in progress. A force
  push should kill the stale run. Including `github.ref` (not
  `github.sha`) is what makes supersession work.
- **Deployments** — group per *environment*, do **not** cancel.
  Cancelling a run that is halfway through a `terraform apply` or a
  rolling restart leaves the environment in a state nothing recorded.
  Serialize instead.

A common refinement is to keep `main` runs uncancellable while
cancelling PR runs:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}
```

Job-level `concurrency:` also exists and is the right place for a
"one deploy at a time, but the rest of the workflow can run in
parallel" shape.

Source:
<https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax>.

### Timeouts

`timeout-minutes` exists at both job and step level. The job default is
**360 minutes**; the platform hard caps are 6 hours per job on
GitHub-hosted runners, 5 days on self-hosted, and 35 days per workflow
run.

Set it on every job. The value is a statement about expected runtime,
so pick roughly 2–3× the observed p95 and treat a timeout as a real
alert rather than a flake to re-run. Step-level timeouts are worth
adding to any step that talks to a third party — a hanging `curl` to a
status API should not consume the whole job budget.

There is no retry primitive in the workflow syntax. `nick-fields/retry`
and similar actions exist; prefer fixing the flake, and when you can't,
bound the retry explicitly rather than re-running the whole workflow by
hand.

## Matrix

```yaml
strategy:
  fail-fast: false
  max-parallel: 4
  matrix:
    os: [ubuntu-24.04, macos-15]
    python-version: ["3.12", "3.13", "3.14"]
    include:
      - os: ubuntu-24.04
        python-version: "3.14"
        coverage: true
    exclude:
      - os: macos-15
        python-version: "3.12"
```

- **`fail-fast` defaults to `true`**, cancelling every sibling leg the
  moment one fails. For a *compatibility* matrix that is exactly wrong:
  you learn that 3.12 broke and nothing about 3.13 or 3.14, so the next
  push repeats the discovery. Set `fail-fast: false` on compatibility
  matrices; leave it `true` on sharded matrices where all legs run the
  same code and one failure means the whole thing is broken.
- **`include` both extends and augments.** An `include` entry whose keys
  all match an existing combination *adds* keys to that leg; one that
  introduces a new value *adds a leg*. This dual behaviour surprises
  people — check the expanded matrix in the run summary rather than
  reasoning about it.
- **`max-parallel`** throttles concurrent legs. Use it when the matrix
  contends on a shared external resource (a rate-limited API, a single
  test database), not as a general cost control.
- **256 jobs per workflow run** is the platform ceiling. A three-axis
  matrix reaches it faster than expected.
- **Quote version numbers.** `python-version: [3.10]` is the float
  `3.1` after YAML parsing. `"3.10"` is the string you meant. This
  breaks silently, running the wrong interpreter.
- **macOS runners are billed at 10× Linux** (Windows at 2×). A
  three-OS matrix is a real budget decision, not a free thoroughness
  win — most repositories want Linux on every PR and the full OS matrix
  nightly or pre-release.

## Shell discipline

### Which shell actually runs

| `shell:` value | Command the runner executes |
|---|---|
| *(omitted, Linux/macOS)* | `bash -e {0}` (falls back to `sh -e {0}`) |
| `bash` | `bash --noprofile --norc -eo pipefail {0}` |
| `sh` | `sh -e {0}` |
| `pwsh` | `pwsh -command ". '{0}'"` |
| `python` | `python {0}` |

The gap between row one and row two is `pipefail`, and it is a
correctness bug, not a style preference:

```yaml
# Green build even when pytest fails: `tee` exits 0.
- run: pytest | tee test.log

# Correct: `shell: bash` adds -o pipefail.
- run: pytest | tee test.log
  shell: bash
```

Set `defaults.run.shell: bash` once at workflow level and stop thinking
about it. Note that `-u` (error on unset variable) is in *neither*
default, so a typo'd `$VERISON` expands to empty and the script runs on.
For any `run:` block longer than a couple of lines, open with
`set -euo pipefail` explicitly — it is self-documenting, and it survives
being copied into a composite action where the `defaults` block does not
apply.

Source:
<https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idstepsshell>.

### Writing the block

- `working-directory:` beats `cd foo && ...`, and applies to the whole
  block.
- Multi-line `run:` blocks are one script with one exit status. Steps
  are the unit of reporting — splitting a 40-line block into four named
  steps turns "job failed" into "the migration step failed" in the UI at
  zero cost.
- Quote every expansion: `"$VAR"`, not `$VAR`. Runner paths contain
  spaces on Windows and macOS, and unquoted expansion of untrusted
  content is how injection becomes execution even after you moved the
  value into `env:`.
- Anything longer than ~30 lines belongs in a checked-in script under
  `scripts/` that a human can run locally. A workflow that can only be
  tested by pushing is a workflow nobody tests.

## Expressions and contexts

### Where `${{ }}` is evaluated

Expressions are interpolated by the runner **before** the step executes,
producing a literal in the generated script. This is the mechanism
behind script injection ([`security.md`](security.md#script-injection))
and it also explains two everyday behaviours:

- `${{ env.FOO }}` reflects `env:` blocks, not values written to
  `$GITHUB_ENV` **in the same step** — environment-file writes apply to
  *subsequent* steps only.
- `${{ secrets.X }}` in an `if:` works, but the result is visible
  through the evaluated condition. Gate on a non-secret flag instead.

### Contexts worth knowing

| Context | Holds | Gotcha |
|---|---|---|
| `github` | event payload, ref, sha, actor | much of `github.event` is attacker-controlled |
| `env` | workflow/job/step `env:` | not `$GITHUB_ENV` writes from the current step |
| `vars` | repository/org/environment **variables** | non-secret config; not redacted |
| `secrets` | repository/org/environment secrets | masked in logs, not in outputs |
| `needs` | upstream job outputs and `result` | strings only |
| `steps` | `outputs`, `outcome`, `conclusion` of prior steps | `outcome` is pre-`continue-on-error` |
| `matrix` | current leg's values | undefined outside a matrix job |
| `runner` | `os`, `arch`, `temp`, `tool_cache` | `runner.temp` beats hardcoded `/tmp` |
| `inputs` | `workflow_dispatch`/`workflow_call`/composite inputs | three different sources, one name |

Context availability is narrower than it looks, and the runner reports
the mistake as an unhelpful parse error rather than "not available
here". The ones that catch people:

- **Job-level `if:` sees only `github`, `needs`, `vars`, `inputs`.** Not
  `env`, not `secrets`, not `steps`. `if: env.DEPLOY == 'true'` on a job
  silently never matches; the same expression on a *step* works.
- **`runs-on` sees `github`, `needs`, `strategy`, `matrix`, `vars`,
  `inputs`** — so a runner label can come from a matrix or a variable,
  but not from an `env:` block.
- **`secrets` is unavailable in composite actions entirely**
  ([`reuse.md`](reuse.md#composite-actions)) and in `runs-on`; pass
  secrets as inputs or through step-level `env:`.

`vars` vs `env` vs hardcoded: put a value in `vars` when it differs per
repository or environment, in workflow-level `env:` when it is the same
everywhere but referenced more than once, and inline when it appears
once. A `vars.NODE_VERSION` that has been `22` in every environment for
a year is indirection with no payoff.

### Environment files

The `::set-output` and `::save-state` workflow commands are deprecated,
and `::set-env`/`::add-path` were **removed** in November 2020 after
CVE-2020-15228: any process that printed the magic string to stdout —
an npm postinstall script, a compiler warning — could set environment
variables for later steps, including `LD_PRELOAD`. The file-based
replacements are the only supported mechanism:

```yaml
- run: |
    echo "version=1.2.3" >> "$GITHUB_OUTPUT"        # step outputs
    echo "CACHE_HIT=true" >> "$GITHUB_ENV"          # env for later steps
    echo "$PWD/bin" >> "$GITHUB_PATH"               # PATH for later steps
    echo "### Results" >> "$GITHUB_STEP_SUMMARY"    # markdown in the UI
```

Multi-line values need heredoc delimiter syntax, and the delimiter must
be unguessable when the content is untrusted — a value containing your
delimiter can forge additional variables
([`security.md`](security.md#github_env-injection)):

```yaml
- run: |
    {
      echo "NOTES<<EOF_$(uuidgen)"
      cat release-notes.md
      echo "EOF_$(uuidgen)"
    } >> "$GITHUB_ENV"
```

`$GITHUB_STEP_SUMMARY` is underused: a summary table of test failures,
coverage delta, or the plan diff turns "read 4,000 lines of log" into
one glance at the run page. It accepts GitHub-flavored Markdown, 1 MiB
per step.

`::add-mask::VALUE` registers a value for redaction — use it for
anything sensitive that was *derived* on the runner (a decoded token, a
generated JWT) rather than read from `secrets`, which is masked
automatically.

Sources:
<https://github.blog/changelog/2020-10-01-github-actions-deprecating-set-env-and-add-path-commands/>,
<https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands>.

## Caching

### Key design

```yaml
- uses: actions/cache@REPLACE_WITH_PINNED_SHA # v4.2.3
  with:
    path: ~/.cache/uv
    key: uv-${{ runner.os }}-${{ hashFiles('uv.lock') }}
    restore-keys: |
      uv-${{ runner.os }}-
```

- **`key` must change when the cached content should change.** Hash the
  lockfile, not the manifest: `pyproject.toml` can change without any
  dependency moving, and `uv.lock` cannot change without one moving.
- **Include `runner.os`** (and the language version, when the cache is
  version-specific) or a macOS leg will restore a Linux cache and fail
  in a way that looks like a dependency bug.
- **`restore-keys` is a prefix fallback**, most-recent-match-first. It
  is what makes a partial cache useful: one new dependency installs
  instead of all of them. A cache with no `restore-keys` is
  all-or-nothing and misses on every lockfile change.
- **Caches are immutable once written.** You cannot update an entry
  under an existing key — a stale cache is fixed by changing the key
  (bump an explicit `v2-` prefix) or deleting it via the API.

### Use the setup action's cache first

`actions/setup-node`, `setup-python`, `setup-java`, `setup-go`, and
`astral-sh/setup-uv` all implement dependency caching with correct keys
built in (`cache: 'npm'`, `enable-cache: true`, …). Hand-rolling
`actions/cache` for a package manager those actions already support is
extra surface for no benefit.

### What not to cache

- **Build outputs that a release consumes.** See
  [`security.md`](security.md#cache-and-artifact-poisoning): caches are
  repository-scoped, writable from PR-triggered runs, and readable from
  the default branch.
- **Anything cheaper to fetch than to restore.** Cache restore is a
  network download plus decompression; a 2 GB cache that saves a
  90-second install is a loss.
- **`node_modules` itself**, generally — cache the package manager's
  store (`~/.npm`, `~/.cache/pnpm`) and let the install step link. A
  restored `node_modules` carries platform-specific binaries and skips
  the integrity check.

### Limits

10 GB per repository, with entries beyond that evicted immediately
(policy tightened November 2025) and any entry untouched for 7 days
evicted. A repository that caches a 3 GB Docker layer set per branch is
continuously evicting its own hot caches and wondering why hit rates
collapsed.

Source:
<https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching>.

## Artifacts

Artifacts move files **between jobs and out of the run**; caches
optimize *within* repeated runs. Using one for the other's job is a
common confusion — a cache is not a delivery mechanism (it can be
evicted, and it is keyed, not named), and an artifact is not a cache (it
costs storage and has retention).

v4+ semantics that break v3 habits:

- **Artifacts are immutable.** You cannot upload twice to the same name.
  In a matrix this fails on the second leg, so name per-leg:
  `name: coverage-${{ matrix.os }}-${{ matrix.python-version }}`.
  `overwrite: true` restores v3 behaviour and reintroduces the
  corruption risk v4 exists to prevent.
- **`actions/download-artifact` with no `name:`** downloads *all*
  artifacts, each into its own subdirectory — use `pattern:` and
  `merge-multiple: true` to fan matrix results back into one tree.
- **Artifacts on public repositories are downloadable by anyone.**
  Combined with `persist-credentials: true` on checkout, uploading the
  workspace publishes the run's token. Never upload `.git/`.
- **`retention-days`** defaults to the repository setting (90 days
  max, 400 for enterprise). CI artifacts nobody reads after the PR
  merges should be 1–7 days; storage is billed.

## Runners

`runs-on` accepts a label, a list of labels (AND semantics for
self-hosted), or a `group:`/`labels:` object.

- **Pin the OS version, don't use `-latest`.** `ubuntu-latest` moves
  between major versions on GitHub's schedule, which means your CI
  changes underneath you on a day you didn't choose. `ubuntu-24.04` is
  a decision; `ubuntu-latest` is a deferred incident. (Counter-position:
  `-latest` surfaces migration breakage early, on your CI rather than in
  production. That is a real argument for a repository whose CI failing
  is cheap — it is a bad one for a release pipeline. Pick per workflow.)
- **Billing multipliers**: Linux 1×, Windows 2×, macOS 10×. Larger
  runners bill per-minute at their own rate and have no free tier.
- **Larger runners** are the right answer to a job that is genuinely
  CPU- or memory-bound; they are the wrong answer to a job that is slow
  because it has no cache.
- **Self-hosted runners** are a security decision before a cost one —
  see [`security.md`](security.md#self-hosted-runners). Never on public
  repositories.

## Platform limits

Worth knowing before designing around them:

| Limit | Value |
|---|---|
| Job execution (GitHub-hosted) | 6 hours |
| Job execution (self-hosted) | 5 days |
| Workflow run total | 35 days |
| Default `timeout-minutes` | 360 |
| Matrix jobs per run | 256 |
| Workflow file size | 500 KB |
| Cache storage per repository | 10 GB |
| `GITHUB_TOKEN` API rate | 1,000 req/hour/repository |
| Concurrent jobs (Free / Enterprise) | 20 / 500 |
| macOS concurrency (Free / Enterprise) | 5 / 50 |
| Re-runs per workflow run | 50 |
| Queued runs per concurrency group (`queue: max`) | 100 |
| Environment approval wait | 30 days |

Source: <https://docs.github.com/en/actions/reference/limits>.
