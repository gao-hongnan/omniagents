# Production Docker/Compose Rulebook Corpus — July 2026
(research digest from web-research agent; source material for omniagents-iac docker skill)

## 1. Dockerfile canon

- Start every Dockerfile with `# syntax=docker/dockerfile:1` (auto-tracks latest stable syntax; `:1-labs` only for experimental flags) — https://docs.docker.com/reference/dockerfile/
- Use multi-stage builds; final stage contains only runtime artifacts, never toolchains — https://docs.docker.com/build/building/best-practices/
- Order layers least→most volatile: base → deps manifest → dep install → source copy; dependency install must not be invalidated by source edits — https://docs.docker.com/build/building/best-practices/
- Use `RUN --mount=type=cache,target=<pkg-cache>` for package managers (apt, uv, npm); use `sharing=locked` when the manager can't handle concurrent access; `--mount=type=bind` for lockfiles instead of COPY — https://docs.docker.com/reference/dockerfile/#run---mounttypecache
- Always ship `.dockerignore` (exclude `.git`, `.venv`, `node_modules`, envs, caches) — https://docs.docker.com/build/concepts/context/#dockerignore-files
- Use heredocs (`RUN <<EOF`) for multi-command RUN instead of `&&` chains; `set -o pipefail` when piping — https://docs.docker.com/reference/dockerfile/#here-documents
- COPY flags: `--chown`/`--chmod` (set ownership at copy time, never a separate chown layer, syntax ≥1.2), `--link` for final-stage `COPY --from` (independent layers, rebase + better remote cache), `--parents` (syntax ≥1.20) to preserve directory structure — https://docs.docker.com/reference/dockerfile/#copy
- Prefer COPY over ADD always; ADD only for verified remote URL/tar cases — https://docs.docker.com/build/building/best-practices/
- Combine `apt-get update && apt-get install -y --no-install-recommends … && rm -rf /var/lib/apt/lists/*` in one RUN; sort multi-line package lists — https://docs.docker.com/build/building/best-practices/
- Base image for Python 2026 consensus: `python:3.X-slim` (Debian/glibc) is the default; AVOID alpine for Python (musl → wheel incompatibility/source builds) — https://pythonspeed.com/articles/alpine-docker-python/, https://www.chainguard.dev/supply-chain-security-101/best-python-docker-image-top-options-compared
- CONTESTED — hardened bases: distroless/Chainguard-Wolfi (glibc, near-zero CVE, SBOM+signature included) for compliance-driven prod VS slim everywhere for debuggability (no shell in distroless); common compromise: slim for dev/staging, distroless/Wolfi for prod — https://www.chainguard.dev/supply-chain-security-101/best-python-docker-image-top-options-compared, https://www.bigiron.cc/guides/distroless-vs-alpine-vs-debian-slim-base-image-choice
- Pin base images as `tag@sha256:digest` (tag for readability, digest for immutability); pair with automated digest-bump PRs — never digest-pin without automation (freezes security patches) — https://docs.docker.com/build/building/best-practices/#pin-base-image-versions, https://docs.renovatebot.com/docker/

## 2. Runtime hardening

- Create a dedicated non-root user with explicit UID/GID and `USER` before CMD; never run app as root — https://docs.docker.com/build/building/best-practices/#user
- Run with read-only rootfs (`read_only: true` + tmpfs for scratch paths), `cap_drop: [ALL]` + add back only needed caps, `security_opt: ["no-new-privileges:true"]`, never `privileged` — CIS Docker Benchmark v1.6/v1.7 §5 — https://www.cisecurity.org/benchmark/docker, https://github.com/docker/docker-bench-security
- PID 1: use exec-form `ENTRYPOINT`/`CMD` only (shell form blocks signal delivery); add an init reaper — `init: true` in compose / `docker run --init` / tini explicitly when the platform can't inject one — https://docs.docker.com/reference/dockerfile/#exec-form-entrypoint-example, https://github.com/krallin/tini
- Wrapper entrypoint scripts must end `exec "$@"` so the server replaces the shell and receives SIGTERM — https://docs.docker.com/build/building/best-practices/#entrypoint
- Uvicorn/FastAPI: one process per container when an orchestrator replicates; `--workers N` only for single-host/compose deployments; `--proxy-headers` behind TLS proxy; deprecated tiangolo/uvicorn-gunicorn images must not be used — https://fastapi.tiangolo.com/deployment/docker/
- HEALTHCHECK: define per-service (compose-level for compose deployments — Kubernetes ignores Dockerfile HEALTHCHECK); exec-form test with no curl dependency on slim/distroless (use app-native check); set `interval`, `timeout`, `retries`, `start_period` explicitly — https://docs.docker.com/reference/dockerfile/#healthcheck, https://docs.docker.com/reference/compose-file/services/#healthcheck
- Always set memory+CPU limits per container; audit hosts with docker-bench-security (script of CIS checks) — https://github.com/docker/docker-bench-security

## 3. Python + uv specifics

- Canonical two-phase install (official uv guide): builder stage runs `RUN --mount=type=cache,target=/root/.cache/uv --mount=type=bind,source=uv.lock,… --mount=type=bind,source=pyproject.toml,… uv sync --locked --no-install-project` (deps-only cacheable layer), then `COPY . .` + `uv sync --locked --no-editable` — https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
- Get uv via `COPY --from=ghcr.io/astral-sh/uv:<pinned-version> /uv /uvx /bin/` onto `python:3.X-slim`, or use `ghcr.io/astral-sh/uv:pythonX.Y-…` derived images; pin the uv version — https://docs.astral.sh/uv/guides/integration/docker/#available-images
- Set `ENV UV_COMPILE_BYTECODE=1` (faster cold start in prod) and `UV_LINK_MODE=copy` (cache mount on separate fs); `UV_NO_DEV=1`/`--no-dev` to exclude dev deps — https://docs.astral.sh/uv/guides/integration/docker/#optimizations
- `--locked` (or `--frozen`) is mandatory in images — never let the container resolve; use `--frozen --no-install-workspace` first for workspaces — https://docs.astral.sh/uv/guides/integration/docker/
- Runtime stage: copy only `/app/.venv` from builder (`COPY --from=builder /app/.venv`), set `ENV PATH="/app/.venv/bin:$PATH"`, do not ship uv itself or source when `--no-editable` — https://docs.astral.sh/uv/guides/integration/docker/#non-editable-installs
- Add `.venv` to `.dockerignore`; dev loop mounts source with anonymous volume shadowing `/app/.venv` — https://docs.astral.sh/uv/guides/integration/docker/#developing-in-a-container

## 4. Supply chain

- Build with `--provenance=mode=max --sbom=true` (buildx); SBOM is opt-in, provenance defaults to mode=min; attestations attach as in-toto/SLSA manifests in the image index — https://docs.docker.com/build/metadata/attestations/
- Sign images in CI with cosign keyless (OIDC via Fulcio + Rekor transparency log) — the 2026 default for OSS/GitHub-Actions shops; Notation for enterprise PKI/trust-store models; Docker Content Trust is retired — https://github.com/sigstore/cosign, https://notaryproject.dev/, https://docs.sigstore.dev/cosign/signing/signing_with_containers/
- Scanning 2026 default: Trivy as primary all-in-one gate (CVE + IaC + secrets + licenses, offline-capable); Grype as second-opinion CVE matcher on critical images; Docker Scout is a Docker-Desktop-native complement, not a replacement — https://github.com/aquasecurity/trivy, https://github.com/anchore/grype, https://www.aikido.dev/blog/top-container-scanning-tools
- Lint every Dockerfile with hadolint in CI (includes ShellCheck on RUN); key gates DL3006 (untagged FROM), DL3008 (unpinned apt), DL3002 (last USER root); config in `.hadolint.yaml`, per-line ignores as comments — https://github.com/hadolint/hadolint
- Automate base-image/digest bumps with Renovate (`docker:pinDigests` preset keeps `tag@digest` fresh via PRs) or Dependabot docker ecosystem; weekly cadence — https://docs.renovatebot.com/docker/

## 5. Compose canon

- Never write top-level `version:` — obsolete, warning-only; Compose always validates against latest schema; use `name:` for the project — https://docs.docker.com/reference/compose-file/version-and-name/
- File layering: `compose.yaml` (canonical base) + `compose.override.yaml` (dev, auto-loaded) + `compose.prod.yaml` applied explicitly with `-f compose.yaml -f compose.prod.yaml`; use `extends`/`include` when merge rules grow complex — https://docs.docker.com/compose/how-tos/multiple-compose-files/, https://docs.docker.com/compose/how-tos/production/
- Profiles are for optional services within one environment (debug tools, admin UIs), not for environment splits — services without `profiles:` always run; activate via `--profile`/`COMPOSE_PROFILES` — https://docs.docker.com/compose/how-tos/profiles/
- Gate startup ordering with long-form `depends_on: {db: {condition: service_healthy}}` (+ `restart: true` for dependency updates); requires a healthcheck on the dependency; every long-running service defines a healthcheck — https://docs.docker.com/reference/compose-file/services/#depends_on
- Secrets: prefer compose `secrets:` (mounted read-only at `/run/secrets/<name>`, file or environment source) over environment variables for credentials — env vars leak via `docker inspect`, logs, and child processes — https://docs.docker.com/compose/how-tos/use-secrets/
- Restart policy: `unless-stopped` (or `always`) for prod services; `no` stays default for one-shot jobs — https://docs.docker.com/reference/compose-file/services/#restart
- Resource limits: use `deploy.resources.limits/reservations` (honored by non-Swarm `docker compose up`); legacy `mem_limit`/`cpus` are superseded — https://docs.docker.com/reference/compose-file/deploy/#resources
- Data: named volumes for persistent service state; bind mounts only for dev source-sync and host-owned config — https://docs.docker.com/reference/compose-file/services/#volumes
- Dev loop: `develop.watch` with `action: sync` for source (`ignore: [.venv/]`) and `action: rebuild` on `pyproject.toml`/lockfile — https://docs.docker.com/compose/how-tos/file-watch/
- env_file: `.env` (git-ignored) for interpolation defaults, `env_file:` for container env; `environment:` overrides `env_file`; commit only `.env.sample` — https://docs.docker.com/compose/how-tos/environment-variables/
- Single-host production on Compose is legitimate in 2026 (Docker documents it) IF you close the gaps: digest-pinned images, healthchecks + restart policies, resource limits, secrets, log rotation, protected docker socket, and an update path; multi-host/self-healing needs an orchestrator — https://docs.docker.com/compose/how-tos/production/, https://distr.sh/blog/running-docker-in-production/
- Prod file must strip dev bind mounts and debug ports, set `restart:`, and configure logging — https://docs.docker.com/compose/how-tos/production/

## 6. Image / tag / release conventions

- Stamp standard OCI annotations: `org.opencontainers.image.{source,revision,version,created,title,description,licenses}` — generated automatically by docker/metadata-action — https://github.com/opencontainers/image-spec/blob/main/annotations.md, https://github.com/docker/metadata-action
- Tag every push with the immutable git SHA; releases additionally get semver triplet (`1.4.2` immutable, `1.4`/`1` floating); ban `:latest` in production deploy manifests (deploy by digest or exact tag); enable registry immutable-tag enforcement where available — https://podostack.com/p/docker-image-tagging-strategies, https://oneuptime.com/blog/post/2026-02-02-docker-image-tagging/view
- Publish multi-arch (`linux/amd64,linux/arm64`) via buildx manifest lists — arm64 is mainstream (Graviton/Apple) — https://docs.docker.com/build/building/multi-platform/
- Registry hygiene: lifecycle policies to expire untagged + aged SHA tags (e.g. ECR lifecycle rules), keep release tags indefinitely — https://docs.aws.amazon.com/AmazonECR/latest/userguide/LifecyclePolicies.html

## 7. CI shape

- Build/push with docker/build-push-action + `cache-from: type=gha` / `cache-to: type=gha,mode=max` (mode=max caches all stages); requires Buildx ≥0.21 (GitHub Cache API v2, mandatory since 2025-04-15); fall back to `type=registry,mode=max` when GHA cache limits bite — https://docs.docker.com/build/ci/github-actions/cache/
- Multi-arch in CI: matrix of native runners (`ubuntu-24.04` + `ubuntu-24.04-arm`), push per-arch digests, merge with `buildx imagetools create` (or Docker's GitHub Builder reusable workflows which automate the split/merge); QEMU single-job only for small/simple images — https://docs.docker.com/build/ci/github-actions/multi-platform/
- Pipeline gate order: hadolint → build (with `--provenance --sbom`) → Trivy scan failing on HIGH/CRITICAL (with `.trivyignore` for accepted findings) → cosign sign → push; tags/labels from docker/metadata-action — https://github.com/hadolint/hadolint, https://github.com/aquasecurity/trivy-action, https://docs.docker.com/build/metadata/attestations/

## What changed 2024 → 2026

- uv displaced pip/poetry in Python images; the astral-sh two-phase `uv sync --locked --no-install-project` + venv-copy pattern is now the canonical Python Dockerfile.
- Compose spec fully killed `version:`; `develop.watch`, `depends_on: service_healthy`, and non-Swarm `deploy.resources` made compose a complete single-host prod story.
- Supply chain went default-on: `--sbom`/`--provenance` at build, cosign keyless in CI, digest pinning + Renovate automation replaced "pin a tag and hope"; Docker Content Trust retired.
- Base-image debate settled against Alpine-for-Python (musl); moved to slim-by-default with distroless/Chainguard-Wolfi (glibc, near-zero-CVE) as the hardened prod tier.
- CI: GitHub Cache API v2 forced Buildx ≥0.21 for `type=gha`; free hosted arm64 runners made native-runner matrix builds the multi-arch norm over QEMU.
