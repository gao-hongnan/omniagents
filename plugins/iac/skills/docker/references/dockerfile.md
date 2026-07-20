# Dockerfile

Catalogue-depth Dockerfile reference for the omniagents-iac docker skill —
the rules a reviewer enforces on every `Dockerfile` in this shop, each
traced to its source, plus worked sketches for the two stacks this org
ships most: Python/uv services and Vite-built static frontends. Voice and
rule-citation model follows `terraform/SKILL.md` (imperative bold-lead
rules, each ending in a source URL); the anti-pattern gallery shape follows
`design-patterns/skills/system/anti-patterns.md`, condensed to failing form
+ one-line why + fix.

Companion references in this directory cover CI/release conventions and
supply-chain hardening — this file is Dockerfile authoring only: what goes
inside the file, not what happens to the image after `docker build` exits.

## Contents

- [Layering](#layering)
- [Cache and bind mounts](#cache-and-bind-mounts)
- [Copy discipline](#copy-discipline)
- [Base images](#base-images)
- [Pinning and updates](#pinning-and-updates)
- [Python and uv](#python-and-uv)
- [Node and Vite](#node-and-vite)
- [Anti-patterns](#anti-patterns)

---

## Layering

House rules for instruction ordering and RUN-instruction shape. These are
conventions, not a single named pattern — apply them as a checklist on
every RUN/COPY/FROM you write.

- **Start every Dockerfile with `# syntax=docker/dockerfile:1`.** This
  auto-tracks the latest stable Dockerfile frontend syntax without pinning
  to a specific release; use the `:1-labs` channel only for experimental
  flags you've deliberately opted into, never in a committed Dockerfile —
  https://docs.docker.com/reference/dockerfile/
- **Use multi-stage builds; the final stage ships only runtime artifacts,
  never a build toolchain.** A stage that ran `uv sync` or `npm run build`
  is not the stage that serves traffic — copy only what the runtime
  actually executes into the last `FROM` —
  https://docs.docker.com/build/building/best-practices/
- **Order instructions least-volatile to most-volatile: base image →
  dependency manifest → dependency install → source copy.** Docker's layer
  cache is keyed by instruction + inputs; an instruction only reruns when
  something above it in the file changed. Put the dependency-install RUN
  behind a COPY of *only* the manifest/lockfile, so a source-only edit
  never invalidates it — https://docs.docker.com/build/building/best-practices/

**Worked example — dependency install survives a source edit.**

```dockerfile
# syntax=docker/dockerfile:1
FROM node:22-slim AS deps
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

FROM deps AS build
COPY . .
RUN npm run build
```

`npm ci` is keyed only by `package.json` + `package-lock.json` (line 5).
Edit any file under `src/` and rebuild: Docker replays the cache through
line 6, then reruns only `COPY . .` (line 9) and `npm run build` (line 10)
— the entire dependency-install layer is reused verbatim, unpacked from
cache instead of hitting the network. Reverse the order (`COPY . .` before
`npm ci`) and *every* source edit reinstalls the full dependency tree.

- **Use heredocs (`RUN <<EOF`) instead of `&&`-chains for multi-command RUN
  instructions; add `set -o pipefail` whenever a command in the block pipes
  into another.** A heredoc reads like a script, diffs cleanly in review,
  and doesn't force every command onto one unreadable line joined by
  backslashes — https://docs.docker.com/reference/dockerfile/#here-documents
- **Collapse `apt-get update` + `install` + cache cleanup into a single
  RUN, with `--no-install-recommends` and an alphabetically sorted package
  list.** Splitting `update` and `install` across separate RUN instructions
  risks a stale package index being reused from cache on a later layer that
  reruns only the `install` half; recommends pull in packages nobody asked
  for; an unsorted list produces noisy diffs when someone adds one entry —
  https://docs.docker.com/build/building/best-practices/

**Worked example — heredoc + pipefail + sorted, cleaned-up apt install.**

```dockerfile
# syntax=docker/dockerfile:1
RUN <<EOF
set -eu
set -o pipefail
apt-get update
apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git
rm -rf /var/lib/apt/lists/*
EOF
```

`set -o pipefail` matters the moment any line in the block pipes into
another (`curl ... | tar -xz`, for instance) — without it, a failing
left-hand command in a pipeline is masked by a succeeding right-hand one,
and the RUN instruction reports success on a broken install.

### ARG and ENV placement

- **Declare `ARG` as close as possible to the instruction that uses it,
  and never rely on it to persist into the running container.** A build
  ARG is scoped to the instructions after its declaration within a single
  stage; it doesn't survive into a later `FROM` unless re-declared, and it
  never appears in the running container's environment unless you also set
  it via `ENV` — https://docs.docker.com/build/building/best-practices/
- **Put ENV values that change per-deployment (log level, feature flags)
  after the dependency-install layers, not before.** An ENV instruction
  placed above the dependency-install RUN becomes part of that layer's
  cache key — bump `LOG_LEVEL` from `info` to `debug` and, if it sits above
  the install, the entire dependency layer reruns for a value the install
  step never reads.

```dockerfile
# BAD — LOG_LEVEL above the install layer busts the dependency cache on
# every value change, even though `uv sync` never reads it.
FROM python:3.14-slim AS bad
ENV LOG_LEVEL=info
COPY uv.lock pyproject.toml ./
RUN uv sync --locked --no-install-project

# GOOD — deploy-time values sit below the layers they don't affect.
FROM python:3.14-slim AS good
COPY uv.lock pyproject.toml ./
RUN uv sync --locked --no-install-project
ENV LOG_LEVEL=info
```

### Why the ordering matters — a second pass

BuildKit's cache is content-addressable per instruction: each layer's
cache key is a hash of the instruction text plus its inputs (the files a
COPY reads, the parent layer's key). A cache hit requires an *exact* match
all the way down the chain — the moment one instruction's key changes,
every instruction after it recomputes too, even if that instruction would
have produced byte-identical output on its own.

```dockerfile
# BAD — COPY . . before the dependency install. Every file change anywhere
# in the repo — a README typo, a comment, an unrelated test fixture —
# busts the cache key for `COPY . .`, which busts every instruction after
# it, including the multi-minute dependency resolve.
FROM python:3.14-slim AS bad
WORKDIR /app
COPY . .
RUN uv sync --locked
```

Compare the worked example above: moving `COPY . .` below the
dependency-install RUN doesn't change what the image contains — it changes
which edits are expensive. That's the entire content of the least→most
volatile rule, restated concretely.

---

## Cache and bind mounts

**Intent.** Make repeated builds fast without corrupting a shared cache
under concurrent access, and stop bind-worthy files (lockfiles, manifests)
from ever becoming COPY-triggered cache-busts.

**Rules.**

- **Mount a persistent cache for every package manager's cache directory
  with `RUN --mount=type=cache,target=<path>`.** apt:
  `/var/cache/apt` + `/var/lib/apt`; uv: `/root/.cache/uv` (or
  `$UV_CACHE_DIR` if you've overridden it); npm: `/root/.npm`. The mount
  persists across builds on the same BuildKit builder, independent of the
  image's own layer cache —
  https://docs.docker.com/reference/dockerfile/#run---mounttypecache
- **Add `sharing=locked` whenever the package manager can't tolerate
  concurrent access to its own cache/lock state.** apt's package cache and
  npm's global cache both corrupt or deadlock under two BuildKit workers
  racing the same cache id; `sharing=locked` serializes access to that
  mount instead of racing it —
  https://docs.docker.com/reference/dockerfile/#run---mounttypecache
- **Bind-mount the lockfile and manifest into the dependency-install RUN
  instead of COPYing them.** A bind mount (`--mount=type=bind`) is not a
  layer — the file exists only for that RUN's duration and never widens
  the set of COPY instructions that could invalidate the build cache —
  https://docs.docker.com/reference/dockerfile/#run---mounttypecache

**Sketch — cache mount per package manager.**

```dockerfile
# syntax=docker/dockerfile:1

# apt: two directories back the package cache and the installed-package
# database; both need locking under concurrent builds.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get install -y --no-install-recommends git

# uv: one cache directory, keyed by wheel/sdist hash — safe to share.
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv sync --locked --no-install-project --no-dev

# npm: global cache directory.
RUN --mount=type=cache,target=/root/.npm,sharing=locked \
    npm ci
```

**Sketch — the full RUN: cache mount + bind-mounted lockfiles together.**
This is the canonical shape for a Python/uv dependency-install layer —
cache the resolved wheels, bind-mount the two files that determine what
gets installed, and copy nothing:

```dockerfile
# syntax=docker/dockerfile:1
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev
```

**When NOT to use.** Cache mounts are BuildKit-only — there is no classic
builder fallback, and the mount's contents are invisible to
`docker history`/layer inspection by design. On a CI runner with no
persistent BuildKit cache volume (a fresh ephemeral VM per job with no
`cache-from`/`cache-to` wired to a shared backend), a cache mount simply
starts cold every run and buys nothing beyond documentation value; wire
`type=gha` or `type=registry` cache export/import instead of relying on the
mount alone in that environment.

**Anti-pattern variant.** `COPY uv.lock pyproject.toml ./` followed by
`RUN uv sync --locked` with no `--mount=type=cache`: the *layer-ordering*
discipline from [Layering](#layering) is intact (a source-only edit still
skips this layer), but a cold cache — a fresh builder, a bumped base image,
a CI runner with no cache volume — pays full network cost to re-resolve
every wheel, every time. See [Anti-patterns](#anti-patterns).

### Cache mount IDs and sharing modes

- **Give a cache mount an explicit `id=` when a monorepo Dockerfile builds
  more than one service that shouldn't share a cache.** Without `id=`, the
  cache id defaults to the mount's target path — two stages that both
  cache `/root/.cache/uv` for genuinely different projects (different
  lockfiles, different Python versions) share one cache bucket unless each
  gets an explicit, distinct `id=` —
  https://docs.docker.com/reference/dockerfile/#run---mounttypecache
- **`sharing` has three modes: `shared` (default), `locked`, and
  `private`.** `shared` lets multiple concurrent builds read/write the
  same cache simultaneously — safe only when the tool itself tolerates
  concurrent writers; `locked` serializes access, one writer at a time —
  the right default for apt and npm; `private` gives each concurrent build
  its own copy-on-write cache instance, trading some cache-hit rate for
  guaranteed isolation when even `locked`'s serialization isn't enough —
  https://docs.docker.com/reference/dockerfile/#run---mounttypecache

```dockerfile
# Two services in one monorepo Dockerfile, each with its own uv cache —
# a distinct `id=` keeps them from colliding on the same cache bucket.
RUN --mount=type=cache,id=uv-api,target=/root/.cache/uv,sharing=locked \
    --mount=type=bind,source=services/api/uv.lock,target=uv.lock \
    --mount=type=bind,source=services/api/pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev
```

**References.**

- https://docs.docker.com/reference/dockerfile/#run---mounttypecache
- https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers

---

## Copy discipline

Rules for `COPY`/`ADD` flags and when `ADD`'s extra behavior is actually
warranted.

- **Prefer `COPY` over `ADD` in all ordinary cases.** `ADD` does two things
  `COPY` doesn't — silent tar auto-extraction and remote-URL fetching — and
  both are surprising when you didn't mean to invoke them —
  https://docs.docker.com/build/building/best-practices/
- **`ADD` has exactly two legitimate uses:** fetching and verifying a
  remote URL with `--checksum`, and auto-extracting a local compressed
  archive on copy. Outside those two cases, an `ADD` in review is a `COPY`
  that hasn't been fixed yet — https://docs.docker.com/build/building/best-practices/

```dockerfile
# ADD legitimate use #1 — fetch a remote artifact, checksum-verified.
# Without --checksum this is an unverified network fetch baked into the
# image — don't ship that.
ADD --checksum=sha256:REPLACE_WITH_REAL_CHECKSUM \
    https://example.com/geolite2/GeoLite2-City.tar.gz /tmp/geoip.tar.gz

# ADD legitimate use #2 — local compressed archive, auto-extracted on copy.
# A plain COPY would leave the .tar.gz sitting there, unextracted.
ADD ./vendor/fonts.tar.gz /usr/share/fonts/custom/
```

- **Set ownership and mode at copy time with `--chown`/`--chmod`; never
  follow a `COPY` with a `RUN chown`.** Syntax ≥1.2. `--chown`/`--chmod`
  apply during the copy, in the same layer, with no extra instruction —
  https://docs.docker.com/reference/dockerfile/#copy
- **Use `--link` on the final stage's `COPY --from`.** A link-mounted copy
  is an independent layer, not dependent on the layers before it in the
  final stage — it can be reordered, and it plays well with
  registry-based remote build cache because the layer's identity doesn't
  shift when earlier, unrelated layers change —
  https://docs.docker.com/reference/dockerfile/#copy
- **Use `--parents` (syntax ≥1.20) when copying a glob that must keep its
  directory structure.** Without it, a multi-directory glob copy flattens
  every matched file into the destination directory, losing the tree
  shape the next stage or the running process expects —
  https://docs.docker.com/reference/dockerfile/#copy

**Sketch — chown/chmod, `--link`, and `--parents` together.**

```dockerfile
# chown/chmod at copy time — never a separate `RUN chown` layer afterward.
COPY --chown=10001:10001 --chmod=550 ./scripts/entrypoint.sh /app/entrypoint.sh

# --link: this layer doesn't depend on the layers before it in this stage —
# safe to reorder, and it caches well against registry-based remote cache.
COPY --link --from=builder /app/.venv /app/.venv

# --parents (syntax >=1.20): preserves src/pkg/mod.py as src/pkg/mod.py in
# the destination, instead of flattening every matched file into /app/.
COPY --parents src/**/*.py /app/
```

### Build context hygiene

`COPY`'s source paths are resolved against the build context, not the
filesystem the Dockerfile lives in — and everything under the context root
that isn't excluded by `.dockerignore` is sent to the BuildKit daemon
before the first instruction even runs, regardless of whether any `COPY`
instruction ever references it. Copy discipline and `.dockerignore`
discipline are the same problem viewed from two ends:

- `.dockerignore` controls what's *available* to `COPY`/`ADD`, and what's
  transferred to the daemon at all.
- `COPY`'s own flags (`--chown`, `--chmod`, `--link`, `--parents`) control
  what happens to the subset actually copied.

Getting the first one wrong (see [missing `.dockerignore`](#anti-patterns))
makes every downstream copy-discipline rule moot — the file is being
disciplined about copying files that never should have entered the build
context in the first place.

### COPY vs. bind mount, for large repos

`COPY . .` in a monorepo copies the *entire* build context into a layer,
even for a service that only needs its own subdirectory. For a
dependency-install step specifically, prefer the bind-mount pattern from
[Cache and bind mounts](#cache-and-bind-mounts) — it never materializes a
layer at all. For the final source copy (the one that *does* need to
become part of the image), scope it to the service's own directory rather
than the repo root:

```dockerfile
# BAD — copies the whole monorepo into the api service's image.
COPY . /app

# GOOD — scoped to what this service actually ships.
COPY --chown=10001:10001 services/api /app
COPY --chown=10001:10001 libs/shared /app/libs/shared
```

---

## Base images

- **Default to a `-slim` (Debian, glibc) base for Python images.**
  `python:3.X-slim` is the 2026 consensus default — small, glibc-based,
  and every `manylinux` wheel on PyPI installs on it without a source
  build — https://pythonspeed.com/articles/alpine-docker-python/
- **Ban alpine for Python.** Alpine's musl libc is not glibc; most
  compiled Python wheels are built against `manylinux` (glibc) and either
  fail to install on alpine or silently fall back to a from-source build —
  slower, larger, and dependent on build toolchains the runtime image
  shouldn't have anyway. This is the house rule, not a style preference —
  https://pythonspeed.com/articles/alpine-docker-python/,
  https://www.chainguard.dev/supply-chain-security-101/best-python-docker-image-top-options-compared
- **CONTESTED — hardened bases vs. slim-everywhere.** Distroless /
  Chainguard-Wolfi bases carry a near-zero CVE count and ship no shell at
  all, which is exactly what makes them harder to debug — there's no
  `docker exec ... sh` into a live container to inspect a stuck process.
  `-slim` bases keep a shell and a full userland, at the cost of a larger
  CVE surface. There is no consensus; the common compromise is `-slim` for
  dev/staging (where you need to get in and poke around) and
  distroless/Wolfi for the production tier (where SBOM + near-zero CVE +
  no shell for an attacker to land in are the priority) —
  https://www.chainguard.dev/supply-chain-security-101/best-python-docker-image-top-options-compared,
  https://www.bigiron.cc/guides/distroless-vs-alpine-vs-debian-slim-base-image-choice

**Decision table.**

| Base | libc | Shell | CVE surface | Use when |
| --- | --- | --- | --- | --- |
| `python:3.X-slim` | glibc | yes (bash/dash) | moderate | default: dev, staging, most production |
| `python:3.X-alpine` | musl | yes (ash) | small binary, but wheel-build breakage | **BANNED for Python** — never |
| `gcr.io/distroless/python3` | glibc | none | near-zero | hardened prod, no in-container debugging need |
| `cgr.dev/chainguard/python` (Wolfi) | glibc | none (dev tag has one) | near-zero + SBOM/signature attached | hardened prod, wants SBOM+sig without a separate step |

Sources for the distroless and Wolfi rows:
https://github.com/GoogleContainerTools/distroless,
https://www.chainguard.dev/supply-chain-security-101/best-python-docker-image-top-options-compared

**Sketch — the same decision expressed as `FROM` lines.** These are
alternatives, not sequential stages of one build — pick one `FROM` per
tier, not all three:

```dockerfile
# Default — Debian slim, glibc, manylinux wheels install without a source build.
FROM python:3.14-slim@sha256:REPLACE_WITH_PINNED_DIGEST AS base

# BANNED for Python — musl libc breaks/forces-source-build manylinux wheels.
# FROM python:3.14-alpine AS base

# Hardened prod tier (CONTESTED — see above): near-zero CVE, no shell, SBOM
# and signature attached by Chainguard's build pipeline.
# FROM cgr.dev/chainguard/python:latest@sha256:REPLACE_WITH_PINNED_DIGEST AS base
```

This same alpine caveat does **not** apply uniformly to every language —
see [Node and Vite](#node-and-vite) for the one place this reference uses
an alpine-adjacent image deliberately, and why that's a different call.

### Why musl breaks wheels

Most published Python wheels on PyPI are built against the `manylinux`
ABI, which targets glibc. Alpine's C standard library is musl — binary
*and* symbol-incompatible with glibc at the level wheels are compiled to.
Installing a package with compiled extensions (`numpy`, `pydantic-core`,
`cryptography`, `psycopg2`, most of the scientific/ML stack) on alpine
either fails outright or falls back to compiling from source, which means
the *runtime* image now needs a full C toolchain, plus extra minutes per
build, plus a larger final image than the slim base it was meant to
shrink — https://pythonspeed.com/articles/alpine-docker-python/

```dockerfile
# On alpine: this either fails, or silently triggers a from-source build
# that pulls in gcc/musl-dev/etc. — the toolchain slim was avoiding.
FROM python:3.14-alpine
RUN apk add --no-cache gcc musl-dev libffi-dev  # ← needed just to compile
RUN pip install pydantic-core                     # ← still slower than slim
```

The apparent size win from alpine's smaller base evaporates the moment a
single compiled dependency needs a source build. It's what happens
*without* the extra `apk add` packages — a hard install failure for many
compiled dependencies — that makes the ban unconditional, not merely a
size tradeoff worth relitigating per project.

### Alpine elsewhere in this reference

The [Node and Vite](#node-and-vite) build stage does not use alpine
either — `node:22.11.0-slim` avoids the same class of native-addon
compilation issues some npm packages hit under musl. The one place this
reference does touch an alpine-family image is the *static file server*
stage, where `nginxinc/nginx-unprivileged` ships both a Debian and an
alpine variant; this reference pins the Debian variant specifically so
the ban's rationale — "don't fight musl for a compiled dependency" —
never has to be relitigated for a pure static-file server with no
compiled Python or Node dependencies running inside it at all.

---

## Pinning and updates

- **Pin every base image as `tag@sha256:digest`.** The tag is for human
  readability in review; the digest is what actually gets pulled —
  immutable, content-addressed, and unaffected by a registry tag being
  force-moved out from under you —
  https://docs.docker.com/build/building/best-practices/#pin-base-image-versions
- **Never digest-pin without automation.** A `tag@digest` pin freezes the
  image at that exact build — including its security patches. Pin it by
  hand and walk away, and six months later you're shipping a base image
  with six months of unpatched CVEs, indistinguishable from an unpinned
  `:latest` except that nobody notices the drift. Wire Renovate's
  `docker:pinDigests` preset (or Dependabot's docker ecosystem) so the
  digest bump arrives as a reviewable PR on a fixed cadence —
  https://docs.docker.com/build/building/best-practices/#pin-base-image-versions,
  https://docs.renovatebot.com/docker/

**Sketch.**

```dockerfile
# syntax=docker/dockerfile:1

# Tag for readability, digest for immutability — the pair is the pin.
# Renovate's docker:pinDigests preset keeps this current via PR, not by hand.
FROM python:3.14.0-slim@sha256:REPLACE_WITH_PINNED_DIGEST
```

```json
{
  "extends": ["config:recommended", "docker:pinDigests"]
}
```

The `docker:pinDigests` preset does two things: it converts existing
`FROM image:tag` lines to `FROM image:tag@digest` on first run, and it
opens a PR whenever the tag's underlying digest moves afterward. Either
half missing — pinning without the automation, or automation without the
pin — leaves you back at "pin it by hand and hope."

### Digest pinning beyond the base image

Every `COPY --from=<image>` and every stage's `FROM` is a pinning
surface, not just the first line of the file. The `uv` binary in the
[Python and uv](#python-and-uv) canonical Dockerfile is pulled from
`ghcr.io/astral-sh/uv:<version>@sha256:<digest>` — that pin needs the same
Renovate/Dependabot coverage as the base image, or it drifts
independently of everything else in the file. A Dockerfile with one
digest-pinned `FROM` and one floating `COPY --from=ghcr.io/astral-sh/uv:latest`
has only partially solved the problem —
https://docs.renovatebot.com/docker/

### Dependabot vs. Renovate

Both cover the docker ecosystem; the meaningful difference for this house
is that Renovate's `docker:pinDigests` preset performs the *initial*
tag→digest conversion for you (rewriting `FROM image:tag` to
`FROM image:tag@digest` in a PR) as well as the ongoing bump, while
Dependabot's docker ecosystem updates an *existing* digest pin but expects
the digest to already be present. Either is an acceptable choice — pick
one and wire it into CI, since "never digest-pin without automation" only
holds if something is actually watching — https://docs.renovatebot.com/docker/

---

## Python and uv

**Intent.** Install dependencies from a lockfile Docker never resolves
itself, in a layer that survives source edits, without shipping the
resolver (`uv`) or the source tree into the runtime image.

**Rules.**

- **Get `uv` via a pinned `COPY --from=ghcr.io/astral-sh/uv:<version>`,
  never `pip install uv` or a curl-piped-to-shell installer script inside
  the image.** The official uv image ships a static binary at `/uv` and
  `/uvx`; copying it in is one COPY, one pin, no extra Python interpreter
  invoked to install the tool that installs your dependencies —
  https://docs.astral.sh/uv/guides/integration/docker/#available-images
- **Set `UV_COMPILE_BYTECODE=1`, `UV_LINK_MODE=copy`, and
  `UV_NO_PROGRESS=1`.** `UV_COMPILE_BYTECODE=1` precompiles `.pyc` files at
  build time instead of on first import in prod (faster cold start);
  `UV_LINK_MODE=copy` avoids hardlinking across the cache-mount's separate
  filesystem, which would otherwise force a slower fallback copy anyway;
  `UV_NO_PROGRESS=1` keeps build logs free of progress-bar noise —
  https://docs.astral.sh/uv/guides/integration/docker/#optimizations
- **Two-phase sync: install dependencies with `--no-install-project`
  first, copy source, then sync the project itself.** Phase 1 depends only
  on the bind-mounted lockfile/manifest; phase 2's `COPY . .` is what a
  source edit invalidates, and it reruns only the (fast, no-network)
  project install — https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
- **`--locked` is mandatory — never let the container resolve
  dependencies at build time.** `--locked` and `--frozen` both refuse to
  re-resolve; the difference is `--locked` first checks that `uv.lock` is
  still consistent with `pyproject.toml` and fails the build loudly if
  it's drifted, while `--frozen` skips that consistency check and
  installs the lockfile exactly as it stands. Prefer `--locked` for the
  ordinary case — a stale lockfile should fail the build, not silently
  ship drifted dependencies — but treat the two as operationally
  equivalent for the actual guarantee that matters here: neither one lets
  uv hit the resolver at image-build time —
  https://docs.astral.sh/uv/guides/integration/docker/
- **Workspace variant: use `--frozen --no-install-workspace` for the
  deps-only phase.** In a uv workspace, the deps-only phase bind-mounts
  only the root lockfile/manifest — the member packages' own
  `pyproject.toml` files aren't present yet, because `--no-install-workspace`
  is explicitly skipping them. A `--locked` consistency check would fail
  against that incomplete workspace view for no real reason; `--frozen`
  sidesteps it. Run the ordinary `--locked`/`--frozen` sync (no
  `--no-install-workspace`) once source is copied in and the full
  workspace is visible — https://docs.astral.sh/uv/guides/integration/docker/
- **Runtime stage copies only `/app/.venv`, never `uv` itself.** Set
  `ENV PATH="/app/.venv/bin:$PATH"` so the venv's interpreter and
  console-script shims resolve first; the runtime image never needs to
  resolve or install anything, so it has no reason to carry the resolver —
  https://docs.astral.sh/uv/guides/integration/docker/#non-editable-installs
- **Add `.venv` to `.dockerignore`.** A host-built `.venv` copied into the
  build context is platform-specific (wrong libc, wrong Python ABI half
  the time) and, if it were ever COPYed in, would bust the cache on every
  local `uv sync` regardless of whether the lockfile actually changed —
  https://docs.astral.sh/uv/guides/integration/docker/#developing-in-a-container

**Sketch — the full canonical Dockerfile.**

```dockerfile
# syntax=docker/dockerfile:1

FROM python:3.14-slim@sha256:REPLACE_WITH_PINNED_DIGEST AS builder

# Pinned uv binary, copied in — never `pip install uv` or curl a script.
# Check https://github.com/astral-sh/uv/releases for the current release.
COPY --from=ghcr.io/astral-sh/uv:0.9.6@sha256:REPLACE_WITH_PINNED_DIGEST /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_PROGRESS=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Phase 1 — dependencies only. Bind-mount the lockfile and manifest instead
# of COPYing them: this layer's cache key is then exactly "did the lockfile
# change," so a source-only edit below never invalidates it.
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

# Phase 2 — copy source, install the project itself. --no-editable: no
# symlink back into a build-only stage that won't exist at runtime.
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv sync --locked --no-editable --no-dev

FROM python:3.14-slim@sha256:REPLACE_WITH_PINNED_DIGEST AS runtime

RUN groupadd --gid 10001 app && \
    useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app

# Runtime never gets uv — copy only the venv the builder produced.
COPY --from=builder --chown=10001:10001 /app/.venv /app/.venv
COPY --from=builder --chown=10001:10001 /app/src /app/src
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app
USER 10001

ENTRYPOINT ["python", "-m", "myapp"]
```

**Sketch — workspace variant of phase 1.**

```dockerfile
# Workspace variant — skip installing workspace-member packages until
# source is copied in; still never let the container resolve.
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-workspace --no-dev

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv sync --frozen --no-dev
```

**`.dockerignore` for the sketch above.**

```text
.venv
.git
__pycache__/
*.pyc
node_modules
dist
.env
```

**When NOT to use.** A short-lived script or a one-off Lambda-style
container with no meaningful dependency churn doesn't need the two-phase
split — a single `uv sync --locked --no-dev` after `COPY . .` is simpler
and the cache-layer benefit doesn't pay for the extra RUN instruction if
the image rebuilds from scratch every time anyway (e.g. CI images rebuilt
once per release, never iterated on locally).

**Anti-pattern variant.** See [Mutating dependencies inside a frozen
build](#anti-patterns) below — the failure mode specific to this pattern.

**Dev-loop note — anonymous volume over `.venv`.** In a Compose dev
override, bind-mounting the source tree over `/app` also shadows whatever
the image built at `/app/.venv` with the host's filesystem view — which is
empty unless you've also run `uv sync` on the host. Add an anonymous
volume scoped to `/app/.venv` so the *image's* venv stays mounted, layered
on top of the source bind mount:

```yaml
services:
  api:
    build: .
    volumes:
      - .:/app        # bind-mount source for the dev loop
      - /app/.venv     # anonymous volume — keeps the image's venv live
                       # instead of being shadowed by the bind mount above
```

— https://docs.astral.sh/uv/guides/integration/docker/#developing-in-a-container

### Multi-platform builds

`uv.lock` records resolution markers per platform/Python-version
combination in one lockfile — it does not need a separate lockfile per
target platform. Building `--platform linux/amd64,linux/arm64` with
`docker buildx build`, the two platform builds each run `uv sync --locked`
independently inside their own emulated/native stage; the lock step
doesn't change, but the *resolved* wheels selected per platform can
differ — a package with no `manylinux_aarch64` wheel falls back to source
on arm64 even though amd64 gets a prebuilt wheel. Worth checking before
assuming a clean amd64 build implies a clean arm64 one.

### FastAPI/uvicorn entrypoint note

For a FastAPI service specifically, run one process per container and let
the orchestrator (ECS, Kubernetes) handle replication — `--workers N`
belongs to a single-host/Compose deployment, not a task that's already
being horizontally scaled by task count. Set `--proxy-headers` when
uvicorn sits behind a TLS-terminating proxy or load balancer so it trusts
`X-Forwarded-*` correctly, and don't reach for the deprecated
`tiangolo/uvicorn-gunicorn` base images — they predate the two-phase uv
build in this reference and bundle process-management decisions this
Dockerfile makes explicitly instead —
https://fastapi.tiangolo.com/deployment/docker/

```dockerfile
ENTRYPOINT ["python", "-m", "uvicorn", "myapp.main:app", \
            "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
```

### Common pitfalls

- **Forgetting `--no-dev` in the runtime-bound sync.** Without it, dev
  dependencies (test runners, linters, type checkers) ship in the
  production image — larger, and a larger dependency-CVE surface for
  tools that never run in production.
- **Bind-mounting the lockfile but still relying on the phase-2 `COPY . .`
  for it.** Harmless but worth knowing: if `COPY . .` in phase 2 already
  copies the repo root, `uv.lock` and `pyproject.toml` arrive again
  through that COPY — phase 1's bind mount only ever mattered for scoping
  *that layer's* cache key to just those two files.
- **Setting `UV_PROJECT_ENVIRONMENT` to a path that doesn't match the
  runtime stage's `COPY --from=builder` source.** The env var controls
  where uv creates the venv in the builder stage; if the runtime stage
  copies from a different path, the copy silently does nothing (or copies
  an empty/missing directory) and the runtime image ships with no venv at
  all.
- **Running `uv sync` without any lock flag in a Dockerfile at all.** An
  unlocked `uv sync` resolves fresh — the one behavior every rule in this
  section exists to prevent. If a build succeeds locally and fails in CI
  (or vice versa) with a dependency-resolution difference, this is almost
  always why.

**References.**

- https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
- https://docs.astral.sh/uv/guides/integration/docker/#available-images
- https://docs.astral.sh/uv/guides/integration/docker/#optimizations
- https://docs.astral.sh/uv/guides/integration/docker/
- https://docs.astral.sh/uv/guides/integration/docker/#non-editable-installs
- https://docs.astral.sh/uv/guides/integration/docker/#developing-in-a-container

---

## Node and Vite

**Intent.** Build static assets with the full npm + Node toolchain, then
serve them from an image that contains neither Node nor the build
toolchain — only the compiled output and a static file server.

**Rules.**

- **Build stage: `npm ci` (not `npm install`) against a pinned, `-slim`
  Node base.** `npm ci` installs exactly what `package-lock.json` says,
  refusing to touch the lockfile — the reproducibility guarantee
  `npm install` doesn't give you —
  https://github.com/nodejs/docker-node/blob/main/docs/BestPractices.md
- **`vite build` writes static output to `dist/` by default; the static
  stage copies only that directory out.** Nothing else from the build
  stage — no `node_modules`, no source, no Node binary — belongs in the
  final image — https://vite.dev/guide/build
- **Static stage: a pinned, non-root static file server — nginx or
  Caddy — never the Node process itself.** `nginxinc/nginx-unprivileged`
  runs as a non-root UID out of the box and listens on 8080 (not 80,
  since an unprivileged process can't bind a port under 1024); if your
  `nginx.conf` still says `listen 80`, the container starts and then fails
  every request — https://github.com/nginxinc/docker-nginx-unprivileged
- **Define a `HEALTHCHECK`.** A static file server rarely wedges, but a
  malformed `nginx.conf` can start the process and still fail every
  request — a `HEALTHCHECK` catches that at the container level instead of
  waiting for the first user report —
  https://docs.docker.com/reference/dockerfile/#healthcheck

**Sketch.**

```dockerfile
# syntax=docker/dockerfile:1

FROM node:22.11.0-slim@sha256:REPLACE_WITH_PINNED_DIGEST AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm,sharing=locked \
    npm ci

COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27@sha256:REPLACE_WITH_PINNED_DIGEST AS static

COPY --from=build --chown=101:101 /app/dist /usr/share/nginx/html
# Custom conf must `listen 8080;` — the unprivileged base can't bind 80.
COPY --chown=101:101 nginx.conf /etc/nginx/conf.d/default.conf

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD ["wget", "--spider", "-q", "http://localhost:8080/healthz"]

EXPOSE 8080
```

**When NOT to use.** A pure API-only backend with no frontend build step
skips this section entirely; and a frontend team already running a
Node-based SSR server (Next.js, Remix in server mode) doesn't get to drop
Node from the runtime stage — the static-file split only applies when the
build output is genuinely static (a Vite SPA/MPA build with no server
runtime).

**Anti-pattern variant.** Shipping the `build` stage's image as the
runtime — `node_modules`, source, and the Node binary all present in
production to serve files nginx could serve alone — is the [single-stage
prod images](#anti-patterns) anti-pattern applied to this stack
specifically.

### Build-time env vars

Vite inlines any `import.meta.env.VITE_*` reference at build time — the
value is baked into the static JS bundle, not read at container startup.
Two consequences that matter for this Dockerfile shape:

- **The same built image cannot be promoted across environments with
  different `VITE_*` values.** A "build once, deploy everywhere" pipeline
  needs either a build-per-environment, or a post-build injection step
  that rewrites the static bundle (a small `env.js` fetched at runtime,
  populated from a real runtime source, referenced instead of a baked
  `VITE_*` value) — https://vite.dev/guide/build
- **Never pass a secret as a `VITE_*` build ARG.** It ends up readable in
  the shipped JavaScript, sent to every browser that loads the page — a
  strictly worse exposure than the [secrets via build
  ARG](#anti-patterns) anti-pattern, because the leak isn't confined to
  people with image-pull access; it's public the moment the bundle loads.

```dockerfile
# BAD — a real secret, baked into a static bundle every visitor downloads.
ARG VITE_API_SECRET
RUN --mount=type=cache,target=/root/.npm,sharing=locked \
    npm run build   # VITE_API_SECRET is now inside dist/assets/*.js
```

Non-secret configuration (an API base URL, a feature-flag default) is a
reasonable use of a `VITE_*` build ARG — the concern here is specifically
secrets, not build-time configuration in general.

### Caddy alternative

Caddy is a reasonable substitute for nginx as the static stage: automatic
HTTPS is irrelevant behind a load balancer that already terminates TLS,
but Caddy's config file is markedly simpler for the common "serve this
directory, healthcheck this path" case:

```dockerfile
FROM caddy:2.9@sha256:REPLACE_WITH_PINNED_DIGEST AS static
COPY --from=build /app/dist /srv
COPY Caddyfile /etc/caddy/Caddyfile
```

Neither choice changes the rules above — pin the digest, keep the image
non-root (Caddy's official image runs as root by default; add a `USER` or
switch to a rootless variant), and define a `HEALTHCHECK`.

**References.**

- https://github.com/nodejs/docker-node/blob/main/docs/BestPractices.md
- https://vite.dev/guide/build
- https://github.com/nginxinc/docker-nginx-unprivileged
- https://docs.docker.com/reference/dockerfile/#healthcheck

---

## Anti-patterns

Gallery of failing forms this reference exists to catch in review. Each
entry: the failing form, one line on why it bites, and the fix.

**Mutating dependencies inside a frozen build.**

```dockerfile
RUN uv add requests --no-sync
RUN uv sync --frozen
```

*Why it bites.* `uv add --no-sync` rewrites `pyproject.toml` and
`uv.lock` on disk but skips syncing; the following `uv sync --frozen` then
installs from that just-mutated lockfile — not the one committed to the
repo, reviewed in the PR, and scanned by CI. The image can silently ship a
dependency nobody approved.

*Fix.* Never run `uv add`/`uv remove` inside a Dockerfile. Resolve and
commit the lockfile change in the source repo; build from the committed
`uv.lock` with `uv sync --locked`, which would have caught this exact
manifest/lockfile mismatch and failed the build instead of installing it —
https://docs.astral.sh/uv/guides/integration/docker/

**`FROM x:latest`.**

```dockerfile
FROM python:latest
```

*Why it bites.* `latest` is a moving target — the same Dockerfile
produces a different, unreviewed base image on every rebuild. hadolint's
DL3006 rule exists specifically to flag this.

*Fix.* Pin `tag@sha256:digest` (see [Pinning and updates](#pinning-and-updates))
— https://github.com/hadolint/hadolint,
https://docs.docker.com/build/building/best-practices/#pin-base-image-versions

**Root runtime.**

```dockerfile
FROM python:3.14-slim
COPY . /app
CMD ["python", "/app/main.py"]
```

*Why it bites.* No `USER` instruction means the process runs as UID 0 —
a container-escape or path-traversal bug in the application now hands the
attacker root inside (and often outside) the container.

*Fix.* Create a dedicated non-root user with an explicit UID/GID and
switch to it with `USER` before `CMD`/`ENTRYPOINT` —
https://docs.docker.com/build/building/best-practices/#user

**Chown-after-copy layers.**

```dockerfile
COPY . /app
RUN chown -R app:app /app
```

*Why it bites.* `RUN chown` after `COPY` produces a second full layer
that duplicates the copied files' storage in the image's layer history —
the original ownership and the re-owned copy both persist — for something
a single COPY flag does in one layer.

*Fix.* `COPY --chown=app:app . /app` — set ownership at copy time —
https://docs.docker.com/reference/dockerfile/#copy

**ADD-for-COPY.**

```dockerfile
ADD . /app
```

*Why it bites.* `ADD` silently auto-extracts any archive it recognizes in
the source and can fetch remote URLs — behavior a plain file copy has no
business triggering, and behavior the next reader won't expect from what
looks like an ordinary copy.

*Fix.* `COPY . /app`; reserve `ADD` for its two legitimate uses (see
[Copy discipline](#copy-discipline)) —
https://docs.docker.com/build/building/best-practices/

**Secrets via build ARG.**

```dockerfile
ARG NPM_TOKEN
RUN echo "//registry.npmjs.org/:_authToken=${NPM_TOKEN}" > .npmrc && npm ci
```

*Why it bites.* `ARG` values are recorded in the image's build history and
in any cached layer that references them — visible to anyone with pull
access to the image, not just to the build process. A leaked registry
token is a supply-chain incident, not a close call.

*Fix.* Use a BuildKit secret mount, which is never written to a layer:
`RUN --mount=type=secret,id=npm_token npm ci`, supplied at build time with
`--secret id=npm_token,src=./token` — https://docs.docker.com/build/building/secrets/

**Missing `.dockerignore`.**

*Why it bites.* Without a `.dockerignore`, the entire build context —
`.git`, `node_modules`, `.venv`, local `.env` files, prior build output —
gets sent to the BuildKit daemon on every build. That bloats context
transfer time on every single build and, for anything that ends up
COPYed, busts the cache on files that were never meant to be part of the
image in the first place.

*Fix.* Ship a `.dockerignore` excluding `.git`, `.venv`, `node_modules`,
local env files, and build caches (see the [Python and uv](#python-and-uv)
sketch above for a worked example) —
https://docs.docker.com/build/concepts/context/#dockerignore-files

**Single-stage prod images.**

```dockerfile
FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:0.9.6 /uv /bin/
COPY . /app
RUN uv sync --locked
CMD ["python", "/app/main.py"]
```

*Why it bites.* The shipped runtime image now contains `uv` itself, the
full pre-install source tree, and every build-time-only tool the sync
step pulled in — expanding both image size and attack surface with things
that provide zero runtime value.

*Fix.* Multi-stage build; copy only the produced `.venv` and application
source into a clean final stage (see [Python and uv](#python-and-uv)) —
https://docs.docker.com/build/building/best-practices/

### Review checklist

Scan a new or changed Dockerfile for these in order — each maps back to
one entry above:

1. **Frozen build integrity.** Does any RUN mutate `pyproject.toml`/
   `uv.lock` (or `package.json`/lockfile) before a `--locked`/`--frozen`
   sync reads them?
2. **Tag hygiene.** Does every `FROM` and `COPY --from=<image>` carry
   `tag@sha256:digest`, with Renovate or Dependabot wired to bump it?
3. **Runtime identity.** Is there a `USER` instruction before `CMD`/
   `ENTRYPOINT`, and is it not UID 0?
4. **Ownership layers.** Does any `RUN chown`/`RUN chmod` follow a `COPY`
   that could have used `--chown`/`--chmod` instead?
5. **ADD usage.** Does every `ADD` instruction fall into one of the two
   legitimate uses — remote fetch with `--checksum`, or local archive
   auto-extraction?
6. **Secret handling.** Does any `ARG`/`ENV` carry a token, key, or
   password, instead of a `--mount=type=secret`?
7. **Context hygiene.** Does a `.dockerignore` exist, and does it exclude
   `.git`, dependency directories, and local env files?
8. **Stage count.** Does the final stage contain a build toolchain,
   resolver binary, or full source tree it doesn't need at runtime?

If the answer to any of these is "no" or "not sure," treat it as a
blocking review comment, not a nit — every one of the eight traces back to
a specific, cited rule above.

---

_Verified as of 2026-07; sources re-checked against docs/superpowers/research/2026-07-20-*.md._
