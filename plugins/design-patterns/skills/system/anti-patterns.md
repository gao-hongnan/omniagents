---
paths:
  - "**/*.py"
  - "**/*.tf"
  - "**/Dockerfile"
  - "**/k8s/**"
  - "**/docker-compose.*.yml"
---

# System-Level Anti-Patterns

> Architecture-scale failure shapes — patterns whose presence predicts incidents. Each
> entry frames the *bad shape*, the *fix* (which other pattern to reach for), and the
> *blast radius* (what production looks like when this anti-pattern fires).

A system-level anti-pattern is a shape that survives every PR review because it lives in
the *gaps between* services — in the route table, the deploy pipeline, the shared
database, the silent retry policy. Code-level smells (god object, primitive obsession)
are caught with `grep` and a careful reviewer; system-level smells require running the
system in production for six months. By then, they are very expensive to fix.

This file complements `software/anti-patterns.md`, which handles code-level smells. There
is one intentional point of overlap: *Distributed Monolith* appears briefly there and in
depth here. Everything else is exclusive.

The default posture: **if you cannot describe the failure mode in one sentence and the
blast radius in another, you don't yet understand the architecture you have**.

## Table of Contents

- [How to use this file](#how-to-use-this-file)
- [Distributed Monolith](#distributed-monolith)
- [Chatty Interfaces (N+1 RPC)](#chatty-interfaces-n1-rpc)
- [Two-Phase Commit Abuse](#two-phase-commit-abuse)
- [Shared Database](#shared-database)
- [Death Star Architecture](#death-star-architecture)
- [Premature Microservices Adoption](#premature-microservices-adoption)
- [Synchronous Cross-Service Calls When Async Fits](#synchronous-cross-service-calls-when-async-fits)
- [Sticky Sessions Everywhere](#sticky-sessions-everywhere)
- [Hot-Path Database Locking](#hot-path-database-locking)
- [Single Point of Failure (SPOF)](#single-point-of-failure-spof)
- [Cascading Failures](#cascading-failures)
- [Retry Storms](#retry-storms)
- [Naive Caching](#naive-caching)
- [Lift-and-Shift Cloud Migration](#lift-and-shift-cloud-migration)
- [Vendor Lock-In by Default](#vendor-lock-in-by-default)
- [Observability as Afterthought](#observability-as-afterthought)
- [Configuration Drift](#configuration-drift)
- [Time Bombs](#time-bombs)
- [Big Bang Migrations](#big-bang-migrations)
- [Review Checklist](#review-checklist)
- [References](#references)

---

## How to use this file

Read this file **before** the design review of any cross-service work, **during** an
incident postmortem to name what happened, and **after** any "we just need to add a
retry" conversation that did not also discuss budgets. Each entry maps the symptom to a
fix in `scaling.md`, `cloud.md`, or `reliability.md`.

Code is Python 3.13+ and written to target mypy `--strict` and pyright `--strict`.
"Bad" examples are deliberately wrong; "Fix" examples sketch the correct shape.

---

## Distributed Monolith

**What it is / How it manifests.** A system split into many services that nevertheless
must deploy together, share a database, and synchronously chain through each other on
every user request. You paid the operational cost of microservices (network, partial
failure, deployment coordination) without getting the benefits (independent scaling,
independent evolution, fault isolation).

**Telltale signs.**

- Releases require a specific *order*: "deploy `users-svc` first, then `orders-svc`."
- A schema migration requires coordinated releases across N services.
- One service's outage takes the whole product down.
- A single user request fans out to ≥ 5 internal calls, all synchronous.
- Teams cannot change their service without another team's review.
- Services share types via a published "shared-models" library that everyone vendors.

**Bad shape.**

```python
# BAD: orders-svc depends on the in-memory state of users-svc and inventory-svc.
# Every order goes through synchronous calls to BOTH; a 300ms inventory call is
# in the order-placement critical path.

async def place_order(user_id: str, sku: str) -> Order:
    user = await users_client.get(user_id)        # 80ms
    item = await inventory_client.reserve(sku)    # 300ms
    pricing = await pricing_client.quote(sku, user.tier)  # 120ms
    order = await orders_repo.create(user, item, pricing) # 50ms
    await notification_client.send_confirmation(user.email, order)  # 200ms
    await analytics_client.record(order)          # 100ms
    return order
# Total p50: ~850ms. p99 if any one downstream blips: minutes.
# All services share `models.shared` for User, SKU, Money.
```

**Fix.**

- Reduce coupling: each service owns its data, exposes a stable API, and is not
  required for the request to *complete* (only to enrich, downstream).
- Move non-critical steps off the critical path: notifications, analytics, audit logs
  are async events.
- Either consolidate to a *modular monolith* until the seams are clear, or extract one
  service at a time using the [Strangler Fig](cloud.md#strangler-fig).
- Replace the shared-models library: each service owns its own canonical types; the wire
  format is the contract.

**Blast radius.** When users-svc goes down at 03:00, every other service's p99 goes to
infinity. Every retry storm starts here. The first time someone tries to roll back
just one service, they discover that the schema migration is incompatible — so now you
must restore from backup or roll forward. Average MTTR doubles for every incident.

**Real-world examples.**

- ThoughtWorks Technology Radar (2014) coined the term to describe many failed
  microservices migrations.
- Sam Newman's *Monolith to Microservices* opens with this anti-pattern as the "worst
  of both worlds."

---

## Chatty Interfaces (N+1 RPC)

**What it is / How it manifests.** A service whose endpoints require many round-trips to
do useful work, often because each "fine-grained" call returns one entity and the client
must call N more times to fetch the related data. Equivalent to ORM N+1 queries, but at
the network level — each "+1" is a serialization, a network hop, and a latency tax.

**Telltale signs.**

- A page that shows 50 orders fires 51 calls (1 list + 50 details).
- A `for ... in items: await client.get(item)` pattern at a service boundary.
- p99 latency is dominated by *count of calls*, not *size of any one call*.
- The service has many tiny endpoints and no batch endpoint.

**Bad shape.**

```python
# BAD: N+1 over the network.
async def render_order_page(order_ids: list[str]) -> list[OrderDetail]:
    details: list[OrderDetail] = []
    for oid in order_ids:                         # 1 request per id
        order = await orders_client.get(oid)      # 80ms each
        items = await inventory_client.lookup_skus(order.sku_ids)  # 100ms each
        details.append(OrderDetail(order=order, items=items))
    return details
# 50 orders × 180ms = 9 seconds for a page render. p99 worse.
```

**Fix.** Add a batch endpoint and a single call:

```python
# FIX: one round-trip; server fans out internally with proper concurrency.
async def render_order_page(order_ids: list[str]) -> list[OrderDetail]:
    return await orders_client.get_batch_with_items(order_ids)
```

For genuine cross-service joins, prefer:

- **GraphQL or BFF (Backend-for-Frontend)** to express the join once at the edge.
- **Materialized views** maintained from event streams, so the read path is a single
  fetch.
- **Concurrent fan-out** (asyncio.gather, with bounded concurrency) — only as a *latency*
  fix, never as a *correctness* fix; the chattiness is still there, just parallelized.

See [Backpressure-aware Scaling](scaling.md#backpressure-aware-scaling) and
[Connection Pooling](scaling.md#connection-pooling) for what happens when the fan-out
is unbounded.

**Blast radius.** Page load time scales linearly with number of items. Bursty traffic
multiplies inner-service load: 10 user requests × 50 orders = 500 internal calls. Pool
exhaustion. Then a retry storm.

---

## Two-Phase Commit Abuse

**What it is / How it manifests.** Using XA transactions or distributed ACID transactions
across services. A transaction coordinator holds locks across services for the duration
of the commit; a coordinator failure leaves participants in `IN-DOUBT` state, requiring
manual recovery.

**Bad shape.** Pseudocode (real XA over services is mostly extinct, mostly because of
this pattern's failure modes):

```python
# BAD: distributed XA across services.
xa.begin()
xa.enlist(orders_db)
xa.enlist(inventory_db)
xa.enlist(payments_db)

orders_db.insert(order)
inventory_db.decrement(sku, qty)
payments_db.charge(amount)

xa.prepare()  # all three say "yes" or "no"
xa.commit()   # if coordinator dies after prepare, participants block
```

**Fix.** Use a [Saga](cloud.md#compensating-transaction) — local transactions per
service, with compensating actions for failures. Sagas are eventually consistent and
operationally tractable; XA is neither.

```python
# FIX: saga with compensations (see cloud.md / distributed.md).
async def place_order(req: OrderRequest) -> OrderId:
    order_id = await orders_repo.create_pending(req)
    try:
        reservation_id = await inventory.reserve(req.sku, req.qty)
    except Exception:
        await orders_repo.mark_failed(order_id)
        raise
    try:
        auth_code = await payments.charge(req.amount, idempotency_key=order_id)
    except Exception:
        await inventory.release(reservation_id)
        await orders_repo.mark_failed(order_id)
        raise
    await orders_repo.mark_confirmed(order_id, auth_code)
    return order_id
```

**Blast radius.** XA's mode of failure is silent: the coordinator's log file fills up
or its disk dies, and dozens of transactions stay in-doubt for hours. Operators must
manually `commit/rollback` each one against each participant. During the process, all
related rows are locked. Application latency shoots to infinity.

**Real-world examples.**

- Fowler, *Patterns of Enterprise Application Architecture*: warns against XA outside
  homogeneous environments.
- Multiple e-commerce postmortems (early 2010s) of Oracle XA + WebSphere coordinator
  failures locking inventory tables.

---

## Shared Database

**What it is / How it manifests.** Multiple services write to the same tables in the
same database. Schema changes require coordinated deploys; a slow query in one service
locks rows that another service is waiting on; the data model encodes assumptions of
*every* service that has ever touched it.

**Telltale signs.**

- A `users` table is updated by `auth-svc`, `profile-svc`, `billing-svc`, and the
  `legacy-monolith`.
- Adding a column requires reviewing N services.
- An incident's root cause is "service A wrote a NULL where service B expected ''".
- The DBA team is the de-facto architecture team.

**Bad shape (sequence diagram in ASCII).**

```
   auth-svc ─┐
             ├──▶ shared `users` table
   profile-svc┤
             ├──▶ shared `users` table
   billing-svc┘
                  ▲
                  │  schema change requires coordination across all three
```

**Fix.**

- *Database-per-service.* Each service owns its data. Other services use the API, never
  the table. (Sam Newman, *Building Microservices*, ch. 4.)
- For migrations from a shared DB, use a *strangler* approach: introduce per-service
  tables behind APIs; dual-write during transition; cut over reads; retire legacy
  tables.
- Where data must be shared *in shape*, publish events; downstream services maintain
  their own materialized views.

**Blast radius.** Service A deploys a column rename; service B (which the deployer did
not know about) starts 500'ing every request. The schema migration cannot be rolled
back without downtime because service A has already started writing to the new column.
Average incident: 4 hours, multiple teams paged.

**Real-world examples.**

- *Most monoliths-to-microservices failures.* The team extracts a service but leaves the
  table behind; the "service" still has the same coupling.
- *Slack's eventual move to per-team Vitess shards* documents the cost of a previously
  shared DB.

**References.**

- Newman, S., *Building Microservices*, 2nd ed., ch. 4.
- Richardson, C., *Microservices Patterns*, ch. 2 (Database per Service).

---

## Death Star Architecture

**What it is / How it manifests.** Service-to-service dependency graph where everything
talks to everything; the diagram looks like an exploded yarn ball or, in Adrian
Cockcroft's borrowed phrasing, the Death Star. No clear bounded contexts, no layering,
no obvious blast-radius boundaries. Adding a service adds N edges, not 1.

**Bad shape.**

```
         ┌──────┐    ┌──────┐    ┌──────┐
         │ S1   │◀──▶│ S2   │◀──▶│ S3   │
         └──┬───┘    └──┬───┘    └──┬───┘
            │           │           │
            ▼           ▼           ▼
         ┌──────┐◀──▶┌──────┐◀──▶┌──────┐
         │ S4   │    │ S5   │    │ S6   │
         └──┬───┘    └──┬───┘    └──┬───┘
            └─────...──┴───────────┘   ← every service eventually depends on every other
```

**Fix.**

- Draw the graph (use tools: Jaeger service map, Backstage Tech Radar, Lucidchart).
- Identify *bounded contexts* (DDD): groups of services that change together and own
  one slice of the domain.
- Define a *layering*: API → domain → integration; or front-of-house / back-of-house.
  Forbid edges that cross boundaries except through documented APIs.
- Architectural fitness functions (`pyarchitecture`, `archunit`) enforce edges in CI.

**Blast radius.** Any one service slowing down propagates to all callers. No team can
predict the impact of their change. Onboarding takes months because nobody can describe
the system on a whiteboard. Eventually, an outage in a "trivial" service takes 90% of
the platform down because, transitively, everything depends on it.

**Real-world examples.**

- Netflix's 2014 microservices diagram (Adrian Cockcroft) — the canonical Death Star
  image. Netflix invested heavily in *isolation* patterns (Hystrix, regional failover)
  to make a Death Star survivable; do not assume the same investment.
- Twitter's pre-rewrite "monorail" architecture, often cited as motivation for the
  manhattan-style restructure.

**References.**

- Cockcroft, A., *Microservices reference architecture*, Netflix Tech Blog.
- Newman, S., *Building Microservices*, 2nd ed., ch. 6 (Workflow).

---

## Premature Microservices Adoption

**What it is / How it manifests.** Splitting a system into services *before* the seams
are visible — before the team has felt the pain of the monolith. Each new feature now
costs network coordination, deploy ordering, schema agreements, and a saga where a
local transaction would do.

**Telltale signs.**

- Headcount < 10, services > 10.
- The team's #1 complaint is "deploys are slow" — and the answer was "split the
  service" instead of "fix the deploy pipeline."
- Most domain changes touch ≥ 3 services.
- A 2-week feature now takes 6 weeks.

**Fix.** Start with a *modular monolith*: enforce module boundaries by imports, not by
network. Extract a service only when one of these is true:

- It needs to scale independently (different load profile).
- It needs to deploy independently (different release cadence).
- It uses a different language or runtime (a Python-only thing alongside a Go fleet).
- It must be isolated for compliance / security (PCI scope reduction).

If none of those is true, the monolith is correct.

**Blast radius.** Velocity halves, then halves again. The business stops shipping
features. The team blames "the architecture" and proposes another rewrite. Two-thirds of
microservices migrations stall here (industry surveys: O'Reilly, ThoughtWorks).

**Real-world examples.**

- Segment, 2018: famously *re-monolithed* a microservices fleet because operational tax
  exceeded the gain. Their post: "Goodbye Microservices: From 100s of problem children
  to 1 superstar."
- Istio's own deployment path: started multi-process, consolidated to fewer processes
  for operational sanity.

**References.**

- Newman, S., *Monolith to Microservices*, ch. 1 ("Just Enough Microservices").
- Fowler, M., *MonolithFirst*, martinfowler.com/bliki, 2015.

---

## Synchronous Cross-Service Calls When Async Fits

**What it is / How it manifests.** A user-facing endpoint that synchronously calls a
non-critical downstream service and *blocks* the response on it. The classic example:
"the order's confirmation email" sent inline in the order endpoint, so a slow SES /
Mailgun degrades order placement.

**Bad shape.**

```python
# BAD: order placement blocks on email.
@app.post("/orders")
async def place(req: OrderRequest) -> OrderResponse:
    order = await orders_repo.create(req)
    await payments.charge(req.payment, idempotency_key=order.id)
    await mailer.send_confirmation(req.email, order)   # ← blocks the response
    await analytics.record(order)                       # ← blocks too
    return OrderResponse(order_id=order.id)
```

If `mailer` has 5s latency, every user waits 5s. If it goes down, no orders go through.

**Fix.** Move non-critical steps onto an event bus or queue:

```python
# FIX: critical path = create + charge. Non-critical = published events.
@app.post("/orders")
async def place(req: OrderRequest) -> OrderResponse:
    order = await orders_repo.create(req)
    await payments.charge(req.payment, idempotency_key=order.id)
    # Fire-and-forget into the event bus; bus durability is the recovery boundary.
    await event_bus.publish("order.placed", OrderPlaced.from_order(order))
    return OrderResponse(order_id=order.id)


# Separate consumers handle confirmation / analytics, with retries and DLQ.
class ConfirmationEmailHandler:
    async def on_order_placed(self, event: OrderPlaced) -> None:
        await mailer.send_confirmation(event.email, event.order_id)
```

See [Choreography vs Orchestration](cloud.md#choreography-vs-orchestration). The rule
of thumb: if the user does not need the answer to complete the action, it should not be
in the critical path.

**Blast radius.** A 5-second latency on an "enhancing" dependency becomes a 5-second
latency on the user-facing endpoint. The cascade is immediate: requests pile up, threads
or async slots saturate, the whole service becomes unresponsive.

**Real-world examples.**

- Multiple e-commerce postmortems where mailer outages took down checkout.
- AWS Builders' Library, *Avoiding Fallback in Distributed Systems*: the original
  Amazon retail outage (~2001) was a *fallback* version of this anti-pattern.

---

## Sticky Sessions Everywhere

**What it is / How it manifests.** Affinity that ties a client to a specific replica via
cookie, IP hash, or session pinning. Used because in-memory state on the replica has not
been moved to a shared store. Deploys, scaling, and replica failures all hurt visibly,
and bugs in session-cleanup code accumulate.

**Bad shape.**

```nginx
# BAD: load balancer config that pins clients via cookie.
upstream app {
    server app-1:8080;
    server app-2:8080;
    server app-3:8080;
    sticky cookie SRV expires=1h;
}
```

The application stores `user_session` in `dict` on each replica. A scale-down event evicts
sessions; users get logged out at random.

**Fix.** Move session state to a shared store (Redis, DynamoDB, the JWT-on-cookie
pattern). Then the load balancer can use [P2C / least-connections](scaling.md#load-balancing).

```python
from typing import Final
from redis.asyncio import Redis


class SessionStore:
    """Replica-agnostic sessions: any replica can serve any user."""

    def __init__(self, redis: Redis, ttl_s: int = 3600) -> None:
        self._redis: Final = redis
        self._ttl_s: Final = ttl_s

    async def get(self, session_id: str) -> dict[str, str] | None:
        raw = await self._redis.get(f"sess:{session_id}")
        return None if raw is None else json.loads(raw)

    async def put(self, session_id: str, data: dict[str, str]) -> None:
        await self._redis.set(f"sess:{session_id}", json.dumps(data), ex=self._ttl_s)
```

**When sticky is correct.** Genuine per-client local state that's expensive to rebuild:
streaming connections (WebSockets, SSE), in-flight ML inference state, GPU-resident
caches. Even then, prefer *consistent hashing* (clients drift to the same replica
*deterministically*) over LB-managed cookies (state is in the LB, which is itself a
SPOF).

**Blast radius.** Deploys cause 100% of users to be re-authenticated. Replica failures
log out 1/N users without warning. Autoscaling-down kills hot replicas; sessions evicted
mid-request manifest as "I just lost my cart." Cumulative customer-experience cost is
hard to measure, easy to feel.

---

## Hot-Path Database Locking

**What it is / How it manifests.** `SELECT ... FOR UPDATE` or `LOCK TABLE` on a row that
sits in the critical path of every user request. Each request holds the lock while it
calls out to other services, reads JSON from disk, or waits for a network round-trip.
Concurrency collapses to 1.

**Bad shape.**

```python
# BAD: hold a row lock across a network call.
async with db.transaction():
    user = await db.fetch_one(
        "SELECT * FROM users WHERE id = $1 FOR UPDATE", user_id
    )
    # ↓ hundreds of milliseconds; the row is locked the whole time
    profile = await profile_client.get(user_id)
    user.last_seen = now()
    user.profile_version = profile.version
    await db.execute("UPDATE users SET ... WHERE id = $1", user_id)
```

Every user contends for the same row's lock; a slow `profile_client` call blocks every
other request for that user. With many users, the *connection pool* fills up too.

**Fix.**

- *Optimistic concurrency.* Read without lock; on update, check that the version did not
  change.
- *Idempotency keys + upserts.* Identify the request and let the database deduplicate.
- *Move the IO outside the transaction.* Read the foreign data first, then open a
  transaction long enough to commit.

```python
# FIX: optimistic concurrency, IO outside the lock.
profile = await profile_client.get(user_id)  # outside the transaction
async with db.transaction():
    rows = await db.fetch(
        "UPDATE users SET last_seen = $1, profile_version = $2 "
        "WHERE id = $3 AND profile_version <= $2 RETURNING id",
        now(), profile.version, user_id,
    )
    if not rows:
        raise OptimisticConflict(user_id)  # caller decides retry policy
```

**Blast radius.** Latency p99 spikes the moment the foreign call gets slow. Pool
exhaustion follows in seconds. Other services that share the DB feel it. PostgreSQL
deadlock detection or lock timeout fires; cleanup happens but only after multi-second
delays. Logs fill with `LockNotAvailable`; the temptation is to *raise the lock timeout*,
which deepens the hole.

**Real-world examples.**

- The classic "bank balance" transfer interview problem, attempted naively in production.
- Multiple Postgres incidents at scale-ups where a `FOR UPDATE` was held across an
  in-process retry loop.

---

## Single Point of Failure (SPOF)

**What it is / How it manifests.** A single component whose failure brings the whole
system down. Single Redis primary, single Kafka broker, single auth service with no
degraded mode, single DNS provider, single payment processor.

**Telltale signs.**

- An incident's RCA reads "X went down." With nothing about why no fallback existed.
- Capacity planning lists this component as "1 instance, will scale up if needed."
- DNS, certificate authorities, internal libraries — all "single" by default in many
  shops.

**Fix.** Replicate. Then design for *graceful degradation* of the dependent services.

| Component | Fix | Notes |
| --- | --- | --- |
| Redis primary | Sentinel / Cluster | Multi-AZ, automated failover. |
| Kafka broker | Min ISR ≥ 2; replication factor ≥ 3 | One broker loss = no data loss; not a stretch goal. |
| Auth service | Cache JWKS at consumers; allow tokens valid for some grace period during outages | Auth being down should not be 100% outage. |
| Single payment processor | Multiple providers via abstraction; fall back per-route on outage | Most hard, most valuable. |
| DNS provider | Multi-provider DNS (Route53 + Cloudflare) | After the 2016 Dyn outage, this is industry baseline. |

**Sketch (degraded auth fallback).**

```python
from datetime import UTC, datetime, timedelta
from typing import Final


class JWKSCache:
    """Cache JWKS keys so auth service brief outages do not = total outage."""

    def __init__(self, ttl: timedelta = timedelta(hours=1), grace: timedelta = timedelta(hours=12)) -> None:
        self._ttl: Final = ttl
        self._grace: Final = grace
        self._keys: dict[str, str] = {}
        self._fetched_at: datetime | None = None

    def is_fresh(self) -> bool:
        return self._fetched_at is not None and datetime.now(UTC) - self._fetched_at < self._ttl

    def is_within_grace(self) -> bool:
        return self._fetched_at is not None and datetime.now(UTC) - self._fetched_at < self._grace

    async def verify(self, token: str, refresh_now: Callable[[], Awaitable[dict[str, str]]]) -> bool:
        if not self.is_fresh():
            try:
                self._keys = await refresh_now()
                self._fetched_at = datetime.now(UTC)
            except Exception:
                if not self.is_within_grace():
                    raise
                # Within grace: serve from stale keys. Emit a degraded-mode counter.
        return _verify_signature(token, self._keys)


def _verify_signature(token: str, keys: dict[str, str]) -> bool:
    raise NotImplementedError
```

**Blast radius.** When the SPOF is down: 100% of dependent traffic fails. The longer
the dependency chain, the wider the radius. The 2016 AWS S3 us-east-1 outage took down
much of the web because S3 was a SPOF for many services that did not realize they
depended on it.

**Real-world examples.**

- AWS S3 us-east-1, Feb 2017 — many sites' static assets, Slack, Heroku.
- 2016 Dyn DDoS — Github, Twitter, Netflix.
- Crowdstrike, July 2024 — kernel-mode update; no canary; global outage.

**References.**

- Amazon's *Fault Isolation Boundaries* — internal AWS doctrine.
- AWS Builders' Library, *Static stability using Availability Zones*.

---

## Cascading Failures

**What it is / How it manifests.** A partial failure in one service causes its callers to
slow down or queue up; their callers feel the slowdown; the slowdown propagates outward
until the whole system is in a degraded state. The classic *metastable failure*: even
when the trigger is removed, the system stays stuck because feedback loops sustain the
overload.

**Telltale signs.**

- "Everything started failing at 14:23." On inspection, *one* downstream went slow at
  14:21.
- p99 latency rises across services that have no direct dependency on the slow one.
- The system does not auto-recover when the original problem is fixed.

**Fix.** Insert circuit breakers, bulkheads, and budgets. From `reliability.md`:

```
[ Rate Limiter ]      ← stay under downstream quota
[ Circuit Breaker ]   ← stop calling a dead dependency
[ Bulkhead ]          ← cap concurrent calls
[ Retry ]             ← transient fault recovery
[ Timeout ]           ← per-attempt deadline
[ the actual call ]
```

Plus:

- Load shedding at ingress (return 503 with `Retry-After`).
- Backpressure: stop accepting new work when queues are full.
- Bulkheads at the infrastructure level (separate clusters per criticality tier; see
  [cloud.md](cloud.md#bulkheading-at-the-infrastructure-level)).

**Blast radius.** All-system outage that cannot be resolved by fixing the original
trigger. Operators spend the first 30 minutes restarting things; then they notice
restarts make it *worse* (cold caches → more DB load → metastable). Eventually requires
*draining traffic* (load shedding) and bringing it back gradually.

**Real-world examples.**

- AWS retail website, ~2001 — the Amazon Builders' Library cascading failure.
- Twitter's "fail whale" era — overload + retries + no circuit breaker.
- Google SRE book, ch. 22 (the canonical reference).

**References.**

- Beyer, B. et al., *SRE*, ch. 22 (Addressing Cascading Failures).
- Bronson, N., *Metastable Failures in Distributed Systems*, HotOS 2021; Marc Brooker's
  blog post.
- Nygard, M., *Release It!*, ch. on stability patterns.

---

## Retry Storms

**What it is / How it manifests.** A partial outage triggers naive retries from many
clients. Each retry adds to the load on the recovering service. Recovery becomes
impossible. Marc Brooker: "in a five-layer service stack with three retries each,
database load increases 243-fold."

**Bad shape.**

```python
# BAD: every layer retries naively. Failure amplification compounds at each layer.
async def call_with_retry(op: Callable[[], Awaitable[T]], attempts: int = 3) -> T:
    last: Exception | None = None
    for _ in range(attempts):
        try:
            return await op()
        except Exception as exc:
            last = exc
    assert last is not None
    raise last


# Layer A retries 3x; calls layer B which retries 3x; calls layer C which retries 3x.
# A single failure at C produces 27 calls hitting C.
```

**Fix.**

- *One retry layer per call chain.* Pick which layer owns retries (usually the
  outermost SDK or gateway) and disable retries everywhere else. Document this
  explicitly.
- *Retry budget.* Cap the *fraction* of calls that may be retries (e.g., retries ≤ 10%
  of throughput). When budget is exhausted, refuse to retry.
- *Full jitter on backoff.* Uniform-random in `[0, cap]`. Exponential-deterministic
  causes the retries to *resynchronize* into bursts.
- *Token-bucket retries* (AWS SDK approach): retries consume tokens; bucket refills at
  a fixed rate; once empty, no retries until refilled.

```python
# FIX: token-bucket retries; one layer owns this; jittered backoff.
import asyncio
import random
from dataclasses import dataclass, field
from typing import Final


@dataclass
class RetryBudget:
    capacity: float = 100.0
    refill_per_s: float = 5.0
    _tokens: float = field(default=100.0, init=False)
    _last: float = field(default_factory=lambda: __import__("time").monotonic(), init=False)

    def try_consume(self, cost: float = 1.0) -> bool:
        now = __import__("time").monotonic()
        self._tokens = min(self.capacity, self._tokens + (now - self._last) * self.refill_per_s)
        self._last = now
        if self._tokens >= cost:
            self._tokens -= cost
            return True
        return False


async def call_with_budgeted_retry(
    op: Callable[[], Awaitable[T]], budget: RetryBudget, *, max_attempts: int = 3, cap_s: float = 5.0
) -> T:
    last: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await op()
        except Exception as exc:
            last = exc
            if attempt == max_attempts or not budget.try_consume():
                break
            delay = random.uniform(0, min(cap_s, 0.1 * 2 ** (attempt - 1)))  # noqa: S311
            await asyncio.sleep(delay)
    assert last is not None
    raise last
```

**Blast radius.** A service that would have recovered in 30 seconds takes 30 minutes to
recover because the retries from upstream pin it. Worse, if the retry storm propagates
*upstream*, the whole platform enters metastable failure: high throughput, zero goodput.

**Real-world examples.**

- AWS DynamoDB September 2015 outage: retries from many clients amplified load.
- Marc Brooker, *Caution: decreasing latency may increase error rate*, brooker.co.za.

**References.**

- Brooker, M., *Timeouts, retries, and backoff with jitter*, AWS Builders' Library.
- Bronson, N. et al., *Metastable Failures in Distributed Systems*, HotOS 2021.

---

## Naive Caching

**What it is / How it manifests.** Caching mutable data with no invalidation strategy;
or cache-aside with no stampede protection; or treating the cache as the source of
truth. Each is a different specific bug, all rooted in "we just put Redis in front of
it."

**Variants.**

- **No invalidation.** TTL = 24h on data that changes hourly. Half the day, the answer
  is wrong.
- **No stampede protection.** Hot key expires, 1000 readers miss simultaneously, all
  hit the DB. Pool exhausted. See [Cache-Aside](scaling.md#cache-aside-lazy-loading).
- **Lookaside cache used as source of truth.** Service falls back to "if cache is empty,
  *create the empty value*" — the next read returns the wrong shape.
- **Negative caching with too long a TTL.** Cache an "object not found" → object is
  created → cache still says not-found for an hour.
- **Caching credentials / per-user data globally.** Hard to spot until somebody else
  sees somebody else's data.

**Bad shape.**

```python
# BAD: cache "result"; no version; no negative cache; no stampede protection.
async def get_user(user_id: str) -> User | None:
    cached = await redis.get(f"user:{user_id}")
    if cached is not None:
        return User.model_validate_json(cached)
    user = await user_repo.get(user_id)
    if user is None:
        return None  # ← did not cache the absence; spam will hit the DB every time
    await redis.set(f"user:{user_id}", user.model_dump_json(), ex=86400)  # 1 day, mutable data
    return user
```

**Fix.** See [Cache-Aside (Lazy Loading)](scaling.md#cache-aside-lazy-loading) for the
full pattern with stampede protection, negative TTL, and a versioned key. The discipline:

- Short TTL by default; explicit invalidation on writes.
- Negative cache with *short* TTL.
- Single-flight on miss: only one request loads the upstream.
- Versioned keys when the *shape* changes.

**Blast radius.** Stampede: 1 hot key + 100 concurrent readers + cold cache → 100x DB
load → DB falls over → cascading failure. Stale data: customer sees old price, billing
disagreement, support ticket. Wrong-user data: privacy/security incident, GDPR exposure.

**Real-world examples.**

- Reddit's 2008 cache stampede outage.
- Multiple SaaS billing leaks where cache keys collided across tenants.

---

## Lift-and-Shift Cloud Migration

**What it is / How it manifests.** Move VMs from on-prem to AWS without re-architecting.
The bill *triples*; reliability does not improve; "cloud native" benefits are absent.

**Telltale signs.**

- EC2 instances that are sized for peak load 24/7.
- No autoscaling; no spot instances; reserved instances chosen by the on-prem capacity
  plan.
- No managed services adopted (still self-running Postgres on EC2 instead of RDS).
- Egress cost dominates the bill because services chat across AZs over public IPs.
- Architecture diagram is identical to the on-prem one with "AWS" relabeled.

**Fix.**

- Re-architect *something* before migrating: go stateless where possible, lean on
  managed services (RDS, S3, SQS, MSK), use auto-scaling, exploit spot for batch.
- Use AWS Migration Acceleration Program style assessment, not "rsync the disk."
- Plan a *strangler* path even within the cloud: move noncritical first, learn, then
  move stateful.

**Blast radius.** A 3x cost increase that nobody can explain. CFO concerns multiply.
Engineering claims "cloud is more expensive than on-prem" — which is true *only when
deployed this way*. The migration is then either rolled back (years of project loss) or
slowly fixed (the right answer, but politically hard).

**Real-world examples.**

- Industry archetype, written up by AWS Solutions Architecture and Gartner.
- Multiple Fortune-500 cloud migrations followed by partial repatriation in 2022–2024.

**References.**

- AWS, *Six R's of Migration* (Rehost, Replatform, Repurchase, Refactor, Retain, Retire).

---

## Vendor Lock-In by Default

**What it is / How it manifests.** Using cloud-vendor SDKs and bespoke services in the
hot path of every service, without a port/adapter abstraction. Migrating between vendors
becomes a multi-year project; vendor-specific features (DynamoDB Streams, AWS SQS FIFO)
ossify the architecture.

**Bad shape.**

```python
# BAD: every service imports boto3 directly and calls SQS.
import boto3

class OrderHandler:
    def __init__(self) -> None:
        self._sqs = boto3.client("sqs")
        self._queue_url = "https://sqs..."

    async def emit(self, order: Order) -> None:
        self._sqs.send_message(QueueUrl=self._queue_url, MessageBody=order.model_dump_json())
```

Every service is now coupled to SQS in 50 places.

**Fix.** A Port-and-Adapters / Hexagonal layout (see `architectural-patterns.md` if in
your tree). Services depend on `Protocol`s for their dependencies; adapters bind to
specific vendors:

```python
from typing import Protocol


class EventBus(Protocol):
    async def publish(self, topic: str, payload: bytes) -> None: ...


class SQSEventBus:
    def __init__(self, sqs_client: object, queue_url: str) -> None: ...
    async def publish(self, topic: str, payload: bytes) -> None: ...


class KafkaEventBus:
    def __init__(self, producer: object) -> None: ...
    async def publish(self, topic: str, payload: bytes) -> None: ...


class OrderHandler:
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    async def emit(self, order: Order) -> None:
        await self._bus.publish("order.placed", order.model_dump_json().encode("utf-8"))
```

**When pragmatism wins.** Going *deliberately* deep on a vendor is sometimes correct:
DynamoDB's transactional writes, Lambda's deep auth integration. Lock-in is bad when
*unintentional*; it's a tradeoff when *measured*.

**Blast radius.** A vendor outage (e.g., AWS us-east-1) takes you down completely; a
multi-cloud strategy is impossible without a rewrite. Vendor pricing changes hit the
bottom line directly. Migration estimates run into person-years.

**Real-world examples.**

- Spotify's deliberate use of GCP-portable abstractions (Dataflow, BigQuery via
  abstractions).
- Netflix's "regional aware" abstractions to support multi-AZ + multi-region failover.

---

## Observability as Afterthought

**What it is / How it manifests.** Logs added during incidents, traces added "next
quarter," metrics that mostly count CPU. The first time the question "why was this
request slow?" arises, the answer requires SSH'ing into a box and running `strace`.

**Bad shape.**

```python
# BAD: print-debugging in production; no structured fields; no IDs.
async def place_order(req: dict) -> dict:
    print("placing order")
    user = await users.get(req["user_id"])
    print(f"got user {user}")
    order = await orders.create(...)
    print(f"created {order.id}")
    return {"order_id": order.id}
```

What is missing: structured logs, trace IDs, request IDs, latency histograms, error
categorization, RED/USE-style metrics.

**Fix.** Bake observability in *from day one*:

- Structured JSON logs with consistent fields (`request_id`, `user_id`, `tenant_id`,
  `latency_ms`, `status`).
- OpenTelemetry tracing across service boundaries (W3C `traceparent` header).
- Histograms for latency (not averages — averages lie about p99).
- Error taxonomy: `client_error / transient / persistent / internal`.
- Sampled (not aggregated) recent events for incident investigation (Honeycomb,
  Lightstep, OpenTelemetry).

```python
import logging
import time
from typing import Final
from contextvars import ContextVar


request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class StructuredLogger:
    def __init__(self, name: str) -> None:
        self._logger: Final = logging.getLogger(name)

    def info(self, event: str, **fields: object) -> None:
        self._logger.info(event, extra={"event": event, "request_id": request_id_ctx.get(), **fields})


log = StructuredLogger(__name__)


async def place_order(req: OrderRequest) -> OrderResponse:
    started = time.monotonic()
    try:
        order = await orders.create(req)
    except Exception as exc:  # noqa: BLE001 — re-raise after logging
        log.info("order.create_failed", reason=type(exc).__name__, latency_ms=int((time.monotonic() - started) * 1000))
        raise
    log.info("order.created", order_id=order.id, latency_ms=int((time.monotonic() - started) * 1000))
    return OrderResponse(order_id=order.id)
```

**Blast radius.** Incidents that should take 15 minutes take hours because nobody can
attribute slowness. Postmortems read "we don't know why" three times. Eventually a
big-bang observability migration is launched, costing months that should have been
weeks of incremental investment.

**Real-world examples.**

- *Honeycomb's manifesto.* Charity Majors, *Observability Engineering*.
- Most pre-2018 startup engineering blogs describing their "we finally added tracing"
  postmortem.

**References.**

- Majors, C. et al., *Observability Engineering*, O'Reilly, 2022.
- Beyer, B. et al., *SRE*, chs. 6 (Monitoring) and 12 (Effective troubleshooting).

---

## Configuration Drift

**What it is / How it manifests.** Production configuration that exists *only* in
production, modified by hand during incidents, never reflected in version control. The
"snowflake server" problem at infrastructure scale: every replica is slightly different;
a fresh replica from the image cannot reproduce production behavior.

**Telltale signs.**

- "Don't restart that box; it has the fix." (The fix is not in code.)
- A new replica behaves differently from the old ones.
- `diff` between two replicas' configs reveals dozens of unexpected changes.
- Disaster recovery rehearsals fail.

**Fix.** Infrastructure as Code (Terraform, Pulumi, CloudFormation) + immutable
infrastructure + GitOps. Treat the infrastructure repo as the *only* source of truth.
Any production change goes through the pipeline; emergency hotfixes still produce a
commit.

```hcl
# Terraform: infrastructure config in version control.
resource "aws_lambda_function" "order_processor" {
  function_name = "order-processor"
  image_uri     = "${var.ecr_repo}:${var.image_tag}"
  memory_size   = 1024
  timeout       = 30
  environment {
    variables = {
      LOG_LEVEL    = var.log_level
      RETRY_BUDGET = var.retry_budget_capacity
    }
  }
}
```

For runtime config that *must* change without deploys, use a
[Configuration Service](cloud.md#configuration-as-a-service) — but the service's value
*and* the SDK reading it are still committed.

**Blast radius.** Disaster recovery fails because the recovered system is missing
hand-applied fixes. New replicas during scale-out behave differently. Audits reveal that
"production config" cannot be reproduced. Compliance findings.

**Real-world examples.**

- Knight Capital, August 2012: $440M loss in 45 minutes from a deployment process that
  forgot one server, leaving an old code path hot. (Configuration drift's most
  expensive day.)

**References.**

- Morris, K., *Infrastructure as Code*, O'Reilly, 2nd ed., 2020.
- Limoncelli, T., *The Practice of Cloud System Administration*, Addison-Wesley, 2014.

---

## Time Bombs

**What it is / How it manifests.** Code or configuration that *will* fail at a specific
future date or after a specific elapsed time, and the failure is silent until that day.
Common shapes: certificates that auto-rotate untested; long timeouts that mask hangs;
hard-coded year-2038 timestamps; license expiries; promotional discount cutoffs.

**Bad shapes.**

```python
# BAD #1: the certificate works today; it expires in 90 days; nobody tested rotation.
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.load_cert_chain(CERTFILE, KEYFILE)


# BAD #2: timeout = 60s "for safety", masks a hung downstream until the queue overflows.
async def fetch(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=60.0) as client:  # 60 *seconds*
        return (await client.get(url)).content


# BAD #3: hard-coded date.
PROMO_END = "2026-12-31T23:59:59"  # what happens 2027-01-01?
```

**Fix.**

- *Test the rotation path,* not the expiry. Cert rotation should run in pre-prod every
  week, not "every 89 days when it's about to expire."
- *Pick timeouts based on SLO,* not on caller paranoia. If the SLO is 1s, the timeout
  cannot be 60s.
- *Document time-dependent behavior* and add tests at the boundary date: parametric
  tests with `freezegun` / `time-machine`.
- *Year-2038 awareness* — `int32` epoch timestamps will overflow on 2038-01-19. Use
  `int64` everywhere.

**Blast radius.** Cert expiry takes the service down at 02:00 on a Saturday. The
on-call engineer renews the cert manually (which works) and goes back to bed; nobody
actually fixes the auto-rotation. It happens again next quarter. Eventually, a cert
deep in the dependency chain (CA chain, Cloudflare origin cert) takes the whole product
down for hours.

**Real-world examples.**

- Microsoft's January 2023 Teams outage: certificate.
- Cloudflare's July 2019 outage: a regex with quadratic backtracking that worked at
  small scale but pinned all CPU at large scale (a "scale time bomb," not a clock time
  bomb, but the same shape).
- Y2K, the original time bomb.

---

## Big Bang Migrations

**What it is / How it manifests.** Replacing a core system in one cutover. Months of
parallel development; a single "go-live" weekend. Either the new system handles
production load on day one, or you roll back — sometimes painfully, sometimes not at
all.

**Telltale signs.**

- The migration plan has the word "freeze" in it.
- "Nobody else is allowed to deploy during the cutover."
- Testing is heavily reliant on a staging environment that does not match production.
- Rollback plan is "restore from backup." (i.e., there is no rollback plan.)

**Fix.** [Strangler Fig](cloud.md#strangler-fig). Migrate one endpoint, one customer
cohort, one tenant at a time. Each step is independently rollback-able. Production load
is felt incrementally.

```
   Week 1:  /catalog routed to new system (5% of customers)
   Week 2:  /catalog routed to new system (50%)
   Week 3:  /catalog routed to new system (100%); old system /catalog disabled
   Week 4:  /orders routed to new system (5%) ...
```

**When Big Bang is the only option.**

- A protocol cutover with no facade possible (rare).
- A regulator-mandated date.
- An expiring contract / vendor.

Even then: minimize big-bang surface. Pre-cut over what you can; bang on the smallest
remaining piece.

**Blast radius.** When it goes wrong, the entire product is degraded for days. Customer
trust takes years to recover. Engineering morale collapses. Two-thirds of "core system
replacement" projects in industry surveys are big-bang failures.

**Real-world examples.**

- *Healthcare.gov, 2013* — big-bang launch failure that became a multi-month emergency
  recovery effort.
- *UK NHS National Programme for IT* — cancelled after billions spent; classic
  big-bang failure.

**References.**

- Newman, S., *Monolith to Microservices*, ch. on migration patterns.
- Fowler, M., *StranglerFigApplication*.

---

## Review Checklist

When you encounter a system change at design or PR review, scan for these in order:

1. **Coupling.** Are services being added that share a database? deploy together?
   share schemas via vendored libraries? *(Distributed Monolith, Shared Database)*
2. **Critical path.** Is a non-essential dependency in the user-facing critical path?
   *(Synchronous Cross-Service Calls)*
3. **Boundaries.** Does the diagram have clear bounded contexts, or does everything
   talk to everything? *(Death Star)*
4. **Failure modes.** What happens when this dependency is *down*? Fail open, fail
   closed, or "the whole product is down"? *(SPOF, Cascading Failures)*
5. **Retries.** How many layers retry? Do they share a budget? Is there full jitter?
   *(Retry Storms)*
6. **Cache.** Does it have stampede protection, negative caching with short TTL, and
   versioned keys? *(Naive Caching)*
7. **State.** Is anything in-process that should be in a shared store? Sticky sessions
   without a documented reason? *(Sticky Sessions)*
8. **Locks on the hot path.** Is there a `FOR UPDATE` or table lock held across IO?
   *(Hot-Path Database Locking)*
9. **Observability.** Can you reconstruct what happened in this code path from logs and
   traces *without* SSH'ing in? *(Observability as Afterthought)*
10. **Reproducibility.** Can a fresh replica from the image reproduce production
    behavior? Or is there hand-applied config? *(Configuration Drift)*
11. **Time-dependent behavior.** Are there certificates, dates, timestamps that will
    bite at a known future date? Have you tested the rotation path? *(Time Bombs)*
12. **Migration shape.** If this is a migration, is it incremental (Strangler Fig) or
    big-bang? If big-bang, why? *(Big Bang Migrations)*
13. **Complexity tax.** Is this microservices boundary earning its keep, or is it
    overhead? *(Premature Microservices)*
14. **Vendor coupling.** Is the SDK called directly in business logic, or behind a port?
    *(Vendor Lock-In)*

If three or more answers are "I don't know" or "we'll figure it out later," the change
is not ready to land.

---

## References

**Books.**

- Newman, S., *Building Microservices*, 2nd ed., O'Reilly, 2021.
- Newman, S., *Monolith to Microservices*, O'Reilly, 2020.
- Richardson, C., *Microservices Patterns*, Manning, 2018.
- Kleppmann, M., *Designing Data-Intensive Applications*, O'Reilly, 2017.
- Nygard, M., *Release It!*, 2nd ed., Pragmatic Bookshelf, 2018.
- Beyer, B. et al., *Site Reliability Engineering*, Google / O'Reilly, 2016 — chs. 21,
  22.
- Majors, C. et al., *Observability Engineering*, O'Reilly, 2022.
- Morris, K., *Infrastructure as Code*, 2nd ed., O'Reilly, 2020.
- Limoncelli, T. et al., *The Practice of Cloud System Administration*, Addison-Wesley,
  2014.

**Papers / posts.**

- Bronson, N. et al., *Metastable Failures in Distributed Systems*, HotOS 2021.
- Brooker, M., *Timeouts, retries, and backoff with jitter*, AWS Builders' Library.
- Brooker, M., *Metastable Failures*, brooker.co.za.
- Vogels, W., *Cell-based architecture*, allthingsdistributed.com.
- AWS Builders' Library, *Avoiding fallback in distributed systems*.
- AWS Builders' Library, *Static stability using Availability Zones*.
- Fowler, M., *MonolithFirst*, *StranglerFigApplication*, martinfowler.com/bliki.

**Postmortems / incidents.**

- AWS S3 us-east-1 outage, February 2017.
- Knight Capital, August 2012.
- Cloudflare regex outage, July 2019.
- CrowdStrike kernel-mode update, July 2024.
- Healthcare.gov launch, October 2013.

**Vendor / industry.**

- Microsoft Azure, *Cloud Design Patterns*, learn.microsoft.com/azure/architecture/patterns.
- AWS, *Builders' Library*, aws.amazon.com/builders-library.
- microservices.io (Chris Richardson).
- ThoughtWorks Technology Radar (historical entries on Distributed Monolith).
