---
name: docker
description: >-
  Use when writing or reviewing Dockerfiles or docker-compose files with
  production discipline: multi-stage builds, BuildKit cache mounts,
  base-image choice and digest pinning, non-root runtime, exec-form and
  PID-1 signal handling, healthchecks, the canonical uv two-phase Python
  install, compose file layering vs profiles, service_healthy dependency
  gating, compose secrets, resource limits, SBOM/provenance, image
  scanning and signing, tag strategy, and CI build-push shape.
when_to_use: >-
  Trigger for Dockerfile*, compose*.yaml, docker-compose*.yml,
  .dockerignore, .hadolint.yaml, image build failures, layer-cache
  misses, container security hardening, uv-in-Docker patterns, Vite
  static-build stages, compose dev/prod splits, healthcheck or
  depends_on design, registry tagging, multi-arch builds, hadolint or
  trivy gates, or "is this image production-grade" tiering questions.
disable-model-invocation: false
user-invocable: true
allowed-tools: []
model: inherit
paths:
  - "**/Dockerfile*"
  - "**/compose*.yml"
  - "**/compose*.yaml"
  - "**/docker-compose*.yml"
  - "**/docker-compose*.yaml"
  - "**/.dockerignore"
  - "**/.hadolint.yaml"
shell: bash
---

# Docker & Compose Production Rulebook

House rules for Docker/BuildKit and the Compose Specification — the
`# syntax=docker/dockerfile:1` + non-Swarm-`deploy.resources` era, where
`uv` is the default Python installer and `version:` is dead. Pin your
actual BuildKit/Compose floor and raise it deliberately, never drift it.
CONTESTED rules (distroless-vs-slim, compose-in-prod) carry both
positions inline — pick one and name why, don't split the difference
silently.

## Default posture

Surface these twelve non-negotiables whenever a proposed Dockerfile or
compose file violates them. Point at the exact rule rather than
re-arguing from first principles — the reference files below carry the
full rationale and source links.

- **`# syntax=docker/dockerfile:1` is line one of every Dockerfile.** It
  auto-tracks the latest stable Dockerfile syntax; reach for `:1-labs`
  only when you deliberately need an experimental flag —
  https://docs.docker.com/reference/dockerfile/
- **Multi-stage, always.** The final stage ships runtime artifacts only
  — compilers, build caches, and package-manager metadata never survive
  into it. A Dockerfile with one `FROM` and a toolchain in the shipped
  image is a review-blocking finding, not a style nit —
  https://docs.docker.com/build/building/best-practices/
- **Non-root `USER` with an explicit UID/GID, set before `CMD`.** Never
  run the application as root; a container that starts as root and
  drops privileges later still shipped a root-capable image —
  https://docs.docker.com/build/building/best-practices/#user
- **Exec-form `ENTRYPOINT`/`CMD`, plus an init reaper.** Shell form
  blocks signal delivery, so `SIGTERM` never reaches the app and
  shutdown hangs until `SIGKILL`; pair exec-form with `init: true`
  (compose) / `docker run --init` / an explicit `tini` when the
  platform doesn't inject one —
  https://docs.docker.com/reference/dockerfile/#exec-form-entrypoint-example
- **`COPY`, not `ADD`.** `ADD`'s remote-URL and auto-extract behavior is
  implicit and unauditable; reach for it only in the rare verified
  remote-tar case —
  https://docs.docker.com/build/building/best-practices/
- **Base images pinned `tag@sha256:digest`, WITH automated bumps.** The
  tag keeps the Dockerfile readable, the digest makes the build
  immutable; digest-pinning without a bump automation (Renovate
  `docker:pinDigests`, Dependabot docker ecosystem) freezes security
  patches — that is worse than an unpinned tag, not safer. Never
  digest-pin without automation —
  https://docs.docker.com/build/building/best-practices/#pin-base-image-versions,
  https://docs.renovatebot.com/docker/
- **`.dockerignore` always.** Exclude `.git`, `.venv`, `node_modules`,
  env files, and caches from the build context on every image, not just
  the ones that seem to need it —
  https://docs.docker.com/build/concepts/context/#dockerignore-files
- **Healthcheck on every long-running service.** Compose-level
  `healthcheck:` for compose deployments (Kubernetes ignores the
  Dockerfile `HEALTHCHECK` instruction); exec-form test with no `curl`
  dependency on slim/distroless bases — use an app-native check; set
  `interval`, `timeout`, `retries`, `start_period` explicitly —
  https://docs.docker.com/reference/compose-file/services/#healthcheck
- **No compose `version:` key.** It is obsolete and warning-only;
  Compose always validates against the latest schema. Use `name:` for
  the project identifier instead —
  https://docs.docker.com/reference/compose-file/version-and-name/
- **Secrets never as environment variables.** `environment:`/`ENV`
  values leak through `docker inspect`, process listings, and logs; use
  compose `secrets:` (mounted read-only under `/run/secrets/<name>`) or
  a runtime secret store —
  https://docs.docker.com/compose/how-tos/use-secrets/
- **Memory and CPU limits everywhere.** `deploy.resources.limits` (not
  legacy `mem_limit`/`cpus`, which non-Swarm `docker compose up` still
  honors but which are superseded); an unlimited container is a noisy
  neighbor waiting to happen —
  https://docs.docker.com/reference/compose-file/deploy/#resources
- **`--locked`/`--frozen` installs only — the container never
  resolves.** `uv sync --locked`, `npm ci`, or the equivalent frozen
  install for every package manager in every image; a build that
  resolves dependencies at image-build time is non-reproducible by
  definition —
  https://docs.astral.sh/uv/guides/integration/docker/

## Tiering

| Control | T1 demo/portfolio | T2 production | T3 regulated |
|---|---|---|---|
| Encryption in transit + AUTH | optional (VPC-scoped SG suffices) | required | required (mandated wrappers) |
| At-rest encryption | provider default | provider default or CMK | CMK + key policy |
| HA / replicas / failover | no | required for stateful path | required |
| Backups / snapshots | no | required (retention named) | required + tested restore |
| Log delivery / audit | no | error+slow logs | full delivery + retention policy |
| Alarms / notifications | no | memory/error alarms | + SNS ops hooks |

Every control names its tier and its pain. A T1 stack passing T1 is
correct, not negligent — enterprise-grade means knowing your tier, not
maximal knobs.

Applied to containers: SBOM, provenance attestations, and image signing
(cosign) are T2+ — a T1 portfolio image with no CI has nothing to
attach them to, and that is correct, not a gap. Read-only rootfs +
`cap_drop: [ALL]` are T2+ — the CIS hardening posture earns its
operational cost (debugging a read-only container needs a sidecar or
`docker exec --user root`) once the workload is production-real.
Distroless/Wolfi base images are T3-or-named-pain — trade the shell and
package manager for near-zero CVE surface only when a compliance
requirement or a specific incident names the pain; T1 gets the posture
list above and nothing more. Adding T2/T3 controls to a T1 image is
unreviewed scope creep nobody asked for, same as in the Terraform
tiering table.

## Stack quick-paths

**(a) Python + uv canonical two-phase build.** Deps layer stays cached
across source edits; runtime stage ships only the venv, never uv or the
toolchain.

```dockerfile
# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.5.11@sha256:REPLACE_WITH_PINNED_DIGEST AS uv

FROM python:3.14-slim@sha256:REPLACE_WITH_PINNED_DIGEST AS builder
COPY --from=uv /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app

# Deps-only layer: cache-mount the uv cache, bind-mount lockfiles so
# editing source never busts this layer.
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

# Now the source — this layer busts on every edit, deps layer above
# does not.
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv sync --locked --no-editable --no-dev

FROM python:3.14-slim@sha256:REPLACE_WITH_PINNED_DIGEST AS runtime
RUN groupadd --gid 1000 app && \
    useradd --uid 1000 --gid app --no-create-home app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:${PATH}"
WORKDIR /app
COPY --chown=app:app . .
USER app:app
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import sys; sys.exit(0)"]
ENTRYPOINT ["python", "-m"]
CMD ["myapp.cli"]
```

**(b) Node/Vite build → static-server stage.** Build stage never ships;
runtime stage is a pinned, non-root static server.

```dockerfile
# syntax=docker/dockerfile:1
FROM node:22-slim@sha256:REPLACE_WITH_PINNED_DIGEST AS build
WORKDIR /app

# Deps layer cached independently of source edits.
RUN --mount=type=cache,target=/root/.npm \
    --mount=type=bind,source=package.json,target=package.json \
    --mount=type=bind,source=package-lock.json,target=package-lock.json \
    npm ci

COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27-alpine@sha256:REPLACE_WITH_PINNED_DIGEST AS runtime
# nginx-unprivileged already runs as a non-root `nginx` user on ports
# >1024 — no separate USER step needed; verify UID if you swap images.
COPY --from=build --chown=nginx:nginx /app/dist /usr/share/nginx/html
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["wget", "-q", "-O", "/dev/null", "http://localhost:8080/"]
EXPOSE 8080
ENTRYPOINT ["nginx"]
CMD ["-g", "daemon off;"]
```

## Reference index

| File | Read when… |
| --- | --- |
| [`references/dockerfile.md`](references/dockerfile.md) | Authoring or reviewing a Dockerfile: layer ordering, cache/bind mounts, heredocs, `COPY` flags (`--chown`/`--chmod`/`--link`/`--parents`), base-image choice (slim vs Alpine-for-Python vs distroless/Wolfi), digest pinning + Renovate, the full uv two-phase pattern including workspaces, the Vite build-stage pattern, or diagnosing an anti-pattern (mutating deps inside a frozen build, `:latest` bases, root runtime, chown-after-copy, ADD-for-COPY). |
| [`references/compose.md`](references/compose.md) | Structuring or reviewing a compose setup: spec baseline (`name:`, no `version:`), base + override + explicit `-f` prod layering vs profiles, long-form `depends_on` with `condition: service_healthy`, compose `secrets:` mechanics, restart policies, `deploy.resources`, named volumes vs binds, `develop.watch`, `env_file` + `.env.sample` conventions, or the single-host-production-on-compose checklist. |
| [`references/hardening-and-supply-chain.md`](references/hardening-and-supply-chain.md) | Hardening runtime or the build pipeline: CIS-derived controls (read-only rootfs + tmpfs, `cap_drop: [ALL]`, `no-new-privileges`, never `privileged`), PID-1/signal discipline and `exec "$@"` wrappers, the uvicorn one-process-per-container model, hadolint rules and `.hadolint.yaml`, Trivy/Grype scanning, SBOM + provenance attestations, cosign keyless signing, or docker-bench-security audits. |
| [`references/ci-and-release.md`](references/ci-and-release.md) | Wiring or reviewing CI build-push: `type=gha,mode=max` cache and the Buildx ≥0.21 requirement, multi-arch via native-runner matrix + `imagetools create`, metadata-action OCI labels, tag strategy (immutable SHA + semver, `:latest` banned from prod), registry lifecycle policies, or the hadolint → build → Trivy → cosign → push gate order. |

Read only the reference relevant to the current decision. Each file
carries its own headings; cite a specific rule as
`references/<file>.md#<anchor>`, where `<anchor>` is the kebab-case
slug of the heading text exactly as written — for example
`compose.md#secrets` or `hardening-and-supply-chain.md#scanning`.

## What this skill does NOT cover

- **Kubernetes manifests or Helm.** Different orchestration surface,
  different rulebook — a `Deployment`/`Pod` spec or a Helm chart is out
  of scope even when it wraps one of the images built here.
- **Orchestrator choice.** Whether a workload belongs on ECS, Nomad,
  Kubernetes, or plain compose is an infrastructure decision made
  before this skill applies, not a Dockerfile/compose authoring
  question.
- **Registry operations beyond lifecycle policy.** Registry
  provisioning, replication, and access control live with the
  infrastructure that hosts the registry, not with the image or
  compose file that pushes to it — this skill stops at tag strategy and
  expiry rules.
- **VM provisioning.** Host-level infrastructure — the EC2 instance,
  the ECS cluster, the network it sits in — is the `terraform` skill's
  domain; route there for anything that provisions the machine this
  container eventually runs on.

If a question lands outside this scope, say so rather than bending one
of the references to fit. If a question lands inside the scope but the
answer isn't in the references yet, that is a signal the catalogue
should be extended — flag it and propose the addition rather than
improvising silently.
