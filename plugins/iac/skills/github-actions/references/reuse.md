# Reuse & Authoring Actions

Four mechanisms share work between workflows, and picking the wrong one
is the most common structural mistake after copy-paste itself. This file
covers the choice, the mechanics of each, and how to version and publish
what you build. Security rules for consuming third-party actions live in
[`security.md`](security.md#supply-chain).

1. [`## Choosing a mechanism`](#choosing-a-mechanism)
2. [`## Reusable workflows`](#reusable-workflows)
3. [`## Composite actions`](#composite-actions)
4. [`## JavaScript and Docker actions`](#javascript-and-docker-actions)
5. [`## action.yml reference`](#actionyml-reference)
6. [`## Versioning and publishing`](#versioning-and-publishing)
7. [`## Testing an action`](#testing-an-action)
8. [`## Anti-patterns`](#anti-patterns)

## Choosing a mechanism

| | Reusable workflow | Composite action | JavaScript action | Docker action |
|---|---|---|---|---|
| Unit of reuse | one or more **jobs** | a sequence of **steps** | one step | one step |
| Called from | `jobs.<id>.uses` | `steps[].uses` | `steps[].uses` | `steps[].uses` |
| Can use `secrets` context | **yes** | **no** (pass as inputs) | via inputs/env | via inputs/env |
| Can choose `runs-on` | **yes** | no (caller's runner) | no | Linux only |
| Can gate on `environment` | **yes** | no | no | no |
| Can run steps before/after in the same job | no | **yes** | **yes** | **yes** |
| Inherits caller's job `env` | **no** | **yes** | yes | yes |
| Marketplace publishable | no | **yes** | **yes** | **yes** |
| Startup cost | new job (runner spin-up) | none | none | image build/pull |

The decision reduces to two questions:

- **Does the reused thing need its own runner, its own secrets, or an
  environment gate?** → reusable workflow. Standardizing "how this
  organization builds, tests, scans, and deploys" across repositories is
  the canonical case.
- **Is it a sequence of steps that belongs inside somebody else's
  job?** → composite action. "Set up our toolchain," "authenticate and
  configure the CLI," "upload coverage the way we do it" are the
  canonical cases.

A job that calls a reusable workflow can contain **nothing else** — no
steps before or after. If you need a step either side, you needed a
composite action.

## Reusable workflows

### Callee

```yaml
# .github/workflows/reusable-build.yml
name: reusable-build

on:
  workflow_call:
    inputs:
      python-version:
        description: "Interpreter version to build against"
        type: string        # string | number | boolean
        required: false
        default: "3.14"
      runner:
        description: "Runner label"
        type: string
        default: ubuntu-24.04
    secrets:
      REGISTRY_TOKEN:
        description: "Token for the internal package registry"
        required: true
    outputs:
      artifact-name:
        description: "Name of the uploaded build artifact"
        value: ${{ jobs.build.outputs.artifact-name }}

permissions:
  contents: read

jobs:
  build:
    runs-on: ${{ inputs.runner }}
    timeout-minutes: 20
    outputs:
      artifact-name: ${{ steps.pack.outputs.name }}
    steps:
      - uses: actions/checkout@REPLACE_WITH_PINNED_SHA # v5.0.0
        with: { persist-credentials: false }
      - id: pack
        env:
          TOKEN: ${{ secrets.REGISTRY_TOKEN }}
        run: |
          set -euo pipefail
          ./scripts/build.sh
          echo "name=dist-${{ inputs.python-version }}" >> "$GITHUB_OUTPUT"
```

### Caller

```yaml
jobs:
  build:
    uses: my-org/ci-workflows/.github/workflows/reusable-build.yml@REPLACE_WITH_PINNED_SHA # v2.1.0
    permissions:
      contents: read
    with:
      python-version: "3.14"
    secrets:
      REGISTRY_TOKEN: ${{ secrets.REGISTRY_TOKEN }}

  publish:
    needs: [build]
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - run: echo "built ${{ needs.build.outputs.artifact-name }}"
```

### Constraints that bite

- **The calling job may only use**: `name`, `uses`, `with`, `secrets`,
  `needs`, `if`, `permissions`, `strategy`, `concurrency`, `cache-mode`.
  Not `steps`,
  not `runs-on`, not `env`, not `timeout-minutes`, not
  `continue-on-error`. Anything the called workflow needs to know
  becomes an input.
- **`env` does not cross the boundary — in either direction.** Neither
  workflow-level nor job-level `env` from the caller reaches the called
  workflow, and the called workflow's `env` is invisible to the caller.
  This is the most common "it works when inlined but not when extracted"
  bug. Pass inputs; return outputs.
- **Permissions only narrow.** The called workflow's `GITHUB_TOKEN`
  permissions can be downgraded but never elevated relative to the
  caller. Grant at the calling job and expect the chain to shrink.
- **Secrets pass only one hop.** In A → B → C, C receives nothing from A
  unless B explicitly re-passes it. `secrets: inherit` does propagate
  down the chain, which is exactly why it is a finding
  ([`security.md`](security.md#secrets)).
- **Outputs must be plumbed twice**: step → job `outputs:` → workflow
  `on.workflow_call.outputs.<id>.value`. Forgetting the second hop
  yields an empty string with no error.
- **A called workflow's outputs are empty when its job was skipped.**
  Guard the consumer.
- **Pin the ref like any other dependency.** `@main` on a reusable
  workflow from another repository is the same mutable-reference problem
  as `@v1` on an action — and it carries more privilege, since it runs
  as its own job. Within the *same* repository, `./.github/workflows/x.yml`
  (no ref) is correct and always resolves to the current commit.
- **Limits**: 10 levels of nesting and 50 unique reusable workflows per
  workflow file on github.com (4 and 20 on GitHub Enterprise Server).

Source:
<https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations>.

## Composite actions

### Shape

```yaml
# .github/actions/setup-toolchain/action.yml
name: Set up toolchain
description: Install uv, sync the locked environment, and export the venv.

inputs:
  python-version:
    description: Interpreter version
    required: false
    default: "3.14"
  registry-token:
    description: Token for the private index (pass a secret here)
    required: false
    default: ""

outputs:
  venv-path:
    description: Absolute path to the created virtualenv
    value: ${{ steps.sync.outputs.venv }}

runs:
  using: composite
  steps:
    - uses: astral-sh/setup-uv@REPLACE_WITH_PINNED_SHA # v7.1.0
      with:
        enable-cache: true
        cache-dependency-glob: uv.lock

    - id: sync
      shell: bash                      # MANDATORY on every run step
      env:
        UV_INDEX_TOKEN: ${{ inputs.registry-token }}
        PYTHON_VERSION: ${{ inputs.python-version }}
      run: |
        set -euo pipefail
        uv python install "$PYTHON_VERSION"
        uv sync --locked
        echo "venv=$PWD/.venv" >> "$GITHUB_OUTPUT"
```

### Rules

- **`shell:` is required on every `run:` step.** There is no
  `defaults.run` inside a composite action, and the workflow's
  `defaults` block does not apply. Write `shell: bash` every time — this
  is also why `set -euo pipefail` at the top of the block is worth the
  two seconds even when `shell: bash` already gives you `-eo pipefail`.
- **No `secrets` context.** GitHub excludes it from composite actions
  deliberately. Secrets arrive as inputs, which means they appear in the
  caller's workflow file as `${{ secrets.X }}` — and are masked in logs
  as usual.
- **Inputs come from the `inputs` context**, not `INPUT_*` environment
  variables (that form is for JavaScript and Docker actions).
- **Outputs need an explicit `value:`** mapping to a step output —
  unlike JavaScript actions, where writing `$GITHUB_OUTPUT` is enough.
- **`${{ github.action_path }}`** is where the action's own files live;
  the working directory is still the caller's workspace. A composite
  action that ships a script runs it as
  `"${{ github.action_path }}/scripts/do.sh"`.
- **Steps within the composite are invisible in the caller's job graph**
  — the whole action reports as one step. Long composites are hard to
  debug for exactly this reason; keep them focused.
- **Local references use `./path` with no `@ref`** and require the
  caller to have run `actions/checkout` first. This trips people up:
  `uses: ./.github/actions/setup-toolchain` before a checkout step fails
  with "Can't find action.yml".
- **Composite actions are inside your injection blast radius.** An
  action that interpolates `${{ inputs.x }}` into a `run:` block is
  injectable by whatever the caller passes — including
  `github.event.*`. Bind inputs to `env:` inside the action too.

Sources:
<https://docs.github.com/en/actions/reference/workflows-and-actions/metadata-syntax>,
<https://docs.github.com/en/actions/reference/workflows-and-actions/contexts>.

## JavaScript and Docker actions

### JavaScript

Reach for one when the logic needs real control flow, API calls with
pagination and retry, or cross-platform behaviour that shell cannot
express cleanly. `runs.using` is `node20` or `node24`.

```yaml
runs:
  using: node24
  pre: dist/setup.js       # runs before the job's other steps
  main: dist/index.js
  post: dist/cleanup.js    # runs at job end; defaults to always()
  post-if: success()
```

- **The committed `dist/` bundle is what runs**, not `src/`. Bundle with
  `@vercel/ncc` (or esbuild) and commit the output; a CI check that
  rebuilds and fails on a dirty tree is standard, because a stale
  `dist/` means the action silently runs old code. Reviewers of *your*
  action read `dist/`, so keep it generated and unminified enough to
  audit.
- **`post:` is the cleanup hook** — revoking a token, removing a
  credential file, stopping a service. It runs even when the job fails,
  which is what makes it the right place for teardown.
- Use `@actions/core` for inputs, outputs, masking (`core.setSecret`),
  and failure (`core.setFailed` — do not `process.exit(1)`, which skips
  output flushing).

### Docker

`runs.using: docker` with `image:` pointing at a `Dockerfile` or a
registry reference. Linux runners only, and the per-step cost is an
image build or pull — often 30–60 seconds. Justified when the action
needs a system toolchain that cannot be installed quickly; otherwise a
composite action invoking a container is more transparent. Pin the image
by digest and apply the `docker` skill's rules to the Dockerfile.

## action.yml reference

The file must be named `action.yml` or `action.yaml` (`.yml`
preferred), and renaming it between releases breaks Marketplace
listings.

```yaml
name: My Action              # required
author: My Org               # optional
description: One sentence.   # required — shown in the Marketplace

inputs:
  some-input:
    description: Required.
    required: false
    default: "1"
    deprecationMessage: Use `other-input` instead.

outputs:
  result:
    description: Required.
    value: ${{ steps.x.outputs.y }}   # composite only

runs:
  using: composite | node20 | node24 | docker
  # ...shape depends on `using`

branding:
  icon: award                # Feather v4.28.0 icon name
  color: green               # white|black|yellow|blue|green|orange|red|purple|gray-dark
```

- Input ids start with a letter or underscore and contain only
  alphanumerics, `-`, and `_`. For JavaScript and Docker actions they
  surface as `INPUT_<UPPERCASED_NAME>` with spaces replaced by
  underscores.
- `required: true` is **not enforced by the runner** for most action
  types — it is documentation plus a Marketplace hint. Validate inputs
  in the action body and fail loudly.
- `default:` values are strings. `default: true` becomes `"true"`;
  compare against the string.
- Outputs are capped at 1 MB per job and 50 MB per workflow.

Source:
<https://docs.github.com/en/actions/reference/workflows-and-actions/metadata-syntax>.

## Versioning and publishing

### The convention consumers expect

Publish immutable `vX.Y.Z` tags **and** maintain a moving `vX` major
tag that points at the newest compatible release. Consumers who pin
SHAs (which is what this rulebook tells them to do) still need the major
tag for Dependabot to resolve version comments.

```bash
git tag -a v1.4.2 -m "v1.4.2"
git tag -fa v1 -m "Update v1 to v1.4.2"
git push origin v1.4.2
git push origin v1 --force
```

Note what this makes true: **you are asking consumers to trust a
force-pushed tag.** That is precisely the mutability the `tj-actions`
compromise exploited. Two ways to close it:

- **Publish as an immutable action** — `actions/publish-immutable-action`
  packages the action as an OCI artifact in GitHub Packages, where tags
  cannot be overwritten. Consumers referencing a SemVer tag then get
  registry-enforced immutability, equivalent to a SHA pin. This is the
  right default for a new shared action.
- **Protect the tags** with rulesets and require a review on the release
  workflow, so moving `v1` is at least an audited act.

Other release discipline:

- **Breaking change → new major tag**, always. Silently changing `v1`
  behaviour breaks every consumer at once, with no changelog in their
  diff.
- **`deprecationMessage` on inputs** before removing them; it surfaces
  as a warning annotation in consumers' runs, which is the only
  deprecation channel that actually reaches them.
- **Release notes that name the behavioural change**, not just the
  commit range — consumers pinned to a SHA read your notes to decide
  whether to bump.
- **Security advisories** through the repository's advisory workflow
  when you ship a fix. The Dependants graph shows who needs to hear it.

Sources:
<https://docs.github.com/en/actions/how-tos/create-and-publish-actions/release-and-maintain-actions>,
<https://github.com/actions/publish-immutable-action>.

## Testing an action

An action nobody tested is a workflow bug distributed to every consumer.
The workable shape:

```yaml
# .github/workflows/test-action.yml
name: test-action
on: [pull_request, push]
permissions:
  contents: read
jobs:
  self-test:
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-24.04, macos-15, windows-2022]
    runs-on: ${{ matrix.os }}
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@REPLACE_WITH_PINNED_SHA # v5.0.0
        with: { persist-credentials: false }
      # Exercise the action from its own repository.
      - id: subject
        uses: ./
        with:
          some-input: "test-value"
      - name: Assert outputs
        shell: bash
        env:
          RESULT: ${{ steps.subject.outputs.result }}
        run: |
          set -euo pipefail
          [[ "$RESULT" == "expected" ]] || { echo "got: $RESULT"; exit 1; }
```

- **Matrix the OSes you claim to support.** A composite action using
  `shell: bash` works on Windows runners (Git Bash) but paths and
  line endings do not; claiming Windows support without a Windows leg
  is how the first bug report arrives.
- **Assert outputs explicitly** rather than asserting the action didn't
  fail. An action that silently produces an empty output passes a
  "did it exit 0" test.
- **Test the failure paths**: a missing required input, an
  unreachable service. Pair `continue-on-error: true` with an
  assertion on `steps.<id>.outcome == 'failure'`.
- **Local runs** via `nektos/act` are useful for the fast loop but do
  not reproduce the runner image, the token, or the context faithfully.
  Treat it as a smoke test, never as the gate.
- For JavaScript actions, unit-test the logic with the runtime's own
  test framework and keep the workflow test for integration.

## Anti-patterns

- **Copy-pasted job across five workflows.** The fourth copy is where
  they diverge and nobody notices. Extract once the same block appears
  twice with intent to appear a third time.
- **Reusable workflow with fifteen boolean inputs.** Each flag is a
  branch in a file nobody can test, and the combinations are untested by
  construction. Split into two workflows, or accept the duplication —
  a parameterized mess is worse than two honest files.
- **Composite action that wraps exactly one `uses:`.** Pure indirection:
  the caller now reads two files to learn what runs, and Dependabot has
  to traverse an extra hop. Inline it.
- **`uses: ./.github/actions/x` before `actions/checkout`.** Local
  actions are files in the workspace; there is no workspace yet.
- **Organization-wide reusable workflow on `@main`.** Every consumer is
  now continuously deployed from your default branch, including the
  commit you push at 18:00 on a Friday.
- **Reusable workflow that reads `env` from the caller.** It does not
  work, and the failure is an empty string rather than an error.
- **Action inputs typed as free-text strings where a closed set exists.**
  `workflow_dispatch` supports `type: choice` with `options:`; use it.
  A deploy triggered with `enviroment: prodcution` should not be
  possible.
