# Distributed Coordination Patterns

_Patterns for getting independent processes — across nodes, regions, networks —
to agree on what happened, in what order, and who is in charge._

These patterns answer one question per section: _what is the smallest piece of
coordination machinery that solves this failure mode, and at what cost?_ The
trap in distributed systems is reaching for a heavyweight algorithm when a small
one will do, or — far more often — reaching for a small one when only a
heavyweight one is correct.

The default posture is **off-the-shelf wherever possible**. Implementing Raft,
Paxos, or even a "correct" distributed lock from scratch is a multi-year
research project disguised as an afternoon's work. Almost every production
system that needs consensus reaches for `etcd`, `ZooKeeper`, `Consul`, or the
consensus primitives baked into a managed product (Kafka's KRaft, Aurora,
Spanner, DynamoDB). The patterns below are framed so you can recognize when
off-the-shelf ends the conversation and when — rarely — it doesn't.

## How to use this file

Read _Intent_ and _When to reach for it_ to decide if a pattern is on the table.
Read the _Sketch_ only after you have decided to use it. Read _When NOT to use_
before you commit — "this looks neat" is the most common reason people implement
consensus protocols nobody needed.

## Table of Contents

- [Distributed Coordination Patterns](#distributed-coordination-patterns)
    - [How to use this file](#how-to-use-this-file)
    - [Table of Contents](#table-of-contents)
    - [The big picture](#the-big-picture)
    - [Saga (orchestration)](#saga-orchestration)
    - [Saga (choreography)](#saga-choreography)
    - [Two-Phase Commit](#two-phase-commit)
    - [Three-Phase Commit, Paxos, Raft](#three-phase-commit-paxos-raft)
    - [Leader Election](#leader-election)
    - [Distributed Lock](#distributed-lock)
    - [Heartbeat and Failure Detector](#heartbeat-and-failure-detector)
    - [Lamport Timestamps and Vector Clocks](#lamport-timestamps-and-vector-clocks)
    - [CRDTs](#crdts)
    - [Quorum Reads and Writes](#quorum-reads-and-writes)
    - [Gossip Protocols](#gossip-protocols)
    - [When to reach for what](#when-to-reach-for-what)
    - [Review Checklist](#review-checklist)

---

## The big picture

Three categories cover most coordination problems:

1. **Workflow coordination across services** — Saga (orchestration or
   choreography).
2. **Cluster coordination** — leader election, membership, config, locks.
   Raft-backed service (etcd, ZooKeeper, Consul). Almost never implemented from
   scratch.
3. **Data convergence under partition** — vector clocks for detection, CRDTs for
   automatic merge, quorum reads/writes for tunable consistency.

These barely overlap. Saga is _application state_. Consensus is _cluster state_.
CRDTs are _replicated data_. Confusing them produces architectures where every
problem is a nail because the team chose one hammer.

---

## Saga (orchestration)

**Intent.** A long-running business workflow spanning multiple services is
decomposed into a sequence of local transactions, each with a _compensating
action_ that semantically undoes it. A central **orchestrator** drives the
sequence — invoking step N, then either advancing to N+1 or running
compensations N..1 in reverse. There is no distributed transaction; only a state
machine that knows which compensations are owed. Named in Garcia-Molina & Salem
(1987) for chaining long-running database transactions; the modern microservice
form is the same idea across services and queues.

**When to reach for it.**

- A workflow touches 3+ services and must end consistent (booked, charged,
  shipped) or undone (refunded, released).
- You need one place to inspect the workflow's state, retry a stuck step, or
  manually compensate.
- The team has bandwidth to operate a workflow engine — Temporal, Step
  Functions, DBOS, or a hand-rolled FSM with persistent state.

**Sketch.** A strict-typed orchestrator with explicit compensation per step.

```python
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final, Protocol, Self
from uuid import UUID, uuid4


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    COMPENSATED = "compensated"


@dataclass(frozen=True, slots=True)
class StepResult[T]:
    value: T


class SagaStep[TIn, TOut](Protocol):
    """Forward action and its compensation. Both must be idempotent."""

    name: str

    async def execute(self, ctx: TIn) -> StepResult[TOut]: ...
    async def compensate(self, ctx: TIn) -> None: ...


@dataclass(slots=True)
class StepRecord:
    name: str
    status: StepStatus
    error: str | None = None


@dataclass(slots=True)
class SagaState:
    saga_id: UUID
    completed: list[StepRecord] = field(default_factory=list)
    failed_at: str | None = None


class SagaStore(Protocol):
    """Persistence for saga state — must survive orchestrator restart."""

    async def save(self, state: SagaState) -> None: ...


class Saga[TCtx]:
    def __init__(self, store: SagaStore) -> None:
        self._store: Final = store
        self._steps: list[SagaStep[TCtx, TCtx]] = []

    def step(self, s: SagaStep[TCtx, TCtx]) -> Self:
        self._steps.append(s)
        return self

    async def run(self, ctx: TCtx) -> TCtx:
        state = SagaState(saga_id=uuid4())
        await self._store.save(state)
        for step in self._steps:
            record = StepRecord(name=step.name, status=StepStatus.RUNNING)
            try:
                result = await step.execute(ctx)
                record.status = StepStatus.SUCCEEDED
                state.completed.append(record)
                await self._store.save(state)
                ctx = result.value
            except Exception as exc:
                record.status = StepStatus.FAILED
                record.error = repr(exc)
                state.completed.append(record)
                state.failed_at = step.name
                await self._store.save(state)
                await self._compensate(state, ctx)
                raise
        return ctx

    async def _compensate(self, state: SagaState, ctx: TCtx) -> None:
        # Compensate successful steps in reverse; skip the failed one.
        for record in reversed(state.completed):
            if record.status is not StepStatus.SUCCEEDED:
                continue
            step = next(s for s in self._steps if s.name == record.name)
            await step.compensate(ctx)
            record.status = StepStatus.COMPENSATED
            await self._store.save(state)
```

**Type-safety notes.**

- `SagaStep[TIn, TOut]` carries the carry-forward type — encode the context
  (`OrderId`, `PaymentId`, `ShipmentId`) explicitly so step 3 cannot pretend to
  receive what step 2 does not produce.
- `StepStatus` as `StrEnum`: human-readable in logs, exhaustiveness-checked in
  `match`.
- State must be **persistent**. An in-memory orchestrator that crashes
  mid-flight has lost the recovery property the saga exists for.

**Idempotency is mandatory.** Both `execute` and `compensate` will be retried —
by orchestrator restart, queue redelivery, operator action. Double-refunding a
customer is worse than the original failure. See _Inbox Pattern_ in `data.md`.

**When NOT to use.** A workflow that fits in one transaction (one DB, one
service). Sagas trade ACID for visibility — pay only when the alternative is a
distributed transaction.

**Real-world examples.** Temporal (workflow-as-code, replays history); AWS Step
Functions (declarative); DBOS (database-backed durable execution); Camunda
Zeebe.

**Anti-pattern variant.** _"Saga without persistence."_ In-memory orchestrator,
no checkpoints. On crash, in-flight sagas vanish — customer charged but never
shipped. If you cannot point to the durable record of saga progress, you have a
try/except with extra steps.

**References.**

- Garcia-Molina & Salem, "Sagas", ACM SIGMOD 1987.
- Chris Richardson, _Microservices Patterns_, ch. 4.
- Temporal docs: <https://docs.temporal.io>.

---

## Saga (choreography)

**Intent.** Same goal as orchestration — eventual consistency across services —
but no central coordinator. Each service publishes an event when its local step
completes; downstream services subscribe. The workflow lives implicitly in the
_event topology_.

**When to reach for it.**

- Short workflow (2–4 steps), unlikely to grow.
- Independent teams that already speak in events.
- You want to avoid the operational footprint of a workflow engine.

**Sketch.** The _shape_ is the topology. The canonical "place an order" flow:

```
   Order Svc ── OrderPlaced ──▶ Payment Svc ── PaymentSucceeded ──▶ Inventory ── StockReserved ──▶ Order Svc
                                       │ (failed)                          │ (unavailable)
                                       ▼                                   ▼
                                  Order Svc                            Payment Svc
                                  CANCELLED                              refund
```

Compensation flows live in the same event-bus topology, along different edges.

**Type-safety notes.** Events are versioned, schema-evolved contracts. Without a
schema registry, every consumer breaks the moment a producer adds a field. Use
`Literal` discriminators and a discriminated union per topic.

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class OrderPlaced:
    event_type: Literal["OrderPlaced"]
    schema_version: Literal[1]
    occurred_at: datetime
    order_id: UUID
    user_id: UUID
    total_cents: int


@dataclass(frozen=True, slots=True)
class PaymentSucceeded:
    event_type: Literal["PaymentSucceeded"]
    schema_version: Literal[1]
    occurred_at: datetime
    order_id: UUID
    payment_id: UUID


@dataclass(frozen=True, slots=True)
class PaymentFailed:
    event_type: Literal["PaymentFailed"]
    schema_version: Literal[1]
    occurred_at: datetime
    order_id: UUID
    reason: str


type OrderEvent = OrderPlaced | PaymentSucceeded | PaymentFailed
```

**Orchestration vs choreography — _who owns the workflow_.**

- **Orchestration**: one service knows the full sequence. Visible, debuggable,
  easy to retry. The orchestrator becomes a hub.
- **Choreography**: each service knows only its own role. No central authority.
  The workflow lives only as an emergent property of the topology — onboarding
  requires drawing the diagram from source.

Rule: **choreography for short, stable workflows; orchestration for everything
else.** Once you have 4+ steps, conditional branching, timeouts, or operator
intervention, the orchestrator earns its keep.

**When NOT to use.** Deep branching, manual approval, long pauses (days/weeks),
or SLAs that require "where is order 12345 stuck right now". Choreography hides
that across N services.

**Real-world examples.** Most early Netflix, eBay, and Shopify workflows started
choreographed and migrated to orchestration as complexity grew. Stripe uses a
mix.

**Anti-pattern variant.** _"Choreography that grew up."_ Starts with three
events, becomes 47 event types across 23 services with no diagram. The fix is to
introduce an orchestrator for the long-tail flows, not yet another consumer.

**References.**

- Sam Newman, _Building Microservices_, 2nd ed., ch. 6.
- microservices.io/patterns/data/saga.html.

---

## Two-Phase Commit

**Intent.** Make a transaction atomic across multiple resource managers
(databases, queues). A **coordinator** asks every participant "can you commit?"
(PREPARE). If all say yes, it tells them "commit" (COMMIT). If any says no,
"abort". XA formalizes this for relational databases.

**When to reach for it.** _Almost never in modern systems._ The pattern is here
so you can recognize when someone proposes it and explain why it does not fit.

**Sketch.** Pseudocode — real 2PC requires participation from every resource
manager.

```
COORDINATOR:
    txn_id = new_id()
    log("BEGIN", txn_id)

    # PHASE 1: PREPARE
    for p in participants:
        send(p, "PREPARE", txn_id)
    responses = collect(timeout=T1)

    if any(r != "VOTE_YES" for r in responses):
        log("ABORT", txn_id)
        for p in participants: send(p, "ABORT", txn_id)
        return ABORTED

    log("COMMIT", txn_id)            # <-- decision point. WAL forced to disk.

    # PHASE 2: COMMIT
    for p in participants:
        send(p, "COMMIT", txn_id)
    wait_for_acks(timeout=T2)        # blocks until everyone acks
    return COMMITTED


PARTICIPANT (on PREPARE):
    if can_commit():
        write_undo_log(); write_redo_log()
        send(coordinator, "VOTE_YES")
        # NOTE: now blocked. cannot release locks until COMMIT or ABORT arrives.
    else:
        send(coordinator, "VOTE_NO")

PARTICIPANT (on COMMIT):
    apply_redo(); release_locks()

PARTICIPANT (on ABORT):
    apply_undo(); release_locks()
```

**The blocking problem.** After voting YES, a participant is **prepared** —
locks held, log written — and must wait for the coordinator's decision. If the
coordinator crashes after logging COMMIT but before sending all COMMIT messages,
surviving participants block indefinitely. Recovery requires the coordinator's
log to survive and the coordinator to come back. In cloud systems this is a soft
failure: no data loss, but the cluster stops.

**Why XA is rare.**

- Cross-node tail-latency amplification — every 2PC pays the worst-case round
  trip of any participant.
- Most modern data stores (most NoSQL, most queues) do not implement XA.
- Sagas are operationally cheaper for the same business outcome.

**When 2PC still survives.** Single-vendor enterprise stacks where every
resource manager speaks XA (WebSphere + DB2 + MQ; some banking, some SAP).
**Not** microservices.

**Type-safety notes.** None — correctness depends on fsync semantics and
recovery procedures the type system cannot encode. Production correctness
depends on the participant having logged its prepare decision _before_
responding. Do not roll your own.

**When NOT to use.** Across heterogeneous data stores (Mongo + Kafka don't both
speak XA); across services owned by different teams (coordinator failure is a
cross-team incident); when eventual consistency works (saga is cheaper).

**Real-world examples.** Java EE / WebSphere / WebLogic ran on XA for two
decades. Spanner, CockroachDB, FoundationDB implement 2PC internally — the
application sees one transaction.

**Anti-pattern variant.** _"Distributed transaction across our microservices."_
A coordinator over HTTP issuing PREPARE/COMMIT. The team has invented 2PC,
inherited all its blocking failure modes, and gained none of its tooling. The
fix is a saga.

**References.**

- Jim Gray & Andreas Reuter, _Transaction Processing: Concepts and
  Techniques_, 1992.
- Pat Helland, "Life beyond Distributed Transactions: an Apostate's Opinion",
  ACM Queue 2007.
- DDIA, ch. 9.

---

## Three-Phase Commit, Paxos, Raft

**Intent.** Reach **agreement among N nodes** that survives any minority
(`f < N/2`) of crash failures in an asynchronous network. This is the consensus
problem.

- **Three-Phase Commit** adds a `pre-commit` to 2PC. Works only under
  synchronous-network assumptions production networks violate. Rarely used.
- **Paxos** (Lamport, 1998) — foundational, proofs classic, pseudocode famously
  opaque.
- **Raft** (Ongaro & Ousterhout, 2014) — Paxos restated for humans. Same
  correctness, easier to implement, audit, debug.

**When to reach for it.**

- You are building a coordination service (etcd, ZooKeeper, Consul) — almost
  never. You are _using_ one.
- You are building a database with a replicated log (CockroachDB, TiKV, MongoDB
  replica sets) — again, you are using one.
- You have a hard requirement for strict serializability across a cluster, you
  have measured that no off-the-shelf option fits, and you have a multi-quarter
  budget. Essentially never the answer for application teams.

**Sketch (Raft, leader election only).** Pseudocode after Raft paper Figure 2.

```
# Per-node persistent state (must survive restart):
currentTerm : int = 0
votedFor    : NodeId | None = None
log         : list[LogEntry] = []

# Per-node volatile:
role        : "follower" | "candidate" | "leader" = "follower"

on election_timeout():
    role = "candidate"
    currentTerm += 1
    votedFor = self.node_id
    persist(currentTerm, votedFor)
    for peer in peers:
        send(peer, RequestVote(
            term=currentTerm, candidateId=self.node_id,
            lastLogIndex=len(log) - 1,
            lastLogTerm=log[-1].term if log else 0,
        ))
    # collect responses; on majority -> become leader.

on RequestVote(term, candidateId, lastLogIndex, lastLogTerm):
    if term < currentTerm:
        return reply(currentTerm, voteGranted=False)
    if term > currentTerm:
        currentTerm, votedFor, role = term, None, "follower"
        persist(currentTerm, votedFor)
    log_ok = (
        lastLogTerm > (log[-1].term if log else 0)
        or (lastLogTerm == (log[-1].term if log else 0) and lastLogIndex >= len(log) - 1)
    )
    if (votedFor is None or votedFor == candidateId) and log_ok:
        votedFor = candidateId
        persist(currentTerm, votedFor)
        return reply(currentTerm, voteGranted=True)
    return reply(currentTerm, voteGranted=False)
```

**Two non-negotiable invariants.** `currentTerm` and `votedFor` must be
persisted **before** the node responds. A server that voted for A in term 5,
crashed, restarted having forgotten the vote, then voted for B in the same term,
has produced two leaders. Forgotten persistence is the canonical bug in
hand-rolled Raft.

**Why off-the-shelf wins.** Real Raft requires log replication, snapshotting,
log compaction, membership change (joint consensus), pre-vote (avoiding
disruption after partition), leader lease (bounded stale reads), and a
state-machine-replication shim — proven correct, ideally model-checked. etcd's
Go implementation is ~10k lines with a TLA+ spec. Hashicorp's Raft library is
similar. Reach for one. The only code you write is the state machine they
replicate.

**When NOT to use.** Application state. If you need to share data across nodes,
you do not implement Raft — you put the data in etcd, Postgres with logical
replication, or DynamoDB. Application-layer Raft is almost always a missing
infrastructure piece in disguise.

**Real-world examples.** etcd (Kubernetes cluster state), Consul (Raft for the
strongly-consistent layer), CockroachDB (per-range Raft groups), TiKV
(per-region Raft), MongoDB replica sets, Kafka KRaft (replaces ZooKeeper).

**Anti-pattern variant.** _"We'll implement Paxos for our config service."_ The
team ships `paxos.py` — a happy-path subset that loses data under partition. Six
months later they revert to etcd.

**References.**

- Diego Ongaro & John Ousterhout, "In Search of an Understandable Consensus
  Algorithm", USENIX ATC 2014. <https://raft.github.io>.
- Leslie Lamport, "Paxos Made Simple", 2001.
- Heidi Howard's blog. DDIA, ch. 9.

---

## Leader Election

**Intent.** Designate exactly one node in a cluster as _leader_ — owner of a
singleton responsibility (writes, scheduling, lock granting). On leader failure,
the cluster elects a new one.

**Three families.**

1. **Bully algorithm** (Garcia-Molina, 1982) — highest-ID wins. Educational,
   rare in production.
2. **Raft-based** — built into consensus. Every term has at most one leader.
   Production answer.
3. **Lease-based** — a coordination service grants a renewable, time-bounded
   lease. The lease holder is leader; on expiry without renewal, another node
   takes over. Built on etcd, ZooKeeper, DynamoDB.

**When to reach for it.**

- A cluster has a singleton job — scheduler, primary writer, lock granter — that
  must auto-failover.
- The job is _not_ "each node does 1/Nth of the work" — that is
  **partitioning**, not leadership. Picking a leader to _assign_ partitions is
  fine; conflating partition-ownership with leadership is the common confusion.

**Sketch (lease-based, etcd-style).** The lease _is_ the leadership token.

```python
import asyncio
from typing import Final, Protocol


class LeaseClient(Protocol):
    async def grant(self, ttl_seconds: int) -> int: ...
    async def keep_alive_once(self, lease_id: int) -> None: ...
    async def put_if_absent(self, key: str, value: str, lease_id: int) -> bool: ...
    async def revoke(self, lease_id: int) -> None: ...


class LeaderElector:
    LEASE_TTL: Final = 10
    RENEW_INTERVAL: Final = 3   # well before TTL
    KEY: Final = "/leaders/scheduler"

    def __init__(self, client: LeaseClient, node_id: str) -> None:
        self._client: Final = client
        self._node_id: Final = node_id
        self._lease_id: int | None = None

    async def campaign(self) -> bool:
        lease_id = await self._client.grant(self.LEASE_TTL)
        won = await self._client.put_if_absent(self.KEY, self._node_id, lease_id)
        if not won:
            await self._client.revoke(lease_id)
            return False
        self._lease_id = lease_id
        return True

    async def keep_leading(self) -> None:
        assert self._lease_id is not None, "must call campaign() first"
        while True:
            await asyncio.sleep(self.RENEW_INTERVAL)
            await self._client.keep_alive_once(self._lease_id)
```

**Type-safety notes.**

- Wrap the lease ID in `NewType("LeaseId", int)` — leadership is not an ambient
  `int`.
- Leadership is not a boolean. It is a _capability_ — the lease object. A leader
  that has lost its lease (renewal failed) but believes it is still leader is
  the canonical split-brain bug. Fencing tokens defend against this.

**Split-brain.** Node A holds the lease. Partition between A and the lease
service. A's clock keeps ticking; A still believes its TTL=10s of leadership.
The service expires the lease and grants it to B. For a window equal to A's
clock skew + processing delay, both believe they are leader. If both write, data
corruption. **Defense: fencing tokens** — every lease carries a strictly
monotonic ID; the resource rejects writes with stale IDs. See _Distributed
Lock_.

**When NOT to use.** "I want one of my workers to handle each task once." That
is a _queue_, not a leader.

**Real-world examples.** Kubernetes controller-manager (etcd lease), Consul
agents (Raft + sessions), Patroni for Postgres, Kafka's controller election.

**Anti-pattern variant.** _"Leader election with no fencing."_ Two replicas race
on Redis SETNX. No token, no rejection at the data store. Loser's GC pause ends
after lease expiry; both write. The fix is fencing.

**References.**

- Hector Garcia-Molina, "Elections in a distributed computing system", IEEE
  TOC 1982.
- etcd concurrency:
  <https://etcd.io/docs/latest/dev-guide/api_concurrency_reference_v3>.

---

## Distributed Lock

**Intent.** Mutual exclusion across processes. Only one client at a time may
hold a named lock.

**The hard truth.** A distributed lock is correct only if the protected
operation is **idempotent** or **fenced**. Anything else has a race window equal
to network + clock uncertainty.

**Two safe shapes.**

1. **Lease + fencing token.** Every acquisition returns a monotonic token. The
   protected resource checks the token on every write, rejecting stale ones.
   ZooKeeper's `zxid`, etcd's revision, Spanner's TrueTime intervals provide
   this.
2. **Idempotent operation under at-most-once-effective semantics.** The lock is
   advisory; correctness comes from duplicate execution being a no-op (CAS,
   idempotency keys — see `reliability.md`).

**When to reach for it.**

- The operation is genuinely not idempotent.
- You can pass a fencing token to the resource layer.

**Sketch (with fencing token).**

```python
from dataclasses import dataclass
from typing import NewType, Protocol


LockToken = NewType("LockToken", int)


@dataclass(frozen=True, slots=True)
class Lease:
    name: str
    holder: str
    token: LockToken      # monotonically increasing
    ttl_seconds: int


class LockService(Protocol):
    async def acquire(self, name: str, holder: str, ttl_seconds: int) -> Lease | None: ...
    async def release(self, lease: Lease) -> None: ...


class FencedStore(Protocol):
    """Stale tokens rejected at the storage layer."""

    async def write(self, key: str, value: bytes, *, fence: LockToken) -> None: ...


async def update_under_lock(locks: LockService, store: FencedStore, key: str, holder: str, value: bytes) -> None:
    lease = await locks.acquire(name=f"resource:{key}", holder=holder, ttl_seconds=10)
    if lease is None:
        raise RuntimeError("could not acquire lock")
    try:
        await store.write(key, value, fence=lease.token)
    finally:
        await locks.release(lease)
```

**Type-safety notes.**

- `LockToken = NewType("LockToken", int)` distinguishes fencing tokens from
  ambient ints. The store's signature requires a `LockToken`, not `int`, forcing
  the call site to pass the lease's token.
- The store enforces fencing — not the lock service, not the client. If your
  "lock" cannot reject stale writes at storage, it is not a safe lock.

**Redlock and the Kleppmann–Antirez exchange (2016).** Kleppmann argued Redlock
— multi-node Redis with majority acquisition — produces no fencing token and is
therefore unsafe under any GC pause, network delay, or clock skew exceeding lock
TTL. Sanfilippo replied that Redlock is safe under stronger assumptions (bounded
clock drift, monotonic clocks). Pragmatic takeaway: **for correctness, use
ZooKeeper's `zxid` / etcd's revision / Spanner's commit timestamp as your
fence.** Redlock is fine for advisory locking where double-execution is
harmless.

**When NOT to use.** The operation is idempotent — skip the lock. The resource
serializes itself (`SELECT ... FOR UPDATE`, version columns) — use that; it is
already fenced. The lock is being used for work distribution — use a queue.

**Real-world examples.** ZooKeeper Curator `InterProcessMutex`, etcd
`election`/`mutex`, Cassandra's lightweight transactions (Paxos-fenced CAS).

**Anti-pattern variant.** _"SETNX with TTL"_ as a critical-section gate without
fencing. Lock holder GC-pauses 30s; TTL expires; another holder takes over;
first holder wakes, writes; last write wins, and last write is the wrong one.

**References.**

- Martin Kleppmann, "How to do distributed locking", 2016.
  <https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html>.
- Sanfilippo's reply: <http://antirez.com/news/101>.
- DDIA, ch. 8, 9.

---

## Heartbeat and Failure Detector

**Intent.** Decide whether a remote node is up. Necessarily probabilistic — in
an async network you cannot distinguish slow from dead. A failure detector
trades **completeness** (eventually flag all dead) against **accuracy** (rarely
flag live as dead).

**Three families.**

1. **TTL-based heartbeat.** "I am alive" every K seconds; mark dead after
   `N * K`. Simple, brittle.
2. **Phi-accrual** (Hayashibara et al., 2004). Continuous suspicion `φ` from the
   historical inter-arrival distribution. Akka default threshold = 8;
   Cassandra's `phi_convict_threshold` = 8, raise to 12 in noisy clouds. Used in
   **Akka Cluster** and **Cassandra**.
3. **External health check** (LB, Kubernetes liveness probe). Out-of-band probe.

**When to reach for which.**

- Cluster membership in a partition-tolerant system: **gossip + phi-accrual**.
- Service-to-service liveness in request-response: **passive** — let requests
  time out, no separate liveness opinion (DDIA, ch. 8).
- Singleton job / leader: **lease expiry** is your failure detector.

**Sketch (phi-accrual, simplified).** Sliding window of inter-arrival times; φ
from the log-likelihood that "time since last heartbeat" is drawn from the
historical distribution. Higher φ ⇒ more likely dead.

```python
import math
from collections import deque
from dataclasses import dataclass, field
from time import monotonic


@dataclass(slots=True)
class PhiAccrualDetector:
    window_size: int = 200
    min_std_deviation_ms: float = 50.0
    arrivals: deque[float] = field(default_factory=deque)
    last_heartbeat_ms: float | None = None

    def heartbeat(self) -> None:
        now = monotonic() * 1000
        if self.last_heartbeat_ms is not None:
            self.arrivals.append(now - self.last_heartbeat_ms)
            while len(self.arrivals) > self.window_size:
                self.arrivals.popleft()
        self.last_heartbeat_ms = now

    def phi(self) -> float:
        if self.last_heartbeat_ms is None or not self.arrivals:
            return 0.0
        elapsed = monotonic() * 1000 - self.last_heartbeat_ms
        mean = sum(self.arrivals) / len(self.arrivals)
        var = sum((x - mean) ** 2 for x in self.arrivals) / len(self.arrivals)
        std = max(math.sqrt(var), self.min_std_deviation_ms)
        y = (elapsed - mean) / std
        e = math.exp(-y * (1.5976 + 0.070566 * y * y))
        return -math.log10(e / (1.0 + e)) if elapsed > mean else -math.log10(1.0 - 1.0 / (1.0 + e))
```

**Type-safety notes.** `phi` is a continuous score — keep threshold checks at
the call site, not inside the detector, so one detector can serve multiple
consumers with different sensitivities.

**False positives under partition.** A cannot reach B for 30s. Phi → infinity; A
declares B dead. B is alive but unreachable. If A unilaterally promotes itself,
split brain. **Failure detection is input to consensus or leader election; it is
not authority to act.**

**When NOT to use.** A request-response service with timeouts. The timeout _is_
your failure detector for that one call.

**Real-world examples.** Akka Cluster (phi-accrual), Cassandra (gossip +
phi-accrual), Hashicorp Serf (SWIM), Kubernetes kubelet liveness (TTL).

**Anti-pattern variant.** _"Acting on suspicion."_ A suspects B; A handles B's
traffic. B suspects A; B keeps its own traffic. Both run. Fix: feed suspicion
into a cluster-wide decision.

**References.**

- Hayashibara, Défago et al., "The φ Accrual Failure Detector", IEEE SRDS 2004.
- Akka docs:
  <https://doc.akka.io/libraries/akka-core/current/typed/failure-detector.html>.
- DDIA, ch. 8.

---

## Lamport Timestamps and Vector Clocks

**Intent.** Order events across nodes with no shared clock. **Lamport** gives a
total order consistent with causality. **Vector clocks** preserve more — they
detect _concurrency_.

**Lamport's rule (1978).** Counter `L` per process. Local event: `L += 1`. Send:
attach `L`. Receive `m`: `L = max(L, m) + 1`. If `a → b` then `L(a) < L(b)`; the
converse does not hold. Total order with process-id tiebreak; no concurrency
detection.

**Vector clocks.** Vector `V[1..N]` per process `i`. Local: `V[i] += 1`. Send:
attach `V`. Receive `m`: `V[j] = max(V[j], m[j])` for all `j`, then `V[i] += 1`.
Two events are causally related iff their vectors are componentwise comparable;
otherwise concurrent.

**When to reach for it.**

- Multi-leader / leaderless replication where conflicts must be detected
  (Dynamo, Riak).
- Distributed debugging needing happens-before.
- CRDTs whose merge uses causal histories.

**Sketch (vector clocks).**

```python
from dataclasses import dataclass, field
from typing import Self


@dataclass(frozen=True, slots=True)
class VectorClock:
    versions: dict[str, int] = field(default_factory=dict)

    def tick(self, node_id: str) -> Self:
        new = dict(self.versions)
        new[node_id] = new.get(node_id, 0) + 1
        return type(self)(versions=new)

    def merge(self, other: Self) -> Self:
        keys = set(self.versions) | set(other.versions)
        return type(self)(versions={k: max(self.versions.get(k, 0), other.versions.get(k, 0)) for k in keys})

    def happens_before(self, other: Self) -> bool:
        """self ≤ other componentwise and self ≠ other."""
        keys = set(self.versions) | set(other.versions)
        leq = all(self.versions.get(k, 0) <= other.versions.get(k, 0) for k in keys)
        return leq and self.versions != other.versions

    def concurrent_with(self, other: Self) -> bool:
        return not self.happens_before(other) and not other.happens_before(self) and self != other
```

**Type-safety notes.**

- Make `VectorClock` immutable; mutating a shared vector across threads is a
  classic bug.
- `node_id` should be `NewType("NodeId", str)`; conflating hostname with logical
  replica id leads to bugs on rehosting.

**When NOT to use.** Single-leader replication — the leader's log is the order.

**Real-world examples.** Riak (sibling resolution); the original Dynamo paper;
CRDTs use causal histories. Cassandra abandoned vector clocks for LWW and
accepted the consequences.

**Anti-pattern variant.** _"Vector clocks for everything."_ Used as a generic
timestamp where UUIDv7 or a Lamport scalar would do. Vector clocks grow with
cluster size; right tool only when you _need concurrency detection_.

**References.**

- Leslie Lamport, "Time, Clocks, and the Ordering of Events in a Distributed
  System", CACM 1978.
- Fidge / Mattern, vector clocks, 1988.
- DDIA, ch. 5.

---

## CRDTs

**Intent.** Replicated data types whose merge is mathematically guaranteed to
converge, regardless of update order. No coordination needed.

**Two formalisms** (Shapiro et al., 2011).

- **State-based (CvRDT).** Exchange state; merge is a semilattice join
  (commutative, associative, idempotent).
- **Operation-based (CmRDT).** Exchange operations; effects commute.

**Useful zoo.**

- **G-Counter** — grow-only; per-replica counters, merge is componentwise max,
  value is sum.
- **PN-Counter** — two G-Counters (incs, decs); value is difference.
- **G-Set** — grow-only set; merge is union.
- **2P-Set** — add + remove; remove forever.
- **OR-Set** — observed-remove. Each add gets a unique tag; remove erases only
  observed tags. Allows re-add.
- **LWW-Register** — last-write-wins by timestamp; loses concurrent writes.
- **MV-Register** — multi-value; concurrent writes returned as siblings.
- **RGA / Treedoc / Logoot** — sequence CRDTs for collaborative text.

**When to reach for it.**

- Multi-region active-active where coordination latency is unacceptable.
- Offline-first apps that sync on reconnect (notes, todos).
- Collaborative editing (Yjs, Automerge, Figma).
- Cross-datacenter counters (Riak CRDTs, Redis CRDB).

**Sketch (G-Counter and PN-Counter).**

```python
from dataclasses import dataclass, field
from typing import Self


@dataclass(frozen=True, slots=True)
class GCounter:
    counts: dict[str, int] = field(default_factory=dict)

    def increment(self, replica_id: str, amount: int = 1) -> Self:
        if amount < 0:
            raise ValueError("non-negative only")
        new = dict(self.counts)
        new[replica_id] = new.get(replica_id, 0) + amount
        return type(self)(counts=new)

    def merge(self, other: Self) -> Self:
        keys = set(self.counts) | set(other.counts)
        return type(self)(counts={k: max(self.counts.get(k, 0), other.counts.get(k, 0)) for k in keys})

    def value(self) -> int:
        return sum(self.counts.values())


@dataclass(frozen=True, slots=True)
class PNCounter:
    inc: GCounter = field(default_factory=GCounter)
    dec: GCounter = field(default_factory=GCounter)

    def increment(self, replica_id: str, amount: int = 1) -> Self:
        return type(self)(inc=self.inc.increment(replica_id, amount), dec=self.dec)

    def decrement(self, replica_id: str, amount: int = 1) -> Self:
        return type(self)(inc=self.inc, dec=self.dec.increment(replica_id, amount))

    def merge(self, other: Self) -> Self:
        return type(self)(inc=self.inc.merge(other.inc), dec=self.dec.merge(other.dec))

    def value(self) -> int:
        return self.inc.value() - self.dec.value()
```

**Type-safety notes.**

- Merge must be **commutative, associative, idempotent**. Pyright cannot check
  this — verify with Hypothesis property tests over random states.
- CRDTs are immutable. "Merge in place" invites bugs where one replica's state
  mutates while being read.

**OR-Set semantics.** A remove erases only the _tags_ the removing replica had
observed. If A adds `x` (tag `a1`), B concurrently adds `x` (tag `b1`), A
removes `x` (erasing `a1`), the merged state still contains `x` via `b1`. Most
users expect "remove undoes my add, not yours"; 2P-Set's "remove forever" is
rarely desired.

**When NOT to use.**

- Data is intrinsically an authoritative sequence (financial ledger). Use a
  single-leader log.
- Strong consistency required (no sibling window allowed).
- Team is not prepared for monotonic state growth (CRDTs need tombstone GC).

**Real-world examples.** Riak CRDTs; Redis Enterprise CRDB; Yjs / Automerge;
Figma; Cosmos DB and DynamoDB use CRDT-like merge in some paths.

**Anti-pattern variant.** _"CRDTs for a banking ledger."_ You wanted agreement
on a balance; you got eventual convergence. Concurrent withdrawals can take the
balance below zero before merge resolves. CRDTs are not a transaction system.

**References.**

- Shapiro, Preguiça, Baquero, Zawirski, "Conflict-free Replicated Data Types",
  INRIA RR-7687, 2011.
- crdt.tech catalogue. DDIA, ch. 5.
- Yjs: <https://docs.yjs.dev>.

---

## Quorum Reads and Writes

**Intent.** Tunable consistency. Define `N` (replicas), `W` (write quorum), `R`
(read quorum). With `R + W > N` any read overlaps the most recent write — strong
consistency under no failures. With `R + W ≤ N`, lower latency, possible stale
reads. Dynamo (DeCandia et al., 2007) made this tunable per request; Cassandra
and Riak inherit it.

**When to reach for it.**

- Leaderless replicated stores (Cassandra, Riak, ScyllaDB, DynamoDB).
- Workloads where some operations need strong consistency and others tolerate
  staleness, with the trade-off explicit per operation.

**Sketch (read with `R` and write with `W`).**

```python
import asyncio
from dataclasses import dataclass
from typing import Final, Protocol


@dataclass(frozen=True, slots=True)
class VersionedValue[T]:
    value: T
    version: int      # vector clock or Lamport stamp; simplified here.


class Replica[T](Protocol):
    async def write(self, key: str, vv: VersionedValue[T]) -> None: ...
    async def read(self, key: str) -> VersionedValue[T] | None: ...


class QuorumStore[T]:
    def __init__(self, replicas: list[Replica[T]], *, w: int, r: int) -> None:
        if not replicas:
            raise ValueError("at least one replica required")
        self._replicas: Final = replicas
        self._w: Final = w
        self._r: Final = r

    async def write(self, key: str, vv: VersionedValue[T]) -> None:
        tasks = [asyncio.create_task(r.write(key, vv)) for r in self._replicas]
        successes = 0
        for fut in asyncio.as_completed(tasks):
            try:
                await fut
                successes += 1
                if successes >= self._w:
                    return
            except Exception:
                continue
        raise RuntimeError(f"write quorum not reached: {successes}/{self._w}")

    async def read(self, key: str) -> VersionedValue[T] | None:
        tasks = [asyncio.create_task(r.read(key)) for r in self._replicas]
        replies: list[VersionedValue[T] | None] = []
        for fut in asyncio.as_completed(tasks):
            try:
                replies.append(await fut)
            except Exception:
                replies.append(None)
            if sum(1 for x in replies if x is not None) >= self._r:
                break
        present = [x for x in replies if x is not None]
        if not present:
            return None
        return max(present, key=lambda v: v.version)  # latest version wins
```

**Type-safety notes.**

- For systems allowing concurrent writes, `VersionedValue` should carry a
  _vector clock_, not a scalar. Example simplifies; production: see Dynamo /
  Riak.
- `R + W > N` is a runtime invariant. Assert it in `__init__`.

**Strict vs sloppy quorum.**

- **Strict** — quorum from the primary replica set. Replica down ⇒ writes block.
- **Sloppy** (Dynamo) — writes accepted anywhere temporarily; "hinted handoff"
  replays to rightful replicas. Higher availability, more reconciliation.

**Read repair and anti-entropy.** Coordinator writes freshest value back to
lagging replicas (read repair); a Merkle-tree background process catches what
reads miss (anti-entropy). See _data.md_.

**When NOT to use.** Single-leader systems — consistency is the leader's job;
quorum is for leaderless.

**Real-world examples.** DynamoDB's _consistent read_ flag (R: 1 → 2);
Cassandra's per-query `ONE`/`QUORUM`/`ALL`; Riak's `r`/`w`/`pr`/`pw`; S3 strong
read-after-write (2020) is internally a quorum protocol.

**Anti-pattern variant.** _"Strong by default, weak when in a hurry."_ Ops flips
`consistency=ONE` for latency, downstream code assumed `QUORUM`, billing ships
stale. Pick consistency per operation; document; code review.

**References.**

- DeCandia et al., "Dynamo: Amazon's Highly Available Key-value Store",
  SOSP 2007.
- DDIA, ch. 5.

---

## Gossip Protocols

**Intent.** Disseminate state across a cluster without a coordinator. Nodes
pair-exchange with random peers periodically. Convergence is `O(log N)` rounds.

**Two flavors.**

- **Anti-entropy** (push/pull/push-pull). Exchange digests; pull what's missing.
- **Rumor mongering** (epidemic). New updates are "hot"; aggressively
  propagated, then cooled.

**When to reach for it.**

- Cluster membership in a partition-tolerant system.
- Slowly-changing state (failure detection, config, version vectors).
- P2P / service-mesh discovery.

**Sketch.** Correctness is in randomization and round structure, not any
particular line.

```
every gossip_interval:
    peer = random_choice(known_peers)
    their_view = exchange(peer, local_state_snapshot())
    merge(local_state, their_view)
```

Cluster membership, phi-accrual suspicion, config generations all ride on
gossip. Each piece of state has a version; merge picks the higher.

**Type-safety notes.** Gossip payloads are CRDT-shaped — versioned monotonic
merges. Encode the contract: every value has a partial order, every merge picks
the upper bound.

**When NOT to use.** Strong consistency (gossip is eventual). Small clusters (<
5 nodes). High-frequency state (per-second updates).

**Real-world examples.** Cassandra (1s gossip), Hashicorp Serf (SWIM), Consul
(Serf-based), CockroachDB metadata.

**Anti-pattern variant.** _"Gossip for application data."_ Convergence latency =
stale reads everywhere. Fix: strongly-consistent KV (etcd) for hot config;
gossip for cluster state.

**References.**

- Demers et al., "Epidemic algorithms for replicated database maintenance",
  PODC 1987.
- Das, Gupta, Motivala, "SWIM", DSN 2002.
- DDIA, ch. 5, 6.

---

## When to reach for what

Stop at the first honest "yes".

1. **All work fits in one DB transaction?** → Use the transaction. None of these
   patterns apply.
2. **Multi-step workflow across services?** → **Saga.** Orchestration for > 4
   steps / branching; choreography for short and stable.
3. **You think you need a distributed transaction across heterogeneous
   services?** → You don't. Saga. (2PC only inside single-vendor enterprise
   stacks.)
4. **Leader election, distributed locks, cluster config?** → **etcd / ZooKeeper
   / Consul.** Do not implement Raft.
5. **Distributed lock and the operation is not idempotent?** → Lease + **fencing
   token** at the storage layer. Or make it idempotent and skip the lock
   (usually right).
6. **Detect liveness in a partition-tolerant cluster?** → **Gossip +
   phi-accrual.** Feed suspicion into consensus; do not act unilaterally.
7. **Detect concurrent writes in leaderless / multi-leader replication?** →
   **Vector clocks** for detection, **CRDTs** for automatic merge.
8. **Active-active across regions?** → **CRDTs** for tolerant data;
   **single-leader** otherwise.
9. **Tunable consistency in a leaderless store?** → **Quorum (R/W/N).**
10. **About to implement consensus by hand?** → Stop. Use **etcd / ZooKeeper /
    Consul / Spanner / DynamoDB.** From-scratch is a research project, not a
    feature.

---

## Review Checklist

1. Every saga has **persistent state** that survives orchestrator restart.
2. All saga steps and compensations are **idempotent**, demonstrably
   (idempotency keys, CAS).
3. Every distributed lock that protects a non-idempotent op uses a **fencing
   token** at storage.
4. Leader election runs on **etcd / ZooKeeper / Consul**, not hand-rolled SETNX.
5. Failure detection feeds **consensus**, not unilateral action.
6. Consistency level is **explicit per operation**, not an ambient default.
7. CRDT merges are **commutative, associative, idempotent**, verified by
   property tests.
8. Vector clocks are used for **concurrency detection**, not as fancy
   timestamps.
9. Gossip carries **slowly-changing cluster state**, not application data.
10. Nobody is reaching for 2PC or hand-rolled Paxos across microservices — the
    answer is a saga.
