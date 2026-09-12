# Compose

House rules for files that follow the Compose Specification (`compose.yaml`,
historically `docker-compose.yml`) — the single schema `docker compose`
validates against today. The Specification absorbed the old 2.x/3.x/Swarm-only
file formats years ago, so there is one grammar, not three forked ones, and
the layering/profiles/watch machinery documented below is what lets that one
grammar cover local dev, CI, staging, and single-host production without
forking into unrelated files per environment —
https://docs.docker.com/reference/compose-file/. Every rule below traces to a
primary source; where the operations community genuinely disagrees on a call,
the disagreement is marked `CONTESTED` rather than flattened into a false
consensus.

## Spec baseline

Two top-level keys get touched on almost every new file: `version` and
`name`. One is dead weight carried forward out of habit, the other is
load-bearing and frequently skipped.

**Rules**

- **Never write a top-level `version:` key.** It exists only for backward
  compatibility with the pre-Specification 2.x/3.x file formats, it is purely
  informative, and Compose always validates against the latest schema
  regardless of what it says — writing one earns a startup warning that the
  attribute is obsolete for zero effect on behavior. Delete it the moment you
  touch a file that still has it; don't leave it as stale ballast just
  because it's harmless. —
  https://docs.docker.com/reference/compose-file/version-and-name/
- **Set `name:` at the top level of the base file.** Without it, Compose
  derives the project name from the containing directory (or from `-p` /
  `COMPOSE_PROJECT_NAME` at invocation time) — fine until two clones of the
  same repo, or a CI runner and a laptop, land on different directory names
  and silently spin up two unrelated project namespaces of the same stack. An
  explicit `name:` pins the project identity into the file itself. —
  https://docs.docker.com/reference/compose-file/version-and-name/
- **Know that `name:` is exposed back out as `COMPOSE_PROJECT_NAME`.** The
  Specification defines it "as the project name to be used if you don't set
  one explicitly," and that resolved name is available for interpolation and
  environment-variable resolution elsewhere in the same file — useful for
  namespacing resources (network names, volume names) off a single source of
  truth instead of repeating a literal string. —
  https://docs.docker.com/reference/compose-file/version-and-name/
- **Know the full top-level shape before deciding where a piece of
  configuration belongs.** Beyond `name:` and `services:`, the Specification
  defines `networks:`, `volumes:`, `secrets:`, and `configs:` as siblings at
  the top level — `configs:` in particular is easy to miss and gets
  conflated with `secrets:`. It exists specifically for non-sensitive
  runtime configuration a service should be able to pick up "without the
  need to rebuild a Docker image" (an `nginx.conf`, a feature-flag file),
  mounted world-readable by default — reach for `secrets:` instead the
  moment the content actually needs restricted read access. —
  https://docs.docker.com/reference/compose-file/configs/
- **Let CLI/env overrides win deliberately, not by accident.** `-p <name>`
  and `COMPOSE_PROJECT_NAME` still take precedence over the file's `name:` —
  useful for spinning up parallel ephemeral stacks (PR-preview environments,
  parallel test runs) from the same file without editing it. Know that
  override chain before debugging "why did compose create a second project
  from the same directory."
- **Use `x-` top-level fields to de-duplicate configuration Compose itself
  has no dedicated merge mechanism for.** Compose ignores any top-level or
  service-level field starting with `x-` outright — the one place an
  unrecognized key is silently accepted rather than rejected — which makes
  it the sanctioned spot to park a YAML anchor that several services then
  merge in via `<<: *anchor`. Reach for it before reaching for `extends`
  when the shared shape is a handful of scalar keys, not an entire service. —
  https://docs.docker.com/reference/compose-file/extension/

```yaml
# compose.yaml — no top-level `version`, an explicit project `name`
name: acme-api

x-env: &env
  environment:
    OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4318
    LOG_LEVEL: info

services:
  api:
    image: acme/api:1.4.2@sha256:9c27e1f3b8a1d9e6f9a0b9c9d9e9f9a0b9c9d9e9f9a0b9c9d9e9f9a0b9c9d9e9
    <<: *env
  worker:
    image: acme/worker:2.1.0@sha256:7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f
    <<: *env
```

The absence of a `version` line above is the rule, not an oversight — every
sketch in this reference omits it for the same reason. Files inherited from
the old 2.x/3.x formats still carry a two-or-three-character quoted string
under that key; the correct fix is deleting the whole line, not bumping the
value to something newer. Compose ignores it either way, so "upgrading" it is
pure noise that invites the next reader to wonder whether it still means
something.

`x-env` above is never a service — Compose never tries to start it, because
nothing under an `x-`-prefixed key is treated as part of the services graph.
Both `api` and `worker` inherit the same `environment` block through the
YAML anchor without either one repeating it, and a third service added later
gets the same behavior for free by adding one `<<: *env` line.

## File layering

Compose resolves multiple `-f` files by deep-merging them left to right into
one in-memory model before validating or running anything —
`docker compose config` prints that merged, interpolated result, and it is
the fastest way to see what will actually launch before finding out the hard
way. Three-file layering exploits two of the CLI's defaults: `compose.yaml`
loads automatically as the base; `compose.override.yaml`, if it exists in the
working directory, is auto-loaded and merged on top of it with zero flags;
anything else needs an explicit `-f`.

**Rules**

- **Know what Compose looks for when no `-f` flag is given at all.**
  Compose searches the working directory and its parents for `compose.yaml`
  and, if present alongside it, `compose.override.yaml`; the base file is
  mandatory — invoking Compose with neither a `-f` flag nor a discoverable
  `compose.yaml` is an error, not a silent no-op. This is the exact
  mechanism the auto-load rule below depends on, not a separate convention. —
  https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/
- **Base file = `compose.yaml`, the canonical shared shape.** Images
  (pinned, not built locally), service topology, networks, named volumes —
  the parts every environment agrees on. —
  https://docs.docker.com/compose/how-tos/multiple-compose-files/
- **`compose.override.yaml` is dev, and it's the one file Compose loads
  without being asked.** A bare `docker compose up` merges `compose.yaml` +
  `compose.override.yaml` (when the second file is present) automatically —
  which is exactly why it should hold only dev conveniences (bind mounts for
  live-reload, published ports, verbose logging, a `build:` block instead of
  a registry `image:`), never anything you'd be unhappy to see land on a
  staging box because an operator typed the bare command out of habit. —
  https://docs.docker.com/compose/how-tos/multiple-compose-files/
- **Everything else is explicit `-f`.** Prod, staging, CI — none of them
  auto-load; each invocation names every file in the chain:
  `docker compose -f compose.yaml -f compose.prod.yaml <command>`. Compose
  merges left to right, later files winning on scalar conflicts. —
  https://docs.docker.com/compose/how-tos/production/
- **Reach for `extends` when one service's shape needs to be *reused*, not
  just re-parameterized per environment.** `extends` lets a service
  definition in one file reference and inherit from a service defined in
  another file — same repo or a separate one — then override specific
  attributes locally. It earns its keep once two services (an `api` and a
  `worker` sharing an image, env block, and volume set) would otherwise
  require repeating that shared 80% in both service blocks across every
  layering file. —
  https://docs.docker.com/reference/compose-file/services/#extends
- **Reach for `include` when the merge itself needs to be modular across
  teams or repos, not just across environments.** The top-level `include:`
  key loads another Compose file — and its own layering chain — as a
  sub-application, with each included file's relative paths resolved
  against its own location. This is the tool for "our service's compose file
  depends on the platform team's compose file," not something file layering
  alone solves. — https://docs.docker.com/reference/compose-file/include/
- **Run `docker compose config` before trusting either the dev or the prod
  stack.** It is the only reliable way to catch a scalar you thought you
  overrode but didn't. List-valued keys such as `volumes`/`ports` are
  concatenated across files by default, not replaced — a frequent surprise
  for anyone coming from merge-by-key tooling elsewhere.
- **In CI, prefer the `COMPOSE_FILE` environment variable over a long
  repeated `-f … -f …` invocation once the chain gets past two files.**
  `COMPOSE_FILE=compose.yaml:compose.prod.yaml` (colon-separated on
  Mac/Linux, semicolon on Windows, overridable via
  `COMPOSE_PATH_SEPARATOR`) drives every subsequent bare `docker compose`
  invocation in that shell/job without repeating flags on every command —
  set once at the top of a CI job, not per step. —
  https://docs.docker.com/compose/environment-variables/envvars/
- **Don't invent a fourth naming scheme.**
  `compose.staging.yml`, `docker-compose-prod.yaml`, and similar ad hoc names
  still work as `-f` arguments, but they buy nothing over `compose.prod.yaml`
  / `compose.staging.yaml` named consistently — pick base / auto-loaded
  override / explicit-named-file and stay there, so every engineer's
  muscle-memory `docker compose up` behaves identically across the fleet.

`extends` in practice — a `worker` service inheriting `api`'s image and
environment from a shared `compose.base.yaml`, then adding its own command
and dropping the port publication `api` needs and `worker` doesn't:

```yaml
# compose.yaml
services:
  worker:
    extends:
      file: compose.base.yaml
      service: api
    command: ["python", "-m", "acme.worker"]
```

The `extends` target (`compose.base.yaml`'s `api` service) is not itself
required to appear in this file's `services:` list — Compose resolves it
from the referenced file directly. That is the difference from `include`:
`extends` pulls in one service's shape; `include` pulls in an entire other
Compose file's applications, profiles, and layering chain as a unit.

**Worked example.** A minimal API service: the dev bind mount and published
port exist only in the override; the prod file adds resource, restart, and
logging policy and never mentions the bind mount or port at all — because
prod's invocation never loads `compose.override.yaml` in the first place.

```yaml
# compose.yaml — base, always loaded
name: acme-api

services:
  api:
    image: acme/api:1.4.2@sha256:9c27e1f3b8a1d9e6f9a0b9c9d9e9f9a0b9c9d9e9f9a0b9c9d9e9f9a0b9c9d9e9
    environment:
      LOG_LEVEL: info
    networks: [backend]

networks:
  backend:
```

```yaml
# compose.override.yaml — dev, auto-loaded on a bare `docker compose up`
services:
  api:
    build: .
    volumes:
      - ./src:/app/src            # live-reload bind mount, dev-only
    ports:
      - "8000:8000"                # published for laptop browser access
    environment:
      LOG_LEVEL: debug
```

```yaml
# compose.prod.yaml — explicit only:
# docker compose -f compose.yaml -f compose.prod.yaml up -d
services:
  api:
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 512M
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

`docker compose up` (dev): merges base + override — the bind mount and
`8000:8000` are present, and the image is built locally from `build: .`.
`docker compose -f compose.yaml -f compose.prod.yaml up -d` (prod): merges
base + prod only — no bind mount, no published port, no `build:` block ever
entered the merge, because the override file was never named in the `-f`
chain. Nothing was stripped after the fact; it was simply never loaded.

## Profiles

Profiles answer a different question than file layering does. File layering
answers "how is this service configured, given the environment I'm in"
(image vs. build, ports, resource limits). Profiles answer "which services
exist in this run at all" — but only within a single environment; they are
not a mechanism for forking dev vs. staging vs. prod.

**Rules**

- **Profiles gate optional services within one environment — admin UIs,
  debug sidecars, one-shot seed/migration jobs — never a dev-vs-prod split.**
  A service tagged `profiles: [debug]` does not start on a bare
  `docker compose up`; a service with no `profiles:` key always runs,
  everywhere that compose file is used, in every environment it's layered
  into. The moment the real question is "which environment is this," reach
  for file layering instead. —
  https://docs.docker.com/compose/how-tos/profiles/
- **Activate with `--profile <name>` (repeatable) or
  `COMPOSE_PROFILES=<a>,<b>` in the shell or `.env`.** Multiple active
  profiles are additive — a service enabled by *any* currently active
  profile runs. — https://docs.docker.com/compose/how-tos/profiles/
- **Explicitly naming a profiled service starts it regardless of active
  profiles.** `docker compose up phpmyadmin` or `docker compose run migrate`
  brings that one service up even with no `--profile` flag set — handy for a
  one-shot job that should never auto-start on a bare `up` but still needs
  to be reachable by name on demand. —
  https://docs.docker.com/compose/how-tos/profiles/

**Decision rule vs. file layering, in one line:** if the answer to "does
this service run at all" changes with which flag you pass, use
`profiles:`; if the answer to "how is this service built, exposed, or
resourced" changes with which environment you're targeting, use file
layering.

```yaml
services:
  api:
    image: acme/api:1.4.2@sha256:9c27e1f3b8a1d9e6f9a0b9c9d9e9f9a0b9c9d9e9f9a0b9c9d9e9f9a0b9c9d9e9
    depends_on: [db]

  db:
    image: postgres:18@sha256:5f3b1c7c4a2e9f7d6c1b8a9e0d4f2c8b7a6e5d4c3b2a1908f7e6d5c4b3a29180

  adminer:
    image: adminer:5@sha256:1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b
    profiles: [debug]
    ports:
      - "8080:8080"

  seed-data:
    image: acme/api:1.4.2@sha256:9c27e1f3b8a1d9e6f9a0b9c9d9e9f9a0b9c9d9e9f9a0b9c9d9e9f9a0b9c9d9e9
    profiles: [debug]
    command: ["python", "-m", "acme.seed"]
    depends_on: [db]
```

`docker compose up` starts `api` and `db` only. `docker compose --profile
debug up` additionally starts `adminer` and `seed-data`. Neither one needed a
separate compose file, an override, or an `-f` flag — they live in the base
file, gated by a label, because they're optional in *every* environment, not
specific to one.

The two mechanisms compose, in the literal sense: a `profiles: [debug]`
service can still be reshaped per environment by `compose.override.yaml` /
`compose.prod.yaml` like any other service. Profiles decide *if* it runs at
all; layering decides *how* it's configured wherever it does.

**Anti-pattern:** tagging the same `api` service `profiles: [dev]` in one
block and `profiles: [prod]` in another, then always passing
`--profile $ENV`, to fake an environment split inside one file. It works
mechanically, but it throws away everything file layering gives for free —
`docker compose config` can no longer show "what does prod actually run"
without also knowing which profile flag was intended, and a bare
`docker compose up` (no profile flag) silently starts *nothing*, which is a
worse failure mode than starting the wrong environment's shape. If two
"profiles" never run together in the same invocation, that's not an optional
service — it's file layering wearing a disguise.

A genuine second use case, distinct from the debug-tools example above: a
`test` profile bringing up a service that exists only to be exercised by an
integration-test run and would be actively wrong to start any other time —
not "optional for convenience" but "must never run outside this one
invocation":

```yaml
services:
  api:
    image: acme/api:1.4.2@sha256:9c27e1f3b8a1d9e6f9a0b9c9d9e9f9a0b9c9d9e9f9a0b9c9d9e9f9a0b9c9d9e9
    depends_on: [db]

  db:
    image: postgres:18@sha256:5f3b1c7c4a2e9f7d6c1b8a9e0d4f2c8b7a6e5d4c3b2a1908f7e6d5c4b3a29180

  integration-tests:
    build: ./tests
    profiles: [test]
    depends_on: [api]
    command: ["pytest", "tests/integration"]
```

`docker compose --profile test up --abort-on-container-exit` runs the whole
stack plus the test runner and exits with the test runner's exit code — the
exact shape a CI job wants, expressed as one file instead of a fourth
compose file whose only difference from the base file is one extra service.

## Startup ordering

`depends_on` has two forms. The short form (`depends_on: [db]`) only orders
container *start*, not readiness — the app container can start and
immediately fail its first database connection because the dependency's
process is running but not yet accepting connections. The long form closes
that gap by gating on a healthcheck result instead of process existence.

**Rules**

- **Use long-form `depends_on` with `condition: service_healthy` for
  anything that needs its dependency actually ready, not merely started.**
  Three condition values exist: `service_started` (the default, equivalent
  to short form), `service_healthy` (waits for the dependency's
  `healthcheck` to report healthy), and `service_completed_successfully`
  (waits for a one-shot dependency — a migration container — to exit `0`
  before starting the dependent). —
  https://docs.docker.com/reference/compose-file/services/#depends_on
- **`service_healthy` has a hard precondition: the dependency must define a
  `healthcheck:`.** Compose cannot evaluate a condition against a check that
  doesn't exist — a dependency with no `healthcheck:` fails validation
  outright the moment something depends on it with
  `condition: service_healthy`. This is why "every long-running service
  defines a healthcheck" is a floor, not a nice-to-have, the instant
  anything downstream depends on it. —
  https://docs.docker.com/reference/compose-file/services/#healthcheck
- **Add `restart: true` under the long-form dependency entry when the
  dependent should restart alongside a Compose-driven update of the
  dependency.** It fires on Compose-initiated restarts of the dependency
  (for example, `docker compose up` after bumping the dependency's image),
  not on ordinary runtime crash-restarts — a different mechanism from the
  top-level `restart:` policy covered under Runtime policies below. —
  https://docs.docker.com/reference/compose-file/services/#depends_on
- **Every long-running service in the file gets a `healthcheck:`,
  dependency or not.** `docker compose ps` and `docker inspect` — and
  anything built on top of Compose — lean on real health reporting, not
  "the process hasn't exited yet." Set `interval`, `timeout`, `retries`, and
  `start_period` explicitly rather than trusting engine defaults;
  `start_period` matters most for anything with real boot time (JVM warm-up,
  migrate-on-boot), since failures during it don't count against `retries`.
  — https://docs.docker.com/reference/compose-file/services/#healthcheck
- **Prefer an app-native or exec-form check over shelling out to `curl` on
  slim or distroless runtime images.** A minimal base frequently doesn't
  ship `curl` at all; a bare TCP probe or a small built-in `/healthz`
  invoked through the app's own runtime avoids pulling in a whole HTTP
  client solely to satisfy the healthcheck, and `CMD-SHELL` should only be
  used when a shell is actually present in the image.

```yaml
services:
  app:
    image: acme/api:1.4.2@sha256:9c27e1f3b8a1d9e6f9a0b9c9d9e9f9a0b9c9d9e9f9a0b9c9d9e9f9a0b9c9d9e9
    depends_on:
      db:
        condition: service_healthy
        restart: true
      redis:
        condition: service_healthy
  redis:
    image: redis:8@sha256:3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      retries: 5
  db:
    image: postgres:18@sha256:5f3b1c7c4a2e9f7d6c1b8a9e0d4f2c8b7a6e5d4c3b2a1908f7e6d5c4b3a29180
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      retries: 5
```

`app` won't start until `redis` and `db` both report healthy, and it
restarts automatically if a Compose-driven update replaces `db`. Neither
`redis` nor `db` needs a `depends_on` entry of its own — they're the leaves
of this ordering graph.

**`docker compose up -d --wait` closes the last gap between "the containers
started" and "the deploy is actually done."** It runs detached and blocks
the invoking shell — a CI job, a deploy script — until every service is
`running` (or `healthy`, for services with a `healthcheck:`), rather than
returning the instant containers are created. Pair it with `--wait-timeout`
in CI so a dependency that never turns healthy fails the pipeline instead of
leaving it green against a stack that silently never came up. —
https://docs.docker.com/reference/cli/docker/compose/up/

`service_completed_successfully` covers the fourth common shape: a one-shot
init container that must finish, not just start, before anything downstream
runs — a schema migration ahead of the API that queries that schema:

```yaml
services:
  migrate:
    image: acme/api:1.4.2@sha256:9c27e1f3b8a1d9e6f9a0b9c9d9e9f9a0b9c9d9e9f9a0b9c9d9e9f9a0b9c9d9e9
    command: ["python", "-m", "acme.migrate"]
    depends_on:
      db:
        condition: service_healthy

  app:
    image: acme/api:1.4.2@sha256:9c27e1f3b8a1d9e6f9a0b9c9d9e9f9a0b9c9d9e9f9a0b9c9d9e9f9a0b9c9d9e9
    depends_on:
      migrate:
        condition: service_completed_successfully
```

If `migrate` exits non-zero, `app` never starts — `docker compose up` reports
the dependency failed rather than racing the API against a half-migrated
schema. This is the same reason `condition: service_healthy` exists for
long-running dependencies: neither condition trusts "the container is
running" as a proxy for "the container is ready."

## Secrets

Compose ships a top-level `secrets:` element modeled on Swarm secrets but
fully usable outside Swarm — file- or environment-sourced, mounted read-only
into the container filesystem instead of injected as an environment
variable.

**Rules**

- **Prefer top-level `secrets:` plus a per-service `secrets:` list over
  `environment:` / `env_file:` for credentials.** Environment variables set
  on a container are readable in plaintext by anything that can run
  `docker inspect`, they surface in `docker compose config` output, they're
  inherited by every child process the entrypoint spawns, and they routinely
  end up in crash logs or error-reporting payloads without anyone
  deliberately printing them. A file-backed secret sidesteps all of that —
  it isn't part of the container's environment at all, and access is
  gated per service via standard filesystem permissions. —
  https://docs.docker.com/compose/how-tos/use-secrets/
- **Two sources: `file:` or `environment:`.** `file:` reads the secret's
  value from a host path (or a mounted secret file from an external agent);
  `environment:` populates the secret's value from a build-time/host
  environment variable, but converts it into a mounted file rather than
  propagating it into the running container's env. Pick `file:` for
  anything already living on disk from a secrets manager (SSM Parameter
  Store agent, Vault agent, CI-injected file); pick `environment:` when the
  only source at compose-invocation time is a shell variable and the goal
  is a mounted file, not an inherited env var. —
  https://docs.docker.com/compose/how-tos/use-secrets/
- **Secrets mount read-only at `/run/secrets/<secret_name>` by default.**
  The application reads the credential as a file, not `os.environ` — and a
  service only gets a given secret when it lists that secret explicitly
  under its own `secrets:` key; there is no ambient access to every secret
  declared in the file. — https://docs.docker.com/compose/how-tos/use-secrets/
- **Use the long-form per-service `secrets:` entry with `target:` to rename
  the in-container filename** when the application expects a specific
  path or filename that doesn't match the top-level secret's name — common
  with third-party images that hardcode a credential-file path.

```yaml
secrets:
  db_password:
    file: ./secrets/db_password.txt

services:
  api:
    image: acme/api:1.4.2@sha256:9c27e1f3b8a1d9e6f9a0b9c9d9e9f9a0b9c9d9e9f9a0b9c9d9e9f9a0b9c9d9e9
    secrets:
      - db_password
    environment:
      DB_PASSWORD_FILE: /run/secrets/db_password
```

`DB_PASSWORD_FILE` here is an application-level convention, not a Compose
feature by itself — the app has to know to read a path from an environment
variable and load that file's contents. Frameworks that already support
Docker/Kubernetes-style secrets natively (many settings libraries do, via a
`_FILE`-suffix convention) need no extra glue at all; for anything that
doesn't, a thin entrypoint step reading the file into the process the app
actually needs it in is cheaper than reintroducing the credential as a
plain environment variable.

**Build-time secrets are a separate, narrower mechanism from the runtime
`secrets:` above — don't conflate them.** A per-service `build.secrets:`
list grants a `docker build` step access to a secret for the duration of
that build only; it never lands in a container filesystem or a running
service, and — critically — declaring a secret at the top level does not
implicitly grant any service's build access to it, each grant is explicit.
Pair it with a Dockerfile `RUN --mount=type=secret,...` instruction so the
value never gets baked into an image layer. —
https://docs.docker.com/reference/compose-file/build/#secrets

```yaml
secrets:
  npm_token:
    environment: NPM_TOKEN

services:
  api:
    build:
      context: .
      secrets:
        - npm_token
```

```dockerfile
# in the Dockerfile this build stage references
RUN --mount=type=secret,id=npm_token \
    NPM_TOKEN="$(cat /run/secrets/npm_token)" npm ci
```

The `RUN` layer above never contains `NPM_TOKEN` in its cache key or its
final filesystem diff — the secret is mounted only for that instruction's
duration, which is the entire reason `--mount=type=secret` exists instead of
a plain build `ARG`.

## Runtime policies

Three independent knobs share the same failure mode: every one of them
defaults to "fine for a laptop, wrong for a service that has to survive a
host reboot or a burst of memory pressure." Restart policy, resource limits,
and log retention are the floor, not optional hardening, for anything
long-lived.

**Rules**

- **`restart: unless-stopped` is the production default.** It restarts the
  container on failure or on daemon/host restart, but stops trying once
  someone explicitly stops it — unlike `always`, which resumes even a
  deliberate stop the next time the daemon itself restarts. —
  https://docs.docker.com/reference/compose-file/services/#restart
- **`restart: no` — the engine default — stays correct for one-shot jobs.**
  Migrations, seed scripts, batch tasks that are supposed to exit and stay
  exited should never carry `unless-stopped`; doing so turns a completed
  migration container into a restart loop the instant it exits `0`. —
  https://docs.docker.com/reference/compose-file/services/#restart
- **`on-failure[:max-retries]` sits between the two** for jobs that should
  retry a bounded number of times on a nonzero exit but never restart after
  a clean one — a narrower tool than `unless-stopped`, worth naming
  explicitly when that's the actual requirement instead of reaching for the
  broader policy by habit. —
  https://docs.docker.com/reference/compose-file/services/#restart
- **Quote `restart: "no"` in YAML.** Unquoted `no`/`yes`/`on`/`off` parse as
  booleans under the YAML core schema Compose files use — an unquoted
  `restart: no` is not a syntax error, but it is silently the wrong type for
  the key, which is why every Compose example that sets this value quotes
  it.
- **Set limits and reservations under `deploy.resources`, not the legacy
  top-level `mem_limit` / `cpus` / `cpu_shares` keys.** `deploy:` reads as
  Swarm-only from its history, but the `resources` sub-key specifically is
  honored by plain, non-Swarm `docker compose up` — `limits` caps what the
  container may consume, `reservations` is a softer guarantee of what it may
  always claim. The legacy flat keys are superseded and shouldn't appear in
  new files. — https://docs.docker.com/reference/compose-file/deploy/#resources
- **Configure the logging driver and rotation explicitly — the engine
  default (`json-file` with no `max-size`) grows without bound.** Set
  `max-size` / `max-file` (and `compress: true` for rotated-out logs) under
  `logging.options`; an unrotated `json-file` log on a long-lived container
  is a routine "disk full at 3am" incident, not a hypothetical edge case. —
  https://docs.docker.com/engine/logging/configure/
- **Set `stop_grace_period` and `stop_signal` for anything that needs more
  than the 10-second default to shut down cleanly.** Compose sends
  `stop_signal` (`SIGTERM` unless overridden) and waits up to
  `stop_grace_period` (10 seconds by default) for the process to exit before
  escalating to `SIGKILL`. A worker mid-drain of an in-flight job, or a
  database flushing to disk, needs that window widened explicitly — the
  default silently truncates any shutdown routine that takes longer. —
  https://docs.docker.com/reference/compose-file/services/#stop_grace_period
- **Set `pull_policy: always` for anything a mutable tag might still point
  at in production, and know the default otherwise.** The engine default,
  `missing`, only pulls when the image isn't already cached locally — cheap,
  but it means a re-deploy of the same tag on a host that already has a
  stale copy cached does nothing without an explicit pull. Digest-pinned
  images (see Single-host production below) sidestep the ambiguity
  entirely, since a given digest is either present or it isn't — there's no
  "stale" version of an immutable reference to accidentally reuse. —
  https://docs.docker.com/reference/compose-file/services/#pull_policy
- **Prefer the top-level `restart:` key over `deploy.restart_policy` unless
  the finer-grained `condition`/`delay`/`max_attempts`/`window` controls are
  actually needed.** `deploy.restart_policy` exists as a more granular
  alternative — Compose falls back to the service's `restart:` field
  whenever `restart_policy` isn't set — so introducing both on the same
  service is redundant at best and conflicting at worst; pick one
  mechanism and let the other stay unset. —
  https://docs.docker.com/reference/compose-file/deploy/

```yaml
services:
  worker:
    image: acme/worker:2.1.0@sha256:7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 1G
        reservations:
          memory: 256M
    logging:
      driver: json-file
      options:
        max-size: "20m"
        max-file: "5"
        compress: "true"

  migrate:
    image: acme/worker:2.1.0@sha256:7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f
    restart: "no"
    command: ["python", "-m", "acme.migrate"]
```

`worker` survives OOM pressure elsewhere on the host without starving its
neighbors, restarts on failure, and rotates its own logs. `migrate` runs
once, exits, and stays exited — no restart policy fights that intent, and no
resource block is needed for a container that lives for seconds.

## Volumes

Two mount mechanisms, two different lifecycles — conflating them is how
"persistent" state quietly stops being persistent, or how a dev bind mount
ends up doing double duty as a production data directory nobody backs up.

**Rules**

- **Named volumes for anything the service needs to survive its own
  container's lifecycle** — database data directories, message-broker
  state, uploaded-file storage. Declared once under the top-level
  `volumes:` key, referenced by name from any service that needs it, with
  Docker owning the storage location — no host path to manage by hand. —
  https://docs.docker.com/reference/compose-file/services/#volumes
- **Bind mounts for dev source-sync and host-owned config, not persistent
  state.** A bind mount ties a container path directly to a host filesystem
  path — right for "the source tree I'm editing live" or "a config file
  ops hand-edits on the host," wrong for "the data this service must not
  lose," because nothing stops a careless host-side `rm`, or the host being
  rebuilt out from under it, from destroying that data entirely outside
  Docker's view. — https://docs.docker.com/reference/compose-file/services/#volumes
- **Short-form (`name:/path` or `./host/path:/path[:ro]`) covers most
  cases; long-form (`type: volume|bind`, plus `read_only`,
  `bind.propagation`, `volume.nocopy`) is for the cases that need those
  extra knobs** — a read-only config bind, a volume that must not
  auto-populate from image content on first mount, mount-propagation or
  SELinux-relabeling flags. Reach for long-form when the short string can't
  express what's needed, not as a default style choice. —
  https://docs.docker.com/reference/compose-file/services/#volumes

  ```yaml
  # short-form — sufficient until a knob below is needed
  volumes:
    - pg-data:/var/lib/postgresql/data:ro
  ```

  ```yaml
  # long-form — same mount, explicit, plus `nocopy`
  volumes:
    - type: volume
      source: pg-data
      target: /var/lib/postgresql/data
      read_only: true
      volume:
        nocopy: true          # skip image-content auto-populate on first mount
  ```

  The two blocks express the same mount for the common case; the long-form
  is only worth the extra lines once `nocopy` (or a bind's `propagation`)
  is actually needed — don't default to long-form syntax for a mount the
  short string already says completely.
- **Know what `docker compose down -v` actually does before running it near
  a named volume.** Plain `down` leaves named volumes intact; adding `-v`
  removes them — the flag standing between a routine teardown and losing
  the state named volumes exist to protect. Treat `-v` as a deliberate,
  named step in a runbook, never a default.
- **Mark a volume `external: true` when its lifecycle is managed outside
  this compose file entirely** — provisioned by a separate bootstrap step,
  shared across multiple independent compose projects, or simply meant to
  outlive this project being torn down and recreated. Compose then looks
  for an existing volume of that name instead of creating one, and errors
  out if it isn't there rather than silently creating a fresh, empty
  volume under a name that was supposed to already hold data. —
  https://docs.docker.com/reference/compose-file/volumes/
- **Use `driver_opts` with the `local` driver to give a bind mount a stable
  volume name, or to back a named volume with something other than local
  disk (NFS being the common case).** This is the escape hatch for "I want
  the naming and lifecycle semantics of a named volume, but the storage
  itself isn't a plain Docker-managed local directory." —
  https://docs.docker.com/reference/compose-file/volumes/

```yaml
volumes:
  pg-data:
  shared-cache:
    external: true       # provisioned outside this compose file
  nfs-archive:
    driver_opts:
      type: nfs
      o: "addr=10.40.0.199,nolock,soft,rw"
      device: ":/docker/archive"

services:
  db:
    image: postgres:18@sha256:5f3b1c7c4a2e9f7d6c1b8a9e0d4f2c8b7a6e5d4c3b2a1908f7e6d5c4b3a29180
    volumes:
      - pg-data:/var/lib/postgresql/data      # named volume: persists past `down`
      - ./config/postgresql.conf:/etc/postgresql/postgresql.conf:ro  # bind: host-owned config
```

`pg-data` outlives `docker compose down`, container recreation, and image
upgrades; the config bind is source-controlled on the host and read-only in
the container, so nothing inside can mutate the file ops manages.
`shared-cache` and `nfs-archive` never get created or destroyed by this
project's `up`/`down` cycle at all — they're declared here only so services
in this file can reference them by name.

**A third mechanism, `tmpfs:`, covers the opposite end of the persistence
spectrum from both** — an in-memory mount that never touches disk and
never survives the container being removed, right for scratch space and
secrets-adjacent temp files that genuinely should vanish on exit rather
than land on any filesystem, host or named volume, even briefly. —
https://docs.docker.com/reference/compose-file/services/#tmpfs

```yaml
services:
  api:
    tmpfs:
      - /tmp
      - /run
```

Pick `tmpfs:` deliberately, not as a default — it competes for host memory
under `deploy.resources.limits.memory` (see Runtime policies above), so an
unbounded `tmpfs` mount on a memory-constrained container is its own
resource-exhaustion risk, not a free lunch relative to disk.

## Dev loop

`develop.watch` replaces "bind-mount the whole source tree and hope the
framework's dev server notices" with declared, per-path sync and rebuild
rules — a mechanism for keeping a running container current without a full
`up` cycle on every keystroke.

**Rules**

- **`action: sync` for source changes a running process can pick up without
  a rebuild** — framework hot-reload, interpreted-language source, static
  assets. Compose copies the changed path straight into the running
  container's filesystem at the matching `target:`, without touching the
  image, and the documentation frames it explicitly as something that "can
  be used in place of bind mounts for many development use cases." —
  https://docs.docker.com/compose/how-tos/file-watch/
- **`action: rebuild` for anything that changes what the image contains,
  not just what's mounted into it** — a manifest or lockfile
  (`pyproject.toml`, `uv.lock`, `package.json`, `package-lock.json`), or a
  Dockerfile edit itself. Compose reruns the build via BuildKit and replaces
  the running container. —
  https://docs.docker.com/compose/how-tos/file-watch/
- **`action: sync+restart` sits between the two** — files land via sync (no
  rebuild), then the service process restarts, for changes a hot-reloader
  won't notice on its own but that don't require touching the image (a
  config file the app only reads at process startup). —
  https://docs.docker.com/compose/how-tos/file-watch/
- **Always set `ignore:` for anything that shouldn't round-trip through the
  watch sync — most importantly `.venv/` and `node_modules/`.** Without it,
  watch either fights the container's own dependency install (a host
  `.venv` overwriting the image's) or burns CPU and inotify handles diffing
  a directory that's supposed to stay container-local in the first place. —
  https://docs.docker.com/compose/how-tos/file-watch/
- **Only declared `path:` entries are watched at all.** A file or directory
  that isn't covered by any `sync`/`rebuild`/`sync+restart` rule produces
  zero action on change — watch never falls back to blanket bind-mount-style
  "everything under the project root is live." Every path a developer
  expects to edit and see reflected needs an explicit rule; a new top-level
  directory added to the project needs a new watch entry, not an assumption
  that it's already covered. — https://docs.docker.com/compose/how-tos/file-watch/

```yaml
services:
  api:
    build: .
    develop:
      watch:
        - action: sync
          path: ./src
          target: /app/src
          ignore: [.venv/]
        - action: rebuild
          path: ./pyproject.toml
        - action: rebuild
          path: ./uv.lock
```

Watch mode is invoked explicitly — `docker compose watch`, or
`up --watch` — separate from a bare `up`. That means a `compose.override.yaml`
can declare `develop.watch` unconditionally without changing the behavior of
an ordinary `docker compose up` for anyone who hasn't opted into watch mode.

`action: rebuild` presumes the service already has a `build:` block —
watch rebuilds the image Compose itself knows how to build; it has no
mechanism to rebuild a service pinned to a registry `image:` with no local
build context. This is one more reason `develop.watch` belongs in
`compose.override.yaml` specifically (see File layering above): the dev
override is exactly the file that swaps a service from `image:` to
`build:` in the first place, so `develop.watch` and the `build:` block it
depends on land in the same layer together, not split across files.

## Env files

Three different "environment" mechanisms exist side by side, each with
different git-hygiene expectations and a defined precedence when two of them
disagree about the same key.

**Rules**

- **`.env` in the project root is for interpolation defaults and Compose
  CLI behavior, and it's git-ignored.** Values there fill in
  `${VAR}` / `${VAR:-default}` placeholders anywhere in the compose file at
  parse time — a Compose-CLI-level mechanism, not something injected into a
  container's runtime environment on its own. —
  https://docs.docker.com/compose/how-tos/environment-variables/
- **`env_file:` on a service loads a file's contents into that container's
  runtime environment** — the container-facing equivalent of a Dockerfile
  `ENV` block, sourced from outside the image at compose time rather than
  baked in at build time. —
  https://docs.docker.com/compose/how-tos/environment-variables/
- **`environment:` on a service wins over `env_file:` when both set the
  same key.** The documented precedence, highest to lowest, is: a value
  passed with `-e`/`--env` to `docker compose run`, the service's
  `environment:` attribute, the service's `env_file:` attribute, then any
  `ENV` baked into the image itself — a value in `environment:` always
  overrides the same key sourced from `env_file:` on that service, never the
  reverse. —
  https://docs.docker.com/compose/how-tos/environment-variables/envvars-precedence/
- **Commit only a `.env.sample` (or `.env.example`) — never the real
  `.env`.** The sample documents every key the compose file interpolates,
  with placeholder or non-secret default values; the real `.env` — actual
  credentials, machine-local overrides such as a host network subnet —
  stays git-ignored, generated per developer or per environment from the
  sample. — https://docs.docker.com/compose/how-tos/environment-variables/
- **Pick the interpolation form that matches whether "unset" should be an
  error.** `${VAR}` substitutes directly; `${VAR:-default}` and
  `${VAR-default}` both supply a fallback, but the colon form additionally
  falls back when the variable is set-but-empty, while the bare form only
  falls back when it's fully unset; `${VAR:?error}` / `${VAR?error}` invert
  that into a hard failure with a custom message instead of a silent
  fallback, for anything that must never resolve to an empty string. Use
  the `:?` form for secrets and connection strings the compose file
  interpolates directly — a silently empty `${DB_PASSWORD:-}` is a footgun,
  not a convenience. —
  https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/
- **Override which `.env` file Compose reads for interpolation with the
  global `--env-file <path>` flag** when the default root-directory `.env`
  isn't the right one for a given invocation — a CI job pointing at a
  `.env.ci` without renaming files, or a monorepo where the compose file
  lives one directory away from the environment file it should use. This is
  a CLI-level override of the interpolation source, distinct from a
  service's own `env_file:` list below, which governs the container's
  runtime environment, not parse-time interpolation. —
  https://docs.docker.com/reference/cli/docker/compose/
- **Reach for the long-form `env_file:` entry (`path:` + `required:`) when
  a file is genuinely optional, and know the multi-file precedence order.**
  `required:` defaults to `true` — a missing file is an error unless it's
  explicitly marked `required: false`. Multiple `env_file:` entries are
  processed top-down, and the last file in the list wins on any key
  duplicated across them, same direction as the file-layering merge rule
  above. —
  https://docs.docker.com/reference/compose-file/services/#env_file

```yaml
# compose.yaml
services:
  api:
    image: acme/api:${API_TAG:-1.4.2}          # interpolated from .env at parse time
    env_file:
      - path: ./api.env
        required: true                          # default
      - path: ./api.local.env
        required: false                         # dev-machine overrides, optional
    environment:
      DB_PASSWORD: ${DB_PASSWORD:?DB_PASSWORD must be set}
      LOG_LEVEL: debug                     # wins over the same key set in either env_file
```

```text
# .env.sample — commit this, placeholder values only
API_TAG=1.4.2
```

```text
# .env — real values, git-ignored, never committed
API_TAG=1.4.9
```

`API_TAG` here does double duty deliberately: it interpolates the image tag
Compose resolves at parse time, while `api.env` and `environment:` govern
what the *running container* sees at runtime — three layers, three different
questions, one precedence order.

## Single-host production

`CONTESTED —` Docker's own documentation walks through deploying an
application to a single production server as a first-class, fully supported
path, with no orchestrator required
(https://docs.docker.com/compose/how-tos/production/); a competing
operations position holds that anything lacking built-in self-healing,
rolling updates, and multi-host scheduling shouldn't carry a "production"
label at all, regardless of how well-hardened the single host is
(https://distr.sh/blog/running-docker-in-production/). This reference takes
Docker's documented position for genuinely single-host workloads —
internal tools, low-QPS APIs, worker fleets that tolerate a restart-driven
blip — and treats "this has to survive losing the host itself, not just a
container on it" as the hard trigger to stop and adopt an orchestrator
instead of arguing the point further.

Getting there is not "just run `docker compose up -d` on a bigger box." It
means closing every gap below, deliberately, in a file that's already
covered by Startup ordering, Secrets, and Runtime policies further up this
reference:

| Gap | Close it with | Source |
| --- | --- | --- |
| Floating image tags | Pin every service `image:` to `tag@sha256:digest`, never a bare tag or `:latest`; pair with an automated digest-bump PR flow so a pin doesn't calcify into a frozen, unpatched CVE | https://docs.docker.com/build/building/best-practices/#pin-base-image-versions, https://docs.renovatebot.com/docker/ |
| Silent process death | `healthcheck:` on every long-running service plus `restart: unless-stopped` — see Startup ordering and Runtime policies above | https://docs.docker.com/reference/compose-file/services/#healthcheck, https://docs.docker.com/reference/compose-file/services/#restart |
| Unbounded resource contention | `deploy.resources.limits` and `reservations` on every service — see Runtime policies above | https://docs.docker.com/reference/compose-file/deploy/#resources |
| Credentials in `docker inspect` / logs | Compose `secrets:`, not `environment:` — see Secrets above | https://docs.docker.com/compose/how-tos/use-secrets/ |
| Disk-filling container logs | `logging.options` rotation (`max-size` / `max-file`) on every service — see Runtime policies above | https://docs.docker.com/engine/logging/configure/ |
| Exposed Docker socket | Never bind-mount `/var/run/docker.sock` into an application container; audit any host process that does need socket access against the CIS Docker Benchmark | https://www.cisecurity.org/benchmark/docker |
| No deploy or rollback path | A named, scripted update sequence (`docker compose pull && docker compose up -d`, driven by CI, not ad hoc SSH-and-edit), with the previous digest recorded so a rollback is a redeploy of the prior pin, not a scramble | https://docs.docker.com/compose/how-tos/production/ |
| Stale cached images masking a redeploy | `pull_policy: always` (or CI always calling `docker compose pull` before `up`) on every service pinned by a tag that might move — the engine's `missing` default only pulls when nothing is cached locally, which does nothing on a redeploy of a tag the host already has | https://docs.docker.com/reference/compose-file/services/#pull_policy |
| Orphaned containers from a removed or renamed service | `docker compose up -d --remove-orphans` as a standard part of the update sequence — it removes containers for services no longer defined in the file, closing the gap a plain `up` leaves whenever a service is deleted or renamed rather than added | https://docs.docker.com/reference/cli/docker/compose/up/ |

A `docker compose -f compose.yaml -f compose.prod.yaml config --quiet` step
belongs ahead of every one of the update-sequence rows above in the actual
CI pipeline, not just in this reference — `--quiet` runs full model
validation and consistency checking without printing the merged file,
making it the cheap gate that catches a broken merge (a typo'd service
name in an `extends`, a `depends_on` pointing at a service that no longer
exists) before any container is touched. —
https://docs.docker.com/reference/cli/docker/compose/config/

None of the rows above are independent extra-credit items — they compose
into a single property: a host that can lose a container, a process, or a
credential leak without losing the whole service, and that can be updated
without an operator improvising the sequence from memory. A single-host
Compose deployment that closes every row above is still a single host; it
has no answer to losing the host itself, and that gap doesn't shrink no
matter how thoroughly the checklist is completed.

The moment any workload on that host needs to survive losing the host
itself — not just a container on it — multi-host scheduling and self-healing
stop being optional extras, and that becomes an orchestrator's job
(Kubernetes, Nomad, ECS), not a Compose file's, however completely the
checklist above has been closed.

---

_Verified as of 2026-07; sources re-checked against docs/superpowers/research/2026-07-20-*.md._
