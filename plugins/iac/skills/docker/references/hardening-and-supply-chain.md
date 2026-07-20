# Hardening & Supply Chain

Catalogue-depth reference for the docker skill's runtime-posture and
supply-chain rules. `SKILL.md`'s Default posture list states each
non-negotiable in one line; this file carries the full rationale,
citations, and sketches behind them. Sibling references cover
adjacent ground: Dockerfile layer mechanics live in
`references/dockerfile.md`, compose service wiring (profiles,
`depends_on`, secrets, resource limits at the compose layer) lives in
`references/compose.md`, and CI pipeline shape plus tag/release
conventions live in `references/ci-and-release.md`. This file owns
everything from "what runs inside the container and how it dies" —
runtime hardening, PID 1 and signal handling, process model,
healthchecks — through "how the image is proven trustworthy before it
ships" — linting, scanning, SBOM/provenance, signing, audit.

House rule, non-negotiable: **Trivy is the primary scanner** — CVE +
IaC + secrets + licenses in one offline-capable binary, the same
house scanner the terraform skill mandates in its
`fmt → validate → tflint → trivy → plan → apply` gate pipeline
(`terraform/references/security-and-gates.md`). Grype is a second
opinion run specifically on critical images. Docker Scout is a
Docker-Desktop-native complement for local dev-loop feedback, never a
CI gate substitute. None of that is contestable within this skill —
see [Scanning](#scanning) below for the mechanics.

Every rule in this file traces back to the docker-compose-canon
research digest §2 (Runtime hardening) and §4 (Supply chain); each
rule below carries its source URL inline rather than restating the
digest as an opaque table.

## Runtime hardening

The posture in this section composes into one assumption: treat the
container as already compromised and minimize what that gets an
attacker. Each rule closes one specific escape hatch; skipping one
doesn't just weaken "defense in depth" in the abstract, it reopens a
concrete, named attack.

### Non-root user with explicit UID/GID

Create a dedicated user and switch to it with `USER` before the final
`CMD`/`ENTRYPOINT` — never let the app run as root inside the
container.

```dockerfile
RUN groupadd --gid 10001 app \
 && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
USER 10001:10001
```

Use an explicit numeric UID/GID (`10001:10001`, not a bare username)
for three reasons: it survives base images that ship no `/etc/passwd`
entry for your app user at all (distroless, Wolfi), it lets an
orchestrator's own `runAsUser`/`--user` override match cleanly against
a known number instead of a name lookup, and it avoids accidental UID
collision with a host-mapped range in user-namespace setups. Pick a
UID above the reserved system range (below 1000 on most distros) and
keep it stable across image rebuilds — a UID that changes between
releases breaks ownership on any bind-mounted or volume-persisted
data written by the previous UID.
Source: <https://docs.docker.com/build/building/best-practices/#user>

### Read-only root filesystem + tmpfs scratch

Run the container's root filesystem read-only and mount `tmpfs` for
the specific paths the process needs to write:

```yaml
read_only: true
tmpfs:
  - /tmp
  - /var/run
```

A read-only rootfs means an attacker who gets code execution inside
the container cannot write a webshell, replace a binary, or persist a
backdoor anywhere in the image filesystem — every write attempt
outside the declared `tmpfs`/volume paths fails outright. The cost is
that any app behavior that assumes an ambient writable filesystem
(cache directories, PID files, log files written to disk instead of
stdout) needs an explicit `tmpfs` entry or a named volume. Audit your
actual app's write paths before flipping this on in production —
`/tmp` covers most Python apps' default cache/tempfile behavior, but
anything using a library-specific cache directory (model weight
caches, font caches) needs its own entry.
Source: CIS Docker Benchmark v1.6/v1.7 §5 —
<https://www.cisecurity.org/benchmark/docker>

### Drop all capabilities, add back only what's needed

```yaml
cap_drop:
  - ALL
cap_add:
  - NET_BIND_SERVICE # only if binding a port <1024
```

Linux capabilities split root's monolithic power into ~40 named
grants (`CAP_NET_BIND_SERVICE`, `CAP_CHOWN`, `CAP_SYS_ADMIN`, and so
on); a default container keeps a broad subset even when running as a
non-root user, because capabilities and UID are orthogonal controls.
`cap_drop: [ALL]` starts from zero and forces every capability the
process genuinely needs back in by name — a deliberate allow-list
instead of an implicit grant. Most FastAPI/uvicorn-style web services
need **zero** added-back capabilities: binding to `8000` doesn't
require `CAP_NET_BIND_SERVICE` (that's only for ports below 1024,
which you shouldn't be binding inside a container behind a proxy
anyway). Only add a capability back when a concrete, named syscall
requires it — never add back a broad capability "just in case."
Source: `capabilities(7)` —
<https://man7.org/linux/man-pages/man7/capabilities.7.html> and CIS
Docker Benchmark §5 — <https://www.cisecurity.org/benchmark/docker>

### `no-new-privileges:true`

```yaml
security_opt:
  - "no-new-privileges:true"
```

This closes a narrower but distinct hole from capability-dropping:
even a process with a minimal capability set can regain privilege at
runtime through a setuid/setgid binary or a file capability baked
into an image layer (`sudo`, `ping`, anything with `cap_setuid` on
disk). `no-new-privileges` tells the kernel to refuse any `execve()`
that would grant more privilege than the calling process already has,
regardless of what's on disk. Set it on every service unconditionally
— it has no legitimate downside for an application container.

### Never `privileged`

Never set `privileged: true` (or `docker run --privileged`) on an
application service. Privileged mode disables almost every isolation
mechanism this section builds — full capability set, direct device
access, no seccomp/AppArmor confinement — effectively making the
container root on the host. The only legitimate uses are
Docker-in-Docker build runners and direct hardware access (camera
capture, USB passthrough); neither applies to a web API, worker, or
static-file server. If a dependency claims it "needs privileged mode,"
that's a signal to find the specific capability it actually needs and
add that back individually instead.

### Memory and CPU limits on every container

```yaml
deploy:
  resources:
    limits:
      cpus: "1.0"
      memory: 512M
    reservations:
      memory: 256M
```

Resource limits aren't a security control in the capability/rootfs
sense above, but they bound the blast radius of a compromised or
merely buggy container the same way capability-dropping bounds what a
compromised process can *do* — a container with a memory leak, a fork
bomb, or a runaway request queue cannot starve every other service on
the same host once it hits its ceiling. `deploy.resources` is honored
by non-Swarm `docker compose up` in modern Compose; the legacy
top-level `mem_limit`/`cpus` keys are superseded — see
`references/compose.md` for the full compose-layer treatment.
Source: <https://docs.docker.com/reference/compose-file/deploy/#resources>

### CIS Docker Benchmark §5 cross-reference

The controls above map onto commonly-cited numbering from the CIS
Docker Benchmark v1.6/v1.7 §5 (Container Runtime) line. Point releases
occasionally renumber individual controls — re-check the specific
number against the current PDF before citing it in an audit
deliverable; the *substance* of each control is stable even when the
number shifts.

| Control (v1.6/v1.7 line, verify before citing) | Requirement | Rule in this section |
| --- | --- | --- |
| §5.3 | Restrict Linux kernel capabilities | `cap_drop: [ALL]` + selective `cap_add` |
| §5.4 | Do not use privileged containers | never `privileged: true` |
| §5.10 / §5.11 | Set memory / CPU priority limits | `deploy.resources.limits` |
| §5.12 | Mount container's root filesystem read-only | `read_only: true` + `tmpfs` |
| §5.25 | Restrict a container from acquiring additional privileges | `security_opt: ["no-new-privileges:true"]` |
| §5.28 | Use the PIDs cgroup limit | `pids_limit` (fork-bomb containment; pair with the memory/CPU limits above) |

Source for the full control text and current numbering:
<https://www.cisecurity.org/benchmark/docker>. The automated
implementation of this whole benchmark is `docker-bench-security` —
see [Audit](#audit) below.

### Compose hardening block sketch

All of the above composed into one service block:

```yaml
services:
  api:
    image: ghcr.io/org/app:1.4.2@sha256:<digest>
    read_only: true
    tmpfs:
      - /tmp
    cap_drop:
      - ALL
    security_opt:
      - "no-new-privileges:true"
    user: "10001:10001"
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 512M
```

Twelve lines, every one of them closing a specific escape hatch
described above — none of it is decorative. A service block missing
any one of `read_only`, `cap_drop: [ALL]`, `no-new-privileges`, or an
explicit `user:` is a review-blocking finding on a production compose
file, the same way an undescribed Terraform variable is in the
terraform skill's own default posture.

### Where hardening can wait

Non-root and never-`privileged` have no legitimate reason to be
skipped at any maturity level — they cost nothing in iteration speed.
Read-only rootfs and full `cap_drop` sometimes get deferred on a very
early demo/portfolio service while the app's write-path behavior is
still being discovered, but treat that as a named, temporary gap to
close before the service takes real traffic — not a permanent T1
exemption the way, say, skipping HA replicas is a legitimate permanent
T1 choice in the terraform skill's tiering table. Hardening posture is
closer to "always on, once you know the app's actual filesystem
footprint" than to a tiered feature.

### Common failure modes when hardening is added retroactively

Retrofitting this posture onto a container that was never designed
for it surfaces a predictable set of failures — worth knowing before
they show up as an on-call page:

- **App tries to write outside its declared `tmpfs`/volume paths.**
  Framework-level caches (a matplotlib font cache, a Hugging Face
  model cache under `~/.cache`, a package manager's own scratch
  directory invoked at runtime rather than build time) are the most
  common culprit. Trace the actual write path with `strace -f -e
  trace=openat <pid>` against a running non-hardened container before
  flipping `read_only: true` on in production, rather than discovering
  it from a crash loop.
- **A build-time step needs root but the runtime doesn't.** Installing
  packages, compiling assets, or running migrations as part of the
  image build is a separate concern from what the *running* container
  needs — do that work in an earlier build stage (or in a `RUN`
  instruction before the final `USER` switch), never by dropping
  `USER` back to root at runtime to "make the error go away."
- **A healthcheck script assumes tooling the hardened image no longer
  has.** A `curl`-based healthcheck copied from an older, less-
  hardened Dockerfile breaks silently switching to a slim/distroless
  base — see [Healthchecks](#healthchecks) below for the app-native
  replacement.
- **Capability creep from copy-pasted compose files.** A `cap_add`
  list inherited from an unrelated service (`SYS_PTRACE` copied in
  because another service needed it for debugging, then never removed)
  is a common source of an unreviewed privilege grant sitting in
  production — audit `cap_add` lists the same way you'd audit an IAM
  policy: every entry should map to a concrete, still-true reason.

## PID 1 and signals

Linux gives PID 1 special semantics: unlike every other process, it
does *not* get default signal dispositions installed automatically.
A normal process that never registers a `SIGTERM` handler still dies
via the kernel's default terminate action; a PID-1 process that never
registers one can simply ignore `SIGTERM` forever. That single fact
is the root cause of nearly every "container takes the full stop
timeout to shut down" bug report.

### Exec-form only — shell form blocks SIGTERM

```dockerfile
# Wrong — shell form
CMD uvicorn app.main:app --host 0.0.0.0 --port 8000

# Right — exec form
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Shell-form `CMD`/`ENTRYPOINT` is silently rewritten to
`/bin/sh -c "uvicorn app.main:app ..."`, which makes `/bin/sh` — not
uvicorn — PID 1. Most shells do not forward signals to child processes
by default, so a `SIGTERM` sent to the container lands on the shell,
which may not relay it to the uvicorn child at all. Docker (and every
orchestrator built on it) then waits out the full stop grace period
before escalating to `SIGKILL`, which means every rolling deploy or
scale-down event pays that timeout in full instead of exiting the
moment the app finishes its graceful shutdown. Exec form runs the
target binary directly as PID 1, so it receives `SIGTERM` immediately
and can act on it.
Source: <https://docs.docker.com/reference/dockerfile/#exec-form-entrypoint-example>

### Init reaper for zombie processes

Exec form alone isn't sufficient once the PID-1 process itself spawns
children that outlive their parent or get orphaned — worker pools,
subprocess-based tooling, anything that forks. PID 1 inherits
responsibility for reaping those zombies, and almost no application
framework does that correctly out of the box. Add an init process in
front of it:

- Compose: `init: true` on the service (translates to `docker run
  --init` under the hood) — injects a minimal built-in init (`tini`
  under the hood) automatically, no image change required.
- Explicit `tini` in the Dockerfile when you need finer control over
  signal forwarding, or on a platform that doesn't auto-inject an
  init for you:

  ```dockerfile
  ENTRYPOINT ["tini", "--", "python", "-m", "app"]
  ```

`init: true` is the lower-friction default for compose-orchestrated
services; reach for an explicit `tini` `ENTRYPOINT` when the image
needs to behave identically outside of Compose too (a bare `docker
run` without `--init`, or a runtime that doesn't offer an equivalent
flag).
Source: <https://github.com/krallin/tini>

### Wrapper scripts must end `exec "$@"`

When a container needs pre-start setup — waiting for a dependency,
running a migration, validating required environment variables — that
logic belongs in a small wrapper script set as `ENTRYPOINT`, with the
real command passed through as `CMD` and invoked as `"$@"`. The script
must end by *exec*ing into that command, not calling it as a plain
subshell invocation:

```bash
#!/usr/bin/env bash
set -euo pipefail

# pre-start setup goes here (e.g., wait-for-deps, migrations)

exec "$@"
```

`exec "$@"` replaces the shell's process image with the target
command **in place** — same PID, same process, no fork. Drop the
`exec` and the target command instead runs as a child of the still-
running shell; the shell becomes the permanent PID 1 and the same
signal-relay problem from the shell-form `CMD` case above reappears,
just introduced through the wrapper script instead of through `CMD`
directly. This is the single most common cause of a container that
technically uses exec-form `CMD` but still eats the full stop timeout
on shutdown — the bug moved into the entrypoint script rather than
being fixed. Wire it up as:

```dockerfile
COPY --chmod=755 entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Source: <https://docs.docker.com/build/building/best-practices/#entrypoint>

### Why this matters beyond a clean `docker stop`

None of this is cosmetic. A container that doesn't forward `SIGTERM`
correctly fails in-flight requests during every rolling deploy instead
of draining them, and it silently accumulates zombie processes under
sustained load if it forks without an init reaper — both failure
modes are invisible in normal operation and only show up under a
scale-down event or a long-running worker, exactly when you can least
afford to be debugging PID-1 semantics.

### Diagnosing a stuck shutdown

When a container consistently takes the full stop timeout (Compose's
default is 10 seconds; many orchestrators default higher) to exit,
work through this checklist before reaching for a bigger timeout:

1. Confirm the actual PID-1 process with `docker top <container>` —
   if the top-listed process is a shell (`sh`, `bash`) rather than the
   application binary, the Dockerfile is using shell-form `CMD` (or a
   wrapper script that never `exec`s), and that's the fix, not the
   timeout.
2. Check whether the process installs its own signal handler at all —
   some frameworks (older WSGI servers, certain job-queue workers)
   need an explicit `--graceful-timeout`/shutdown-hook configuration
   flag before they honor `SIGTERM` gracefully rather than ignoring it
   until `SIGKILL`.
3. Confirm an init reaper is present with `docker inspect
   --format '{{.Config.Entrypoint}}' <image>` (or check the compose
   file for `init: true`) if child processes seem to be piling up as
   defunct/zombie entries in `docker top` output over the container's
   lifetime.
4. If a wrapper script is involved, `grep -n 'exec "\$@"' entrypoint.sh`
   as a fast sanity check — its absence is the single most common root
   cause described above.

`dumb-init` (<https://github.com/Yelp/dumb-init>) is a viable
alternative to `tini` for the same init-reaper role — pick one and use
it consistently across an org's images rather than mixing both.

## Process model

### One process per container under an orchestrator

When an orchestrator (ECS, Kubernetes, Nomad) is responsible for
replication, run exactly one uvicorn process per container and scale
horizontally through the orchestrator's replica count — ECS desired
count, Kubernetes `replicas:` — not by stacking multiple uvicorn
workers inside a single container. The orchestrator's health checks,
restart policy, and autoscaling signals all operate at container
granularity: stacking workers inside one container hides individual
worker crashes from the orchestrator (it only sees the container as a
whole), muddies CPU/memory-based autoscaling signals (one container
now represents N workers' combined load instead of one clean unit),
and multiplies the PID-1/signal-forwarding problem from the previous
section — now every stacked worker needs its `SIGTERM` correctly
relayed, not just one process.

### `--workers N` — single-host and compose only

```dockerfile
# Orchestrator-replicated (ECS, Kubernetes) — one process, scale via replicas
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

# Single-host / compose, no orchestrator replicating this service
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

`uvicorn --workers N` is the correct tool exactly when the container
*is* the whole deployment unit — a single-host Compose production
deployment (legitimate per `references/compose.md`'s single-host-prod
guidance) with no orchestrator doing replica-level scaling above it.
There, multi-worker mode is how you use more than one core on the
host. The moment an orchestrator sits above the container, its
replica count is that same lever and `--workers` becomes redundant at
best, actively harmful at worst (see above).

### `--proxy-headers` behind a TLS-terminating proxy

Enable `--proxy-headers` when uvicorn sits behind a trusted reverse
proxy or load balancer that terminates TLS (an AWS ALB, nginx, Caddy)
— it makes uvicorn trust `X-Forwarded-Proto`/`X-Forwarded-For` from
that proxy so redirects and generated URLs use the correct `https://`
scheme and client-IP logging reflects the real client rather than the
proxy's own address. Only enable it when the proxy is the sole path
into the service — never on a uvicorn process directly reachable from
the public internet, since an untrusted caller could spoof those
headers to fake its origin. Scope trust further with
`--forwarded-allow-ips` when the proxy's address is known and stable.

### Deprecated: `tiangolo/uvicorn-gunicorn` images

Do not use the `tiangolo/uvicorn-gunicorn` (or
`tiangolo/uvicorn-gunicorn-fastapi`) Docker images — they are
deprecated. That image baked in gunicorn as a process manager running
N uvicorn workers inside one container, which is exactly the
one-container-many-workers pattern this section argues against once
an orchestrator is in the picture; it duplicates replica management
the orchestrator already does and reintroduces the multi-worker
signal-forwarding complexity from the previous section. FastAPI's own
deployment documentation now recommends building a plain
`python:3.X-slim` (or uv-based, see `references/dockerfile.md`) image
running a single uvicorn process, scaled by whatever orchestrator sits
above it.
Source: <https://fastapi.tiangolo.com/deployment/docker/>

### Graceful shutdown is an application concern, not just a container one

Exec-form `CMD` and an init reaper (see [PID 1 and
signals](#pid-1-and-signals)) get `SIGTERM` to the right process
promptly; what that process *does* with it is still the application's
responsibility. FastAPI/Starlette applications should use `lifespan`
shutdown handlers (or the older `@app.on_event("shutdown")` hook) to
close database connection pools, flush queued background work, and
stop accepting new requests before the process actually exits —
uvicorn forwards `SIGTERM` into an orderly ASGI shutdown sequence, but
only if the application registers something in that hook to do the
draining. A container that has correct PID-1 signal handling but no
application-level shutdown logic still drops in-flight work on every
deploy; it just fails faster and more visibly than the shell-form
case, which is progress but not the actual goal.

### Mapping to orchestrator primitives

The "one process, orchestrator scales replicas" model maps directly
onto the primitives each orchestrator already exposes for this
purpose — an ECS task definition's `desiredCount` on the service, or a
Kubernetes Deployment's `spec.replicas` — rather than requiring any
container-internal process-count configuration. Keep the two concerns
separate: the Dockerfile/image decides *how many processes run inside
one container* (one, per this section), and the orchestrator manifest
decides *how many containers run* (however many replicas the service
needs) — conflating them by tuning `--workers` to hit a target
concurrency, instead of tuning replica count, reintroduces every
problem described in [One process per container under an
orchestrator](#one-process-per-container-under-an-orchestrator).

## Healthchecks

### Exec-form test, no shell wrapping

Healthcheck tests follow the same exec-form reasoning as `CMD`: use
the array form so the check runs the target process directly rather
than through an implicitly-injected shell.

### No curl on slim — use an app-native check

`python:3.X-slim` does not ship `curl` by default, and distroless or
Chainguard-Wolfi images (the hardened prod tier per
`references/dockerfile.md`'s base-image guidance) never will — no
shell, no package manager, no incidental tooling at all. Installing
`curl` purely to satisfy a healthcheck adds an unnecessary package
(and its own CVE surface for Trivy to flag) to an otherwise minimal
image. Use a check written in the language already running inside the
container instead:

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]
```

`urllib.request` is stdlib — no extra dependency, no extra image
layer, works identically on slim and on distroless variants that still
ship a Python interpreter. `urlopen` raises on any non-2xx response or
connection failure, which is exactly the failure signal Docker's
healthcheck runner needs: a non-zero exit from the `CMD` marks the
check as failed.
Sources: <https://docs.python.org/3/library/urllib.request.html> and
<https://docs.docker.com/reference/dockerfile/#healthcheck>

### Set interval, timeout, retries, and start_period explicitly

Never rely on Docker's built-in healthcheck defaults — state all four
parameters:

- `--interval` — time between checks once the container is
  considered started (`30s` is a reasonable default for a web API;
  tighten it for services where fast failure detection matters more
  than probe overhead).
- `--timeout` — how long a single check attempt may run before it
  counts as a failure; keep it well below `--interval` so a slow
  check doesn't overlap the next one.
- `--retries` — consecutive failures required before the container
  flips to `unhealthy` (`3` is a common floor — enough to absorb a
  single transient blip without masking a real outage).
- `--start-period` — a grace window during container startup where
  failures don't count toward `--retries`. This is the parameter
  people forget, and it's the one that matters most for anything with
  a non-trivial cold start (model-weight loading, cache warmup,
  connection-pool establishment): without it, a slow-starting process
  gets marked unhealthy before it's had a chance to become ready, and
  a restart policy or orchestrator can kill-and-restart it in a loop
  that never actually gets past startup.

### Compose-level healthcheck

The Dockerfile `HEALTHCHECK` instruction and the compose-level
`healthcheck:` key are independent — a compose file that wants
`depends_on: condition: service_healthy` gating (see
`references/compose.md`) needs its own `healthcheck:` block; it
doesn't inherit one from the image automatically in every Compose
version, so define it explicitly at the service level too:

```yaml
healthcheck:
  test:
    [
      "CMD",
      "python",
      "-c",
      "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)",
    ]
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 10s
```

Source: <https://docs.docker.com/reference/compose-file/services/#healthcheck>

### Kubernetes ignores the Dockerfile `HEALTHCHECK`

If a deployment target is Kubernetes, the Dockerfile `HEALTHCHECK`
instruction is inert — Kubernetes never reads it. Liveness, readiness,
and startup probes are defined independently in the Pod spec and
target the same underlying endpoint conceptually, but the probe
*definition* (the orchestrator-layer equivalent of
interval/timeout/retries/`start_period` above) lives in the manifest,
not the image. Reuse the same `/health` endpoint logic the
`HEALTHCHECK` instruction above calls, but don't expect the
instruction itself to do anything on a Kubernetes-targeted image;
Kubernetes manifest authoring itself is out of scope for this skill —
see `SKILL.md`'s "what this skill does NOT cover" section.
Source: <https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/>

### What a healthcheck does and doesn't do

A failing `HEALTHCHECK` changes the container's reported status
(`docker ps` shows `unhealthy`) and — critically for compose — gates
`depends_on: condition: service_healthy` for any dependent service.
It does **not**, by itself, restart the container under plain `docker
run`; that still requires a restart policy (`unless-stopped`) reacting
to the container actually exiting, or an orchestrator making its own
health-based rescheduling decision on top of the reported status.
Don't assume adding a `HEALTHCHECK` alone gives you self-healing.

### Common pitfalls

- **Healthcheck fails during legitimate startup dependency waits.** A
  service whose `/health` endpoint checks downstream dependencies
  (database connectivity, a required cache) will report unhealthy
  while those dependencies are still starting up in the same
  `docker compose up` — this is precisely what `start_period` exists
  to absorb; widen it rather than weakening the health endpoint's
  actual check.
- **Conflating liveness with readiness in one `/health` endpoint.** A
  single endpoint that answers both "is the process alive" and "is
  the process ready to serve traffic" makes the Dockerfile
  `HEALTHCHECK`/compose `healthcheck:` do double duty; that's
  acceptable for a Dockerfile-level check (there's only one signal
  available there) but is exactly the distinction Kubernetes' separate
  liveness/readiness/startup probes exist to make once a workload
  moves to that orchestrator — see [Kubernetes ignores the Dockerfile
  HEALTHCHECK](#kubernetes-ignores-the-dockerfile-healthcheck) above.
- **Checking a port instead of the application layer.** A TCP-connect-
  only check (the port accepts connections) can pass while the
  application behind it is deadlocked or returning 500s on every
  request — prefer an HTTP check against a real endpoint (as in the
  `urllib` example above) over a bare socket check whenever the
  process speaks HTTP at all.

## Linting

### hadolint in CI

Lint every Dockerfile with `hadolint` as an early, fast CI gate — it
bundles ShellCheck against the contents of every `RUN` instruction, so
shell-scripting bugs inside `RUN` lines (unquoted variables, missing
`set -e`, broken conditionals) get caught for free alongside
Dockerfile-specific rules.
Source: <https://github.com/hadolint/hadolint>

### Key gates

- **DL3006** — untagged `FROM`. A bare `FROM python` (no tag)
  silently resolves to `:latest` at build time and drifts to whatever
  the registry currently serves that tag — the exact non-reproducible
  build this skill's pinning rules exist to prevent (see
  `references/dockerfile.md` for the full `tag@digest` treatment).
- **DL3008** — unpinned `apt-get install` package version. `apt-get
  install -y foo` without `foo=<version>` lets the installed package
  version drift silently between builds even when the base image tag
  is pinned, because the Debian package mirror serves whatever the
  latest version in that release channel is on build day.
- **DL3002** — last `USER` is `root`. hadolint tracks the *effective*
  final `USER` in the image and flags a Dockerfile whose last `USER`
  instruction (or absence of one, which defaults to root) leaves the
  built image running as root — directly enforcing this file's own
  [non-root rule](#non-root-user-with-explicit-uidgid) at lint time,
  before the image is ever built or scanned.

### `.hadolint.yaml` sample

```yaml
failure-threshold: warning
ignored:
  - DL3008 # apt version pinning; deps are pinned separately via uv.lock / --locked
trustedRegistries:
  - docker.io
  - ghcr.io
```

This sample deliberately ignores `DL3008` project-wide on the
assumption that the Python dependency layer is already pinned exactly
through `uv sync --locked` (see `references/dockerfile.md`) — the
`apt-get` layer is the one hadolint is actually gating here. Flip that
ignore off the moment a Dockerfile installs `apt` packages whose exact
version genuinely matters (a specific `libpq` ABI version, a pinned
compiler toolchain) — the ignore is a project-wide default, not a
blanket exemption for every Dockerfile.

### Per-line ignore comments over blanket config

For a one-off exception, prefer a per-line ignore comment over adding
another rule to the project-wide `ignored:` list:

```dockerfile
# hadolint ignore=DL3006
FROM some-vendor/base-image
```

A per-line ignore is visible in the diff that introduces it and scoped
to exactly the line that needs it; a config-level `ignored:` entry
silently suppresses the rule everywhere, including in future
Dockerfiles that might have genuinely violated it for a real reason.
Reach for the config-level ignore only when the rule is structurally
inapplicable to the whole project (as with the `DL3008` example
above, where a different, stricter pinning mechanism already covers
the same ground).

### Further hadolint rules worth knowing

Beyond the three gates called out above, a few more rules catch
mistakes specific to this skill's other conventions:

| Rule | Catches |
| --- | --- |
| DL3003 | `cd` used instead of `WORKDIR` — breaks layer-cache reasoning about the working directory |
| DL3009 | Missing apt cache cleanup after `apt-get install` — bloats image layers |
| DL3015 | Missing `--no-install-recommends` on `apt-get install` — pulls in unnecessary recommended packages |
| DL4006 | `SHELL` not set for fail-fast piping (`set -o pipefail`) when a `RUN` instruction pipes commands together |
| SC2086 (ShellCheck) | Unquoted variable expansion inside a `RUN` instruction — the same class of bug ShellCheck catches in any shell script, surfaced here because hadolint runs it against `RUN` content |

### Running hadolint locally

```bash
docker run --rm -i hadolint/hadolint < Dockerfile
```

Running the same check locally before pushing catches a gate failure
in seconds instead of waiting on CI — use the identical
`.hadolint.yaml` config either way by mounting it in:

```bash
docker run --rm -i -v "$(pwd)/.hadolint.yaml:/.hadolint.yaml" hadolint/hadolint < Dockerfile
```

### Where it sits in the pipeline

hadolint runs first in the CI gate order — before build, before
scanning, before signing — precisely because it's the cheapest check:
failing fast on a lint violation costs seconds, not the minutes a full
`docker buildx build` and Trivy scan would cost to reach the same
verdict. Full pipeline ordering and the `docker/build-push-action`
wiring live in `references/ci-and-release.md`.

## Scanning

### Trivy is the primary scanner — house rule

Trivy is the default all-in-one gate: CVE scanning across OS packages
and language dependencies, IaC misconfiguration scanning, secrets
detection, and license scanning, all in one offline-capable binary
(embeddable/downloadable vulnerability database, so it works inside
air-gapped or otherwise network-restricted CI runners). This is the
same scanner the terraform skill mandates in its
`fmt → validate → tflint → trivy → plan → apply` pipeline — one
scanner, one mental model, across both Terraform and Docker surfaces
in this plugin.
Source: <https://github.com/aquasecurity/trivy>

Fail CI on HIGH or CRITICAL findings:

```bash
trivy image --severity HIGH,CRITICAL --exit-code 1 --ignorefile .trivyignore ghcr.io/org/app:1.4.2
```

The same gate expressed as a checked-in config file instead of CLI
flags, for teams that prefer config-as-code over pipeline-step flags:

```yaml
# trivy.yaml
severity:
  - HIGH
  - CRITICAL
exit-code: 1
ignorefile: .trivyignore
```

### `.trivyignore` for accepted findings — never for unreviewed ones

`.trivyignore` lists specific CVE IDs to exclude from the failing
severity gate, each with a comment explaining *why* it's accepted —
an upstream fix that doesn't exist yet, a false positive against the
actual usage pattern, or a finding mitigated by a control outside the
image (network policy, WAF rule). Never add a CVE to this file to
"make CI green" without that justification recorded next to it — the
file is a reviewed exception list, not a scanner-silencing knob.

```
# CVE-2024-XXXXX: no upstream fix yet, tracked in JIRA-1234, mitigated by network policy blocking the affected port
CVE-2024-XXXXX
```

Source: <https://aquasecurity.github.io/trivy/latest/docs/configuration/filtering/>

### Grype — second opinion on critical images

Run Grype as a second CVE matcher specifically on images classified
as critical (public-facing entry points, anything handling
credentials or PII). Trivy and Grype source and match against
different vulnerability-database lineages, so they don't always agree
— a finding Trivy misses due to a matching gap in its DB is a
plausible catch for Grype, and vice versa. Grype is not a replacement
for Trivy's broader IaC/secrets/license coverage; it's a narrower,
deliberately redundant CVE cross-check reserved for the images where a
false negative is most costly.
Source: <https://github.com/anchore/grype>

### Docker Scout — Desktop-native complement only

Docker Scout (`docker scout cves`, and the Docker Desktop UI
integration) is a legitimate local dev-loop tool — fast feedback while
iterating on a Dockerfile, before anything reaches CI — but it is not
a substitute for the Trivy CI gate. Treat it the way you'd treat an
IDE linter next to a CI linter: useful for the person actively
editing, not the system of record for what merges.
Sources: <https://docs.docker.com/scout/> and
<https://www.aikido.dev/blog/top-container-scanning-tools>

### Scanner comparison at a glance

| | Trivy | Grype | Docker Scout |
| --- | --- | --- | --- |
| Role in this skill | Primary CI gate | Second opinion, critical images only | Local dev-loop complement |
| Coverage | CVE + IaC + secrets + licenses | CVE only | CVE, plus Docker Desktop UI integration |
| Offline-capable | Yes (downloadable/embeddable DB) | Yes | Requires Docker Hub/Desktop connectivity for full feature set |
| CI gate authority | Yes — fails the build | Advisory on critical images | No |

The point of running three tools isn't redundant busywork — each
covers a gap the others don't: Trivy's breadth makes it the right
default gate, Grype's independent vulnerability-database lineage
catches what Trivy's matching logic might miss on the highest-value
images, and Docker Scout's IDE/Desktop integration is the fastest
feedback loop available *before* either of the other two ever runs in
CI.

### Keep scans clean over time — automate digest bumps

A clean scan today doesn't stay clean without action: new CVEs get
disclosed against packages already baked into a pinned, unchanging
image layer. Automate base-image and digest bumps with Renovate
(the `docker:pinDigests` preset keeps `tag@digest` pins fresh via
automated PRs) or the Dependabot Docker ecosystem, on at least a
weekly cadence. This closes the loop with the scanning gate above —
scanning catches what's already wrong; automated digest bumps are what
keeps today's clean result from quietly rotting as upstream patches
ship.
Source: <https://docs.renovatebot.com/docker/>

### Pipeline gate order

Full CI wiring lives in `references/ci-and-release.md`; the scanning-
relevant slice of that order is:

```
hadolint  →  build (--sbom --provenance)  →  trivy (fail HIGH/CRITICAL)  →  grype (critical images)  →  cosign sign  →  push
```

## SBOM and provenance

### `--sbom=true --provenance=mode=max`

```bash
docker buildx build \
  --sbom=true \
  --provenance=mode=max \
  --tag ghcr.io/org/app:1.4.2 \
  --push .
```

Neither attestation is on by default in the way you'd expect from
"secure by default" framing: provenance defaults to `mode=min` (a
thin builder-identity record) unless you explicitly raise it to
`mode=max`, and SBOM generation is entirely opt-in — it's off unless
`--sbom=true` is passed. Treat both flags as mandatory on every
production build, not optional hardening.
Source: <https://docs.docker.com/build/metadata/attestations/>

### What each attestation actually records

- **SBOM** (software bill of materials) — an itemized inventory of
  every package and library baked into the image, typically emitted
  in SPDX or CycloneDX format. It answers "what is in this image,"
  and it's the same list Trivy and Grype consume when matching
  against vulnerability databases — a build-time SBOM and a scan-time
  vulnerability match are two views of the same underlying data.
  Sources: <https://spdx.dev/> and <https://cyclonedx.org/>
- **Provenance** — an attestation of *how* and *by whom* the image
  was built: the build definition, the source materials that went
  into it, resolved base-image digests, and builder identity,
  structured per the SLSA provenance schema. It answers "how was this
  image built, and can I trust that description," which is exactly
  the input [cosign verification](#signing) needs to confirm an image
  came from the workflow it claims to.
  Source: <https://slsa.dev/spec/v1.0/provenance>

`mode=min` provenance records only minimal builder info — enough to
say an attestation exists, not enough to meaningfully verify the build
process. `mode=max` includes the full build configuration and
resolved materials, which is the level SLSA-style provenance
verification downstream actually needs to be useful rather than
decorative.

### Where the attestations live

Both SBOM and provenance attach as in-toto-formatted attestation
manifests directly inside the OCI image index — they travel with the
image through any registry that supports the OCI image-index format,
rather than existing as a separate artifact you have to track,
publish, and keep in sync by hand.
Source: <https://in-toto.io/>

Inspect what got attached to a pushed image:

```bash
docker buildx imagetools inspect ghcr.io/org/app:1.4.2 --format '{{ json .SBOM }}'
```

### SPDX vs CycloneDX — pick one and stay consistent

Buildx's `--sbom=true` produces an SPDX-format SBOM by default; both
SPDX and CycloneDX are legitimate, broadly-tooled formats and neither
is a house preference over the other in this skill — what matters is
picking one per project and keeping every image's SBOM in the same
format, since downstream vulnerability-matching and license-scanning
tooling (including Trivy) consumes either format, but a mixed fleet
complicates any tooling that assumes one consistently.

## Signing

### cosign keyless (OIDC via Fulcio + Rekor) — the 2026 default

For GitHub-Actions-driven OSS and internal shops alike, cosign's
keyless signing flow is the 2026 default: the CI job's own OIDC token
(GitHub Actions' built-in OIDC identity provider) is exchanged with
Sigstore's Fulcio certificate authority for a short-lived signing
certificate bound to that specific workflow's identity, the resulting
signature and certificate are recorded in Sigstore's Rekor
transparency log, and no long-lived private signing key ever needs to
be generated, stored, rotated, or leaked. This is a meaningfully
different trust model from classic key-based signing — trust is
anchored to "this exact workflow, on this exact repo, at this commit"
rather than to possession of a key file.
Sources: <https://github.com/sigstore/cosign> and
<https://docs.sigstore.dev/cosign/signing/signing_with_containers/>

```bash
cosign sign --yes ghcr.io/org/app@sha256:<digest>
```

Sign by immutable digest, never by a mutable tag — `--yes` skips the
interactive confirmation prompt, which is required for a non-
interactive CI runner.

### Verification pins the expected identity

```bash
cosign verify \
  --certificate-identity-regexp '^https://github\.com/org/repo/\.github/workflows/release\.yml@refs/heads/main$' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/org/app@sha256:<digest>
```

Always pin the expected workflow identity and OIDC issuer on the
verifying side. Skipping `--certificate-identity-regexp` degrades the
check to "was this signed by *some* keyless cosign identity," which
confirms far less than it appears to — the whole value of keyless
signing is that verification can assert *which* workflow produced the
image, not merely that some CI produced it.

### Attesting the SBOM alongside the signature

`cosign sign` proves *who* produced the image; `cosign attest` binds a
predicate — commonly the SBOM itself — to the image under the same
keyless identity, so a verifier can pull both the signature and a
signed SBOM through one trust chain rather than trusting the
build-time SBOM attestation from [SBOM and
provenance](#sbom-and-provenance) on its own separate authority:

```bash
cosign attest --yes --type spdxjson --predicate sbom.spdx.json ghcr.io/org/app@sha256:<digest>
```

This is additive to, not a replacement for, the `--sbom=true`
build-time attestation above — `buildx` attaches the SBOM to the
image index at build time; `cosign attest` is what makes that (or an
independently regenerated) SBOM verifiable against the same keyless
identity as the image signature itself.

### Notation — enterprise PKI alternative

Where an organization already runs its own certificate authority and
trust-store model rather than relying on OIDC-issued short-lived
certificates, Notation (the CNCF project, distinct from cosign) is the
documented alternative for enterprise PKI-based signing. It isn't a
house preference over cosign in this skill — cosign keyless is the
default specifically because it fits the GitHub-Actions-OIDC shape
this plugin assumes; Notation is the correct answer when that
assumption doesn't hold.
Source: <https://notaryproject.dev/>

### Docker Content Trust is retired

Do not build new signing workflows on Docker Content Trust
(`DOCKER_CONTENT_TRUST=1`, backed by Notary v1) — it is retired.
Legacy documentation remains published for migration reference only,
not as a currently-recommended signing path.
Source (legacy): <https://docs.docker.com/engine/security/trust/>

### Sign after scan, before push

Order matters: run signing after the Trivy scan gate passes, and push
only after signing succeeds. Signing an image before it's scanned
risks shipping a cryptographically-attested signature on an image that
scanning would have rejected moments later; pushing an unsigned image
defeats the entire point of the gate. The full ordering is captured in
[the scanning section's pipeline diagram](#pipeline-gate-order) above.

## Audit

### `docker-bench-security` — CIS Docker Benchmark, automated

`docker-bench-security` runs the CIS Docker Benchmark's checks as an
automated shell script against the host and daemon themselves — not a
single image. It inspects host configuration, Docker daemon
configuration, container runtime configuration, and general Docker
security operations, covering the host/daemon layer that none of the
other tools in this file reach: Trivy and Grype scan image contents,
hadolint lints Dockerfile source, but nothing else here looks at
*how the daemon serving those images is actually configured*.
Source: <https://github.com/docker/docker-bench-security>

```bash
docker run --rm --net host --pid host --userns host --cap-add audit_control \
  -v /var/lib:/var/lib:ro -v /var/run/docker.sock:/var/run/docker.sock:ro \
  docker/docker-bench-security
```

### Cadence: per-release or monthly, whichever is more frequent

Run the audit on every release that touches host or daemon
configuration, and on a monthly schedule as a floor for environments
where releases happen less often than that. Whichever cadence is
tighter for a given environment is the one that applies — a
fast-moving service with weekly releases gets audited weekly by
virtue of the per-release trigger; a stable, rarely-redeployed host
still gets the monthly floor so daemon-level drift doesn't go
unnoticed for months at a stretch.

### Triaging findings

Findings map back to the same CIS Docker Benchmark control-ID family
referenced in [Runtime hardening](#runtime-hardening) above, plus the
earlier §1–§4 controls (host configuration, daemon configuration) that
this file's other sections don't reach at all, since those apply to
the host running the daemon rather than to any individual
image or compose file. Treat a WARN on a host-level control — auditd
rules, a dedicated partition for `/var/lib/docker`, daemon socket
permissions — as an environment-owned finding to route to whoever owns
host provisioning; no Dockerfile or compose change can fix a
daemon-configuration gap, and trying to paper over one at the
image/compose layer only hides where the real fix belongs.
Source: <https://www.cisecurity.org/benchmark/docker>

### Complementary standards worth knowing

Two broader references worth keeping on hand when a finding from any
of the tools above needs more context than this file provides: the
OWASP Docker Security Cheat Sheet
(<https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html>)
covers much of the same ground as this file's [Runtime
hardening](#runtime-hardening) section from an attacker's-eye-view
framing, and NIST SP 800-190, the Application Container Security
Guide (<https://csrc.nist.gov/pubs/sp/800/190/final>), is the
standards-body reference most audit and compliance conversations will
eventually point back to. Neither replaces the rules above — both are
useful when a reviewer or auditor asks "what's this based on" beyond
"the digest said so."

_Verified as of 2026-07; sources re-checked against docs/superpowers/research/2026-07-20-*.md._
