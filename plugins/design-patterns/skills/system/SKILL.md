---
name: system
description: >-
  Use when designing or reviewing cross-service, cross-process, regional, or
  operator-facing system shape: timeouts, retries, circuit breakers, bulkheads,
  rate limits, idempotency, DLQs, REST/gRPC/GraphQL/pub-sub, service mesh,
  webhooks, Saga, Raft/Paxos, distributed locks, CQRS, event sourcing, outbox,
  sharding, replication, caching, autoscaling, sidecars, strangler migrations,
  distributed monoliths, cascading failures, retry storms, or shared databases.
---

# System Patterns — Across Services

Strict-typed Python 3.13+ patterns for shapes that span services,
processes, regions, or operators: reliability (timeout, retry, circuit
breaker, bulkhead), communication (pub/sub, API gateway, BFF, service
mesh), distributed coordination (saga, leader election, Raft, CRDTs),
data architecture (CQRS, event sourcing, sharding, replication),
scaling (cache, load balancing, autoscaling), cloud topology (sidecar,
ambassador, strangler fig, cell-based), system-level anti-patterns.
For in-service concerns (class boundaries, domain modelling, in-process
concurrency, code smells), load the `software` skill from this plugin
instead.

## Default posture

Surface these non-negotiables when proposed code violates them. Point at
the exact reference rather than re-arguing from first principles.

- **Strict typing always.** Python 3.13+, `Protocol` over `ABC`, PEP 695
  generics (`class Foo[T]:`), PEP 604 unions (`X | Y`), `list[int]` not
  `List[int]`, `Self` for fluent returns, `Final` for constants, `@override`
  where applicable, and no `Any` leakage. Use the annotation-evaluation policy
  in the conventions section below; omit `from __future__ import annotations`
  only when runtime introspection genuinely requires evaluated annotations.
  Code blocks in this catalogue are written to target `mypy --strict` and
  `pyright --strict`.
- **Fail fast, fail explicitly, recover deliberately.** No silent
  fallbacks. No unbounded retries. No exception swallowing. No
  library-default timeouts. Every remote call has a timeout; every retry
  has a budget; every degraded mode is observable.
- **Smallest shape that satisfies the constraint.** Don't reach for
  Repository, Unit of Work, CQRS, Event Sourcing, Microservices, Saga,
  or a Visitor when a plain function over the ORM would do. Each
  pattern carries an *overkill threshold* — if you cannot name today's
  concrete pain, don't introduce it.
- **Encode invariants in types, not in services.** Anemic dataclasses +
  `*Service` mutators are an anti-pattern. Behaviour lives on the
  entity; orchestration lives in the service.
- **Make illegal states unrepresentable.** Wlaschin's framing — sum
  types, `NewType`, smart constructors, `frozen=True`, `Final`. The
  type checker does the work.

## Pydantic & typing conventions assumed

Every Python block in this catalogue binds itself to these rules. They are
inlined here so the system-patterns skill remains correct even when no other
skill is loaded.

- **Strict-typed Python 3.13+.** Blocks target `mypy --strict` and
  `pyright --strict`: PEP 695 generics (`class Foo[T]:`), PEP 604 unions
  (`X | Y`), `list[int]` not `List[int]`, `Self` for fluent returns, `Final`
  for constants, and `@override` on subclass methods.
- **Protocol over ABC.** Use `Protocol` for structural extension contracts
  unless explicit registration, shared default behavior, or runtime subclass
  checks require an ABC.
- **No `Any` leaks.** Bare `Any` is forbidden outside I/O boundaries. Boundary
  adapters may carry one `cast` only with an inline reason comment naming the
  vendor docs reference.
- **Typed ignores only.** `# type: ignore` requires an error code and an inline
  reason: `# type: ignore[arg-type]  # third-party stub missing field X`. Bare
  `# type: ignore` is forbidden.
- **Suffix-`T` type parameters.** Prefer `KeyT`, `ValueT`, `ItemT`,
  `ReturnT`, `InputT`, and `OutputT`; never bare `T`, `K`, or `V`. Use PEP
  695 syntax such as `class Registry[KeyT, ValueT]:`, not
  `Generic[KeyT, ValueT]`.
- **Pydantic at boundaries, dataclasses inside.** Use Pydantic when a value
  crosses a trust boundary: deserialization, untrusted input,
  payload-on-the-wire, or configuration. Use
  `@dataclass(frozen=True, slots=True)` for in-process domain types.
- **Pydantic v2 always.** Use `Annotated[T, Field(...)]`; bare `Field()` as a
  default is forbidden. Boundary models add
  `model_config = ConfigDict(frozen=True, extra="forbid")` to reject unknown
  fields and prevent post-construction mutation.

The `python:typings` skill in the sister python plugin holds the full
canonical examples and rationale behind each rule. If both plugins are
installed, you can load it via the Skill tool when you need the deep reference,
but this catalogue does not require it to be loaded to be correct.

## Reference index (~10,800 lines across 7 refs)

| File | Read when… |
| --- | --- |
| [`reliability.md`](reliability.md) | A call crosses a process / network / disk / queue boundary: Timeout, Retry + Exponential Backoff + Full Jitter, Circuit Breaker, Bulkhead, Rate Limiting (Token Bucket / Leaky Bucket / GCRA), Adaptive Concurrency Limits (Netflix-style), Idempotency Keys (Stripe-style), Dead-Letter Queue, Hedged Requests (Dean & Barroso), Fallback / Graceful Degradation, Health Checks (liveness vs readiness vs startup), Heartbeat, Backpressure. Includes a stacking-order guide. |
| [`communication.md`](communication.md) | Designing the channel between services: Request/Reply (REST vs gRPC vs GraphQL with type-safety triage), Pub/Sub (Kafka / RabbitMQ / Redis Streams / SNS-SQS / GCP Pub/Sub with delivery-semantics table), Event-Driven Architecture (thin vs fat events), API Gateway (and the "smart pipes / dumb endpoints" anti-pattern), Backend-for-Frontend, Service Mesh, Webhooks (HMAC + replay window), Long Polling / SSE / WebSockets, Async Request-Reply (`202 + Location + Retry-After`), Claim Check. |
| [`distributed.md`](distributed.md) | Coordinating across nodes: Saga (orchestration vs choreography), Two-Phase Commit (and why it's almost always wrong), Raft pseudocode + Paxos overview, Leader Election (lease-based with renewable TTL), Distributed Lock with fencing (the Kleppmann–Antirez exchange), Heartbeat / phi-accrual failure detector, Vector Clocks / Lamport Timestamps, CRDTs (G-Counter, PN-Counter, OR-Set, LWW-Register), Quorum Reads/Writes (N/R/W), Gossip Protocols. |
| [`data.md`](data.md) | Shaping persistent state: CQRS (lightweight vs full), Event Sourcing (replay, snapshot, projection), Outbox (`FOR UPDATE SKIP LOCKED`), Inbox (consumer-side dedup), Materialized View, Database per Service (with migration steps from a shared DB), Sharding (range / hash with consistent hashing + vnodes / directory / geographic), Replication (single-leader / multi-leader / leaderless / semi-sync), Eventual Consistency (read-your-writes, monotonic reads, causal), Read Repair / Anti-entropy, Change Data Capture (Debezium-style), Soft Delete / Tombstones. |
| [`scaling.md`](scaling.md) | Performance and scale: Cache-Aside (with single-flight stampede protection), Read-Through, Write-Through, Write-Behind, Refresh-Ahead (XFetch probabilistic), CDN / Edge (`stale-while-revalidate`, surrogate keys), Vertical vs Horizontal Scaling (the "scale-up first" pragmatic argument), Auto-scaling (reactive / predictive / scheduled, KEDA-style queue-age triggers), Load Balancing (round-robin / least-conn / consistent-hash / power-of-two-choices / EWMA), Connection Pooling (HikariCP / PgBouncer math), Backpressure-aware Scaling. |
| [`cloud.md`](cloud.md) | Topology decisions: Sidecar, Ambassador (and the Sidecar-vs-Ambassador direction split), Adapter (system-level), Anti-Corruption Layer (system-level, one-way DDD translation), Strangler Fig (route-table proxy), Choreography vs Orchestration, Service Discovery (server-side LB vs client-side Consul/Eureka), Configuration as Service (LaunchDarkly / Unleash), Async Request-Reply, Claim Check (S3 + queue), Compensating Transaction, Throttling Gateway, Bulkheading at Infra Level (cells / AZs), Cell-Based Architecture (AWS-style with jump-consistent hashing). |
| [`anti-patterns.md`](anti-patterns.md) | Distributed-architecture review: Distributed Monolith, Chatty Interfaces (N+1 RPC + chained sync calls), Two-Phase Commit Abuse, Shared Database, Death Star Architecture, Premature Microservices Adoption, Synchronous Cross-Service Calls (when async fits), Sticky Sessions Everywhere, Hot Path DB Locking, Single Point of Failure, Cascading Failures, Retry Storms (with the 243× amplification math), Naive Caching, Lift-and-Shift, Vendor Lock-in by Default, Observability as Afterthought, Configuration Drift, Time Bombs, Big Bang Migrations. Each entry includes a real production incident (Knight Capital, S3 us-east-1, CrowdStrike, Healthcare.gov) where the anti-pattern fired. |

Read **only** the reference relevant to the current decision — every
file has a Table of Contents at the top; jump to the specific anchor.

## Decision flow

1. **Is this a structural decision?** Failure-mode / channel-shape /
   data-topology / scaling-shape / deployment-topology, or a refactor
   of one. If no, skip this skill — these references are about
   *shape*, not algorithms or business logic.
2. **Pick the axis.**
   - Cross-boundary failure → `reliability.md`
   - Channel choice (sync / async / event-driven / streaming) →
     `communication.md`
   - Consensus, ordering, locks across nodes → `distributed.md`
   - Write/read split, replication, sharding → `data.md`
   - Caching, load balancing, autoscaling → `scaling.md`
   - Topology / migration / extraction → `cloud.md`
   - Distributed-architecture refactor target → `anti-patterns.md`
3. **Read the relevant reference.** Use the ToC. Each pattern entry
   follows a fixed shape — `Intent` · `When to reach for it` ·
   `Sketch` (strict-typed Python, plus another language where
   idiomatic) · `Type-safety notes` · `When NOT to use` · `Real-world
   examples` · `Anti-pattern variant` · `References`. Skim *Intent*
   and *When NOT to use* before reading the full sketch.
4. **Apply the strict-typed sketch directly.** The references already
   account for `Protocol`, `Self`, `override`, `Final`, PEP 604/695.
   Don't re-derive ABC-heavy Java-style translations. Don't sprinkle
   `Any` to make types "easier" — the sketch already shows the
   type-clean form.
5. **Check the *When NOT to use* / overkill threshold before
   adopting.** Most patterns are wrong by default; they earn their
   place only against a specific named pain.

## Citing a specific section

Anchor on the heading exactly as written in the file — for example
`reliability.md#circuit-breaker`, `data.md#event-sourcing`,
`cloud.md#strangler-fig`. Anchors are kebab-case slugs of the heading
text.

## What this skill does NOT cover

- **In-service code shape** — class boundaries, GoF patterns, domain
  modelling, functional patterns, package layouts, in-process
  concurrency, code-level anti-patterns. Load the `software` skill
  from this plugin for those.
- **Vendor / library choices** (Kafka vs RabbitMQ, Redis vs
  Memcached, Consul vs etcd, Envoy vs Linkerd) — the references show
  *shapes* and delivery-semantics tradeoffs, not vendor
  recommendations.
- **Deployment / SRE specifics** (Terraform modules, K8s manifests,
  observability stack choice). The cloud and reliability files
  describe shapes; codifying them in particular tooling lives
  elsewhere.

If a question lands outside this scope, say so rather than bending one
of the references to fit. If a question lands *inside* the scope but
the answer isn't in the references, that's a signal the catalogue
should be extended — flag it and propose the addition rather than
improvising silently.
