# CI & Release

House rules for building, tagging, and shipping the images this skill's
Dockerfiles and compose files describe. Scope is the GitHub Actions +
`docker/build-push-action` shape, because that is the 2026 default for
GitHub-hosted OSS and most shops; the underlying mechanics (cache
backends, `buildx imagetools create`, OCI annotations, tag immutability,
registry lifecycle rules) are provider-agnostic and port to GitLab CI,
Buildkite, or CircleCI with the same flags on a different YAML skeleton.
Pin your Buildx floor deliberately per the version notes below and raise
it on a schedule, not by surprise when a workflow starts failing.

This file does not repeat the runtime-hardening or supply-chain-security
gate configuration — those live in
[`hardening-and-supply-chain.md`](hardening-and-supply-chain.md), and the
[`## Pipeline`](#pipeline) section below cross-references it rather than
re-deriving hadolint and Trivy rule sets here. This file owns the shape
around those gates: cache strategy, multi-arch fan-out, image metadata,
tag/version policy, and registry cleanup — the parts of "get an image
from a Dockerfile to a registry, correctly, every push" that are CI
plumbing rather than security gates.

Five decisions this file answers, in the order a new pipeline usually
needs them:

1. How do repeated builds avoid re-doing identical work? →
   [`## Build cache`](#build-cache)
2. How does one pipeline produce images for more than one CPU
   architecture? → [`## Multi-arch`](#multi-arch)
3. How does an image describe itself — where it came from, what commit,
   what version? → [`## Labels`](#labels)
4. What string identifies a specific build, and which of those strings
   are allowed to move? → [`## Tag strategy`](#tag-strategy)
5. What stops the registry from filling up with orphaned SHA tags
   forever? → [`## Registry hygiene`](#registry-hygiene)

The [`## Pipeline`](#pipeline) section closes the file by putting all
five, plus the security gates owned elsewhere, into one ordered list.

## Build cache

BuildKit supports several cache export/import backends
(`type=inline`, `type=local`, `type=registry`, `type=gha`, `type=s3`,
…); in a GitHub Actions pipeline the GitHub Actions cache backend
(`type=gha`) is the default choice because it needs no extra
infrastructure — no S3 bucket, no separate registry namespace — and is
scoped to the repository automatically. `docker/build-push-action` wires
BuildKit's `--cache-from`/`--cache-to` flags through two action inputs of
the same name:

- **`cache-from: type=gha`** — read prior layers from the GitHub Actions
  cache before building.
- **`cache-to: type=gha,mode=max`** — write layers back to the GitHub
  Actions cache after building.

The `mode=max` qualifier is not cosmetic. BuildKit's default cache mode
(`mode=min`) exports layers for the final image only; in a multi-stage
Dockerfile — which every Dockerfile authored under this skill is, per
the `dockerfile.md` posture rule — that means every intermediate stage
(the `builder` stage doing `uv sync`, the `build` stage doing
`npm run build`) gets no cache at all and re-executes from scratch on
every run regardless of whether its inputs changed. `mode=max` exports
cache for every stage in the build graph, so a source-only edit that
doesn't touch `uv.lock` or `package-lock.json` still gets a cache hit on
the dependency-install layer even though that layer lives in a stage
that never reaches the final image. Skipping `mode=max` is the single
most common reason a team ships a "cached" pipeline that still takes
full-install minutes on every run.

Source:
<https://docs.docker.com/build/ci/github-actions/cache/>.

### Buildx floor

`type=gha` cache depends on GitHub's Cache API, and GitHub replaced
Cache API v1 with Cache API v2 — v1 became unusable, not merely
deprecated, as of **2025-04-15**. Buildx picked up v2 support in
**0.21**; a runner pinning an older Buildx (via an old
`docker/setup-buildx-action` version, or a self-hosted runner with a
stale Buildx binary) will fail to read or write `type=gha` cache against
the current API, and the failure mode is a silent cache miss on every
run rather than an obvious error — the build still succeeds, it's just
never actually cached. Treat "workflow suddenly runs full-length on
every push" as a Buildx-floor question before assuming the cache backend
itself changed behavior. Pin `docker/setup-buildx-action` to a version
that ships Buildx ≥0.21 and let Renovate/Dependabot keep it current
alongside the other pinned actions in the workflow.

Source (same page as above):
<https://docs.docker.com/build/ci/github-actions/cache/>.

### Registry fallback

The GitHub Actions cache service applies a per-repository storage quota
with least-recently-used eviction. A pipeline that fans out across many
architectures and stages (see [`## Multi-arch`](#multi-arch) below) can
push enough cache entries to start evicting mid-workflow, which shows up
as inconsistent cache-hit rates that vary run to run for no code reason.
The documented fallback is the registry cache backend:

```yaml
cache-from: type=registry,ref=ghcr.io/OWNER/REPO:buildcache
cache-to: type=registry,ref=ghcr.io/OWNER/REPO:buildcache,mode=max
```

`type=registry` stores cache blobs as an image manifest in the same
registry the build already pushes to, so it isn't bound by the GitHub
Actions cache quota — it inherits whatever retention the registry
itself applies (see [`## Registry hygiene`](#registry-hygiene) for
keeping a `buildcache` tag out of the same expiry rule that reclaims
untagged SHA images). Reach for the registry backend only once `gha`
cache limits are the actual observed bottleneck; it needs a registry
write credential in a build job that otherwise might only need push
access at the end, which is its own scope-widening cost.

Source: <https://docs.docker.com/build/ci/github-actions/cache/>.

### Workflow sketch

A minimal build-cache-correct job. Multi-arch fan-out, OCI labels, and
tag rules are layered on in the sections below — this sketch isolates
just the cache wiring.

```yaml
jobs:
  build:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3   # ships Buildx >=0.21
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: ghcr.io/OWNER/REPO:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

Sources for the actions pinned above:
<https://github.com/actions/checkout>,
<https://github.com/docker/setup-buildx-action>,
<https://github.com/docker/login-action>,
<https://github.com/docker/build-push-action>.

Action versions shown (`@v6`, `@v5`, …) are the current majors at
writing — adopt whatever is current and let Renovate/Dependabot track
them, as with the Buildx floor.

### Cache mistakes worth naming

| Mistake | Symptom | Fix |
| --- | --- | --- |
| `cache-to: type=gha` without `mode=max` | Intermediate build/deps stages never cache; only the final stage does | Always pair `cache-to` with `mode=max` for multi-stage Dockerfiles |
| Buildx <0.21 on a self-hosted or pinned-old runner | Cache silently never hits post-2025-04-15; build still "succeeds" | Bump `docker/setup-buildx-action`, verify with `docker buildx version` in a debug step |
| One shared `type=gha` scope across unrelated multi-arch jobs | Cache thrash between `amd64` and `arm64` cache entries competing for the same quota | Scope cache with `scope=` per matrix leg, or move to `type=registry` |
| Cache import but no `cache-to` at all | Every run reads a cache that's never refreshed — reads the same stale layers forever | Cache import and export must be paired in the same workflow |

### Cache backend comparison

`type=gha` and `type=registry` are the two backends this reference
covers, but BuildKit's cache export/import is pluggable, and knowing the
alternatives explains why `gha` is the default rather than the only
option:

| Backend | Storage | Needs | Best for |
| --- | --- | --- | --- |
| `type=gha` | GitHub Actions cache service | Buildx ≥0.21, no extra credentials | Default for GitHub-hosted CI |
| `type=registry` | A manifest pushed to the target (or a dedicated) registry | Registry write access | Self-hosted/non-GitHub runners, or once `gha` quota is the observed bottleneck |
| `type=local` | A directory on the runner's filesystem | A persistent cache directory across jobs (e.g. via `actions/cache`) | Self-hosted runners with durable local disk |
| `type=inline` | Baked into the pushed image's own layers | Nothing extra | Legacy/simple single-stage cases; cannot cleanly express `mode=max` for a multi-stage build, so `type=registry` supersedes it here |
| `type=s3` | An S3 bucket | AWS credentials, a bucket | Non-GitHub CI already running inside AWS |

`gha` and `registry` are the two that matter for the workflows in this
file — `local`, `inline`, and `s3` exist for CI topologies (self-hosted
runners, non-GitHub pipelines) this skill's GitHub Actions examples
don't target, but the same `cache-from`/`cache-to` shape applies to all
of them.

Confirm a cache is actually being hit rather than trusting the workflow
file: `docker buildx build --progress=plain` prints `CACHED` next to
each layer that resolved from cache, and `docker buildx du` reports
local build-cache disk usage on a runner. A pipeline that "has caching
configured" but shows no `CACHED` lines in its build log has a
misconfigured backend, scope, or Buildx floor — not a working cache.

Source: <https://docs.docker.com/build/ci/github-actions/cache/>.

### Porting this to non-GitHub CI

`docker/build-push-action`'s `cache-from`/`cache-to` inputs are a thin
wrapper over BuildKit's own `--cache-from`/`--cache-to` build flags —
the same flags apply verbatim to a bare `docker buildx build` command on
any CI system, not only inside a GitHub Actions step. `type=gha`
specifically only works where a GitHub Actions cache endpoint exists
(GitHub-hosted or GitHub-connected self-hosted runners), so a
GitLab CI, Buildkite, or CircleCI pipeline can't use that backend
directly — but `type=registry` from the [`### Registry fallback`
](#registry-fallback) section above needs nothing GitHub-specific at
all, and is the natural default cache backend once the pipeline moves
off GitHub Actions. The multi-arch native-runner matrix
([`## Multi-arch`](#multi-arch)) depends only on the CI system offering
both an amd64 and an arm64 runner pool — most managed CI providers do —
and the rest of this file (labels, tag strategy, registry hygiene,
gate order) has no GitHub Actions dependency at all; it's registry and
`buildx`/`docker` CLI behavior throughout.

Source: <https://docs.docker.com/build/ci/github-actions/cache/>.

## Multi-arch

The 2026 default for a multi-architecture image is a matrix of **native**
runners — one job per target architecture, each running BuildKit
natively on that architecture — rather than a single job cross-compiling
every target through QEMU emulation. GitHub's hosted runner fleet now
includes `ubuntu-24.04-arm` alongside `ubuntu-24.04`, so a two-leg matrix
covers `linux/amd64` and `linux/arm64` without any self-hosted arm
infrastructure:

```yaml
jobs:
  build:
    strategy:
      matrix:
        include:
          - runner: ubuntu-24.04
            platform: linux/amd64
          - runner: ubuntu-24.04-arm
            platform: linux/arm64
    runs-on: ${{ matrix.runner }}
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - id: build
        uses: docker/build-push-action@v6
        with:
          context: .
          platforms: ${{ matrix.platform }}
          push: true
          # per-arch digest only — no shared tag yet
          outputs: type=image,name=ghcr.io/OWNER/REPO,push-by-digest=true,name-canonical=true
          cache-from: type=gha,scope=${{ matrix.platform }}
          cache-to: type=gha,mode=max,scope=${{ matrix.platform }}

  merge:
    needs: build
    runs-on: ubuntu-24.04
    steps:
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - run: |
          docker buildx imagetools create \
            -t ghcr.io/OWNER/REPO:${{ github.sha }} \
            ghcr.io/OWNER/REPO@sha256:AMD64_DIGEST \
            ghcr.io/OWNER/REPO@sha256:ARM64_DIGEST
```

Each matrix leg builds and pushes its own architecture-specific image
and reports a digest; a separate `merge` job collects those digests and
runs `docker buildx imagetools create` to publish a single manifest list
under the shared tag, pointing at both per-arch digests. Consumers who
`docker pull ghcr.io/OWNER/REPO:<sha>` get the manifest list and their
container runtime resolves the correct architecture automatically — the
split/merge shape is invisible to them. Docker also publishes reusable
GitHub Actions workflows that automate exactly this split/merge
sequence, for teams that would rather not hand-wire the digest-passing
between the matrix job and the merge job.

QEMU-based emulation (`docker/setup-qemu-action` plus a single job
targeting `platforms: linux/amd64,linux/arm64`) still has a place, but a
narrow one: trivial images — a static binary copy, a tiny Alpine-based
utility — where the emulation tax is small relative to total build time.
For anything compiling code, resolving native dependencies, or running a
multi-stage Python/Node build (the shape this skill's Dockerfiles use),
QEMU emulation is dramatically slower than native execution — instruction-level
emulation of the entire toolchain, not just the final binary — and the
native-runner matrix above should be the default, not the fallback.

arm64 is not a niche target to special-case: AWS Graviton is now a
mainstream, often cost-preferred, EC2/Fargate/ECS instance family, and
Apple Silicon means most developers building images locally are on
arm64 hosts already. Treating `linux/amd64` as "the" platform and arm64
as an afterthought produces images that build slowly and behave
differently for a large fraction of both the deployment fleet and the
engineering team's laptops.

Sources: <https://docs.docker.com/build/building/multi-platform/>,
<https://docs.docker.com/build/ci/github-actions/multi-platform/>.

### Multi-arch mistakes worth naming

| Mistake | Symptom | Fix |
| --- | --- | --- |
| Single QEMU job for a full uv/npm build | Build times balloon (native compile steps run emulated) | Split into a native-runner matrix |
| Pushing a shared tag from each matrix leg independently | Last-writer-wins single-arch tag; the manifest list is never created | Push per-arch digests (`push-by-digest=true`), merge once with `imagetools create` |
| Forgetting `scope=` on per-arch cache | `amd64` and `arm64` cache entries evict each other under one quota | Scope `cache-from`/`cache-to` per matrix leg (see [`## Build cache`](#build-cache)) |
| Treating arm64 as optional/experimental | Graviton and Apple Silicon consumers get a slow or absent image | Build and merge both architectures for every release, not just amd64 |

### Native vs QEMU

| Approach | Speed | Setup | Best for |
| --- | --- | --- | --- |
| Native-runner matrix | Full native speed per architecture | Requires an architecture-matched runner (`ubuntu-24.04-arm` for arm64) | Any build that compiles code, resolves native wheels/binaries, or runs a multi-stage uv/npm install — the default case for this skill's Dockerfiles |
| QEMU emulation, single job | Emulates the entire instruction stream for the non-native target; often several times slower wall-clock, not a fixed small overhead | One job, no architecture-matched runner needed | Trivial images only — a static binary `COPY`, a tiny Alpine utility with no build step |

The QEMU column is not "slightly slower" — it is emulating every
instruction the toolchain executes, not just the final binary, so a
`uv sync` or `npm run build` step that takes two minutes natively can
take much longer under emulation. That cost is invisible in a
single-architecture pipeline and becomes very visible the moment a
second architecture is added the QEMU way instead of the native-matrix
way. Default to the native matrix; reach for QEMU deliberately, for a
named image that's actually trivial, not as the default multi-arch
strategy.

### Testing each architecture before merging

The `merge` job in the sketch above trusts that both matrix legs
produced a working image; nothing in `buildx imagetools create` runs the
image to confirm that. Add a smoke-test step per matrix leg — pull the
just-pushed per-arch digest with `docker run --platform ${{
matrix.platform }} ... <smoke test command>` — before the `merge` job
runs, so an arm64-only runtime bug (a native extension that only ships
an amd64 wheel, for example) fails the matrix leg instead of silently
shipping in the merged manifest list.

### Manifest lists and the OCI image index

`docker buildx imagetools create` doesn't build anything — it writes an
OCI image index (the manifest-list format) that lists the two per-arch
manifests produced by the matrix and their platform metadata, under one
shared tag. This is why the merge job needs no build context, no
Dockerfile, and no BuildKit build step of its own: it's a metadata
operation over two already-pushed digests, not a rebuild. `docker
buildx imagetools inspect ghcr.io/OWNER/REPO:<tag>` shows the resulting
index and both platform entries, which is the fastest way to confirm a
release actually shipped both architectures rather than silently
publishing amd64-only because the arm64 matrix leg failed without
failing the job.

Sources: <https://docs.docker.com/build/building/multi-platform/>,
<https://docs.docker.com/build/ci/github-actions/multi-platform/>.

## Labels

Every image this skill builds should carry the standard OCI image
annotations under the `org.opencontainers.image.*` namespace:

| Annotation | Meaning |
| --- | --- |
| `org.opencontainers.image.source` | Repository URL the image was built from |
| `org.opencontainers.image.revision` | Exact commit SHA of the build |
| `org.opencontainers.image.version` | Human version string (semver tag on release, git ref otherwise) |
| `org.opencontainers.image.created` | RFC 3339 build timestamp |
| `org.opencontainers.image.title` | Human-readable image name |
| `org.opencontainers.image.description` | One-line description |
| `org.opencontainers.image.licenses` | SPDX license identifier |

These are the annotations the OCI Image Format Specification defines
under `org.opencontainers.image`, and hand-writing all seven as `LABEL`
instructions in every Dockerfile (and keeping them in sync with the
actual commit and build time) does not scale. `docker/metadata-action`
generates the full label set — plus the tag rules covered in
[`## Tag strategy`](#tag-strategy) — from the GitHub Actions event
context in one step, and its output feeds directly into
`docker/build-push-action`'s `labels:` input:

```yaml
- id: meta
  uses: docker/metadata-action@v5
  with:
    images: ghcr.io/OWNER/REPO
    labels: |
      org.opencontainers.image.licenses=Apache-2.0
      org.opencontainers.image.description=Example service API
- uses: docker/build-push-action@v6
  with:
    context: .
    push: true
    tags: ${{ steps.meta.outputs.tags }}
    labels: ${{ steps.meta.outputs.labels }}
```

`metadata-action` derives `source`, `revision`, `created`, and `title`
automatically from the GitHub context (repository URL, `github.sha`,
build time, repository name); `version` is derived from whichever tag
rule matched (see [`## Tag strategy`](#tag-strategy)). Only
`licenses` and `description` — values that don't exist anywhere in the
Actions context — need explicit input, as shown above. Anything the
action can derive should be left to it rather than hardcoded, because a
hardcoded `revision` or `created` label silently goes stale the moment
someone copies the Dockerfile step into a new pipeline without updating
it.

Verify the labels landed post-push with `docker buildx imagetools
inspect ghcr.io/OWNER/REPO:<tag>` (or `crane config`), not by trusting
the workflow file — a `labels:` input typo or a step ordering mistake
(labels computed after the build step that needed them) is a common,
silent failure that only a post-push inspection catches.

Sources: <https://github.com/opencontainers/image-spec/blob/main/annotations.md>,
<https://github.com/docker/metadata-action>.

### Where labels get consumed

The seven annotations aren't decorative — each has a real reader:

- `source` and `revision` let anyone with `docker inspect` or
  `crane config` trace a running container back to the exact repository
  and commit that produced it, without needing access to the CI system
  that built it.
- `created` lets a fleet-wide image-age audit (part of
  [`## Registry hygiene`](#registry-hygiene) housekeeping) answer "how
  old is what's actually deployed" without cross-referencing registry
  push timestamps, which reflect when a tag last moved, not when the
  underlying image was built.
- `version` and `title` are what shows up in registry UIs, vulnerability
  dashboards, and SBOM viewers grouping findings by human-readable image
  identity instead of a bare digest.
- `licenses` is what license-compliance scanning tools read to build a
  dependency/base-image license report without opening the Dockerfile.

A pipeline that skips labels doesn't fail any build — it just makes
every one of those consumers fall back to manual digest archaeology.

### License identifier notes

`org.opencontainers.image.licenses` should be a valid SPDX license
expression (`Apache-2.0`, `MIT`, `MIT OR Apache-2.0`) matching the
project's actual `LICENSE` file, not a free-text string like
"Proprietary" or "See LICENSE" — license-compliance tooling that reads
this annotation expects SPDX syntax and will silently fail to classify
anything else. For a genuinely closed-source internal image, omit the
annotation rather than putting a non-SPDX placeholder in it.

## Tag strategy

Two, and only two, tag shapes should ever be pushed:

| Trigger | Tag(s) pushed | Mutable? |
| --- | --- | --- |
| Every push to any branch | `<git-sha>` (full 40-char or metadata-action's short form) | No — immutable by construction |
| Release (tag `v1.4.2`) | `1.4.2` | No — immutable by convention, enforce at the registry |
| Release (tag `v1.4.2`) | `1.4`, `1` | Yes — intentionally floating, re-pointed by the next patch/minor release |
| Never | `latest` | N/A — banned from production deploy manifests |

Every push — not just releases — gets tagged with the immutable git
SHA. That SHA tag is the only tag a deploy manifest or a rollback script
should ever reference during day-to-day operation, because it is
provably bound to one exact build: reproducing "what's running in
staging right now" is a `git show <sha>` away. On top of that, a release
(driven by a semver git tag, e.g. `v1.4.2`) additionally gets the full
semver triplet (`1.4.2`, itself effectively immutable — nobody should
force-push a new build over an already-published patch version) plus
the floating `1.4` and `1` convenience tags, which move forward to point
at the newest matching build as later patch/minor releases ship. Those
floating tags exist for humans browsing a registry UI or writing a
`FROM ghcr.io/OWNER/REPO:1.4` base-image reference that wants "whatever
the latest 1.4.x is" — they are not deploy-manifest material.

`:latest` is banned from any production deploy manifest, full stop.
`:latest` is not a version — it is whichever image happened to be
pushed most recently under that mutable name, and a manifest pinned to
it silently redeploys a different image on every restart/reschedule
even when nothing in the manifest itself changed, which defeats the
entire purpose of a deploy manifest as a reproducible artifact. Deploy
by digest (`ghcr.io/OWNER/REPO@sha256:...`) or by the exact immutable
SHA tag — never by a tag that moves.

`metadata-action`'s `tags:` input generates exactly this taxonomy from
one rule block, keyed off GitHub event context:

```yaml
- id: meta
  uses: docker/metadata-action@v5
  with:
    images: ghcr.io/OWNER/REPO
    tags: |
      type=sha,format=long
      type=semver,pattern={{version}}
      type=semver,pattern={{major}}.{{minor}}
      type=semver,pattern={{major}}
```

`type=sha` fires on every push; the three `type=semver` rules fire only
when the triggering ref is a semver git tag, producing the immutable
triplet plus the two floating shorthands in one pass.

Where the registry supports it, turn on immutable-tag enforcement (e.g.
an ECR repository policy that rejects overwriting an existing tag) so
"someone force-pushed over `1.4.2`" becomes a rejected API call instead
of a silent, undetectable image swap — this is a backstop for when the
tagging convention above is violated by mistake or by a compromised
credential, not a replacement for following it.

### Deploy-time consequences

The `:latest`-ban and deploy-by-digest rule above isn't pedantry about
tag names — it changes observable deploy behavior:

- **GitOps tools** (Argo CD, Flux) diff the manifest in git against
  what's running; if the manifest says `:latest`, the diff never
  changes even when the underlying image does, so a GitOps reconciler
  has nothing to act on and "what's deployed" silently drifts from
  "what git says is deployed." Pin the manifest to the immutable SHA
  tag or digest so every image change is a real git diff.
- **Kubernetes `imagePullPolicy`** defaults to `Always` for the
  `:latest` tag specifically (every other tag defaults to
  `IfNotPresent`) — precisely because Kubernetes itself assumes
  `:latest` is mutable and can't be trusted to mean the same image
  twice. Deploying by digest sidesteps the whole question: a digest
  reference is unambiguous regardless of `imagePullPolicy`, since
  `sha256:...` can only ever resolve to one set of bytes.
- **Rollback** becomes "redeploy the previous immutable reference," not
  "hope the registry still has whatever `:latest` used to point at
  before someone re-pushed it."

### Rollback runbook

With immutable SHA tags on every push, rollback needs no rebuild:

1. Identify the last-known-good SHA from CI run history or the
   registry's tag list — the same SHA the previous successful deploy
   used.
2. Update the deploy manifest's image reference to that exact SHA tag
   or digest.
3. Apply/redeploy. The registry already holds that exact artifact
   (assuming [`## Registry hygiene`](#registry-hygiene) hasn't expired
   it — size the aged-SHA-tag retention window with rollback in mind).
4. No new build, no new scan, no new sign step — the previous build
   already cleared every gate in [`## Pipeline`](#pipeline) the first
   time it shipped.

### Release cadence

The two rows of the tag table map to two different triggers, and
conflating them is a common source of "why didn't this get a semver
tag" confusion:

- **Every push** (any branch, any commit) → the SHA-tag row fires
  automatically off `github.sha`. This needs no human action and no
  release process — it's the default, continuous output of the
  pipeline in [`## Pipeline`](#pipeline).
- **A release** → the semver rows fire only when the ref that triggered
  the workflow is a semver git tag (`v1.4.2`). Getting there is a
  separate, deliberate step: either a maintainer pushes an annotated
  tag directly, or a release-automation tool (semantic-release,
  Changesets, release-please, or an equivalent) computes the next
  version from commit history and pushes the tag on the maintainer's
  behalf. Either way, the image-tagging pipeline itself stays
  unchanged — `metadata-action`'s `type=semver` rules react to
  whatever tag arrives, they don't decide when a release happens.

Keeping these decoupled means the CI pipeline never needs its own
opinion about semver bumps (major vs minor vs patch) — that judgment
call lives entirely in the release-tagging step, upstream of the image
pipeline described in this file.

Sources: <https://podostack.com/p/docker-image-tagging-strategies>,
<https://oneuptime.com/blog/post/2026-02-02-docker-image-tagging/view>.

## Registry hygiene

An immutable-SHA-per-push tagging strategy (above) means every single
push accumulates a permanent tag — left alone, the registry grows
without bound and old SHA images from abandoned branches or superseded
commits never get reclaimed. Registry lifecycle policies close that gap
by expiring images on rules rather than manual cleanup:

- Expire **untagged** images (a digest that no tag points at anymore —
  typically left behind after a multi-arch merge, or after a tag was
  moved) after a short grace window.
- Expire **aged SHA tags** — a `<git-sha>` tag past some age threshold
  that was never promoted to a release — while keeping a smaller,
  recent window for rollback purposes.
- **Never** expire release tags (the semver triplet and its floating
  shorthands from [`## Tag strategy`](#tag-strategy)) — those need to
  survive indefinitely as the historical record of what shipped.

An ECR lifecycle policy expresses this as prioritized, numbered rules
evaluated in order:

```json
{
  "rules": [
    {
      "rulePriority": 1,
      "description": "Expire untagged images after 7 days",
      "selection": {
        "tagStatus": "untagged",
        "countType": "sinceImagePushed",
        "countUnit": "days",
        "countNumber": 7
      },
      "action": { "type": "expire" }
    },
    {
      "rulePriority": 2,
      "description": "Keep only the newest 50 non-release SHA tags",
      "selection": {
        "tagStatus": "tagged",
        "tagPrefixList": ["sha-"],
        "countType": "imageCountMoreThan",
        "countNumber": 50
      },
      "action": { "type": "expire" }
    }
  ]
}
```

Rule 1 reclaims untagged digests quickly since nothing should reference
them once a tag has moved past them. Rule 2 keeps a bounded recent
window of SHA-tagged builds (enough for practical rollback) and expires
older ones once the count grows past the threshold; because the rule's
`tagPrefixList` scopes it to the `sha-` prefix, semver release tags
(which don't match that prefix) are excluded from this rule entirely and
persist indefinitely, satisfying the "keep release tags forever"
requirement without a separate allow-list. Adjust the prefix and
`countNumber` to match the tagging convention actually in use in the
`metadata-action` config from [`## Tag strategy`](#tag-strategy).

The same shape — expire untagged, cap aged non-release tags, keep
release tags forever — applies to any registry offering lifecycle or
retention rules, not only ECR; the rule syntax differs per registry but
the policy intent above is the portable part.

### Previewing a lifecycle policy before enabling it

A lifecycle policy is a standing deletion rule — get the tag-pattern
scoping wrong and it deletes images a running deployment still
references, silently, on its next evaluation. ECR supports a preview
mode (`start-lifecycle-policy-preview` / `get-lifecycle-policy-preview`
in the ECR API/CLI) that reports exactly which images a candidate policy
would expire without deleting anything. Run the preview against a
repository's real image list before enabling a new or edited policy,
and re-run it any time the tagging convention in
[`## Tag strategy`](#tag-strategy) changes — a prefix/pattern rule that
was correct for the old convention can silently start matching (or
stop matching) release tags under a new one.

### Registry hygiene mistakes worth naming

| Mistake | Symptom | Fix |
| --- | --- | --- |
| Aged-tag rule with no prefix/pattern scoping | Release tags get swept along with SHA tags once they're old enough | Scope with `tagPrefixList`/`tagPatternList` so only non-release tags match |
| Enabling a policy without a preview run | Images a live deployment still references disappear on the next evaluation | Preview first, on every policy change, not just the first |
| Applying the same aged-tag rule to a `buildcache` registry-backend tag | The cache from [`## Build cache`](#build-cache)'s registry fallback gets reclaimed instead of reused, and every build goes cold | Exclude the cache tag from the aged-tag rule, or give it its own short-lived rule instead |
| No visibility into what a policy actually expired | Registry growth "mysteriously" resumes after a rule edit breaks silently | Check the lifecycle evaluation results/events the registry exposes after each policy change, don't assume the JSON is doing what it says |

### Beyond ECR

The rule shape in this section — expire untagged, cap aged non-release
tags, keep release tags forever — is what to configure regardless of
registry; only the mechanism differs. GitHub Container Registry exposes
retention configuration through repository/organization package
settings rather than a JSON policy document; Google Artifact Registry
and other managed registries expose their own cleanup-policy resources
with similar tag-state and age predicates. Whichever registry hosts the
images this pipeline pushes, translate the same three bullets into that
registry's native policy mechanism rather than trying to force ECR's
exact JSON shape onto a different API — the policy *intent* from
[`## Registry hygiene`](#registry-hygiene) is the portable part, the
rule syntax above is ECR-specific.

Source: <https://docs.aws.amazon.com/AmazonECR/latest/userguide/LifecyclePolicies.html>.

## Pipeline

The full gate order, every push, no gate skipped for a "quick" release:

1. **hadolint** — lint the Dockerfile itself before spending any build
   time on it; a Dockerfile that fails hadolint's `DL3006`/`DL3008`/`DL3002`
   gates (untagged `FROM`, unpinned `apt` packages, `USER root` as the
   last user) should never reach the build step. Full rule set and
   `.hadolint.yaml` shape:
   [`hardening-and-supply-chain.md#linting`](hardening-and-supply-chain.md#linting).
2. **Build**, with `--provenance --sbom` (via `build-push-action`'s
   `provenance:`/`sbom:` inputs, or the equivalent buildx flags) — every
   image ships build provenance and a software bill of materials as
   attestations in the image index, not as an afterthought bolted on
   post-push. Cache wiring for this step is
   [`## Build cache`](#build-cache); multi-arch fan-out is
   [`## Multi-arch`](#multi-arch); tags and labels for this step come
   from `docker/metadata-action` as shown in
   [`## Labels`](#labels) and [`## Tag strategy`](#tag-strategy).
3. **Trivy**, failing the pipeline on any `HIGH`/`CRITICAL` finding, with
   `.trivyignore` as the explicit, reviewed escape hatch for accepted
   findings — never a silently-skipped scan. Full scanner configuration
   and the fail-on-severity gate:
   [`hardening-and-supply-chain.md#scanning`](hardening-and-supply-chain.md#scanning).
4. **cosign sign** — keyless signing (OIDC via Fulcio, transparency log
   via Rekor) over the pushed digest, so a deploy-time policy can verify
   provenance before running the image. Signing mechanics and the
   keyless-vs-PKI decision:
   [`hardening-and-supply-chain.md#signing`](hardening-and-supply-chain.md#signing).
5. **Push** — the image, its per-arch manifest merge (multi-arch
   builds), its tags, and its labels all land in the registry together;
   nothing downstream of this step should ever push an unscanned,
   unsigned, or untagged image under a different code path "just this
   once."

Every gate above operates on the same tag/label set that
`docker/metadata-action` computed once, at the top of the job — hadolint
runs against source, but the build, scan, sign, and push steps all
consume `steps.meta.outputs.tags` and `steps.meta.outputs.labels` rather
than each recomputing its own notion of what this build should be
called. A gate skeleton showing the ordering (security-gate internals
live in `hardening-and-supply-chain.md`, referenced rather than
repeated):

```yaml
jobs:
  release:
    runs-on: ubuntu-24.04
    permissions:
      contents: read
      packages: write
      id-token: write   # cosign keyless OIDC
    steps:
      - uses: actions/checkout@v4

      # 1. hadolint — see hardening-and-supply-chain.md#linting
      - uses: hadolint/hadolint-action@v3.1.0
        with:
          dockerfile: Dockerfile

      - uses: docker/setup-buildx-action@v3
      - id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/OWNER/REPO
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      # 2. build, with attestations
      - id: build
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          provenance: mode=max
          sbom: true
          cache-from: type=gha
          cache-to: type=gha,mode=max

      # 3. Trivy — see hardening-and-supply-chain.md#scanning
      - uses: aquasecurity/trivy-action@0.28.0
        with:
          image-ref: ghcr.io/OWNER/REPO@${{ steps.build.outputs.digest }}
          severity: HIGH,CRITICAL
          exit-code: 1

      # 4. cosign sign — see hardening-and-supply-chain.md#signing
      - uses: sigstore/cosign-installer@v3
      - run: cosign sign --yes ghcr.io/OWNER/REPO@${{ steps.build.outputs.digest }}

      # 5. push already happened in step 2; this job's success gates
      #    whatever deploy workflow consumes steps.build.outputs.digest
```

Note that "push" in the numbered list above and "push" as a build-step
flag are the same event, not two separate steps — `build-push-action`
performs the push as part of step 2, but the image is not fit to be
*consumed* until it has cleared steps 3 and 4. Anything that deploys off
this pipeline's output (a CD workflow, a Terraform `image` variable, a
compose pull) should reference `steps.build.outputs.digest` — the
digest emitted only after the whole job, gates included, succeeds — not
a tag that a partially-failed run may have already pushed.

### Gate summary

| # | Gate | Tool | Blocks on | Config / detail lives at |
| --- | --- | --- | --- | --- |
| 1 | Lint | hadolint | Dockerfile rule violations (`DL3006`, `DL3008`, `DL3002`, …) | [`hardening-and-supply-chain.md#linting`](hardening-and-supply-chain.md#linting) |
| 2 | Build | Buildx / `build-push-action` | Build failure; cache/multi-arch/tag/label misconfiguration | [`## Build cache`](#build-cache), [`## Multi-arch`](#multi-arch), [`## Labels`](#labels), [`## Tag strategy`](#tag-strategy) |
| 3 | Scan | Trivy | Any `HIGH`/`CRITICAL` finding not in `.trivyignore` | [`hardening-and-supply-chain.md#scanning`](hardening-and-supply-chain.md#scanning) |
| 4 | Sign | cosign | OIDC/signing failure | [`hardening-and-supply-chain.md#signing`](hardening-and-supply-chain.md#signing) |
| 5 | Push | (already executed as part of gate 2) | N/A — gate 5 is "this digest may now be consumed," not a separate action | — |

### What happens when a gate fails

The gates are not symmetric in what a failure leaves behind, and a
pipeline's failure handling should account for that:

- **Gate 1 (lint) fails** — cheapest possible failure. No build
  resources spent, nothing pushed, nothing to clean up.
- **Gate 2 (build) fails** — no image reaches the registry at all;
  same as gate 1 in terms of cleanup, just later in the pipeline.
- **Gate 3 (scan) fails** — because `push: true` already ran inside
  gate 2, the vulnerable image is *already sitting in the registry* by
  the time Trivy reports it. This is the normal shape for
  digest-based scanning (Trivy needs something to pull), not a bug —
  but it means "is this image absent from the registry" is **not**
  a valid signal that it failed a gate. The signal deploy tooling must
  actually check is cosign verification (gate 4) — an image that never
  reached gate 4 was never signed, and a deploy policy that requires a
  valid signature rejects it regardless of what's sitting in the
  registry. [`## Registry hygiene`](#registry-hygiene)'s untagged/aged
  expiry rules are what eventually reclaim the failed image's storage;
  they are cleanup, not the safety control.
- **Gate 4 (sign) fails** — same shape as gate 3: image already pushed,
  unsigned. Same mitigation: deploy tooling gates on signature
  verification, never on registry presence alone.

This is the concrete reason [`## Labels`](#labels) and
[`## Tag strategy`](#tag-strategy) both point deploy manifests at
`steps.build.outputs.digest` rather than a tag computed earlier in the
job — the digest is a stable identifier available before the gates even
run, and pairing it with a cosign-verify step at deploy time is what
actually enforces "only gate-cleared images run," not the mere fact
that something reached the registry.

Sources: <https://github.com/hadolint/hadolint>,
<https://github.com/aquasecurity/trivy-action>,
<https://docs.docker.com/build/metadata/attestations/>,
<https://github.com/sigstore/cosign-installer>.

_Verified as of 2026-07; sources re-checked against docs/superpowers/research/2026-07-20-*.md._
