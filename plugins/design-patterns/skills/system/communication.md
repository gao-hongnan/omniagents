# Inter-Service Communication Patterns

> How services talk: synchronous request/reply, asynchronous pub/sub, event
> streams, gateways, sidecars, webhooks, streaming sockets, and the small set of
> patterns that handle large payloads, long-running work, and heterogeneous
> client tailoring. The companion file ([reliability.md](./reliability.md))
> covers what to do when those calls fail; this file covers the call shapes
> themselves.

## How to use this file

Each entry follows the same shape: _intent → when to reach for it → strict-typed
sketch → type-safety notes → when not to use → real-world examples →
anti-pattern variant → references._ The sketches are Python 3.13+ using `httpx`,
`fastapi`, `aiokafka`, `faststream`, `pydantic`, and PEP 695 generics. Every
block is written to target `mypy --strict` and `pyright --strict` with no `Any`
and the annotation-evaluation policy in `SKILL.md` conventions. The
`python:typings` sister skill has the full canonical reference if it is also
loaded.

Conventions used in every sketch:

- `Protocol` over `ABC` for boundaries.
- PEP 695 generics — `class Foo[T]:`, never `Generic[T]`.
- PEP 604 unions — `int | None`, never `Optional[int]`; `list[int]`, never
  `List[int]`.
- `Self`, `Final`, `@override`, no `Any`, and the annotation-evaluation policy
  in `SKILL.md` conventions.

Communication patterns rarely live alone — they compose with the resilience
patterns in [reliability.md](./reliability.md). Cross-references appear inline.

---

## Picking a shape

Before reaching for a pattern, decide along three axes:

| Axis            | Choices                                        | Question to answer                                                 |
| --------------- | ---------------------------------------------- | ------------------------------------------------------------------ |
| **Coupling**    | sync / async                                   | "Does the caller need the result _now_ to make its next decision?" |
| **Cardinality** | 1:1 / 1:N                                      | "Is there exactly one consumer of this message, or many?"          |
| **Durability**  | best-effort / at-least-once / effectively-once | "If this message is lost, what breaks?"                            |

The pairs that fall out:

- **sync, 1:1, best-effort** → request/reply over HTTP/gRPC.
  ([request-reply-sync](#request-reply-sync))
- **async, 1:N, at-least-once** → pub/sub topic.
  ([pub-sub-async](#pub-sub-async))
- **async, 1:1, at-least-once** → message queue / job queue.
- **sync, 1:1, long-running** → asynchronous request-reply with polling or
  callback. ([asynchronous-request-reply](#asynchronous-request-reply))
- **outbound notification, 1:1, at-least-once** → webhook.
  ([webhooks](#webhooks))
- **server → client streaming, browser** → SSE.
  ([long-polling-sse-websockets](#long-polling-sse-websockets))
- **bidirectional streaming** → WebSockets / gRPC streaming.

The rest of the file walks the patterns in roughly that order, then layers on
the cross-cutting machinery (gateway, BFF, mesh) and the patterns that handle
special-case payloads (claim check) or one-off legacy migrations (strangler
fig).

---

## Request/Reply (sync)

**Intent.** The default. Caller sends a request, blocks on the response,
proceeds with the result. The two parties are tightly coupled in _time_ (both
must be available simultaneously) but loosely coupled in _space_ (no shared
address space). Most service-to-service traffic looks like this.

**When to reach for it.**

- The caller's next step depends on the result (a query, a validation, a
  resource creation that returns an ID).
- Both ends are operationally co-located enough that mutual availability is a
  reasonable assumption.
- Latency requirements are bounded by a single network round-trip, not a
  human-paced workflow.

**The three big choices: REST, gRPC, GraphQL.**

| Property       | REST + JSON                | gRPC                     | GraphQL                                        |
| -------------- | -------------------------- | ------------------------ | ---------------------------------------------- |
| Schema         | Optional (OpenAPI)         | Mandatory (protobuf)     | Mandatory (SDL)                                |
| Wire format    | JSON / text                | Binary protobuf          | JSON                                           |
| Streaming      | Limited (SSE/chunked)      | Full bidi                | Subscriptions                                  |
| Browser-native | Yes                        | gRPC-Web only            | Yes                                            |
| Typing         | OpenAPI codegen            | protoc codegen           | codegen via tools                              |
| Best at        | Public APIs, CRUD, caching | Internal east-west, perf | Aggregating heterogeneous backends for clients |

**Sketch — REST with FastAPI + httpx.** Strict-typed Python 3.13+:

```python
import httpx
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Final, NewType, Self

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel


UserId = NewType("UserId", str)


class UserDTO(BaseModel):
    user_id: UserId
    display_name: str
    email: str


# Server side.
app: Final = FastAPI()

_USERS: dict[UserId, UserDTO] = {}


@app.get("/users/{user_id}", response_model=UserDTO)
async def get_user(user_id: UserId) -> UserDTO:
    if (user := _USERS.get(user_id)) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user not found")
    return user


# Client side.
@dataclass(frozen=True, slots=True)
class UserClient:
    base_url: str
    timeout: httpx.Timeout = httpx.Timeout(connect=2.0, read=5.0, write=5.0, pool=2.0)

    @asynccontextmanager
    async def _client(self) -> AsyncIterator[httpx.AsyncClient]:
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
        ) as client:
            yield client

    async def get_user(self, user_id: UserId) -> UserDTO:
        async with self._client() as client:
            response = await client.get(f"/users/{user_id}")
            response.raise_for_status()
            return UserDTO.model_validate_json(response.content)
```

**Sketch — gRPC.** Generated stubs are typed; you compose them with the same
resilience controls:

```python
import grpc
from collections.abc import Awaitable
from typing import Final

# Generated stubs (assume protoc-generated):
from gen import users_pb2, users_pb2_grpc


@dataclass(frozen=True, slots=True)
class UserGrpcClient:
    target: str
    deadline_s: float = 5.0

    async def get_user(self, user_id: str) -> users_pb2.User:
        async with grpc.aio.insecure_channel(self.target) as channel:
            stub = users_pb2_grpc.UsersStub(channel)
            return await stub.GetUser(
                users_pb2.GetUserRequest(user_id=user_id),
                timeout=self.deadline_s,
            )
```

gRPC's deadlines propagate across hops via the `grpc-timeout` metadata header —
every downstream call inherits the remaining time, so you cannot accidentally
exceed your caller's budget.

**Type-safety story.**

- **REST.** OpenAPI schemas + `pydantic` on the server, codegen
  (`openapi-python-client`, `datamodel-code-generator`) on the client. Quality
  varies; verify the generator's output passes `mypy --strict`. The weakness is
  that JSON is structurally typed at runtime — a missing field becomes a
  `ValidationError` at call time, not a compile error.
- **gRPC.** protobuf + `protoc` codegen produces strongly-typed stubs and
  message classes. Stronger guarantees end-to-end (the wire format is the
  schema), at the cost of binary bodies and harder browser interop.
- **GraphQL.** SDL + codegen (Strawberry, Ariadne, hot-chocolate). Compile-time
  guarantees that selected fields exist and have the expected shape. Opaque to
  HTTP-layer caching.

**Type-safety notes.** `NewType` for IDs prevents
"oh-I-passed-a-product-id-where-a-user-id-was-expected" bugs. `pydantic`
enforces shape at the boundary. `Final` on the FastAPI app prevents accidental
rebinding.

**When NOT to use.**

- Long-running operations (anything > a few seconds at p99). Use asynchronous
  request-reply ([asynchronous-request-reply](#asynchronous-request-reply)) so
  the caller doesn't hold the connection open through GC pauses, network blips,
  and load balancer idle timeouts.
- Fan-out: 1:N delivery via request/reply means N round-trips and N tightly
  coupled availabilities. Use pub/sub.
- Notifications where the receiver doesn't need to acknowledge before the sender
  proceeds. Use a fire-and-forget pattern (queue, webhook).

**Real-world examples.**

- **Stripe API** is a model REST surface: versioned URLs, idempotency headers,
  rate-limit headers, deep OpenAPI spec.
- **Google's internal infrastructure** runs on gRPC; the public Google Cloud
  APIs ship in both REST and gRPC flavours.
- **GitHub** ships both REST and GraphQL APIs side-by-side; GraphQL for the
  aggregate-heavy use cases (one query for issue + assignees + labels +
  milestones), REST for everything else.

**Anti-pattern variant.**

- **Synchronous chains across many services.** Service A → B → C → D, each
  blocking. Latency adds; failure of any one fails all; the coupling forms a
  distributed monolith. Break with async events at the seams that don't need a
  result _now_.
- **REST that pretends to be RPC.** `POST /users/getUser` with a `{"id": ...}`
  body. Throws away HTTP caching, idempotency semantics, and status-code
  routing. If it walks like RPC, _use_ RPC (gRPC).
- **GraphQL exposed publicly without query-cost limits.** A single query can fan
  out to thousands of resolvers. Always cap depth, complexity, and concurrency
  at the gateway.

**References.**

- Roy Fielding. _Architectural Styles and the Design of Network-based Software
  Architectures._ Doctoral dissertation, UC Irvine, 2000.
- _gRPC Documentation_, grpc.io.
- _GraphQL Specification_, graphql.org.
- Sam Newman. _Building Microservices._ 2nd ed., Chapter 5.

---

## Pub/Sub (async)

**Intent.** A producer publishes messages to a _topic_ (or _exchange_ /
_stream_); zero or more consumers subscribe and receive copies. Producer and
consumers are decoupled in time (consumers can be down when a message is sent)
and space (they don't need to know each other's addresses). Cardinality is
naturally 1:N.

**When to reach for it.**

- Multiple consumers care about the same event (analytics, search index, audit
  log all want every order).
- Consumers operate on different SLAs (one near-real-time, one batch).
- The producer should not be coupled to the _list_ of consumers — adding a new
  consumer is a config change, not a code change.

**Sketch — aiokafka producer + consumer.** Strict-typed Python 3.13+:

```python
import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Final, NewType

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from pydantic import BaseModel


OrderId = NewType("OrderId", str)
TOPIC: Final = "orders.created.v1"


class OrderCreated(BaseModel):
    event_id: str
    occurred_at: datetime
    order_id: OrderId
    customer_id: str
    total_cents: int


@dataclass(slots=True)
class OrderProducer:
    bootstrap_servers: str
    _producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            acks="all",            # wait for full ISR ack — at-least-once
            enable_idempotence=True,  # producer-side dedup of in-flight retries
        )
        await self._producer.start()

    async def stop(self) -> None:
        if self._producer is not None:
            await self._producer.stop()

    async def publish(self, event: OrderCreated) -> None:
        if self._producer is None:
            raise RuntimeError("producer not started")
        await self._producer.send_and_wait(
            TOPIC,
            value=event.model_dump_json().encode(),
            key=event.order_id.encode(),  # partition by order_id ⇒ ordering per order
        )


@asynccontextmanager
async def consume(
    bootstrap_servers: str, group_id: str
) -> AsyncIterator[AsyncIterator[OrderCreated]]:
    consumer = AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        enable_auto_commit=False,  # commit only after successful processing
        auto_offset_reset="earliest",
    )
    await consumer.start()
    try:
        async def stream() -> AsyncIterator[OrderCreated]:
            async for msg in consumer:
                event = OrderCreated.model_validate_json(msg.value)
                yield event
                await consumer.commit()  # at-least-once: commit after handler returns
        yield stream()
    finally:
        await consumer.stop()
```

**Sketch — FastStream over Kafka.** Same pattern, less boilerplate, with
schema-driven AsyncAPI generation:

```python
from faststream import FastStream
from faststream.kafka import KafkaBroker
from typing import Final


broker: Final = KafkaBroker("localhost:9092")
app: Final = FastStream(broker)


@broker.subscriber("orders.created.v1", group_id="search-indexer")
async def index_order(event: OrderCreated) -> None:
    # Pydantic validation happens automatically at the boundary.
    await _upsert_to_search(event)


@broker.publisher("orders.created.v1")
async def emit_order_created() -> OrderCreated:
    ...
```

**Delivery semantics.**

| Guarantee            | What it means                                                         | When it's true                                                                                                                    |
| -------------------- | --------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| **At-most-once**     | Each message delivered 0 or 1 times. Possible loss; no duplicates.    | Producer fire-and-forget; consumer commits offset _before_ processing.                                                            |
| **At-least-once**    | Each message delivered 1 or more times. No loss; possible duplicates. | Producer waits for ack; consumer commits offset _after_ processing. The default for most queues.                                  |
| **Effectively-once** | Each message has _one observable effect_, even with duplicates.       | At-least-once + idempotent consumer. Not the same as the broker delivering "exactly once" — the dedup happens at the application. |

"Exactly-once delivery" is a marketing term. Brokers can offer exactly-once
_processing semantics_ within a single broker (Kafka EOS via transactions) or
_exactly-once produce_ (idempotent producers). End-to-end exactly-once across
producer, broker, and consumer requires the consumer to be idempotent — which is
the [idempotency-keys](./reliability.md#idempotency-keys) pattern from the
companion file.

**Comparison of common brokers.**

| Broker                    | Best for                                                                           | Delivery                                                                | Streaming/Replay                                      | Operational complexity                  |
| ------------------------- | ---------------------------------------------------------------------------------- | ----------------------------------------------------------------------- | ----------------------------------------------------- | --------------------------------------- |
| **Kafka**                 | Event streams, high throughput, replay, time-windowed processing                   | At-least-once + idempotent producer + EOS transactions                  | First-class — log retention, consumer groups, offsets | High (managed: Confluent Cloud, MSK)    |
| **RabbitMQ**              | Work queues, complex routing (topic/header/fanout exchanges), short-lived messages | At-least-once with publisher confirms + manual ack                      | No — messages deleted after ack                       | Moderate (managed: CloudAMQP, AmazonMQ) |
| **Redis Streams**         | Lightweight messaging within a microservice cluster, low-latency                   | At-least-once with `XACK`, consumer groups via `XREADGROUP`             | Limited — capped streams, no long-term replay         | Low (already running Redis)             |
| **GCP Pub/Sub**           | Managed pub/sub at GCP scale, global topic, push or pull                           | At-least-once; ordered delivery with ordering keys                      | 7-day replay buffer                                   | Very low (fully managed)                |
| **AWS SNS / SQS**         | Fan-out (SNS) → buffered work queues (SQS)                                         | At-least-once for SQS standard; FIFO has effectively-once via dedup IDs | No replay; explicit DLQ                               | Very low (fully managed)                |
| **NATS / NATS JetStream** | Ultra-low latency, edge-friendly, "Cloud Native Messaging"                         | Core: at-most-once; JetStream: at-least-once with persistence           | JetStream supports replay                             | Low–moderate                            |

**SNS-SQS fanout.** The canonical AWS pattern: a single SNS topic fans out to N
SQS queues, one per consumer. Each consumer drains its own queue at its own
pace; one slow consumer doesn't slow others. Combine with SQS DLQs for
poison-message handling.

**Type-safety notes.** Pydantic at the deserialisation boundary catches schema
drift at message arrival rather than deep in the handler. Schema versioning
(`orders.created.v1`) in the topic name is a low-tech but very effective
contract — bumping to `.v2` doesn't break v1 consumers, both can exist in
parallel during migration.

**When NOT to use.**

- A request that needs a _result_ before proceeding. Use request/reply.
- A 1:1 RPC dressed up as a topic. The indirection is overhead with no benefit.
- A workload that genuinely cannot tolerate duplicates and where the handler
  cannot be made idempotent. The broker won't save you here.

**Real-world examples.**

- **LinkedIn** open-sourced Kafka explicitly to handle the firehose of activity
  events — pub/sub at the scale of all member activity.
- **Shopify** uses Kafka extensively for order lifecycle events —
  `order.placed`, `order.fulfilled`, `order.refunded` — with each consumer
  (search, analytics, accounting) owning its own offset.
- **Slack** uses RabbitMQ for work-queue distribution to message-fan-out
  workers.
- **GCP Pub/Sub** is the backbone of internal Google event flows; it powers
  Cloud Storage notifications, BigQuery streaming inserts, and Cloud Functions
  triggers.

**Anti-pattern variant.**

- **At-least-once + non-idempotent consumer.** Duplicates are inevitable;
  treating them as "shouldn't happen" guarantees data corruption when they do.
- **Topic-per-consumer.** Defeats the point: you are now coupling the producer
  to the consumer set. Use one topic with multiple consumer groups, or SNS
  fanout.
- **Kafka as a database.** Kafka is durable, but `KSQL` / scanning topics for
  query results is an anti-pattern at scale. If you need read access by key,
  project the topic into a key-value store.
- **No partition key strategy.** Partitioning by random / round-robin destroys
  per-entity ordering. Pick a key (`order_id`, `customer_id`) intentionally.

**References.**

- Jay Kreps. _I Heart Logs._ O'Reilly, 2014. The conceptual basis for Kafka.
- _Apache Kafka Documentation_, kafka.apache.org.
- _RabbitMQ Documentation_, rabbitmq.com.
- _AWS — SNS-SQS Fanout Pattern_, AWS Architecture Center.

---

## Event-Driven Architecture

**Intent.** Structure inter-service communication around _events_ — immutable
facts about things that have happened — rather than commands. A producing
service emits "order.placed" with no opinion about who consumes it; subscribing
services react in their own time, in their own way. The contract is the event
schema.

**When to reach for it.**

- Multiple services need to react to the same domain change without the source
  service knowing about them.
- Audit, analytics, and search index need a "tap" on the operational database
  without coupling to its query patterns.
- The system has natural workflow seams — payments → fulfilment, signup →
  onboarding — where the receiving step doesn't gate the sending step.

**Events vs commands.** Both flow over the same broker; the _shape_ and
_semantics_ differ.

| Property    | Command                           | Event                                         |
| ----------- | --------------------------------- | --------------------------------------------- |
| Tense       | Imperative present (`PlaceOrder`) | Past (`OrderPlaced`)                          |
| Cardinality | 1:1 (intended for one consumer)   | 1:N (any subscribed consumer)                 |
| Receiver    | Specifically targeted             | Unknown / unbounded                           |
| Failure     | Receiver may reject               | Receiver may not reject (the fact happened)   |
| Ownership   | Sender owns the request shape     | Producer owns the schema as a public contract |

A useful test: if you can _not_ execute the command, that's a normal outcome. If
you can _not_ receive the event, that's a bug — the event already happened.

**The "thin event" vs "fat event" debate.**

- **Thin event** (event-notification): contains only the identifier and enough
  metadata to fetch the rest. `{"order_id": "...", "occurred_at": "..."}`.
  Subscribers call back to the producing service for details. _Pros:_ small
  payloads, no schema duplication. _Cons:_ increases load on the producing
  service, couples consumers to the producer's read API, fails replays if entity
  has been deleted.
- **Fat event** (event-carried state transfer): contains the full state of the
  changed entity.
  `{"order_id": "...", "items": [...], "total_cents": ..., "customer_id": ...}`.
  _Pros:_ consumers are self-sufficient, replay works against historical state.
  _Cons:_ larger payloads, schema duplication, version-skew risk.

**Default to fat events.** Subscribers should be able to do their job from the
event alone. Thin events trade producer load for "small" payloads — usually a
bad trade because the producer is the bottleneck and the consumer call rate
equals the event rate, which equals the _total_ event rate for the producer.

**Sketch.** Strict-typed Python 3.13+ — fat events with versioned schema:

```python
from datetime import datetime
from enum import StrEnum
from typing import Final, Literal, NewType

from pydantic import BaseModel, Field
from typing import Annotated


OrderId = NewType("OrderId", str)
CustomerId = NewType("CustomerId", str)


class EventKind(StrEnum):
    ORDER_PLACED = "order.placed.v1"
    ORDER_PAID = "order.paid.v1"
    ORDER_FULFILLED = "order.fulfilled.v1"
    ORDER_REFUNDED = "order.refunded.v1"


class OrderItem(BaseModel):
    sku: str
    quantity: int
    unit_price_cents: int


class OrderPlaced(BaseModel):
    """A customer placed an order. Past tense — the fact, not a request."""

    event_id: str  # UUID; stable across redeliveries
    event_kind: Literal[EventKind.ORDER_PLACED] = EventKind.ORDER_PLACED
    schema_version: Final[int] = 1
    occurred_at: datetime

    order_id: OrderId
    customer_id: CustomerId
    items: list[OrderItem]
    total_cents: Annotated[int, Field(ge=0)]


class OrderPaid(BaseModel):
    event_id: str
    event_kind: Literal[EventKind.ORDER_PAID] = EventKind.ORDER_PAID
    schema_version: Final[int] = 1
    occurred_at: datetime
    order_id: OrderId
    payment_method: str
    amount_cents: Annotated[int, Field(ge=0)]
```

**Schema evolution.** Events are public contracts; treat them like APIs.

- **Add fields with defaults.** Backwards-compatible.
- **Never change the meaning of an existing field.** Add a new field; deprecate
  the old.
- **Bump the version when the contract breaks.** `order.placed.v2` ships
  alongside `order.placed.v1`; the producer dual-publishes during a transition
  window; consumers migrate; the v1 topic is retired.

**The transactional outbox.** A near-universal companion pattern: when a service
updates a database row _and_ must publish an event about that update, do both
atomically. The naïve "commit, then publish" loses events on a crash between the
two steps.

```sql
-- Step 1: write business state and outbox in one transaction.
BEGIN;
INSERT INTO orders (id, customer_id, ...) VALUES (...);
INSERT INTO outbox (event_id, kind, payload, created_at)
  VALUES ('uuid-...', 'order.placed.v1', '{"order_id": ...}', NOW());
COMMIT;

-- Step 2: a separate process polls the outbox and publishes to the broker,
-- marking each row 'published' on success.
```

This converts the "two writes, one transaction" problem into "two reads, no
transactional coupling," with at-least-once delivery and no events lost on
crash. (See
[microservices.io — Transactional Outbox](https://microservices.io/patterns/data/transactional-outbox.html).)

**Type-safety notes.** Pinning `event_kind` to a `Literal[...]` lets a
discriminated-union consumer dispatch with full type narrowing — the body of the
`match` for `OrderPlaced` knows it has `items` and `total_cents`, not just "some
event." `Field(ge=0)` enforces invariants at the schema level; consumers never
have to defend against negative totals.

**When NOT to use.**

- A workflow whose steps are _intrinsically synchronous_ — e.g. interactive CRUD
  where the user waits for a result.
- A small monolith with no service boundaries to decouple. Events internally
  just become an in-process pub/sub layer with extra complication.

**Real-world examples.**

- **Shopify** drives most cross-team flows from order events; fulfilment,
  accounting, search, and customer notifications all subscribe to the same
  `orders.*` event family.
- **Confluent's "Stream Lineage"** is a tool for visualising event-driven
  topologies — itself an event-driven product.
- **Stripe's event types** (`charge.succeeded`, `invoice.payment_failed`) are
  the public, versioned event schema that powers webhooks.

**Anti-pattern variant.**

- **Commands disguised as events.** `OrderShouldBeRefunded`. That's not an
  event; that's a command. Either own the action (call the refund service
  synchronously) or model the _fact_ (`RefundRequested` — something the user did
  — distinct from `RefundIssued` — what the refund service did).
- **Event-as-RPC.** Consumer subscribes, processes, _publishes a reply event_
  keyed by correlation ID; original publisher subscribes back waiting on the
  reply. Now you have synchronous request/reply with five times the moving
  parts. If you want a reply, use request/reply.
- **No outbox.** Service updates DB, then publishes; crash in between loses the
  event. Months later, "the order succeeded but search never saw it." Use the
  outbox.
- **Schema-on-demand.** No registry, no versioning, no validation. Producers add
  fields silently; consumers crash on the new field; field-by-field debugging
  follows. Use a schema registry (Confluent, Apicurio).

**References.**

- Martin Fowler. _What do you mean by "Event-Driven"?_, martinfowler.com, 2017.
- Sam Newman. _Building Microservices._ 2nd ed., Chapter 4 ("Microservice
  Communication Styles").
- Chris Richardson. _Microservices Patterns._ Chapters 3–5.
- _microservices.io — Transactional Outbox._
- Adam Bellemare. _Building Event-Driven Microservices._ O'Reilly, 2020.

---

## API Gateway

**Intent.** A single ingress point in front of a fleet of internal services,
owning cross-cutting concerns: TLS termination, authentication, authorisation,
rate limiting, request routing, response transformation, audit logging. Clients
see one URL and one auth scheme; services see a homogeneous internal contract.

**When to reach for it.**

- A microservice architecture exposed publicly. Without a gateway, every service
  implements its own auth, rate limiting, CORS, and request-ID propagation — by
  the time you have ten services, you have ten inconsistent implementations.
- A migration from monolith → microservices. The gateway can route `/users/*` to
  the new service while `/orders/*` still hits the monolith, invisible to
  clients. (See also [strangler-fig](#strangler-fig).)
- A multi-tenant API where per-tenant rate limits, key management, and audit
  logging belong centrally.

**What sits in a typical gateway.**

| Concern                 | Why central                                                | Anti-pattern variant                                      |
| ----------------------- | ---------------------------------------------------------- | --------------------------------------------------------- |
| TLS termination         | Certs in one place; internal mesh can be plaintext or mTLS | Termination per service: 10 services × 10 certs = pain    |
| Auth (token validation) | Validate JWT once; pass identity downstream as header      | Each service re-validates the JWT                         |
| Rate limiting           | Global, per-key, per-tenant                                | Per-service limiters that can't see global rate           |
| Request ID propagation  | One ID origin; every downstream call inherits              | IDs generated separately per service; impossible to trace |
| Response shaping        | Transform `snake_case` → `camelCase` for the public client | Each service knows the public format                      |
| Audit logging           | Single log of who-called-what with bodies                  | Reconstruct from N service logs                           |

**Sketch — minimal gateway in Python.** In production, use Kong / Envoy / AWS
API Gateway / Apigee — but the shape is small enough to demonstrate:

```python
import httpx
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import Response


@dataclass(frozen=True, slots=True)
class Route:
    prefix: str
    upstream_base: str


ROUTES: Final = (
    Route(prefix="/users", upstream_base="http://users-svc:8080"),
    Route(prefix="/orders", upstream_base="http://orders-svc:8080"),
)


app: Final = FastAPI()
http: Final = httpx.AsyncClient(timeout=httpx.Timeout(connect=2.0, read=10.0, write=10.0, pool=2.0))


def _resolve(path: str) -> Route | None:
    for route in ROUTES:
        if path.startswith(route.prefix):
            return route
    return None


async def _validate_token(token: str) -> str:
    """Validate JWT and return the user ID. In real life: call an authz cache."""
    if not token.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer")
    # ... actual JWT verification ...
    return "user-123"


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(full_path: str, request: Request) -> Response:
    route = _resolve("/" + full_path)
    if route is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no route")

    user_id = await _validate_token(request.headers.get("authorization", ""))

    upstream_url = f"{route.upstream_base}/{full_path}"
    body = await request.body()

    upstream_resp = await http.request(
        method=request.method,
        url=upstream_url,
        params=request.query_params,
        headers={
            **{k: v for k, v in request.headers.items()
               if k.lower() not in ("host", "content-length", "authorization")},
            # Pass identity downstream as a trusted header.
            "x-user-id": user_id,
            # Propagate tracing.
            "x-request-id": request.headers.get("x-request-id") or _new_request_id(),
        },
        content=body,
    )

    return Response(
        content=upstream_resp.content,
        status_code=upstream_resp.status_code,
        headers={k: v for k, v in upstream_resp.headers.items() if k.lower() != "content-encoding"},
    )


def _new_request_id() -> str:
    import uuid
    return uuid.uuid4().hex
```

**Off-the-shelf options.**

- **Kong** — Lua-based, plugin ecosystem, deployed widely. Good for on-prem,
  hybrid, multi-cloud.
- **AWS API Gateway** — fully managed REST/HTTP/WebSocket gateway. Tightly
  integrated with Lambda; pay-per-request.
- **Envoy** — Lyft's L7 proxy; the data plane behind Istio and many service
  meshes; can also stand alone as an edge proxy.
- **Traefik** — Kubernetes-native ingress with automatic service discovery.
- **Apigee** (Google) — enterprise-grade with monetisation, developer portal,
  full lifecycle management.

**Type-safety notes.** Gateways are inherently _protocol-translating_ — they sit
between an opaque inbound HTTP request and an outbound call to a typed service.
The proxy sketch above takes raw bytes through; in practice, you'd validate
inbound bodies against a per-route schema before forwarding. Don't try to make
the gateway statically aware of every upstream service's schema; that's coupling
you don't want. Schema validation belongs in the upstream service.

**When NOT to use.**

- A single service. The gateway is overhead with no benefit.
- An internal-only east-west mesh. Use a service mesh
  ([service-mesh](#service-mesh)) for that — the gateway's job is the
  _north-south_ (public ingress) traffic.

**Real-world examples.**

- **Netflix Zuul** (1.0 and 2.0) — the canonical case study; routes billions of
  requests/day to internal services with cross-cutting filters for auth,
  throttling, and routing.
- **Stripe's API gateway** terminates TLS, validates API keys, enforces rate
  limits, and routes to internal Ruby/Go services. Public-facing client never
  touches an internal service directly.
- **AWS** itself runs every public service behind API Gateway / ELB.

**Anti-pattern variant.**

- **Smart pipes, dumb endpoints.** The gateway accumulates _business_ logic —
  multi-step orchestration, payload enrichment, business rule evaluation — and
  becomes a god-service. Now changes to any flow require redeploying the
  gateway; the gateway team becomes a bottleneck for every team. Keep gateways
  _generic_ (cross-cutting only); push business logic to the services.
- **Gateway as the only resilience layer.** Putting all retries and
  circuit-breaking in the gateway means downstream service-to-service calls
  (which the gateway never sees) have none. Use the gateway for ingress
  concerns; use a mesh or in-process libraries for east-west.
- **Inflexible request shape.** "All requests must be REST + JSON." Cuts off
  WebSocket, gRPC, SSE clients. Pick a gateway that supports the protocols you
  need.

**References.**

- Sam Newman. _Building Microservices._ 2nd ed., Chapter 5.
- _Microsoft Azure — API Gateway Pattern._
- _Netflix Tech Blog — Zuul 2 in Production._
- _Envoy Documentation_, envoyproxy.io.

---

## Backend for Frontend (BFF)

**Intent.** Per-client tailored backends that aggregate downstream microservices
into the exact response shape one specific frontend needs. Instead of one
general-purpose API trying to please web, mobile, partner, and TV clients (and
pleasing none of them), each client has its own backend that owns its own
contract. Sam Newman canonised the pattern; it's common in companies with
multiple distinct client surfaces.

**When to reach for it.**

- Multiple distinct clients with diverging needs: a mobile app needs a thin
  response over slow, costly networks; a web app needs richer payloads; a TV app
  needs minimal text and big-image URLs.
- Clients evolve at different velocities. Mobile ships a new version every 6
  weeks; web ships daily; partner integrations change yearly.
- One general-purpose API has accumulated a "show-everything" parameter pattern
  (`?include=foo,bar,baz`) — a sign it's straining to serve too many masters.

**Sketch.** Strict-typed Python 3.13+ — a mobile BFF that aggregates two
downstream services and returns a slim payload:

```python
import asyncio
import httpx
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Final, NewType

from fastapi import FastAPI
from pydantic import BaseModel


UserId = NewType("UserId", str)


# Slim shape tailored for mobile — only the fields the mobile UI renders.
class MobileHomePayload(BaseModel):
    user_display_name: str
    unread_count: int
    recent_orders: list["MobileOrderSummary"]


class MobileOrderSummary(BaseModel):
    order_id: str
    status: str
    item_count: int
    formatted_total: str  # already-localised string; mobile doesn't reformat


@dataclass(frozen=True, slots=True)
class BFFConfig:
    users_url: str
    orders_url: str
    notifications_url: str
    timeout: httpx.Timeout = httpx.Timeout(connect=1.0, read=2.0, write=2.0, pool=1.0)


app: Final = FastAPI(title="Mobile BFF")
config: Final = BFFConfig(
    users_url="http://users-svc:8080",
    orders_url="http://orders-svc:8080",
    notifications_url="http://notifications-svc:8080",
)


@app.get("/mobile/home/{user_id}", response_model=MobileHomePayload)
async def mobile_home(user_id: UserId) -> MobileHomePayload:
    async with httpx.AsyncClient(timeout=config.timeout) as client:
        # Parallel fan-out to three services; one BFF call, three internal calls.
        user_task = client.get(f"{config.users_url}/users/{user_id}")
        orders_task = client.get(f"{config.orders_url}/users/{user_id}/orders?limit=3")
        notif_task = client.get(f"{config.notifications_url}/users/{user_id}/unread")

        user_resp, orders_resp, notif_resp = await asyncio.gather(
            user_task, orders_task, notif_task
        )

    user = user_resp.json()
    orders = orders_resp.json()
    notif = notif_resp.json()

    return MobileHomePayload(
        user_display_name=user["display_name"],
        unread_count=notif["unread"],
        recent_orders=[
            MobileOrderSummary(
                order_id=o["id"],
                status=o["status"],
                item_count=len(o["items"]),
                formatted_total=_format_money(o["total_cents"], o["currency"]),
            )
            for o in orders[:3]
        ],
    )


def _format_money(cents: int, currency: str) -> str:
    return f"${cents / 100:,.2f} {currency}"
```

The web BFF would have its own service, its own slimmer/richer schema, its own
optimisations. Both BFFs call the same underlying microservices.

**Variants.**

- **Per-client-type BFF.** One BFF for mobile, one for web, one for partner.
  Each BFF team owns the per-client contract.
- **Per-client-app BFF.** Distinct BFFs for _each_ client app — the Netflix
  Android app's BFF differs from the iOS app's BFF, which differs from the
  smart-TV app's. Justified at scale where each client has its own engineering
  org.
- **GraphQL as BFF.** A single GraphQL endpoint where each client composes its
  own query. Trades per-client backend code for per-client client code. Works
  well when clients have stable patterns; can fan-out catastrophically without
  query-cost limits.

**Type-safety notes.** Each BFF owns its own response schema
(`MobileHomePayload`) distinct from the underlying service shapes. The
translation in the BFF is where mobile-specific concerns (slim fields,
pre-formatted money strings) belong. The aggregation pattern (`asyncio.gather`)
gives the BFF a single RTT to its upstreams.

**When NOT to use.**

- A single client. You don't have a backends-for-frontends problem if you only
  have one frontend. A regular API suffices.
- Few enough downstream services that a thin gateway aggregation suffices. BFFs
  come into their own when the aggregation logic is non-trivial and per-client.

**Real-world examples.**

- **Netflix** ships dedicated BFFs per device type (the original "experience
  APIs"); the Android BFF differs from the iOS BFF differs from the TV BFF.
- **SoundCloud** standardised BFFs as their solution to mobile/web divergence.
- **Spotify** uses BFFs to pre-compute per-device home pages.
- **The original _backends for frontends_ pattern** comes from the ThoughtWorks
  / Sam Newman work at SoundCloud and others, ~2015.

**Anti-pattern variant.**

- **God-BFF.** One BFF serving every client; ends up with per-client
  conditionals everywhere. You've reinvented the general-purpose API you were
  escaping.
- **BFF that owns business logic.** "Refund processing happens in the mobile
  BFF." Now the web BFF doesn't know how to refund, or duplicates the logic.
  BFFs are _aggregators and adapters_, not domain owners.
- **Per-screen BFFs.** "We have a BFF for the home screen and a BFF for the
  search screen." That's not a BFF, that's screen-coupled service-per-screen.
  Combine into a per-client BFF.

**References.**

- Sam Newman. _Backends for Frontends._
  samnewman.io/patterns/architectural/bff/.
- Phil Calçado. _The Back-end for Front-end Pattern (BFF)._ 2015.
- _Microsoft Azure — Backends for Frontends Pattern._
- _AWS — Backends for Frontends._

---

## Service Mesh

**Intent.** Push the cross-cutting concerns of service-to-service communication
— mTLS, retries, timeouts, circuit breaking, traffic splitting, telemetry — out
of application code and into a _sidecar_ proxy that runs alongside every service
instance. The mesh is the network of those sidecars plus a control plane that
configures them.

**When to reach for it.**

- A microservice deployment with many services, in many languages, where
  duplicating Hystrix-equivalent libraries per language is exhausting.
- An organisation with strong security posture requirements: every
  service-to-service call must be mTLS-encrypted, identity must be a
  cryptographic property, traffic must be authenticated and authorised.
- An ops team that wants L7 traffic shaping (canary, mirror, fault injection)
  without involving every service team.

**The four canonical features.**

| Feature                                   | What it does                                                                                                | Example                                                     |
| ----------------------------------------- | ----------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| **mTLS everywhere**                       | Every connection between services is mutually authenticated and encrypted, transparently to the application | Istio's PeerAuthentication; Linkerd's automatic identity    |
| **Retries / timeouts / circuit-breaking** | Sidecar applies the [reliability patterns](./reliability.md) without app code                               | Envoy's `retry_policy`, `circuit_breakers`                  |
| **Traffic management**                    | Split traffic between versions for canary; mirror to a shadow cluster; inject faults                        | Istio `VirtualService` weights                              |
| **Observability**                         | Per-call metrics, distributed tracing, access logs — all uniform across the mesh                            | Linkerd's `linkerd viz`; Istio + Prometheus + Grafana stack |

**Sketch.** A mesh isn't really sketched in application code; it's _configured_
declaratively. An Istio `VirtualService` for canary:

```yaml
apiVersion: networking.istio.io/v1
kind: VirtualService
metadata:
    name: orders
spec:
    hosts:
        - orders
    http:
        - route:
              - destination:
                    host: orders
                    subset: v1
                weight: 90
              - destination:
                    host: orders
                    subset: v2
                weight: 10
          retries:
              attempts: 3
              perTryTimeout: 2s
              retryOn: 5xx,reset,connect-failure
          timeout: 8s
```

The application code calls `http://orders/users/123` — agnostic of the canary
split, retry policy, or mTLS. The sidecar handles all of it.

**The implementations.**

| Mesh                    | Data plane            | Control plane         | Notes                                             |
| ----------------------- | --------------------- | --------------------- | ------------------------------------------------- |
| **Istio**               | Envoy                 | Istiod                | Most feature-rich, highest operational complexity |
| **Linkerd**             | Linkerd2-proxy (Rust) | Linkerd control plane | Simpler, lighter weight, opinionated              |
| **Consul Connect**      | Envoy                 | Consul                | Integrates with Consul service discovery          |
| **Cilium Service Mesh** | eBPF + Envoy          | Cilium                | Sidecar-less option using eBPF                    |
| **AWS App Mesh**        | Envoy                 | AWS managed           | Tied to AWS networking                            |

**The "what it costs" debate.** Sidecar-per-pod has real overhead:

- **CPU & memory.** A few hundred MB of memory and small but non-zero CPU per
  pod, multiplied by every replica.
- **Latency.** Two extra hops (out through your sidecar, in through theirs) per
  call. Typically sub-millisecond, but real.
- **Operational complexity.** Mesh upgrades affect every service. A
  misconfigured mesh becomes a network outage. The "control plane is down"
  failure mode is harder to debug than "service is down."
- **Sidecar lifecycle coupling.** Pod startup gates on sidecar readiness;
  shutdown ordering matters; init containers and the sidecar race for network
  setup. Most of the early Istio horror stories came from these races.

The sidecar-less alternatives (Cilium, eBPF-based meshes; ambient mode in Istio
1.18+) are partly a response to these costs.

**Type-safety notes.** Mesh config is declarative YAML/JSON, validated against
the mesh's own schema (e.g. Istio's CRDs). The trick is that the _effects_ of
mesh policy aren't visible in the application's type system at all — your code
thinks it's calling `orders`, but the mesh might be splitting traffic to
`orders-v2`, retrying, or rejecting on policy. Mesh behaviour belongs in mesh
tests, not service tests.

**When NOT to use.**

- Small deployments. The operational cost of a mesh dwarfs any benefit if you
  have three services.
- Single-language stacks. If you can put the same library in every service
  (gRPC + a shared resilience library, for example), the mesh buys you less than
  its cost.
- Teams without dedicated platform / infra ownership. A mesh is a full-time
  platform-team project.

**Real-world examples.**

- **Lyft** built Envoy and runs the largest known Envoy deployment; their mesh
  handles every internal call.
- **Stripe's mesh** (called "Veneur" historically; replaced over time) was an
  early mesh-as-platform play.
- **Google internal traffic** runs over Stubby (now mostly gRPC) with
  service-mesh-equivalent infrastructure (BNS, Borg, Mixer predecessors).

**Anti-pattern variant.**

- **App-layer retries duplicated by the mesh.** App retries 3×; mesh retries 3×.
  Now every call is up to 9×. Pick _one_ layer (typically the mesh; remove
  app-layer retries when the mesh is in place).
- **Trust the mesh for auth, ignore in app.** mTLS proves the _peer service_'s
  identity, not the _user_'s. End-user auth still belongs in the app. Layer
  them: mesh handles service identity; app handles user identity.
- **Mesh as the only thing wrapping a database.** Meshes target
  service-to-service HTTP/gRPC; many don't speak Postgres wire protocol. The DB
  connection still needs its own pooling, retries, and timeouts.

**References.**

- Phil Calçado. _Pattern: Service Mesh._ 2017. The canonical introduction.
- William Morgan (Buoyant). _What's a service mesh? And why do I need
  one?_ 2017.
- _Istio Documentation_, istio.io.
- _Linkerd Documentation_, linkerd.io.
- _Envoy Documentation_, envoyproxy.io.

---

## Webhooks

**Intent.** Outbound HTTP callbacks: a service notifies a registered endpoint on
another service when an event occurs. Inverse of polling — the sender pushes
when there's news. The receiver runs an HTTP server; the sender does the
calling. Common for third-party integrations (Stripe → your-backend; GitHub →
CI; Slack → app).

**When to reach for it.**

- The sender is third-party (Stripe, GitHub, Twilio, Shopify, Slack) and
  publishes a webhook contract.
- The receiver is operationally co-located with users (always-on service); the
  sender is event-driven (sporadic notifications).
- An event can wait seconds to be delivered (not microseconds — webhooks ride
  best-effort HTTP).

**Sketch.** Strict-typed Python 3.13+ — receiving + verifying a Stripe-style
HMAC-signed webhook:

```python
import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Final

from fastapi import FastAPI, Header, HTTPException, Request, status


@dataclass(frozen=True, slots=True)
class WebhookConfig:
    secret: bytes
    tolerance_s: int = 300  # reject anything older than 5 minutes


# Persistent store of seen event IDs — replay protection.
_SEEN_EVENT_IDS: set[str] = set()


def _verify_signature(
    payload: bytes,
    timestamp: str,
    signature: str,
    config: WebhookConfig,
) -> None:
    # Reject too-old timestamps (replay window).
    try:
        ts = int(timestamp)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "bad timestamp") from exc

    if abs(time.time() - ts) > config.tolerance_s:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "stale signature")

    # Reconstruct signed payload and verify HMAC in constant time.
    signed = f"{timestamp}.{payload.decode()}".encode()
    expected = hmac.new(config.secret, signed, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad signature")


app: Final = FastAPI()
config: Final = WebhookConfig(secret=b"whsec_REDACTED")


@app.post("/webhooks/stripe", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(..., alias="Stripe-Signature"),
) -> dict[str, str]:
    payload = await request.body()

    # Stripe signature header looks like: "t=1655245200,v1=abc123..."
    parts = dict(p.split("=", 1) for p in stripe_signature.split(","))
    timestamp = parts["t"]
    signature = parts["v1"]
    _verify_signature(payload, timestamp, signature, config)

    # Replay protection: track event IDs.
    import json
    event = json.loads(payload)
    event_id = event["id"]
    if event_id in _SEEN_EVENT_IDS:
        # Already processed; ack but don't re-handle.
        return {"status": "duplicate"}
    _SEEN_EVENT_IDS.add(event_id)

    # Hand off asynchronously — return 200 fast; the sender's timeout is short.
    await _enqueue_for_processing(event)
    return {"status": "accepted"}


async def _enqueue_for_processing(event: dict[str, object]) -> None:
    # Push into your internal queue / outbox / job system.
    ...
```

**The non-negotiables.**

- **HMAC signature verification.** Every payload signed with a secret only the
  sender and receiver know; verified with `hmac.compare_digest` (constant-time,
  immune to timing side channels).
- **Timestamp in the signed payload + tolerance window.** Bind the signature to
  a timestamp; reject anything outside (typically) ±5 minutes. Without the
  timestamp, an attacker who captured one valid request can replay it forever.
- **Replay protection by event ID.** Even within the time window, the same event
  may be redelivered (sender's retry, network blip, your 5xx). Track event IDs;
  idempotent handlers.
- **Fast 200.** Return 200 (or 2xx) within seconds; the sender's timeout is
  typically 30s or less. Move the actual work to a queue and process
  asynchronously. If processing takes 30s and you do it inline, the sender times
  out, retries, and you do it twice.
- **Retries with exponential backoff** by the sender. Stripe retries up to 16
  times over ~3 days; Slack retries 3 times over ~1 hour; GitHub retries with
  exponential backoff. Receivers must handle redelivery.

**The "exactly-once is a lie" framing.** Webhooks are _at-least-once_. The
sender retries on failure; on success, the response may be lost in transit; the
sender retries again. Your handler will see duplicates. The only correct mental
model:

> "I will see this event one or more times. My handler is idempotent."

Track event IDs; treat duplicates as "ack and skip." Never assume a webhook
delivers exactly once because the sender promises "exactly-once delivery" — what
they mean is "exactly-once produce" (their side won't accidentally fire twice in
a single attempt) plus "best-effort delivery of each attempt." Your side still
gets duplicates from network retries.

**Type-safety notes.** Pinning `stripe_signature` as a typed `Header(...)`
parameter on the FastAPI handler means the framework enforces presence at the
boundary. The handler returns a typed dict; FastAPI generates the OpenAPI
schema. The actual event payload is `dict[str, object]` because Stripe's type
discriminator is in `event.type` — production code would parse into a
discriminated union (Pydantic V2's `Discriminator("type")`).

**When NOT to use.**

- The receiver isn't reachable on the public internet (firewall, intranet only).
  Use polling against a public sender API, or a long-poll pattern.
- The event volume is high enough that 1 HTTP call per event is wasteful. Use a
  streaming protocol or batch endpoint.
- Strict ordering matters across many events. Webhooks parallelise delivery;
  ordering is best-effort. Use a stream (Kafka, Kinesis) or consume the sender's
  full event stream API instead.

**Real-world examples.**

- **Stripe webhooks.** Signed with HMAC-SHA256. Retry policy: 16 attempts over 3
  days. `Stripe-Signature` header carries timestamp + signature.
- **GitHub webhooks.** `X-Hub-Signature-256` header (HMAC-SHA256). Retry for ~30
  days on certain triggers.
- **Slack events.** `X-Slack-Signature` and `X-Slack-Request-Timestamp`.
  3-second response timeout (very strict). Retries 3 times over ~1 hour.
- **Shopify webhooks.** `X-Shopify-Hmac-SHA256`. 5-second response timeout;
  retries over 48 hours.

**Anti-pattern variant.**

- **No signature verification.** Anyone who knows your URL can spoof events.
  Free ticket to inject fake `payment.succeeded` events into your pipeline.
- **Signature without timestamp.** Replay-vulnerable. A captured valid request
  stays valid forever. Always bind to a timestamp + tolerance.
- **Inline processing.** Doing the actual work synchronously within the webhook
  handler. Slow → sender times out → retry → duplicate work → cascading
  slowness. Always 200-fast and process async.
- **String comparison instead of `compare_digest`.** Timing-side-channel attack:
  an attacker can probe one byte at a time by measuring response times. Use
  constant-time compare _always_ for HMACs.
- **Trusting the sender's "I delivered this once" claim.** Plan for duplicates.
  Always.

**References.**

- _Stripe — Webhook signing_, stripe.com/docs.
- _Slack — Verifying requests from Slack_, api.slack.com.
- _GitHub — Securing your webhooks_, docs.github.com.
- Brandur Leach. _Implementing Stripe-like Idempotency Keys_, brandur.org.

---

## Long polling, SSE, WebSockets

**Intent.** Three patterns for "the server has updates the client wants to see
soon, ideally now." Each fits a different shape of streaming-ish work.

**The choices.**

| Pattern                      | Direction                      | Connection model                           | Browser-native?     | When it shines                                                       |
| ---------------------------- | ------------------------------ | ------------------------------------------ | ------------------- | -------------------------------------------------------------------- |
| **Long polling**             | server → client                | One HTTP request held open                 | Yes (XHR/fetch)     | Compatibility with strict networks; updates infrequent               |
| **SSE (Server-Sent Events)** | server → client                | One HTTP connection, server streams events | Yes (`EventSource`) | Server-pushed updates to a browser; one-way; auto-reconnect built in |
| **WebSockets**               | bidirectional                  | Persistent TCP, upgraded from HTTP         | Yes (`WebSocket`)   | Bidirectional, frequent, low-latency; chat, presence, multiplayer    |
| **gRPC streaming**           | unary / client / server / bidi | Persistent HTTP/2 stream                   | gRPC-Web only       | Internal east-west; typed contracts                                  |
| **Webhooks**                 | server → server                | Outbound HTTP from sender                  | N/A                 | Cross-org server-to-server notifications (see [webhooks](#webhooks)) |

**Long polling.** Client makes a request; server holds the connection open until
either (a) it has data to send, or (b) a timeout fires. On response, client
immediately reissues. Trades a constantly-open connection for chunkier resource
use during quiet periods.

```python
import asyncio
from fastapi import FastAPI, Request, Response, status


app = FastAPI()
_subscribers: dict[str, asyncio.Queue[bytes]] = {}


@app.get("/subscribe/{user_id}/messages")
async def long_poll(user_id: str, request: Request, timeout_s: float = 30.0) -> Response:
    queue = _subscribers.setdefault(user_id, asyncio.Queue())
    try:
        async with asyncio.timeout(timeout_s):
            payload = await queue.get()
        return Response(content=payload, media_type="application/json")
    except TimeoutError:
        # Empty 204 — client reissues.
        return Response(status_code=status.HTTP_204_NO_CONTENT)
```

**SSE.** A single long-lived HTTP response with a
`Content-Type: text/event-stream`. The server writes events in
`data: <line>\n\n` format; the browser's `EventSource` consumes them and
auto-reconnects on disconnect.

```python
import asyncio
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse


app = FastAPI()


async def event_stream(user_id: str) -> AsyncIterator[bytes]:
    last_event_id = 0
    while True:
        events = await _fetch_since(user_id, last_event_id)
        for event in events:
            last_event_id = event.id
            payload = (
                f"id: {event.id}\n"
                f"event: {event.kind}\n"
                f"data: {event.body_json}\n\n"
            )
            yield payload.encode()
        await asyncio.sleep(0.5)


@app.get("/sse/{user_id}/events")
async def sse(user_id: str) -> StreamingResponse:
    return StreamingResponse(
        event_stream(user_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

SSE is the right default for _server-to-browser_ streaming. It's HTTP, so it
works through standard infrastructure (CDNs, load balancers, proxies) with
minimal special-casing; the browser does the reconnection, replay (via
`Last-Event-ID`), and event-typing for free.

**WebSockets.** Persistent, bidirectional, frame-based. Upgraded from HTTP on a
single connection. The server maintains state per connection — every connected
client is an open file descriptor and an event-loop task.

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Final


app: Final = FastAPI()
_connections: set[WebSocket] = set()


@app.websocket("/ws/chat")
async def chat(ws: WebSocket) -> None:
    await ws.accept()
    _connections.add(ws)
    try:
        async for message in ws.iter_text():
            # Broadcast to every other connection.
            for other in _connections:
                if other is not ws:
                    await other.send_text(message)
    except WebSocketDisconnect:
        pass
    finally:
        _connections.discard(ws)
```

**When each fits.**

- **Long polling** — fallback for environments hostile to long-lived connections
  (corporate proxies, ancient load balancers); when updates arrive a handful of
  times per minute.
- **SSE** — server pushes updates to browsers, _one direction_: live
  notifications, log tailing, LLM token streams, build progress, news feeds.
  Auto-reconnect built in. **The right default** for server → browser streaming.
- **WebSockets** — bidirectional, frequent: chat, presence, collaborative
  editing, multiplayer games, live cursors, device control.
- **gRPC streaming** — internal east-west, where you want typed contracts (proto
  schema), bidirectional streams, and client-/server-/bidi-stream modes.
- **Webhooks** — server → server, cross-org, infrequent (covered separately
  above).

**The connection-as-state cost.** WebSockets and SSE keep connections open per
client. The server's concurrency model shifts from "thousands of ephemeral
requests" to "thousands of long-lived connections." This burns file descriptors
and event-loop slots; many load balancers have idle-connection timeouts (60s ALB
default) that silently drop connections. Mitigations:

- **Heartbeat** ([reliability.md heartbeat](./reliability.md#heartbeat)) —
  server sends ping every 30s to defeat NAT / LB timeouts.
- **Connection budget per pod.** Cap active connections; reject new ones with a
  `503` and let the LB pick another pod.
- **Sticky sessions** when state lives per-pod, or a shared store (Redis
  pub/sub) when it doesn't.

**Type-safety notes.** WebSocket and SSE messages are wire-typed strings or
bytes; layer your own schema on top. For SSE, parse `event:` and `data:` into
typed Pydantic models. For WebSocket, define a discriminated union of message
types (`{"type": "join", ...}`, `{"type": "message", ...}`); validate at
receive.

**When NOT to use.**

- Server polls client. The client should poll the server (or use a push
  pattern); inverse polling is a shape that makes everyone unhappy.
- "We need real-time" without defining what real-time means. Sub-100ms is
  WebSockets; sub-second is SSE; few-seconds is long polling or just short
  polling. Pick the simplest pattern that meets the latency requirement.

**Real-world examples.**

- **OpenAI's streaming chat completions** — SSE; tokens arrive as individual
  events.
- **GitHub's "live updates"** for Issues — long polling historically; modern UI
  uses SSE.
- **Slack's RTM API** — WebSocket-based bidirectional event stream.
- **Discord's gateway** — WebSocket for everything user-facing.

**Anti-pattern variant.**

- **WebSocket because "modern."** A notification stream is one-way. WebSockets
  buy you complexity (connection state, frame protocol, reconnection logic) you
  don't need. Use SSE.
- **Long polling without timeout caps.** A misbehaving client holds thousands of
  connections forever; pod runs out of FDs.
- **No heartbeat.** ALB closes the connection silently after 60s of no data;
  client thinks it's connected; messages drop into the void. Always heartbeat at
  sub-LB-timeout intervals.

**References.**

- _MDN — Server-Sent Events_, developer.mozilla.org.
- _RFC 6455 — The WebSocket Protocol._
- _gRPC — Streaming RPCs_, grpc.io.
- ByteByteGo, _Short/long polling, SSE, WebSocket_.

---

## Asynchronous Request-Reply

**Intent.** A request that takes longer than a synchronous round-trip is
practical (seconds-to-hours): the API accepts the request, returns a _handle_
immediately, and the caller checks in later. The caller is freed from holding a
connection open through GC pauses, load-balancer idle timeouts, and network
blips. The server is freed from streaming state-of-progress.

**When to reach for it.**

- Long-running operations: video transcoding, large export, ML inference,
  multi-step workflow.
- Operations where the caller is a script, batch job, or workflow engine that
  can poll on its own schedule.
- Any synchronous operation that "almost always" takes seconds but occasionally
  takes minutes — the long-tail latency would burn caller threads otherwise.

**The two flavours.**

1. **Polling URL.** Server returns `202 Accepted` + `Location: /jobs/<id>`.
   Caller polls that URL; server responds with `200 OK` (or `200` + final result
   body) when complete, or `202 Accepted` (still running) otherwise.
   Standardised by HTTP semantics.
2. **Callback URL (push).** Caller submits its own callback URL with the
   request. Server invokes it when the work is done. Effectively a webhook, but
   initiated by the caller.

**Sketch.** Strict-typed Python 3.13+ — the polling-URL flavour:

```python
import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, UTC
from enum import StrEnum
from typing import Final

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(slots=True)
class Job:
    job_id: str
    status: JobStatus
    submitted_at: datetime
    result: dict[str, object] | None = None
    error: str | None = None


_JOBS: dict[str, Job] = {}


app: Final = FastAPI()


@app.post("/exports", status_code=status.HTTP_202_ACCEPTED)
async def submit_export(request: dict[str, object]) -> JSONResponse:
    job = Job(
        job_id=uuid.uuid4().hex,
        status=JobStatus.PENDING,
        submitted_at=datetime.now(UTC),
    )
    _JOBS[job.job_id] = job
    asyncio.create_task(_run_export(job, request))

    return JSONResponse(
        content={"job_id": job.job_id, "status": job.status.value},
        status_code=status.HTTP_202_ACCEPTED,
        headers={
            "Location": f"/jobs/{job.job_id}",
            "Retry-After": "5",  # hint: poll in 5s
        },
    )


@app.get("/jobs/{job_id}")
async def get_job(job_id: str) -> JSONResponse:
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such job")

    if job.status in (JobStatus.PENDING, JobStatus.RUNNING):
        return JSONResponse(
            content={
                "job_id": job.job_id,
                "status": job.status.value,
                "submitted_at": job.submitted_at.isoformat(),
            },
            status_code=status.HTTP_200_OK,
            headers={"Retry-After": "5"},
        )

    return JSONResponse(
        content={
            "job_id": job.job_id,
            "status": job.status.value,
            "result": job.result,
            "error": job.error,
        },
        status_code=status.HTTP_200_OK,
    )


async def _run_export(job: Job, request: dict[str, object]) -> None:
    job.status = JobStatus.RUNNING
    try:
        await asyncio.sleep(10)  # simulate work
        job.result = {"download_url": "https://example.com/exports/abc.csv"}
        job.status = JobStatus.SUCCEEDED
    except Exception as exc:
        job.error = repr(exc)
        job.status = JobStatus.FAILED
```

**Correlation IDs.** The `job_id` _is_ the correlation ID. Every log line, every
metric, every downstream call carries it; reconstructing "what happened to that
export" becomes a single grep. The Enterprise Integration Patterns book
canonised the correlation ID for messaging systems; the same idea applies here.

**Polling cadence.** The server hints with `Retry-After`; the client should
respect it but also apply jitter (don't have all clients poll on the exact
second). Exponential backoff with a floor (e.g. 1s minimum, 30s ceiling) is
sane.

**Webhooks-as-completion.** Combining the two flavours: client submits with
`callback_url`; server pings the callback when done. The client still has the
option to _also_ poll, defending against missed callbacks (network failure,
server crash mid-fire). Stripe's "checkout session completed" pattern looks like
this.

**Type-safety notes.** `JobStatus` as a `StrEnum` gives you exhaustive matching
in code that processes status updates; `Final` on the in-memory store prevents
accidental rebinding. In production, the `_JOBS` dict would be a Redis hash or
Postgres row keyed by `job_id` — same shape, shared across replicas.

**When NOT to use.**

- Operations that genuinely complete in milliseconds. The polling overhead is
  wasted; just use a sync request.
- Sub-second jobs where holding the request is fine and avoids the polling
  client complexity.

**Real-world examples.**

- **AWS S3 multipart upload completion** — submit, get an `UploadId`, poll
  `ListMultipartUploads` for status.
- **Stripe Checkout sessions** — create a session, get a URL; the customer pays;
  you receive a webhook when complete (and can also poll the session status).
- **GitHub Actions** — workflow run is an async job; the API returns a run URL;
  you poll status or subscribe to webhook completion events.
- **OpenAI's batch API** — submit a batch of completion requests, poll the batch
  ID until done; download results from the resulting URL.

**Anti-pattern variant.**

- **Inventing your own polling protocol.** Use the standard HTTP shapes:
  `202 Accepted`, `Location` header, `Retry-After` hint. Clients (and load
  balancers) understand them.
- **No expiry on jobs.** A job table that grows forever; storage cost
    - slow lookups. Set a TTL on completed jobs (24h–30d depending on use case).
- **Callback without retry.** "We tried once, the call failed, we don't re-try
  the callback." Now the client has no idea their job is done. Pair callbacks
  with retries-with-backoff (treat callbacks as webhooks).

**References.**

- _Microsoft Azure — Asynchronous Request-Reply Pattern._
- _Enterprise Integration Patterns — Correlation Identifier._
- _RFC 7231 §6.3.3 — 202 Accepted._
- Sam Newman. _Building Microservices._ 2nd ed., Chapter 5.

---

## Claim Check

**Intent.** When a message is too large to pass through the broker (or when
transferring it through the broker is wasteful — large binaries, big PDFs, video
frames, model weights), pass a _reference_ (the "claim check") through the
message system and put the actual payload in out-of-band storage (S3, GCS, Azure
Blob). The broker handles routing and ordering; the storage handles the bulk.

**When to reach for it.**

- Payloads larger than the broker's message size limit (Kafka's default is 1 MB;
  SQS is 256 KB; SNS is 256 KB; RabbitMQ is configurable but large messages hurt
  throughput).
- Payloads that _most_ consumers don't need to fully consume — they only care
  about metadata; only one consumer needs the bulk.
- Cost-driven: keeping bytes in cheap object storage instead of broker storage.

**Sketch.** Strict-typed Python 3.13+ — producer uploads to S3, publishes the
URL; consumer downloads on demand:

```python
import boto3
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Final, NewType

import aioboto3
from pydantic import BaseModel


ClaimCheckUri = NewType("ClaimCheckUri", str)


class LargePayloadEvent(BaseModel):
    event_id: str
    occurred_at: datetime
    correlation_id: str
    # The pointer — small, durable. The bulk lives in S3.
    claim_check: ClaimCheckUri
    content_type: str
    size_bytes: int
    sha256_hex: str  # consumer can verify integrity on download


@dataclass(frozen=True, slots=True)
class S3Bucket:
    name: str
    prefix: str = ""


async def publish_with_claim_check[T: bytes](
    bucket: S3Bucket,
    payload: T,
    content_type: str,
    publish_to_broker: Callable[[LargePayloadEvent], Awaitable[None]],
) -> None:
    import hashlib
    import uuid

    object_key = f"{bucket.prefix}{uuid.uuid4().hex}"

    session = aioboto3.Session()
    async with session.client("s3") as s3:
        await s3.put_object(
            Bucket=bucket.name,
            Key=object_key,
            Body=payload,
            ContentType=content_type,
        )

    event = LargePayloadEvent(
        event_id=uuid.uuid4().hex,
        occurred_at=datetime.now(UTC),
        correlation_id=uuid.uuid4().hex,
        claim_check=ClaimCheckUri(f"s3://{bucket.name}/{object_key}"),
        content_type=content_type,
        size_bytes=len(payload),
        sha256_hex=hashlib.sha256(payload).hexdigest(),
    )

    await publish_to_broker(event)


async def consume_with_claim_check(event: LargePayloadEvent) -> bytes:
    bucket, _, key = event.claim_check.removeprefix("s3://").partition("/")

    session = aioboto3.Session()
    async with session.client("s3") as s3:
        response = await s3.get_object(Bucket=bucket, Key=key)
        body: bytes = await response["Body"].read()

    # Verify integrity before returning.
    import hashlib
    if hashlib.sha256(body).hexdigest() != event.sha256_hex:
        raise ValueError(
            f"sha256 mismatch for claim check {event.claim_check}: "
            f"expected {event.sha256_hex}"
        )
    return body
```

**Lifecycle.**

- **TTL on the claim check object.** Set an S3 lifecycle policy: delete objects
  older than N days. Without TTL, the bucket grows forever and paying for the
  unread payloads of dead consumers.
- **TTL aligned with consumer SLA.** If the slowest consumer takes 24h to drain,
  set TTL ≥ 48h. If a consumer is more than 24h behind, it expects the claim
  check to be missing — and should treat that as a recoverable error (alert +
  skip, not crash).
- **Pre-signed URLs for cross-account.** When the consumer is in a different AWS
  account or org, generate a pre-signed URL with a bounded TTL instead of
  granting cross-account bucket policy.

**Integrity.** Always include a SHA-256 (or equivalent) of the payload in the
claim-check event. The consumer verifies on download. This catches:

- Truncated downloads.
- Mid-flight modification (object overwritten between produce and consume).
- Wrong-key bugs (claim check pointed to the wrong object).

**Type-safety notes.** `NewType` for `ClaimCheckUri` prevents accidental
string-to-string contamination. The PEP 695 generic `[T: bytes]` constrains the
payload type; consumers know they're dealing with bytes, not arbitrary objects.
Pydantic at the schema boundary enforces required fields.

**When NOT to use.**

- Small messages. The two-hop overhead (broker + storage) plus the S3 latency
  dwarfs the broker round-trip for sub-MB payloads.
- Workloads where every consumer needs every byte. The "downloads on demand"
  benefit only kicks in when most consumers can stay metadata-only.

**Real-world examples.**

- **AWS Kinesis Data Streams** explicitly recommends claim check for payloads
  over the 1 MB limit.
- **Apache Kafka with large messages** — the recommended pattern is exactly
  this; Confluent's docs call out "passing large messages through Kafka is
  generally an anti-pattern; use S3 / blob storage with a Kafka pointer."
- **Azure Service Bus** ships an `EventGrid + Blob Storage` reference
  architecture.
- **GCP Pub/Sub + GCS** — same pattern; Pub/Sub messages cap at 10 MB, but
  real-world GCS-references are the canonical large-payload shape.

**Anti-pattern variant.**

- **No TTL on storage.** The bucket fills with payloads no consumer will ever
  read again; bill grows; catastrophic when audited.
- **No integrity check.** Object overwritten in flight; consumer sees truncated
  bytes; debugging lasts a week.
- **Storage in the same blast radius as the broker.** S3 outage takes out the
  message system entirely. Pick storage in a different failure domain —
  typically a different _service_ in the same region (S3 vs Kafka), not "S3 vs
  S3."
- **Claim check that's also the message body.** "We pass the URL _and_ the body,
  just in case." Defeats the entire pattern; use one or the other.

**References.**

- Hohpe & Woolf. _Enterprise Integration Patterns._ Addison-Wesley, 2003. (The
  book that names the pattern.)
- _AWS — Sending Large Messages Using Amazon S3 and Amazon SQS._
- _Microsoft Azure — Claim-Check Pattern._
- _Confluent — Working with Large Messages_.

---

## Choreography vs Orchestration

**Intent.** Two ways to coordinate a multi-step workflow across services.
_Choreography:_ services react to events from each other; no central
coordinator; the workflow is the emergent sum of independent reactions.
_Orchestration:_ a central coordinator (workflow engine) explicitly sends
commands to each service and tracks progress.

**This file gives only the intro; full saga-pattern depth lives in
`system/distributed.md`.**

**The choice.**

| Property         | Choreography                                                       | Orchestration                                                             |
| ---------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------- |
| Coordination     | Distributed (each service knows its piece)                         | Centralised (one service knows the whole workflow)                        |
| Coupling         | Services depend on event schemas                                   | Services depend on workflow engine + commands                             |
| Visibility       | Hard to see "where is order #123 in the flow?"                     | First-class — query the orchestrator                                      |
| Adding steps     | Subscribe new service to existing events                           | Update orchestrator definition                                            |
| Failure handling | Compensating events per service                                    | Centralised compensation logic                                            |
| Right when…      | Loose coupling matters more than visibility; small number of steps | Long-running workflows with explicit branches; you need to query progress |

**Tooling.**

- **Choreography:** Kafka / RabbitMQ + your own event handlers.
- **Orchestration:** Temporal, Cadence, AWS Step Functions, Camunda, Airflow
  (for batch).

**Real-world examples.**

- **Choreography**: Shopify's order pipeline — payment service emits
  `payment.succeeded`, fulfilment service subscribes and reacts; no central
  coordinator.
- **Orchestration**: Uber's trip lifecycle (post-2019) — Cadence workflow tracks
  each trip from request → matched → started → completed → paid.

**When NOT to use either.**

- A single-service flow with no inter-service coordination. Just write the
  function.

**Defer.** For full saga semantics, compensating transactions, retry policies
inside workflows, and the long debate on "centralised vs distributed
coordination," see `system/distributed.md` (other agent's output).

**References.**

- Bernd Rücker. _Practical Process Automation._ O'Reilly, 2021.
- _Temporal Documentation_, temporal.io.
- _AWS Step Functions Documentation._
- Chris Richardson. _Microservices Patterns._ Chapter 4.

---

## Strangler Fig

**Intent.** Migrate from a legacy system (often a monolith) to a new
architecture incrementally, by routing requests for one slice of functionality
at a time to the new implementation while the rest still hits the legacy. Named
for the strangler fig tree, which grows around an existing host until the host
is gone.

**This file gives only the intro; full migration playbook lives in
`system/cloud.md`.**

**The shape.**

1. Front the legacy system with a façade (typically an API gateway or reverse
   proxy).
2. Build the new implementation of one feature.
3. Update the façade to route that feature's requests to the new implementation.
4. Repeat for each feature until the legacy system has no traffic.
5. Decommission the legacy.

The crucial part is _the façade is permanent through the migration_; clients
never see the routing change. New endpoints can be added without touching the
legacy; the legacy can be turned off once all routes are moved.

**When to reach for it.**

- A monolith that's too big to rewrite in one go.
- A legacy system with quality / scaling / talent issues that you can't retire
  all at once.
- A system where parts evolve at different rates — finance is business-critical
  and slow; recommendations is fast-moving and could be rebuilt sooner.

**When NOT to use.**

- The legacy fits in one engineer-month rewrite. Just rewrite.
- The legacy has so much hidden coupling that "one feature" can't be cleanly
  extracted. Refactor the monolith first; _then_ strangle.

**Real-world examples.**

- **The original Martin Fowler post** (2004) describes the pattern as used for
  large enterprise migrations.
- **GitHub's monolith → microservices** has been an explicit multi-year
  strangler-fig migration.
- **The Guardian** strangled their legacy CMS over years using a façade router.

**Defer.** For migration sequencing, dual-writes, dual-reads, read-shadow-writes
verification, and decommissioning, see `system/cloud.md` (other agent's output).

**References.**

- Martin Fowler. _StranglerFigApplication._ martinfowler.com, 2004.
- Sam Newman. _Monolith to Microservices._ O'Reilly, 2019.
- _Microsoft Azure — Strangler Fig Pattern._

---

## Stacking the patterns

Communication patterns rarely live alone; they layer. A typical full stack for a
public REST API:

```
Public client
   │
   ▼
[ CDN / WAF ]                ← edge protections; not in this file
   │
   ▼
[ API Gateway ]              ← TLS, auth, rate limit, request ID
   │
   ▼
[ BFF (per-client) ]         ← aggregate, shape for THIS client
   │
   ├─ Service A (sync REST/gRPC)
   ├─ Service B (sync REST/gRPC)
   └─ emits → [ Pub/Sub topic ] ← async events for downstream consumers
              │
              └─ analytics, search index, audit log
```

For a payment-style flow:

```
[ Webhook receiver ] ← signed payload from Stripe
   │
   ▼
[ Idempotency check ] ← skip duplicates, see reliability.md
   │
   ▼
[ Outbox write ]      ← persist event + business state atomically
   │
   ▼
[ Outbox publisher ]  ← reads outbox, publishes to Kafka topic
   │
   ▼
[ Kafka ]             ← at-least-once, partitioned by entity_id
   │
   ▼
[ Consumer group N ]  ← idempotent handler, dedup by event_id
```

For a long-running operation:

```
[ Sync REST POST ]    ← returns 202 + Location
   │
   ▼
[ Job queue ]         ← worker picks up the job
   │
   ▼
[ Worker (long) ]     ← does the work; updates job state
   │
   ▼
[ GET /jobs/<id> ]    ← caller polls for completion
   │
   ▼
[ Webhook callback ]  ← optional push when done
```

The reliability patterns from [reliability.md](./reliability.md) — timeouts,
retries, circuit breakers, bulkheads, hedging — apply at _every_ arrow above.
The communication pattern decides the arrow's _shape_; the reliability pattern
decides what to do when the arrow fails.

---

## Review checklist

For any inter-service communication:

1. Sync or async? Does the caller need the result _now_ to make its next
   decision?
2. 1:1 or 1:N? Does adding a new consumer require a code change in the producer?
3. What's the delivery guarantee? At-most-once, at-least-once, effectively-once?
4. If at-least-once: is the consumer idempotent? How is dedup done?
5. If a webhook receiver: signature + timestamp + replay protection + fast-200 +
   async processing?
6. If WebSocket / SSE: heartbeat with timeout > LB idle?
7. If event-driven: schema versioned in the topic name? Outbox for the producer
   side?
8. If long-running: 202 + Location + Retry-After?
9. If large payload: claim check with TTL on storage and integrity check?
10. If behind a gateway: cross-cutting concerns (auth, rate limit, request ID)
    in the gateway, business logic in services?
11. If a service mesh is in place: are app-layer retries duplicated by the mesh?
12. If introducing a BFF: does it stay an aggregator, not a domain owner?

If any answer is "don't know," stop and decide.

---

## References

### Books

- Sam Newman. _Building Microservices._ 2nd ed. O'Reilly, 2021. Chapters 4–5 are
  the canonical text on inter-service communication shapes.
- Sam Newman. _Monolith to Microservices._ O'Reilly, 2019. The strangler-fig
  migration in detail.
- Chris Richardson. _Microservices Patterns._ Manning, 2018; companion site
  microservices.io.
- Hohpe & Woolf. _Enterprise Integration Patterns._ Addison-Wesley, 2003. The
  original taxonomy of messaging patterns including claim check, correlation
  identifier, request-reply.
- Adam Bellemare. _Building Event-Driven Microservices._ O'Reilly, 2020.
- Bernd Rücker. _Practical Process Automation._ O'Reilly, 2021. Orchestration
  depth.
- Martin Kleppmann. _Designing Data-Intensive Applications._ O'Reilly, 2017.
  Chapters 8–11.

### Papers and articles

- Phil Calçado. "Pattern: Service Mesh." 2017.
- William Morgan. "What's a service mesh? And why do I need one?" Buoyant
  blog, 2017.
- Sam Newman. "Backends For Frontends." samnewman.io.
- Martin Fowler. "StranglerFigApplication." martinfowler.com, 2004.
- Martin Fowler. "What do you mean by 'Event-Driven'?" 2017.
- Microservices.io. "Pattern: Transactional Outbox."
- Microservices.io. "Pattern: API Gateway."
- Roy Fielding. _Architectural Styles and the Design of Network-based Software
  Architectures._ PhD thesis, UC Irvine, 2000.

### Specifications

- _RFC 6455 — The WebSocket Protocol._
- _RFC 7231 §6.3.3 — 202 Accepted._
- _gRPC Specification._ grpc.io/docs.
- _GraphQL Specification._ graphql.org.

### Vendor / product references

- _Stripe — Webhook signing._ stripe.com/docs.
- _Slack — Verifying requests from Slack._ api.slack.com.
- _GitHub — Securing your webhooks._ docs.github.com.
- _AWS — SNS-SQS Fanout Pattern._ AWS Architecture Center.
- _AWS — Sending Large Messages Using Amazon S3 and Amazon SQS._
- _Microsoft Azure — Asynchronous Request-Reply Pattern._
- _Microsoft Azure — Backends for Frontends Pattern._
- _Microsoft Azure — Claim-Check Pattern._
- _Microsoft Azure — Strangler Fig Pattern._
- _Istio Documentation._ istio.io.
- _Linkerd Documentation._ linkerd.io.
- _Envoy Documentation._ envoyproxy.io.
- _Kong Documentation._ docs.konghq.com.
- _Apache Kafka Documentation._ kafka.apache.org.
- _RabbitMQ Documentation._ rabbitmq.com.
- _Confluent — Working with Large Messages._ docs.confluent.io.

### Python libraries referenced

- `httpx` — async/sync HTTP with proper timeout primitives.
- `fastapi` — typed REST framework.
- `aiokafka` — asyncio Kafka client.
- `faststream` — typed framework over aiokafka, RabbitMQ, NATS, Redis.
- `aioboto3` — async AWS SDK (S3 for claim check).
- `pydantic` — schema validation at message boundaries.
- `grpcio` + `grpcio-tools` — gRPC for Python.
- `strawberry` — typed GraphQL.
