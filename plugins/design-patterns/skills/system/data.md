# Data Architecture Patterns

_Patterns for shaping how data is written, read, replicated, and observed across
services._

The naive shape is a single relational database accessed through an ORM. It
works for a long time. This file is about what to do when it stops — when reads
dwarf writes, when a schema change paralyzes three teams, when an event vanishes
mid-flight, when one replica cannot serve global traffic.

Default posture: **the simplest data shape that holds the load**, with explicit
signposts to upgrade. Premature event sourcing, premature CQRS, premature
sharding — each buys a small future option at large present cost.

Persistence patterns one layer below this (Repository, Unit of Work, Domain
Events, basic Outbox) live in moirae's _Enterprise Patterns_ reference; this
file goes deeper and adds what that document does not cover.

## How to use this file

_When to reach for it_ and _When NOT to use_ are the trail heads. _Sketches_ are
reference, not tutorial — read after deciding to adopt. Saga lives in
`distributed.md` as coordination; here it appears only as data-shape
consequences.

## Table of Contents

- [Data Architecture Patterns](#data-architecture-patterns)
    - [How to use this file](#how-to-use-this-file)
    - [Table of Contents](#table-of-contents)
    - [The big picture](#the-big-picture)
    - [CQRS](#cqrs)
    - [Event Sourcing](#event-sourcing)
    - [Outbox Pattern](#outbox-pattern)
    - [Inbox Pattern](#inbox-pattern)
    - [Materialized View](#materialized-view)
    - [Database per Service](#database-per-service)
    - [Sharding](#sharding)
    - [Replication](#replication)
    - [Eventual Consistency](#eventual-consistency)
    - [Read Repair and Anti-entropy](#read-repair-and-anti-entropy)
    - [Change Data Capture (CDC)](#change-data-capture-cdc)
    - [Tombstones and Soft Delete](#tombstones-and-soft-delete)
    - [Saga's data consequences](#sagas-data-consequences)
    - [When to reach for what](#when-to-reach-for-what)
    - [Review Checklist](#review-checklist)

---

## The big picture

Five questions:

1. **Read shape diverges from write shape?** → CQRS (lightweight or full).
2. **Reconstruct historical state? Audit _why_ the state is what it is?** →
   Event Sourcing.
3. **Mutate state and tell another process atomically?** → Outbox + Inbox.
4. **One DB struggles with load?** → Replication first, then Sharding.
5. **Services trampling each other through shared schema?** → Database per
   Service.

Every other pattern here serves one of those five.

---

## CQRS

**Intent.** Split the read model from the write model. Writes and reads have
fundamentally different shapes — writes enforce invariants and transactions;
reads denormalize, paginate, span aggregates. A single model is bad at both.
Coined by Greg Young (2010) on top of Bertrand Meyer's earlier command-query
separation principle.

**When to reach for it.**

- Reads dominate writes (or vice versa) by an order of magnitude.
- Read queries cannot be served from the write schema without unmaintainable
  joins.
- The read shape and write shape have visibly diverged — "view-only" fields keep
  accruing on the domain model.
- Vernon (_Implementing DDD_): "complex domains with skewed read/write".

**Sketch (lightweight CQRS — same DB, separate types).**

```python
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID


# Write side: domain model. Enforces invariants.

class OrderStatus(StrEnum):
    DRAFT = "draft"
    PLACED = "placed"
    SHIPPED = "shipped"
    CANCELLED = "cancelled"

class EmptyOrderError(Exception): ...

@dataclass(slots=True)
class LineItem:
    sku: str
    quantity: int
    price_cents: int

@dataclass(slots=True)
class Order:
    id: UUID
    user_id: UUID
    items: list[LineItem]
    status: OrderStatus

    def place(self) -> None:
        if not self.items: raise EmptyOrderError
        self.status = OrderStatus.PLACED

class OrderRepository(Protocol):
    def get(self, order_id: UUID) -> Order | None: ...
    def add(self, order: Order) -> None: ...


# Read side: cheap projections. Skip the domain.

@dataclass(frozen=True, slots=True)
class OrderListItemView:
    order_id: UUID
    user_email: str          # denormalized
    item_count: int
    status: str
    placed_at: datetime
    total_cents: int

class OrderReadModel(Protocol):
    def list_for_user(self, user_id: UUID, *, limit: int) -> Sequence[OrderListItemView]: ...
```

**Type-safety notes.** Read DTOs are `frozen=True, slots=True` — values, not
entities. Use `Sequence[T]`, not `list[T]`, to discourage caller mutation.

**Lightweight CQRS** keeps one DB; most benefit for 10% of the cost.
**Eventual-consistency CQRS** introduces a separate read store (Elasticsearch,
denormalized SQL, materialized view). Pursue only when reads cannot be served
from the write store — full-text search, complex aggregation, geographic
distribution.

**When NOT to use.** Most applications. CQRS is high-commitment: two models, two
code paths, plus a projection pipeline (in the EC form). CRUD over one aggregate
does not need it.

**Real-world examples.** Most e-commerce separates "orders write" from "orders
list" without calling it CQRS. Stack Overflow's "questions list" vs "post new"
is canonical lightweight CQRS. Event-sourced systems pair with full CQRS —
projections _are_ the read side.

**Anti-pattern variant.** _"CQRS without complex read needs."_ Read side is a
1:1 mirror; every query goes through both for no benefit. Fix: delete it, or
downgrade to lightweight CQRS.

**References.**

- Greg Young, "CQRS Documents", 2010 — codebetter.com.
- Vaughn Vernon, _Implementing Domain-Driven Design_, ch. 4.
- Martin Fowler, "CQRS", martinfowler.com.

---

## Event Sourcing

**Intent.** Persist state as an append-only log of _events_ (facts that
happened) rather than a mutable snapshot. Current state is a left-fold over
events. Read models, aggregations, history, audit — all derived. The history is
the truth: rebuild any past state, project events into a new view without data
migration; audit is automatic; new read models are cheap.

**When to reach for it.**

- The domain _is_ a sequence of events (financial ledgers, version-controlled
  documents, IoT, audit-heavy systems).
- "Why is the state what it is?" is a real user question.
- The team has operational budget for projections, schema-evolution machinery,
  and event-store tooling.

**Sketch.**

```python
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal, Self
from uuid import UUID, uuid4


# Events: immutable facts. Versioned (event_type + schema_version).

@dataclass(frozen=True, slots=True)
class Event:
    event_id: UUID
    aggregate_id: UUID
    occurred_at: datetime

@dataclass(frozen=True, slots=True)
class AccountOpened(Event):
    event_type: Literal["AccountOpened"] = "AccountOpened"
    schema_version: Literal[1] = 1
    owner: str = ""

@dataclass(frozen=True, slots=True)
class MoneyDeposited(Event):
    event_type: Literal["MoneyDeposited"] = "MoneyDeposited"
    schema_version: Literal[1] = 1
    amount_cents: int = 0

@dataclass(frozen=True, slots=True)
class MoneyWithdrawn(Event):
    event_type: Literal["MoneyWithdrawn"] = "MoneyWithdrawn"
    schema_version: Literal[1] = 1
    amount_cents: int = 0

type AccountEvent = AccountOpened | MoneyDeposited | MoneyWithdrawn


# Aggregate: rebuilt by folding events.

class AccountClosedError(Exception): ...
class InsufficientFundsError(Exception): ...


@dataclass(slots=True)
class Account:
    id: UUID
    owner: str
    balance_cents: int = 0
    closed: bool = False
    pending: list[AccountEvent] = field(default_factory=list)

    @classmethod
    def open(cls, account_id: UUID, owner: str) -> Self:
        acct = cls(id=account_id, owner=owner)
        acct._apply(AccountOpened(uuid4(), account_id, datetime.now(UTC), owner=owner))
        return acct

    @classmethod
    def replay(cls, account_id: UUID, events: Iterable[AccountEvent]) -> Self:
        acct = cls(id=account_id, owner="")
        for e in events:
            acct._apply(e, record=False)
        return acct

    def deposit(self, cents: int) -> None:
        if self.closed: raise AccountClosedError
        if cents <= 0: raise ValueError("must be positive")
        self._apply(MoneyDeposited(uuid4(), self.id, datetime.now(UTC), amount_cents=cents))

    def withdraw(self, cents: int) -> None:
        if self.closed: raise AccountClosedError
        if cents <= 0: raise ValueError("must be positive")
        if cents > self.balance_cents: raise InsufficientFundsError
        self._apply(MoneyWithdrawn(uuid4(), self.id, datetime.now(UTC), amount_cents=cents))

    def _apply(self, event: AccountEvent, *, record: bool = True) -> None:
        match event:
            case AccountOpened(owner=o): self.owner = o
            case MoneyDeposited(amount_cents=a): self.balance_cents += a
            case MoneyWithdrawn(amount_cents=a): self.balance_cents -= a
        if record:
            self.pending.append(event)
```

**Type-safety notes.**

- Events are tagged unions. `event_type: Literal[...]` +
  `schema_version: Literal[N]` lets pyright exhaustively check `match` over
  events.
- Aggregate ID = stream ID. `NewType("AccountId", UUID)` prevents
  cross-aggregate confusion.
- `replay` and user-facing methods share `_apply` — behavior cannot drift
  between live and reconstruction.

**Snapshots.** Every K events, record state + index; on replay, resume past the
snapshot.

**Schema evolution**, in order of cost: (1) **weak schema** — optional new
fields, additive only; (2) **upcasting** — transform v1 → v2 on read; (3)
**copy-and-transform** — migrate the store, expensive, rare. Rule: events are
immutable history; add new _types_, not new fields.

**Projections.** `(state, event) -> state` with its own checkpoint. Rebuild a
read model by drop-and-replay.

```python
@dataclass(slots=True)
class AccountSummary:
    account_id: UUID
    owner: str
    balance_cents: int


def project_summary(state: AccountSummary | None, event: AccountEvent) -> AccountSummary:
    match event:
        case AccountOpened(aggregate_id=aid, owner=o):
            return AccountSummary(aid, o, 0)
        case MoneyDeposited(amount_cents=a) if state is not None:
            return AccountSummary(state.account_id, state.owner, state.balance_cents + a)
        case MoneyWithdrawn(amount_cents=a) if state is not None:
            return AccountSummary(state.account_id, state.owner, state.balance_cents - a)
        case _:
            raise RuntimeError("event before AccountOpened")
```

**When NOT to use.**

- CRUD domain — events mirror table mutations and gain nothing.
- "We might need audit someday" — the binlog/WAL or a CDC-fed audit table is the
  answer. Event sourcing is a heavier commitment.
- The team has not internalized "events are immutable history" — without that
  discipline, the system degenerates into "events with mutable fields", worst of
  both worlds.

**Real-world examples.** Banks (every ledger is event-sourced in disguise),
EventStoreDB, Marten, Yjs and Automerge, many trading systems, DynamoDB Streams
as a building block.

**Anti-pattern variant.** _"Event Sourcing for CRUD."_ Every UPDATE becomes an
event; nobody reads history; projections are 1:1 mirrors of the original tables.
5x complexity for an audit log that `created_at`/`updated_at`/`deleted_at` would
have given you.

**References.**

- Martin Fowler, "Event Sourcing", martinfowler.com, 2005.
- Greg Young, "A Decade of DDD, CQRS, Event Sourcing".
- Vaughn Vernon, _Implementing DDD_, ch. 8. DDIA, ch. 11.

---

## Outbox Pattern

**Intent.** Atomically persist a state change and the event that announces it.
Without it, a crash between "DB commit" and "publish to broker" leaves consumers
unaware of a committed change.

**The dual-write problem.**

```python
session.add(order)
session.commit()                      # 1. DB committed
broker.publish(OrderPlacedEvent(...)) # 2. broker may fail
```

If step 2 fails, the order exists; no consumer hears. Reordering is worse —
publishing before commit can broadcast a change the database never records.

**The shape.** Write the event into an `outbox` table in the same transaction as
the state change. A separate publisher reads the outbox and forwards to the
broker.

**When to reach for it.**

- A mutation must produce an event observed by another process/service.
- "Lost an event" is a real bug (billing, notifications, downstream sagas).
- You have a transactional database the broker does not share.

**Sketch.**

```python
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase, Session


class Base(DeclarativeBase): ...


class OutboxRow(Base):
    __tablename__ = "outbox"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    aggregate_id: Mapped[str]
    event_type: Mapped[str]
    schema_version: Mapped[int]
    payload: Mapped[bytes]
    occurred_at: Mapped[datetime]
    published_at: Mapped[datetime | None] = mapped_column(default=None, nullable=True)


@dataclass(frozen=True, slots=True)
class OutboundEvent:
    aggregate_id: str
    event_type: str
    schema_version: int
    payload: bytes
    occurred_at: datetime


def write_outbox(session: Session, events: Iterable[OutboundEvent]) -> None:
    for e in events:
        session.add(OutboxRow(
            aggregate_id=e.aggregate_id, event_type=e.event_type,
            schema_version=e.schema_version, payload=e.payload, occurred_at=e.occurred_at,
        ))


class Broker:
    async def publish(self, event_type: str, payload: bytes, *, key: str) -> None: ...


async def relay_outbox(factory: Callable[[], Session], broker: Broker, *, batch: int = 100) -> int:
    """One pass over the outbox. Run on a schedule."""
    with factory() as session:
        # FOR UPDATE SKIP LOCKED -> multiple relayers cooperate without races.
        stmt = (
            select(OutboxRow).where(OutboxRow.published_at.is_(None))
            .order_by(OutboxRow.id).with_for_update(skip_locked=True).limit(batch)
        )
        rows = list(session.execute(stmt).scalars())
        for row in rows:
            await broker.publish(row.event_type, row.payload, key=row.aggregate_id)
            row.published_at = datetime.now(UTC)
        session.commit()
        return len(rows)
```

**Type-safety notes.** Store serialized payload (`bytes`) +
`(event_type, schema_version)`; consumer deserializer keyed off both. Never
store pickled Python — it is an RCE channel. Order by `id` (autoincrement) —
publication order, not business `occurred_at`.

**Ordering.** If consumers care, partition by `aggregate_id`. Cross-aggregate
ordering destroys throughput.

**At-least-once.** Relayer crash between publish and mark-published produces
duplicates. Consumers must be **idempotent** — see _Inbox_ and
`idempotency keys` in `reliability.md`.

**Outbox vs CDC.** Outbox publishes _domain events_; CDC publishes _row
changes_. Hybrid: CDC over an outbox table.

**When NOT to use.** Single-process, single-DB with no cross-process consumers —
emit events in-process after commit.

**Real-world examples.** Debezium outbox-event-router, Eventuate. Stripe's
"deliveries" system.

**Anti-pattern variant.** _"Two writes, fingers crossed."_ No outbox; a network
blip drops 0.01% of events; billing is off by a tail.

**References.**

- Chris Richardson, _Microservices Patterns_, ch. 3.
- microservices.io/patterns/data/transactional-outbox.html.

---

## Inbox Pattern

**Intent.** Consumer-side dedup for at-least-once delivery. Each consumer
maintains a table of processed event IDs; before processing, check; if present,
skip.

**When to reach for it.**

- Consuming from at-least-once brokers (Kafka, SQS, RabbitMQ, Kinesis, NATS
  JetStream).
- Handler has side effects (charge a card, send email, mutate downstream) that
  double-execution corrupts.
- Handler cannot be made naturally idempotent (CAS / unique constraint / LWW).

**Sketch.**

```python
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column, Session


class InboxRow(Base):
    __tablename__ = "inbox"

    event_id: Mapped[str] = mapped_column(primary_key=True)
    consumer: Mapped[str] = mapped_column(primary_key=True)
    processed_at: Mapped[datetime]


def process_once(session: Session, *, event_id: str, consumer: str, handler: Callable[[Session], None]) -> None:
    try:
        session.add(InboxRow(event_id=event_id, consumer=consumer, processed_at=datetime.now(UTC)))
        session.flush()           # IntegrityError if duplicate
    except IntegrityError:
        session.rollback()
        return                    # already processed
    handler(session)              # runs in the same transaction as the marker
    session.commit()
```

**Type-safety notes.**

- `(event_id, consumer)` composite PK lets N consumers process the same event
  independently.
- Handler runs inside the same transaction as the inbox insert; both commit or
  both roll back.

**Retention.** Inbox rows accumulate. Time-based (retain N days, lean on broker
retention) or high-watermark (drop rows below the broker's committed offset).
For Kafka, the consumer offset _is_ the watermark; inbox covers the narrow
window between "received" and "ack'd offset".

**When NOT to use.** Handler is naturally idempotent (unique constraint, CAS,
upsert), or the broker+framework provides EOS.

**Real-world examples.** Debezium outbox + consumer inbox. Most Kafka consumers
in finance. Event-sourced projection workers use an inbox-shaped position table
per projection.

**Anti-pattern variant.** _"Idempotent by hope."_ `INSERT` without
`ON CONFLICT`, trusting EOS. First redelivery inserts a duplicate. Fix: inbox or
unique constraint.

**References.**

- Chris Richardson, _Microservices Patterns_, ch. 3.
- microservices.io/patterns/data/transactional-inbox.html.

---

## Materialized View

**Intent.** Precompute and store an expensive query as a regular table. Refresh
on a schedule, on demand, or continuously via change streams. Reads are O(scan),
not O(5-way join).

**When to reach for it.**

- A read-side query with multi-way joins/aggregations against tables too large
  for per-request recomputation.
- Reporting / dashboards / analytics that tolerate seconds-to-minutes of
  staleness.
- The CQRS read side, when events project into a view.

**Refresh strategies.**

1. **Synchronous** — on every write the app updates the view. Always fresh;
   couples write-path cost; projection failure aborts the write.
2. **Eventual via CDC / events** — a consumer updates the view. Lag exists;
   write path unaffected.
3. **Periodic full refresh** — Postgres `REFRESH MATERIALIZED VIEW`.
   Low-frequency reports.
4. **Incremental** — built into Oracle, SQL Server, Snowflake dynamic tables,
   ksqlDB, Materialize. Postgres lacks built-in.

**Sketch (Postgres MV + manual refresh).**

```sql
CREATE MATERIALIZED VIEW order_summary AS
SELECT o.id AS order_id, u.email AS user_email,
       COUNT(li.id) AS item_count, SUM(li.price_cents) AS total_cents,
       o.status, o.placed_at
FROM orders o
JOIN users u ON u.id = o.user_id
JOIN line_items li ON li.order_id = o.id
GROUP BY o.id, u.email, o.status, o.placed_at;

CREATE UNIQUE INDEX order_summary_pk ON order_summary (order_id);
```

```python
from typing import Final
from sqlalchemy import text
from sqlalchemy.orm import Session


class OrderSummaryRefresher:
    REFRESH_SQL: Final = text("REFRESH MATERIALIZED VIEW CONCURRENTLY order_summary")

    def __init__(self, session: Session) -> None:
        self._session: Final = session

    def refresh(self) -> None:
        # CONCURRENTLY requires a unique index; readers see old data until refresh completes.
        self._session.execute(self.REFRESH_SQL)
        self._session.commit()
```

**Type-safety notes.**

- The app reads the view through a typed DTO (e.g. `OrderListItemView`). The MV
  is the implementation; the DTO is the contract.
- A test verifies the MV column set matches the DTO fields; schema drift is the
  common bug.

**When NOT to use.** Reads already cheap (single index lookup) — MV maintenance
cost not justified. Strong freshness required — MVs always lag (unless
synchronous, which couples write throughput to recomputation).

**Real-world examples.** Postgres `MATERIALIZED VIEW`, Oracle MV, Snowflake
dynamic tables, Materialize, ksqlDB, ClickHouse `MaterializedView` engine. Most
analytics dashboards in production are MV-shaped, fed by CDC or events.

**Anti-pattern variant.** _"Synchronous refresh in the request path."_ MV is a
5-way aggregation; refresh takes 30s; writes time out. Fix: asynchronous
projection or smaller, focused MV.

**References.**

- DDIA, ch. 3, 11.
- Postgres docs:
  <https://www.postgresql.org/docs/current/rules-materializedviews.html>.
- McSherry et al., _Differential Dataflow_ — the basis of Materialize.

---

## Database per Service

**Intent.** Each microservice owns its schema. Coupling moves from shared schema
to explicit API and events.

**When to reach for it.**

- Microservice-shaped system; shared-schema coupling causes cross-team
  incidents.
- Services have independent scaling profiles.

**The shape.** Each service's schema is **internal**. Other services see
HTTP/gRPC APIs and the public event stream. They never JOIN.

**Don't share.** "We just want a quick read across services" — say no. The
precedent dissolves the boundary. Provide the read through an API or a
materialized read store fed by events.

**Migrating from a shared DB.** Strangler Fig; mechanics in `cloud.md`. Data
steps: (1) split tables by service, one schema each; (2) eliminate cross-service
JOINs — API call or materialized denormalization; (3) introduce events for
cross-service reactions; (4) finally move to separate clusters.

**Type-safety notes.** The other service's schema is not in your repo — do not
import its SQLAlchemy models. Define typed clients with DTOs matching the API
contract, not the row.

```python
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PaymentInfoDto:
    payment_id: UUID
    order_id: UUID
    amount_cents: int
    status: str


class PaymentClient(Protocol):
    async def get_for_order(self, order_id: UUID) -> PaymentInfoDto | None: ...
```

**When NOT to use.** A monolith that does not need it — separate schemas without
microservices is operational complexity for no benefit. Teams not ready for
eventual consistency — without a shared DB, there are no shared transactions.

**Real-world examples.** Amazon's "two-pizza team owns its data" (2002 mandate).
Netflix's microservice-per-DB shape.

**Anti-pattern variant.** _"Database per service, except this one shared `users`
table."_ The shared table becomes a cross-team coordination point. Fix: make
`users` either an internal table of one service (with API) or a proper identity
service.

**References.**

- microservices.io/patterns/data/database-per-service.html.
- Sam Newman, _Building Microservices_, 2nd ed., ch. 4.

---

## Sharding

**Intent.** Partition data horizontally across stores. Each shard is sized,
replicated, and operated independently. The shard key determines where a row
lives.

**Four schemes.**

1. **Range-based.** Key ranges (`A–F`, `G–M`). Range scans local; hot shards if
   traffic is skewed by range.
2. **Hash-based.** `hash(key) % N` or consistent hashing. Even distribution;
   range scans fan-out.
3. **Directory-based.** Lookup service maps key → shard. Flexible rebalancing,
   hand-placed hot keys; the directory is a critical component.
4. **Geographic.** By user region. Latency, regulatory; cross-region queries are
   expensive.

**When to reach for it.**

- A single replicated DB cannot serve write throughput / latency / footprint —
  _measured_, not guessed.
- The shard key aligns with access patterns (`tenant_id`, `user_id`,
  `order_id`). Queries without the shard key become scatter-gather.

**Sketch (consistent-hash sharding).**

```python
import hashlib
from bisect import bisect_right
from dataclasses import dataclass
from typing import NewType


ShardId = NewType("ShardId", str)


@dataclass(frozen=True, slots=True)
class HashRing:
    ring: list[tuple[int, ShardId]]      # sorted by hash position

    @classmethod
    def build(cls, shards: list[ShardId], *, vnodes_per_shard: int = 128) -> "HashRing":
        ring = sorted(
            (cls._hash(f"{s}:{i}"), s) for s in shards for i in range(vnodes_per_shard)
        )
        return cls(ring=ring)

    @staticmethod
    def _hash(s: str) -> int:
        return int.from_bytes(hashlib.blake2b(s.encode(), digest_size=8).digest(), "big")

    def shard_for(self, key: str) -> ShardId:
        if not self.ring:
            raise RuntimeError("empty ring")
        positions = [p for p, _ in self.ring]
        return self.ring[bisect_right(positions, self._hash(key)) % len(self.ring)][1]
```

**Type-safety notes.**

- `ShardId = NewType("ShardId", str)`. Conflating `database_url` and `shard_id`
  produces silent misplacement bugs.
- Shard key types should also be `NewType` — `TenantId`, not `str` — so you
  cannot shard by `email` by mistake.

**Hot-shard problem.** One tenant produces 80% of traffic; one shard saturates
while others idle. Mitigations: per-tenant placement (directory-based);
sub-sharding hot tenants by `(tenant_id, modulo)`; read replicas for read-heavy
hot keys.

**Resharding pain.** Hash+modulo: adding a shard moves _most_ keys. Consistent
hashing: moves `1/N` of keys, but every moved key produces dual-write windows,
lag, verification. Lesson: size shard count for two-year growth from day one, or
use a system with built-in resharding (DynamoDB, MongoDB, CockroachDB, Spanner).

**When NOT to use.** You have not measured. A single primary + read replicas
suffices for almost every workload below ~10k writes/sec.

**Real-world examples.** MongoDB sharded clusters, DynamoDB partitions,
Cassandra/ScyllaDB token rings, Vitess for MySQL (YouTube, Slack), Citus for
Postgres, Pinterest's MySQL sharding, Discord's Cassandra.

**Anti-pattern variant.** _"Sharding before measuring."_ Day-one sharding "for
future growth"; ops is 10x harder; the workload would have fit on one Postgres
for three years.

**References.**

- DDIA, ch. 6 ("Partitioning").
- Pinterest, "Sharding Pinterest"; Discord, "How Discord Stores Trillions of
  Messages".

---

## Replication

**Intent.** Multiple copies across nodes/regions for **durability**,
**availability**, **read scale**, **locality**.

**Three families.**

1. **Single-leader.** All writes to leader; replicas propagate. Default for
   relational DBs.
2. **Multi-leader.** Writes at multiple leaders; conflicts resolved by LWW,
   custom merge, or CRDT.
3. **Leaderless** (Dynamo). All replicas accept writes; clients use quorum
   reads/writes.

**Sync vs async vs semi-sync.**

- **Async** — leader acks client, replication in background. Lowest latency;
  risk of data loss on leader failure.
- **Sync** — leader waits for all replicas. Most durable; one slow replica
  blocks all writes.
- **Semi-sync** — wait for at least one replica or a quorum. Postgres
  `synchronous_commit`, MySQL semi-sync. Pragmatic default.

**Replication lag.** Replicas lag the leader; reads are stale. Symptoms: user
creates a record, next page hits a stale replica, sees "not found".

Mitigations: **Read-your-writes** (pin reads to leader after writes, or tag with
seq number and wait for replica catchup); **Monotonic reads** (pin session to
one replica, not a bouncing LB); **Causal** (vector clocks or explicit
wait-for-offset).

**Sketch (read-your-writes, application-level).**

```python
from dataclasses import dataclass
from typing import Final, NewType, Protocol


WriteToken = NewType("WriteToken", int)


@dataclass(frozen=True, slots=True)
class WriteResult:
    write_token: WriteToken


class PrimaryDb(Protocol):
    async def write(self, key: str, value: bytes) -> WriteResult: ...
    async def read(self, key: str) -> bytes | None: ...


class ReplicaDb(Protocol):
    async def replication_position(self) -> WriteToken: ...
    async def read(self, key: str) -> bytes | None: ...


class ReadYourWritesStore:
    def __init__(self, primary: PrimaryDb, replicas: list[ReplicaDb]) -> None:
        self._primary: Final = primary
        self._replicas: Final = replicas

    async def write(self, key: str, value: bytes) -> WriteToken:
        return (await self._primary.write(key, value)).write_token

    async def read(self, key: str, *, after: WriteToken | None) -> bytes | None:
        if after is None:
            return await self._replicas[0].read(key)
        for r in self._replicas:
            if await r.replication_position() >= after:
                return await r.read(key)
        return await self._primary.read(key)
```

**Type-safety notes.**

- `WriteToken` is a `NewType` — mixing replication tokens with `int` is a type
  error.
- Callers must pass `after=`; `after=None` is a knowing acceptance of stale
  reads, not a default.

**Multi-leader gotchas.** Cross-region active-active seems attractive but the
hidden cost is conflict resolution. Without CRDTs or careful per-row LWW, you
end up with custom handlers nobody remembers. Most "active-active" in production
is either CRDT-backed (Riak, Redis CRDB) or partitioned-by-region.

**When NOT to use.** Replication is the default; the question is which family.
The mistake is multi-leader without a conflict-resolution strategy.

**Real-world examples.** Postgres streaming replication; MySQL semi-sync;
Cassandra (leaderless); CockroachDB (Raft, looks single-leader); MongoDB replica
sets; DynamoDB global tables (LWW); Redis Cluster (single-leader per shard).

**Anti-pattern variant.** _"Read from any replica, no lag consideration."_ Users
see their own writes vanishing for 200ms. Engineers debug "missing record"
quarterly and never find it — by the time they look, the replica has caught up.

**References.**

- DDIA, ch. 5.
- Postgres replication docs. Marc Brooker, "On reading from replicas",
  brooker.co.za.

---

## Eventual Consistency

**Intent.** With no further writes, replicas converge. No upper bound on
"eventually". Eventual is a _bounded_ guarantee under write quiescence —
unbounded in practice, because writes never quiesce.

**Stronger sub-models** (in order of strength): **Read-your-writes** (client
sees own writes); **Monotonic reads** (successive reads do not move backward);
**Monotonic writes** (writes applied in submission order); **Causal** (related
ops in order; concurrent may not be); **Bounded staleness** (replicas at most
_T_ seconds behind — Cosmos DB, Spanner).

Progression: _strong_ > _causal_ > _RYW / monotonic_ > _eventual_. Most apps
need at least RYW for the user's own data.

**When eventual is fine.** Cross-tenant aggregations, search indexes, activity
feeds, dashboards, recommendations.

**When eventual is not fine.** User's view of their own actions; financial;
inventory gating purchases; authorization checks.

**Type-safety notes.** Encode the consistency level a read requires; a
`read(key)` that silently returns stale data is a defect waiting to happen.

```python
from enum import StrEnum


class ConsistencyLevel(StrEnum):
    EVENTUAL = "eventual"
    READ_YOUR_WRITES = "read_your_writes"
    BOUNDED_STALENESS = "bounded_staleness"
    STRONG = "strong"
```

**Real-world examples.** S3 (strong RAW since 2020); DynamoDB (default eventual,
opt-in strong); Cassandra (per-query level); DNS (eventually consistent
globally).

**Anti-pattern variant.** _"Eventual everywhere."_ "Eventual" treated as a
cost-saving default; users see their own actions vanish. Fix: identify the RYW
set (user's own data) and serve it from the leader or a session-pinned replica.

**References.**

- Werner Vogels, "Eventually Consistent", CACM 2009.
- DDIA, ch. 5. AWS Builders' Library.

---

## Read Repair and Anti-entropy

**Intent.** Detect and repair divergence in leaderless / async-replicated
systems (Dynamo).

- **Read repair** — quorum read sees inconsistent versions; coordinator writes
  the freshest back inline.
- **Anti-entropy** — periodic Merkle-tree comparison over key ranges; repairs
  what reads miss.

**When to reach for it.**

- Leaderless or quorum-based store (Cassandra, Riak, DynamoDB).
- Cold keys exist (never read, never refreshed by traffic). Without
  anti-entropy, cold-key divergence persists invisibly.

**Sketch (read repair, simplified).**

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VersionedValue[T]:
    value: T
    version: int


async def read_with_repair[T](replicas: list[Replica[T]], key: str, *, r: int) -> VersionedValue[T] | None:
    replies: dict[Replica[T], VersionedValue[T] | None] = {}
    for replica in replicas:
        replies[replica] = await replica.read(key)
        if sum(1 for v in replies.values() if v is not None) >= r: break
    present = [v for v in replies.values() if v is not None]
    if not present: return None
    latest = max(present, key=lambda v: v.version)
    for replica, reply in replies.items():
        if reply is None or reply.version < latest.version:
            await replica.write(key, latest)        # fire-and-forget
    return latest
```

**Anti-entropy.** Pairs of replicas exchange Merkle trees of `(range → hash)`;
mismatches trigger key-by-key repair. Cassandra's `nodetool repair`. Run within
`gc_grace_seconds` to avoid resurrected tombstones.

**When NOT to use.** Single-leader systems — the leader's log is authoritative.

**Real-world examples.** Cassandra (`nodetool repair`), Riak (active
anti-entropy trees), Dynamo paper.

**Anti-pattern variant.** _"No anti-entropy ever."_ Relying entirely on read
repair; cold keys diverge silently; DR restores expose it years later.

**References.**

- DeCandia et al., "Dynamo", SOSP 2007. DDIA, ch. 5.

---

## Change Data Capture (CDC)

**Intent.** Treat the database as the event source. A connector reads the
transaction log (Postgres WAL, MySQL binlog, MongoDB oplog) and emits change
events to a broker.

**When to reach for it.**

- Downstream systems must observe row-level changes without modifying the
  application.
- Migrating from shared schema toward DB-per-service.
- Feeding an analytics warehouse, search index, or cache from the source DB.

**Sketch.** No application code — connector config.

```yaml
# Debezium Postgres connector
config:
    connector.class: io.debezium.connector.postgresql.PostgresConnector
    database.dbname: orders
    table.include.list: public.orders,public.line_items
    plugin.name: pgoutput
    topic.prefix: db.orders
    transforms: outbox
    transforms.outbox.type: io.debezium.transforms.outbox.EventRouter
```

Consumer sees Kafka topics like `db.orders.public.orders`:
`{"op": "u", "before": {...}, "after": {...}, "ts_ms": ...}`.

**Outbox vs CDC trade-off.**

- **Outbox** — app authors domain events. Payload is what consumers want. Tight
  coupling to app; clean event schema.
- **CDC** — connector emits row diffs. Payload is storage schema. No app change;
  consumers see ORM internals.

**Hybrid:** CDC over an outbox table. Outbox semantics with CDC delivery.
Debezium's outbox event router does this.

**Type-safety notes.** CDC payload is storage schema — strongly type the
consumer projection so a producer-side rename is a CI type error.

**When NOT to use.** Only consumer is the writing service; DB does not expose a
stable replication log; you need exact domain events without the hybrid setup.

**Real-world examples.** Debezium (Postgres, MySQL, MongoDB, Cassandra, SQL
Server), Maxwell, AWS DMS, Kafka Connect JDBC source.

**Anti-pattern variant.** _"Polling for changes."_
`WHERE updated_at > last_seen` every 30s — misses sub-resolution changes, does
not capture deletes. Fix: CDC, every time.

**References.**

- DDIA, ch. 11. Debezium docs.
- Martin Kleppmann, "Turning the database inside-out with Apache Samza", 2015.

---

## Tombstones and Soft Delete

**Intent.** Mark a record deleted without physical removal. In append-only /
replicated stores, physical delete is hard to propagate consistently; a
tombstone flows through the same write path as any update.

**Two contexts.**

1. **Application-level soft delete** — `deleted_at: datetime | None`; queries
   filter `WHERE deleted_at IS NULL`. Trivial to implement; trivial to forget
   the filter.
2. **Storage-level tombstones** — Cassandra, Bigtable, DynamoDB write tombstone
   markers; purged after `gc_grace_period`.

**When to reach for it.**

- You need "undelete".
- The store is replicated and hard delete cannot be applied consistently.
- Compliance requires retention.

**Sketch (application-level soft delete).**

```python
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.orm import Mapped, mapped_column


class UserRow(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(primary_key=True)
    email: Mapped[str]
    deleted_at: Mapped[datetime | None] = mapped_column(default=None, nullable=True)


def find_active_user(session: Session, user_id: str) -> UserRow | None:
    stmt = select(UserRow).where(UserRow.id == user_id, UserRow.deleted_at.is_(None))
    return session.execute(stmt).scalar_one_or_none()


def soft_delete(session: Session, user_id: str) -> None:
    session.execute(
        update(UserRow)
        .where(UserRow.id == user_id, UserRow.deleted_at.is_(None))
        .values(deleted_at=datetime.now(UTC))
    )
```

**Type-safety notes.**

- Encode "include deleted?" at the query layer, never as a global setting.
- For Cassandra-style tombstones, application code never sees the tombstone —
  only `None`. Ensure serialization treats "tombstone" and "missing key"
  identically.

**Tombstone retention.** Tombstones cost storage and read amplification.
Cassandra's `gc_grace_seconds` (default 10 days) bounds retention; run
anti-entropy within that window to avoid "zombie" rows.

**Right to be forgotten** (GDPR, CCPA). Soft delete is _not_ sufficient — build
a retention pipeline that hard-deletes after the compliance window.

**When NOT to use.** Hot tables with no audit/restoration need; pure caches can
be hard-deleted.

**Real-world examples.** Most CRUD apps use `deleted_at`. Cassandra/DynamoDB
tombstones are internal. Kafka log compaction uses tombstones (key K, null
value).

**Anti-pattern variant.** _"Soft delete, no retention."_ Five years in, 80% of
rows are tombstones; queries slow. Soft delete is a delay, not a cancellation.

**References.**

- DDIA, ch. 3, 5.
- Cassandra docs on tombstones and `gc_grace_seconds`.

---

## Saga's data consequences

**Intent.** Saga is a coordination pattern (see `distributed.md`). Its
**data-architecture consequences** belong here: what happens to data shape when
atomicity stops at the service boundary?

**The shape.** A multi-service operation cannot be atomic. There is no instant
where "order placed + payment captured + inventory reserved" is true; there are
intermediate states where some hold and some are pending or compensated. Your
data must _represent_ those intermediate states.

**Implications.**

1. **Status fields are mandatory** — `DRAFT`, `PENDING`, `CONFIRMED`,
   `COMPENSATING`, `CANCELLED`. "Exists but saga running" is a real state.
2. **Read consistency is best-effort** — reads between steps see partial
   reality.
3. **Compensation events are first-class** — `OrderCancelled`,
   `PaymentRefunded`, `StockReleased` have their own consumers and retry
   semantics.
4. **Idempotency keys percolate** — every external side effect needs a key
   derived from saga identity.
5. **The materialized view absorbs it** — every saga step projects into the
   view; eventually- consistent CQRS becomes non-optional.

**Type-safety notes.** Encode intermediate states in the types. A boolean
`placed` collapses too many states.

```python
from enum import StrEnum

class OrderSagaState(StrEnum):
    DRAFT = "draft"
    PAYMENT_PENDING = "payment_pending"
    PAYMENT_CONFIRMED = "payment_confirmed"
    INVENTORY_RESERVED = "inventory_reserved"
    SHIPPING_SCHEDULED = "shipping_scheduled"
    CANCELLED = "cancelled"
    COMPENSATING = "compensating"
    REFUNDED = "refunded"
```

**When NOT.** Single-service workflows. One transaction; status fields optional.

**Real-world examples.** Every checkout flow at scale (Amazon, Shopify, Uber
Eats): order has a saga state machine, read side denormalizes it, events log
every transition.

**Anti-pattern variant.** _"Saga without intermediate states."_ DB has only
"placed" / "not placed"; customer support cannot answer "where is order 12345
stuck" because the answer is in the orchestrator's private state. Fix: project
saga state into the order's read model.

**References.**

- See _Saga_ sections in `distributed.md`.
- Pat Helland, "Life beyond Distributed Transactions", ACM Queue 2007.
- Vernon, _Implementing DDD_, ch. 8.

---

## When to reach for what

Stop at the first honest "yes".

1. **One service, one DB, modest reads?** → ORM + moirae _Enterprise Patterns_.
   Nothing here yet.
2. **Reads dominate; shapes diverged?** → **Lightweight CQRS** first;
   eventually-consistent CQRS only if the read store cannot live alongside the
   write store.
3. **Publish a fact atomically with a state change?** → **Outbox** + **Inbox**.
4. **Expensive aggregation recomputed per request?** → **Materialized View**
   with the right refresh strategy.
5. **Team deploys blocked by another team's migrations?** → **Database per
   Service** + events + explicit API.
6. **A single-replica DB cannot serve load?** → **Replication first** (read
   replicas, semi-sync); shard only when replication is fully used.
7. **Cross-region active-active needed?** → **CRDT multi-leader** for tolerant
   data; **partitioned single-leader** otherwise.
8. **Feed warehouse / search / other service from source DB without app
   change?** → **CDC**, or the **outbox + CDC hybrid** for clean domain events.
9. **Domain is a sequence of events; "why is state what it is" matters?** →
   **Event Sourcing** + full CQRS.
10. **Delete with undelete / audit / compliance?** → **Soft delete /
    tombstones** + retention pipeline.
11. **Saga produces user-visible intermediate states?** → Project saga state
    into the read model; model compensation events explicitly.

---

## Review Checklist

1. CQRS adopted only where read/write shapes have actually diverged.
2. Event sourcing: events immutable, additive change only,
   `schema_version: Literal[N]`.
3. Every cross-process state-change publication goes through an **outbox**;
   consumers are **inbox-protected** or naturally idempotent.
4. Every materialized view has an explicit, monitored refresh strategy.
5. Database-per-service enforced by _not importing_ other services' models; no
   shared `users` table.
6. Sharding is measured, not premature; queries are scoped by the shard key.
7. Replication mode is async/semi-sync/sync — visible in types on RYW paths.
8. Every read endpoint has an explicit consistency level.
9. Anti-entropy scheduled within `gc_grace_seconds` on leaderless stores.
10. CDC consumers typed against the storage schema; CI breaks on upstream column
    rename.
11. Soft-deleted rows have a retention policy that hard-deletes after compliance
    window.
12. Saga intermediate state visible in the read model, not hidden in the
    orchestrator.
