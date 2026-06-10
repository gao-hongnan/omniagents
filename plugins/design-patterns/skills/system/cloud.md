# Cloud and Microservices Structural Patterns

> Structural patterns for systems built from many processes that talk over a
> network. Each entry frames the _deployment topology_, the _ownership boundary
> it draws_, and the _failure mode it is designed to absorb_.

These patterns answer questions that don't apply inside a single process: where
does a cross-cutting concern live (logging, retries, mTLS) when the application
is many services? How does a request that takes minutes fit into a protocol
designed for sub-second responses? How do you migrate a 15-year-old monolith
without a 12-month freeze? How do you shrink the blast radius of a single bad
deploy from 100% of customers to 1%?

The default posture in this document is **draw the boundary explicitly, push
concerns to the smallest container that can own them, and never let a structural
decision disguise itself as a runtime detail**.

## How to use this file

Read this when you are about to:

- Add a new service to the platform (does the new concern want a sidecar, an
  ambassador, or just a library?).
- Rewrite or migrate something old (Strangler Fig, ACL).
- Coordinate work across services (Saga: choreography or orchestration?).
- Reduce the blast radius of a deploy or an outage (Bulkhead, Cell).

Code is Python 3.13+ and written to target mypy `--strict` + pyright `--strict`:
`Protocol` over `ABC`, PEP 695 generics, PEP 604 unions, no `Any`, and the
annotation-evaluation policy in `SKILL.md` conventions. Examples use `fastapi`,
`httpx`, `pydantic`, and `redis-py` as representative libraries; adapt them to
the consuming project's stack.

Resilience patterns referenced here (circuit breakers, timeouts, retries) are
detailed in `reliability.md`. Code-level smells (god object, primitive
obsession) are in `software/anti-patterns.md`. System-level smells (distributed
monolith, shared database) are in `anti-patterns.md`.

---

## Sidecar

**What it is / Intent.** A helper process or container deployed alongside the
main application, sharing its lifecycle and its host (pod, VM). The sidecar
handles _cross-cutting concerns_ — TLS termination, log shipping, secrets
injection, metrics collection — so the main application can stay focused on
business logic and stay free of the dependencies the sidecar provides.

**When to reach for it / How it manifests.**

- A polyglot platform (Python, Go, Java services) needs the _same_ cross-cutting
  capability without re-implementing it per language.
- The capability is owned by a different team (security, platform,
  observability) than the one writing the application.
- The capability changes on a different cadence than the application — security
  patches, mTLS cert rotation, log format updates.
- You need fine-grained resource isolation between the application and the
  helper (cap the proxy at 200 MB RAM independent of the app).

**Deployment topology.**

```
   ┌─────────────────────── Pod / VM ───────────────────────┐
   │  ┌────────────────┐                  ┌──────────────┐  │
   │  │ Application    │  loopback (TCP / │  Sidecar     │  │
   │  │ container      │  unix socket)    │  container   │  │
   │  │  (your code)   │ ◀──────────────▶ │  (proxy /    │  │
   │  └────────────────┘                  │   log ship / │  │
   │           ▲                          │   secrets)   │  │
   │           │ shared FS / env          └──────────────┘  │
   │           ▼                                  ▲          │
   │   /var/log /var/run/secrets                  │ network  │
   └──────────────────────────────────────────────┼──────────┘
                                                  ▼
                                           external systems
```

**Sketch (k8s pod with Envoy sidecar — conceptual YAML; the Python piece is the
app's config that _trusts_ the sidecar).**

```yaml
# k8s/order-service.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
    name: order-service
spec:
    replicas: 3
    template:
        spec:
            containers:
                - name: app
                  image: registry/order-service:v1.4.2
                  env:
                      - name: UPSTREAM_BASE_URL
                        value: "http://127.0.0.1:15001" # talk to the sidecar, not the world
                      - name: METRICS_ADDR
                        value: "127.0.0.1:9091"
                - name: envoy # sidecar: mTLS, retries, metrics, tracing
                  image: envoyproxy/envoy:v1.29
                  ports: [{ containerPort: 15001 }]
                  volumeMounts:
                      - { name: envoy-config, mountPath: /etc/envoy }
                - name: fluent-bit # sidecar: log shipping
                  image: fluent/fluent-bit:3.0
                  volumeMounts:
                      - {
                            name: app-logs,
                            mountPath: /var/log/app,
                            readOnly: true,
                        }
            volumes:
                - { name: envoy-config, configMap: { name: envoy-config } }
                - { name: app-logs, emptyDir: {} }
```

**Sketch (Python app trusts the sidecar to do mTLS).**

```python
from typing import Final
import httpx


# All outbound calls go to the local sidecar; the sidecar applies mTLS, retries,
# circuit breaker, and tracing. The application's code never sees the upstream URL.
SIDECAR_BASE_URL: Final[str] = "http://127.0.0.1:15001"


class OutboundClient:
    def __init__(self, sidecar_url: str = SIDECAR_BASE_URL) -> None:
        self._client: Final = httpx.AsyncClient(
            base_url=sidecar_url, timeout=httpx.Timeout(connect=1.0, read=5.0)
        )

    async def get_user(self, user_id: str) -> httpx.Response:
        # Path "users/{id}" maps to upstream cluster "users" in Envoy config.
        return await self._client.get(f"/users/{user_id}")
```

**When NOT to use / What it costs.**

- _Tiny services / per-pod overhead._ A 50 MB sidecar next to a 30 MB function
  app doubles your footprint. For Lambda-class workloads, prefer a library or
  extension.
- _Latency-critical inner loops._ Loopback adds tens of microseconds. For
  trading, sub-millisecond databases, etc., link the library directly.
- _Platform already provides it._ If your runtime ships mTLS, retries, and
  tracing natively (e.g. AWS App Mesh, GCP Service Mesh), a manual sidecar is
  duplication.
- _Independent scaling._ If the helper needs to scale differently from the app,
  it is a separate service, not a sidecar.

**Real-world examples.**

- _Istio / Linkerd_ — Envoy or `linkerd-proxy` as the data-plane sidecar.
- _Dapr_ — building blocks (state, pub/sub, secrets) exposed via a sidecar
  HTTP/gRPC API.
- _Vault Agent_ — sidecar that fetches and renews secrets, writes them to a
  shared volume.
- _Fluent Bit / OpenTelemetry Collector_ — log and metric shippers as sidecars.

**References.**

- Microsoft Azure, _Sidecar Pattern_,
  learn.microsoft.com/azure/architecture/patterns/sidecar.
- Burns, B., _Designing Distributed Systems_, O'Reilly, 2018 — ch. 2.
- Istio docs, _Architecture_, istio.io.

---

## Ambassador

**What it is / Intent.** An _outbound_ proxy that sits between an application
and a remote dependency, handling network concerns: retries, timeouts,
authentication, mTLS, metrics, circuit breaking, request shaping. The
application makes a _local_ call to the ambassador; the ambassador owns the
_remote_ call.

**Sidecar vs Ambassador.** Both run alongside the app. The distinction is
_direction_: sidecars are general-purpose helpers (logs, secrets,
observability); ambassadors are specifically about outbound network behavior. In
practice, an ambassador is usually _deployed as_ a sidecar — Envoy doing
outbound is the canonical example.

**When to reach for it / How it manifests.**

- A legacy app calls a remote API directly with no retries, no metrics, no auth
  — and you cannot modify it.
- Cross-cutting _connectivity_ concerns (mTLS rotation, observability, traffic
  shifting) need to be owned by infrastructure, not by every team.
- The remote dependency requires complex auth (OAuth refresh, AWS SigV4) that
  you do not want to implement N times across N services.

**Deployment topology.**

```
   App ──▶ Ambassador ──▶ Remote API
            (local)          (over WAN)
   +────────────+    +─────────────────+
   │ retries    │    │ TLS + auth      │
   │ tracing    │    │ DNS resolution  │
   │ throttling │    │ connection pool │
   │ logs       │    │                 │
   +────────────+    +─────────────────+
```

**Sketch (FastAPI middleware as a tiny in-process Ambassador for outbound
calls).**

This is the in-process version, useful when you cannot ship a sidecar (small
services, edge environments). For polyglot fleets, prefer a real out-of-process
ambassador (Envoy, HAProxy).

```python
import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Final, Protocol, Self

import httpx


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AmbassadorPolicy:
    timeout_s: float = 5.0
    max_retries: int = 2
    backoff_base_s: float = 0.1
    retry_on_status: frozenset[int] = field(default_factory=lambda: frozenset({502, 503, 504}))


class TokenSource(Protocol):
    async def fetch(self) -> str: ...


@dataclass(slots=True)
class HTTPAmbassador:
    """Outbound HTTP proxy with retries, auth refresh, and structured logging."""

    upstream_base_url: str
    token_source: TokenSource
    policy: AmbassadorPolicy = field(default_factory=AmbassadorPolicy)
    _client: httpx.AsyncClient = field(init=False)

    def __post_init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=self.upstream_base_url,
            timeout=httpx.Timeout(connect=1.0, read=self.policy.timeout_s),
        )

    async def request(self, method: str, path: str, *, body: bytes | None = None) -> httpx.Response:
        token = await self.token_source.fetch()
        headers = {"authorization": f"Bearer {token}"}
        last_status: int | None = None
        for attempt in range(1, self.policy.max_retries + 1):
            started = time.monotonic()
            try:
                resp = await self._client.request(method, path, headers=headers, content=body)
            except httpx.TimeoutException:
                logger.warning("ambassador.timeout", extra={"path": path, "attempt": attempt})
                last_status = 504
            else:
                logger.info(
                    "ambassador.ok" if resp.is_success else "ambassador.upstream_error",
                    extra={
                        "path": path, "attempt": attempt,
                        "status": resp.status_code,
                        "latency_s": time.monotonic() - started,
                    },
                )
                if resp.status_code not in self.policy.retry_on_status:
                    return resp
                last_status = resp.status_code
            if attempt < self.policy.max_retries:
                await asyncio.sleep(self.policy.backoff_base_s * (2 ** (attempt - 1)))
        raise RuntimeError(f"ambassador exhausted retries; last_status={last_status}")

    @classmethod
    def for_payments(cls, token_source: TokenSource) -> Self:
        return cls(upstream_base_url="https://api.stripe.com", token_source=token_source)
```

**When NOT to use / What it costs.**

- _Latency-critical paths._ Each hop adds latency. For high-frequency trading or
  sub-ms RPC, link a library directly.
- _Single-language fleet._ If everyone speaks Python, a shared `httpx`-based
  client library is cheaper than an out-of-process proxy.
- _Idempotency-unsafe operations._ The ambassador must _know_ which operations
  are safe to retry. Auto-retrying a `POST /charge` doubles the charge;
  auto-retrying `GET /user/42` is fine.

**Real-world examples.**

- _Envoy as outbound proxy_ — service mesh data plane.
- _AWS RDS Proxy_ — ambassador for Postgres/MySQL connection pooling and IAM
  auth.
- _Vault Agent in proxy mode_ — auto-injects tokens into outbound HTTP.
- _Knative Net-Istio_ — ambassador for serverless functions to upstream
  services.

**References.**

- Microsoft Azure, _Ambassador Pattern_,
  learn.microsoft.com/azure/architecture/patterns/ambassador.
- Burns, B., _Designing Distributed Systems_, O'Reilly, 2018 — ch. 3.

---

## Adapter (System-Level)

**What it is / Intent.** A process or service that _translates_ between
protocols, data formats, or authentication regimes at an integration boundary.
The system-level Adapter is the GoF Adapter pattern hoisted to the network:
instead of one class wrapping another, one _service_ wraps a foreign system.

**When to reach for it / How it manifests.**

- A legacy system speaks SOAP; the new system speaks JSON over HTTP.
- A vendor API speaks gRPC; your fleet speaks REST.
- A partner sends EDI / fixed-width files; you ingest events on Kafka.
- An IoT device speaks MQTT; your services speak HTTP.

**Deployment topology.**

```
   New world           Adapter             Old world
   (REST/JSON)  ────▶  Adapter   ────▶  (SOAP/XML)
                       service
                          │
                  protocol translation
                  schema mapping
                  retry + timeout
                  observability
```

**Sketch (FastAPI adapter for a SOAP backend).**

```python
from typing import Final
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx


SOAP_ENDPOINT: Final = "https://legacy.example.com/CustomerService.svc"
SOAP_REQUEST_TEMPLATE: Final = """\
<?xml version="1.0"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body><GetCustomer xmlns="urn:legacy"><Id>{id}</Id></GetCustomer></s:Body>
</s:Envelope>
"""


class Customer(BaseModel):
    id: str
    name: str
    email: str


app = FastAPI()


@app.get("/customers/{customer_id}", response_model=Customer)
async def get_customer(customer_id: str) -> Customer:
    """REST/JSON facade in front of a SOAP service."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.post(
            SOAP_ENDPOINT,
            content=SOAP_REQUEST_TEMPLATE.format(id=customer_id),
            headers={"content-type": "text/xml; charset=utf-8", "soapaction": "GetCustomer"},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="upstream legacy error")
    return _parse_customer(resp.text)


def _parse_customer(soap_xml: str) -> Customer:
    # Real impl: defusedxml, schema-validated parsing.
    raise NotImplementedError
```

**When NOT to use / What it costs.**

- _Translation in every call site._ If five services all call the legacy SOAP
  API, do not have five copies of the SOAP code; centralize in the adapter.
- _Lossy translation._ If the legacy schema cannot be expressed in the new
  protocol without information loss, the adapter must surface that — a partial
  translation is a silent bug factory.
- _Tight coupling to the legacy system's quirks._ The adapter is a _boundary_,
  not a proxy. If callers must understand SOAP-specific error codes, the
  boundary leaks; see Anti-Corruption Layer.

**Real-world examples.**

- _AWS API Gateway_ — adapter from REST to Lambda / SQS / Kinesis.
- _Kafka Connect_ — adapter from CSV / JDBC / S3 / Salesforce to Kafka topics.
- _Zeebe / Camunda gateway_ — adapter from BPMN orchestrator to REST / gRPC
  services.

**References.**

- GoF, _Design Patterns_, 1994 — Adapter (the inspiration).
- Hohpe, G., Woolf, B., _Enterprise Integration Patterns_, Addison-Wesley, 2003
  — § Channel Adapter.

---

## Anti-Corruption Layer (System-Level)

**What it is / Intent.** A boundary service that _protects_ a bounded context
from a foreign or legacy model leaking in. Different from the Adapter (which
_translates_ protocols): the ACL translates _concepts_, not just bytes. Eric
Evans, DDD: "A separate layer that translates between the two models so that one
can keep its conceptual integrity."

**When to reach for it / How it manifests.**

- A new service must integrate with a legacy system whose data model is awkward,
  inconsistent, or simply wrong by modern standards.
- A partner's API uses concepts that do not match your domain (their "Order" is
  your "Quote").
- You are _strangling_ a legacy system; the new code must not adopt the legacy
  concepts even when reading from the legacy DB during migration.

**Deployment topology.**

```
   New context                 ACL                 Foreign / legacy context
   (clean domain)  ────▶   ACL service   ────▶    (legacy domain model)
   ─────────────           ───────────             ─────────────
   Order                   Order ⇆ LegacyOrder     LegacyOrder
   Money                   Money ⇆ DecimalCurrency DecimalCurrency
   CustomerId              CustomerId ⇆ "CUST00042" "CUST00042"
```

**Sketch (translating concepts, not just fields).**

```python
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Protocol


# --- Clean domain (new context) ----------------------------------------------
@dataclass(frozen=True, slots=True)
class Money:
    amount_cents: int
    currency: str


@dataclass(frozen=True, slots=True)
class Order:
    order_id: str
    customer_id: str
    placed_at: datetime
    total: Money


# --- Legacy model (foreign context) ------------------------------------------
@dataclass(frozen=True, slots=True)
class LegacyOrder:
    """Mapped from the legacy table; do NOT leak into the clean domain."""
    OrdrID: str
    CustNum: int
    OrdrDt: date  # date only; no timezone
    Amt: Decimal
    Curr: str  # 3-char or sometimes "USD$" with a $ for legacy clients


class LegacyOrderRepository(Protocol):
    async def fetch(self, ordr_id: str) -> LegacyOrder: ...


# --- The ACL: translates LegacyOrder → Order, NEVER the other way ------------
class OrderACL:
    """Reads from the legacy system; emits clean Orders.

    The translation is one-way at the boundary: callers in the new context never
    see LegacyOrder. The ACL absorbs ALL legacy quirks (currency parsing, date-only
    timestamps, customer ID format).
    """

    def __init__(self, legacy: LegacyOrderRepository) -> None:
        self._legacy = legacy

    async def get_order(self, order_id: str) -> Order:
        legacy = await self._legacy.fetch(order_id)
        return Order(
            order_id=legacy.OrdrID,
            customer_id=f"cust_{legacy.CustNum:08d}",
            placed_at=datetime.combine(legacy.OrdrDt, datetime.min.time(), tzinfo=UTC),
            total=Money(
                amount_cents=int(legacy.Amt * 100),
                currency=legacy.Curr.replace("$", "").strip().upper(),
            ),
        )
```

**When NOT to use / What it costs.**

- _When the foreign model is your model._ If the legacy system is the source of
  truth and the concepts are correct, just use them. The ACL only earns its keep
  when the foreign concepts are _wrong_ for the new domain.
- _Two-way translation._ ACLs are conceptually one-way (foreign → clean). If you
  find yourself round-tripping data through the ACL, the boundary has been
  mis-drawn — the ACL is leaking.

**Real-world examples.**

- _Stripe → in-house billing._ Stripe charges and refunds expressed as in-house
  `Transaction` events.
- _Salesforce → internal CRM._ Salesforce's `Account` translated to internal
  `Customer` + `Contract`.
- _Healthcare HL7 → modern EHR._ HL7 v2 messages translated to FHIR-style
  resources via an ACL.

**References.**

- Evans, E., _Domain-Driven Design_, Addison-Wesley, 2003 — ch. 14 (Maintaining
  Model Integrity).
- Vernon, V., _Implementing Domain-Driven Design_, Addison-Wesley, 2013 —
  ch. 13.

---

## Strangler Fig

**What it is / Intent.** Incrementally replace a legacy system by routing more
and more traffic to a new system, until the legacy is dead and removed. Named
for the strangler fig vine, which germinates in a host tree's canopy and grows
downward, eventually replacing the host. Coined by Martin Fowler in 2004.

**The core trick.** A _façade_ (proxy, gateway, route table) sits in front of
both systems. New endpoints are implemented in the new system; the façade routes
them there. Old endpoints stay in the legacy system. Over months or years,
endpoints migrate one at a time. When the route table no longer references the
legacy system, the legacy is decommissioned.

**When to reach for it / How it manifests.**

- A monolith has grown unwieldy and a Big Bang rewrite is too risky.
- New features are easier to write in a new stack but cannot wait for a full
  migration.
- A vendor system is being replaced; users cannot tolerate a freeze.
- You inherited a system with no tests; you cannot rewrite it confidently in one
  go.

**Deployment topology.**

```
                         ┌────────────────────┐
                         │  Façade / Gateway  │
                         │  (route table)     │
                         └──────┬─────────────┘
                                │
             ┌──────────────────┼─────────────────────┐
             ▼                  ▼                     ▼
   ┌─────────────────┐  ┌───────────────┐    ┌───────────────────┐
   │ Legacy monolith │  │ New service A │    │ New service B     │
   │ (shrinking)     │  │ (e.g. /orders)│    │ (e.g. /catalog)   │
   └─────────────────┘  └───────────────┘    └───────────────────┘
```

**Sketch (FastAPI façade routing by path).**

```python
from typing import Final
from fastapi import FastAPI, Request
from fastapi.responses import Response
import httpx


# Route table: source of truth for "what the strangler has eaten so far."
ROUTE_TABLE: Final[dict[str, str]] = {
    # Path prefix → upstream
    "/orders":     "http://orders-svc.internal",   # migrated
    "/catalog":    "http://catalog-svc.internal",  # migrated
    "/recommend":  "http://recs-svc.internal",     # migrated this sprint
    # Everything else falls through to the legacy.
}
LEGACY_BACKEND: Final = "http://legacy-monolith.internal"


app = FastAPI()


def _resolve_upstream(path: str) -> str:
    for prefix, upstream in ROUTE_TABLE.items():
        if path.startswith(prefix):
            return upstream
    return LEGACY_BACKEND


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(full_path: str, request: Request) -> Response:
    upstream = _resolve_upstream(f"/{full_path}")
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.request(
            method=request.method,
            url=f"{upstream}/{full_path}",
            headers={k: v for k, v in request.headers.items() if k.lower() != "host"},
            content=await request.body(),
            params=dict(request.query_params),
        )
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers={k: v for k, v in resp.headers.items() if k.lower() not in {"content-encoding", "transfer-encoding"}},
    )
```

**Common progressions.**

- _Storefront._ Migrate read-only product pages first (cacheable, easy to
  verify); then cart; then checkout (the hard one).
- _Auth._ Migrate session validation first; then login flow; then password reset
  and MFA.
- _Database._ The hardest case — see Microsoft's database-strangler diagram.
  Stage: (1) new system reads/writes legacy DB, (2) shadow-write to new DB, (3)
  reads cut over, (4) writes cut over, (5) legacy DB retired.

**When NOT to use / What it costs.**

- _Small / trivial systems._ If the rewrite is two engineer-weeks, just rewrite
  it.
- _Cannot intercept calls._ Strangler requires a façade. If clients hit the
  legacy directly via a hard-coded URL you cannot change, the pattern is not
  available.
- _Façade becomes a SPOF._ The façade is critical-path; treat it like a load
  balancer (HA, monitoring, no business logic in it).
- _Migration drags forever._ The dangerous failure mode is "we got 60% done and
  stopped" — now you operate _both_ systems forever. Set an explicit retirement
  date for the legacy.

**Real-world examples.**

- _Shopify, ~2019._ Storefront monolith → modular monolith → service extraction.
- _Etsy, 2013–2020._ PHP monolith → service-oriented architecture via
  incremental extraction.
- _British Gas, 2010s._ Mainframe billing strangled by JVM services; Sam
  Newman's _Monolith to Microservices_ uses this as a recurring case.

**References.**

- Fowler, M., _StranglerFigApplication_, martinfowler.com/bliki, 2004.
- Newman, S., _Monolith to Microservices_, O'Reilly, 2020.
- Microsoft Azure, _Strangler Fig Pattern_,
  learn.microsoft.com/azure/architecture/patterns/strangler-fig.

---

## Choreography vs Orchestration

**What it is / Intent.** Two ways to coordinate a multi-service workflow.

- _Choreography._ Each service publishes events; downstream services subscribe
  and react. No central coordinator. The workflow is _implicit_ in the event
  topology.
- _Orchestration._ A dedicated orchestrator service tells each participant what
  to do next. The workflow is _explicit_ in one place.

This is deeper than the question of synchronous vs asynchronous communication
(see `communication.md` if it exists in your tree). It is about _who owns the
workflow_.

**Choreography — sketch.**

```python
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class OrderPlaced:
    order_id: str
    customer_id: str
    total_cents: int


@dataclass(frozen=True, slots=True)
class PaymentAuthorized:
    order_id: str
    auth_code: str


class EventBus(Protocol):
    async def publish(self, topic: str, event: object) -> None: ...


# Each service knows only its own input and output events.
class OrderService:
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    async def place(self, order_id: str, customer_id: str, total_cents: int) -> None:
        await self._bus.publish("order.placed", OrderPlaced(order_id, customer_id, total_cents))


class PaymentService:
    """Reacts to OrderPlaced; emits PaymentAuthorized."""

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    async def on_order_placed(self, event: OrderPlaced) -> None:
        # ... charge ...
        await self._bus.publish("payment.authorized", PaymentAuthorized(event.order_id, "auth_xyz"))
```

The shipment service then subscribes to `payment.authorized`, and so on. Each
service sees only its own slice. _No one place documents the workflow._

**Orchestration — sketch.**

```python
from enum import StrEnum
from typing import Final, Protocol


class OrderState(StrEnum):
    PLACED = "placed"
    PAID = "paid"
    SHIPPED = "shipped"
    COMPLETED = "completed"
    FAILED = "failed"


class PaymentClient(Protocol):
    async def charge(self, order_id: str, amount_cents: int) -> str: ...
    async def refund(self, auth_code: str) -> None: ...


class ShipmentClient(Protocol):
    async def book(self, order_id: str) -> str: ...
    async def cancel(self, shipment_id: str) -> None: ...


class OrderOrchestrator:
    """One place owns the workflow. Each step knows the next step."""

    def __init__(self, payment: PaymentClient, shipment: ShipmentClient) -> None:
        self._payment: Final = payment
        self._shipment: Final = shipment

    async def run(self, order_id: str, total_cents: int) -> OrderState:
        try:
            auth_code = await self._payment.charge(order_id, total_cents)
        except Exception:
            return OrderState.FAILED
        try:
            await self._shipment.book(order_id)
        except Exception:
            await self._payment.refund(auth_code)  # compensating transaction
            return OrderState.FAILED
        return OrderState.COMPLETED
```

**When to choose which.**

| Choreography                                                    | Orchestration                                            |
| --------------------------------------------------------------- | -------------------------------------------------------- |
| Few participants; flow is "one notifies the rest"               | Many participants; flow has branches and conditionals    |
| Loosely coupled teams; each owns its slice                      | Strong workflow ownership (a "workflow team")            |
| Domain events are first-class concepts                          | Workflow steps are first-class concepts                  |
| You can tolerate "the workflow lives in the event bus topology" | You need to read the workflow in one file                |
| Compensation is local (each service handles its own undo)       | Compensation is centralized (orchestrator triggers undo) |

**The classic failure mode of choreography.** Six months in, no one knows what
happens when service C is down — does B retry, dead-letter, or alert? The answer
is "depends who you ask," because the workflow lives in nobody's head
completely. Add an orchestrator-level dashboard or migrate to orchestration when
the workflow sprouts more than ~3 conditional branches.

**The classic failure mode of orchestration.** The orchestrator becomes a "god
service" holding all business logic; every change requires deploying it;
participants become anemic. Mitigation: keep the orchestrator small (state
machine + step dispatch), keep domain logic in the participants.

**Real-world examples.**

- _Choreography._ Uber's earlier microservices; Netflix's notification system.
- _Orchestration._ Netflix Conductor; Uber Cadence / Temporal; AWS Step
  Functions.

**References.**

- Richardson, C., _Microservices Patterns_, Manning, 2018 — ch. 4 (Sagas).
- microservices.io, _Pattern: Saga_.
- Temporal docs, _Workflow patterns_.

---

## Service Discovery

**What it is / Intent.** A way for clients to find the network address of a
service that moves around (containers come and go, IPs change, replicas scale).
Two flavors.

- _Server-side discovery._ A load balancer in front of the service. Client knows
  only the LB's address. AWS ELB, GCP Internal LB, k8s `Service`.
- _Client-side discovery._ Client queries a registry, picks an instance,
  connects directly. Consul, Eureka, etcd, Zookeeper.

**Push vs pull.** A registry can _push_ updates to clients (long-lived gRPC
streams, xDS), or clients can _pull_ periodically. Push is fresher but harder to
operate; pull is simpler but eventually consistent.

**When to reach for it.**

- _Server-side._ Default for stateless HTTP services on cloud platforms — let
  the platform's LB handle it.
- _Client-side._ When you need direct connections (bypassing an LB hop),
  advanced load balancing (P2C, EWMA), or per-call routing decisions (canary,
  A/B).

**Sketch (Consul-like client-side registry).**

```python
import asyncio
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Final


@dataclass(frozen=True, slots=True)
class Endpoint:
    host: str
    port: int
    healthy: bool = True


class ServiceRegistry(Protocol):
    async def list(self, service_name: str) -> list[Endpoint]: ...
    async def watch(self, service_name: str, on_change: Callable[[list[Endpoint]], None]) -> None: ...


@dataclass
class ClientSideDiscovery:
    """Cache endpoints locally; refresh on watch events."""

    registry: ServiceRegistry
    service_name: str
    _cache: list[Endpoint] = field(default_factory=list, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    async def start(self) -> None:
        self._cache = await self.registry.list(self.service_name)
        await self.registry.watch(self.service_name, self._on_change)

    def _on_change(self, endpoints: list[Endpoint]) -> None:
        self._cache = endpoints

    async def pick(self) -> Endpoint:
        async with self._lock:
            healthy = [e for e in self._cache if e.healthy]
            if not healthy:
                raise RuntimeError(f"no healthy endpoints for {self.service_name}")
            return random.choice(healthy)  # noqa: S311 — random is fine for LB
```

**When NOT to use / What it costs.**

- _Client-side discovery in a polyglot fleet._ You will write the same registry
  client in N languages. A sidecar (Envoy) that does the discovery on behalf of
  every service is usually better.
- _Stale registry._ If the registry is slow to mark instances unhealthy, clients
  keep routing to dead replicas. Always pair with health checks at the client
  (active probe
    - outlier ejection).

**Real-world examples.**

- _Kubernetes Service + kube-proxy_ — server-side discovery via virtual IPs.
- _AWS Cloud Map / Consul_ — DNS or API-based registry.
- _Netflix Eureka_ — historical client-side discovery (now mostly Envoy/Istio).

**References.**

- Newman, S., _Building Microservices_, 2nd ed., 2021 — ch. 5.
- Richardson, C., _Microservices Patterns_, 2018 — ch. 3.

---

## Configuration as a Service

**What it is / Intent.** Externalize configuration (feature flags, limits,
routing rules, kill switches) into a service or store, separate from code.
Changes deploy without rebuilding the application.

**When to reach for it / How it manifests.**

- A config change should not require a redeploy (feature flag flip, kill
  switch).
- Different environments (dev/staging/prod) need different values.
- Multi-tenant systems need per-tenant overrides.
- An incident needs an immediate behavior change (raise a quota, disable a
  feature).

**Sketch (Pydantic Settings + remote refresh).**

```python
import asyncio
from collections.abc import Awaitable, Callable
from typing import Annotated, Final, Self

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FeatureFlags(BaseModel):
    new_checkout_enabled: bool = False
    max_items_per_cart: Annotated[int, Field(ge=1, le=1000)] = 50
    payment_provider: str = "stripe"


class AppConfig(BaseSettings):
    """Static-at-startup config from env / file."""

    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env")
    db_dsn: str
    redis_url: str
    flag_refresh_interval_s: float = 30.0


class FlagSource(Protocol):
    async def fetch(self) -> FeatureFlags: ...


class DynamicFlags:
    """Hot-reloadable flags. Background task refreshes from a remote source."""

    def __init__(self, source: FlagSource, refresh_interval_s: float) -> None:
        self._source: Final = source
        self._refresh_interval_s: Final = refresh_interval_s
        self._current: FeatureFlags = FeatureFlags()
        self._task: asyncio.Task[None] | None = None

    @property
    def current(self) -> FeatureFlags:
        return self._current

    async def start(self) -> None:
        self._current = await self._source.fetch()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self._refresh_interval_s)
            try:
                self._current = await self._source.fetch()
            except Exception:  # noqa: BLE001 — keep last-known-good
                continue
```

**When NOT to use / What it costs.**

- _Critical-path config that must be deterministic per deploy._ Database DSN,
  encryption keys, schema versions — these belong in env or secrets, not in a
  flag service.
- _No fallback when the flag service is down._ Every feature flag must have a
  default baked in. A flag service outage that takes down dependent services is
  a self-inflicted SPOF.
- _Excessive flag count._ "Permanent" flags accumulate; clean them up after
  rollouts. See "feature toggle hygiene" in _Continuous Delivery_.

**Real-world examples.**

- _LaunchDarkly_ — managed feature flag service with SDK + streaming updates.
- _Unleash_ — open-source feature flags.
- _AWS AppConfig + Parameter Store_ — managed dynamic config.
- _Etsy's `etcd`-backed flags_, written up on Code as Craft.

**References.**

- Microsoft Azure, _External Configuration Store Pattern_.
- Hodgson, P., _Feature Toggles (aka Feature Flags)_, martinfowler.com.
- Humble, J., Farley, D., _Continuous Delivery_, Addison-Wesley, 2010.

---

## Asynchronous Request-Reply

**What it is / Intent.** A long-running operation cannot complete in the
request/response window. The server returns immediately with a _handle_ (a
polling URL or callback URL), and the client checks back later for the result.

**When to reach for it / How it manifests.**

- The work takes more than a few seconds: report generation, image transcoding,
  ML inference, large data exports.
- The client cannot accept callbacks (browser behind a NAT, a webhook target
  that's firewalled).
- Synchronous retries on the original request would duplicate work.

**Protocol shape (Microsoft Azure / RFC-aligned).**

```
1. POST /jobs                      → 202 Accepted
                                     Location: /jobs/{id}
                                     Retry-After: 5

2. GET /jobs/{id}  (every ~5s)     → 200 OK, body: {status: "running"}
                                     ...
                                     → 303 See Other
                                       Location: /reports/{id}

3. GET /reports/{id}               → 200 OK, body: <result>
```

**Sketch (FastAPI: kick off + poll).**

```python
import uuid
from datetime import UTC, datetime
from typing import Final
from enum import StrEnum

from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class JobState(BaseModel):
    job_id: str
    status: JobStatus
    created_at: datetime
    last_updated_at: datetime
    percent_complete: int = 0
    result_url: str | None = None
    error: dict[str, object] | None = None


_JOB_STORE: Final[dict[str, JobState]] = {}


app = FastAPI()


@app.post("/reports", status_code=status.HTTP_202_ACCEPTED)
async def kick_off(request: BaseModel, response: Response) -> JobState:
    job_id = uuid.uuid4().hex
    state = JobState(
        job_id=job_id,
        status=JobStatus.PENDING,
        created_at=datetime.now(UTC),
        last_updated_at=datetime.now(UTC),
    )
    _JOB_STORE[job_id] = state
    # Enqueue real work onto a queue (Celery/SQS/Kafka).
    response.headers["Location"] = f"/jobs/{job_id}"
    response.headers["Retry-After"] = "5"
    return state


@app.get("/jobs/{job_id}")
async def status_endpoint(job_id: str, response: Response) -> JobState | None:
    state = _JOB_STORE.get(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="unknown job")
    if state.status is JobStatus.SUCCEEDED and state.result_url is not None:
        response.headers["Location"] = state.result_url
        response.status_code = status.HTTP_303_SEE_OTHER
        return None
    return state
```

**When NOT to use / What it costs.**

- _Real-time client._ Sockets/SSE/WebSockets are better for "tell me as soon as
  it's done." Polling is for clients that cannot accept push.
- _Polling storm._ If 10,000 clients poll every second, the status endpoint is
  now your most-trafficked endpoint. Use `Retry-After`, exponential client-side
  backoff, and serve from cache.
- _No idempotency on submission._ If POST `/reports` retries on transient
  network failure, you may enqueue the same job twice. Accept an
  `Idempotency-Key`.

**Real-world examples.**

- _AWS S3 multipart uploads_ — async + polling.
- _AWS Athena queries_ — `StartQueryExecution` returns ID; poll
  `GetQueryExecution`.
- _GitHub Actions workflow runs_ — job + status URL.

**References.**

- Microsoft Azure, _Asynchronous Request-Reply Pattern_.
- RFC 9457 (Problem Details for HTTP APIs).
- IETF draft-ietf-httpapi-idempotency-key-header.

---

## Claim Check

**What it is / Intent.** A messaging system has limits on payload size (SQS: 256
KB, Kafka: typically configured ≤ 1 MB). Large payloads (images, video, ML model
artifacts, multi-MB JSON blobs) bypass the broker: store the payload in object
storage; send only a _claim_ (URL or key) in the message. Consumers fetch the
payload from object storage on the way to processing.

**When to reach for it / How it manifests.**

- Message size exceeds broker limits.
- Large messages are degrading broker throughput.
- Most subscribers don't need the full payload (only ~10% will fetch it).
- Sensitive data should not pass through the broker (centralized access via the
  blob store with KMS-managed keys).

**Deployment topology.**

```
   Producer ──── 1. PUT large object  ────▶ Object store (S3 / GCS / Blob)
        │                                          │
        │ 2. publish small message with claim      │
        ▼                                          │
   Message broker (SQS / Kafka / Service Bus)     │
        │                                          │
        │ 3. consume small message                 │
        ▼                                          │
   Consumer ──── 4. GET by claim ─────────────────┘
```

**Sketch (S3 + SQS with strict typing).**

```python
import json
import uuid
from typing import Final, Protocol

import aioboto3
from pydantic import BaseModel


class LargePayload(BaseModel):
    user_id: str
    raw_csv: str  # potentially MBs


class ClaimEnvelope(BaseModel):
    claim_bucket: str
    claim_key: str
    content_type: str
    size_bytes: int


class ObjectStore(Protocol):
    async def put(self, bucket: str, key: str, body: bytes, content_type: str) -> None: ...
    async def get(self, bucket: str, key: str) -> bytes: ...


class MessageBus(Protocol):
    async def publish(self, queue: str, body: str) -> None: ...


CLAIM_BUCKET: Final = "internal-claim-checks"


class ClaimCheckProducer:
    def __init__(self, store: ObjectStore, bus: MessageBus) -> None:
        self._store: Final = store
        self._bus: Final = bus

    async def publish(self, queue: str, payload: LargePayload) -> None:
        body = payload.model_dump_json().encode("utf-8")
        key = f"{uuid.uuid4().hex}.json"
        await self._store.put(CLAIM_BUCKET, key, body, "application/json")
        envelope = ClaimEnvelope(
            claim_bucket=CLAIM_BUCKET, claim_key=key,
            content_type="application/json", size_bytes=len(body),
        )
        await self._bus.publish(queue, envelope.model_dump_json())


class ClaimCheckConsumer:
    def __init__(self, store: ObjectStore) -> None:
        self._store: Final = store

    async def handle(self, message_body: str) -> LargePayload:
        envelope = ClaimEnvelope.model_validate_json(message_body)
        raw = await self._store.get(envelope.claim_bucket, envelope.claim_key)
        return LargePayload.model_validate_json(raw)
```

**When NOT to use / What it costs.**

- _Small messages._ Two round-trips (broker + object store) is overhead for a 1
  KB message. Apply _conditionally_ — switch to claim-check only when payload
  exceeds a threshold.
- _Object-store eventual consistency._ If the consumer fires _before_ the upload
  finalizes, the GET fails. S3 is now strongly consistent (since 2020); older
  systems and other stores are not. Verify.
- _No cleanup._ Claim objects accumulate. Set a lifecycle policy (S3: delete
  after N days) or add explicit deletion in the consumer.
- _Permission asymmetry._ Producer can write but not delete; consumer can read
  but not delete; nobody runs the cleanup. Use lifecycle rules.

**Real-world examples.**

- _AWS SQS + S3 Extended Client_ — official SDK abstraction.
- _Kafka with object storage_ — message key + S3 URL pattern; some teams use
  `kafka-storage-extender`.
- _Azure Service Bus + Blob Storage_ — Microsoft's reference implementation.

**References.**

- Microsoft Azure, _Claim-Check Pattern_.
- Hohpe, G., Woolf, B., _Enterprise Integration Patterns_, 2003 — § Claim Check.

---

## Compensating Transaction

**What it is / Intent.** A distributed workflow cannot use traditional ACID
transactions across services. Instead, each step is committed locally; if a
later step fails, the earlier steps are _undone_ by explicit _compensating
actions_. Together they form a _saga_. (See `distributed.md` for the full saga
treatment; this entry focuses on the compensation half.)

**When to reach for it / How it manifests.**

- Booking a trip: reserve flight → reserve hotel → reserve car. If the car
  fails, release the hotel, release the flight.
- Payment + shipment: charge card → ship item. If shipment fails, refund the
  card.
- Provisioning: create tenant → seed data → enable login. If seeding fails,
  delete the tenant.

**Sketch.**

```python
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Final


@dataclass(frozen=True, slots=True)
class Step[T]:
    name: str
    forward: Callable[[], Awaitable[T]]
    compensate: Callable[[T], Awaitable[None]]


@dataclass
class Saga:
    """Run a series of steps. On failure, run compensations in reverse."""

    name: str
    _executed: list[tuple[Step[object], object]] = field(default_factory=list, init=False)

    async def run(self, steps: list[Step[object]]) -> None:
        try:
            for step in steps:
                result = await step.forward()
                self._executed.append((step, result))
        except Exception:
            await self._compensate()
            raise

    async def _compensate(self) -> None:
        # Reverse order: most recent action undone first.
        for step, result in reversed(self._executed):
            try:
                await step.compensate(result)
            except Exception:  # noqa: BLE001 — compensation must be best-effort logged
                # Real impl: log + alert + send to a "manual reconciliation" queue.
                continue
```

**Compensation must be idempotent.** A compensation can itself fail and be
retried. Refunding the same charge twice must be safe (`idempotency_key` on the
refund).

**Compensation is not always rollback.** Sometimes the right "undo" is a forward
action: a refund (not a database rollback), a cancellation email (not a delete),
a status flip to "voided" (not a row removal). Pick the action that's correct
for the _business_, not the one that's textbook for the _database_.

**When NOT to use / What it costs.**

- _Single service / single DB._ Use a real transaction.
- _Compensations are impossible._ "We sent the SMS." There is no undo. Then the
  workflow must be designed so that the irreversible step is _last_ and only
  attempted when the prior steps succeeded.
- _Compensation cascades to other workflows._ A refund triggers an accounting
  update triggers a tax recalculation. If the cascade is unbounded, the workflow
  is too coupled.

**Real-world examples.**

- _AWS Step Functions_ — built-in catch + compensation.
- _Temporal / Cadence_ — sagas are first-class.
- _Stripe billing reversals_ — refund as compensation for charge.

**References.**

- Garcia-Molina, H., Salem, K., _Sagas_, ACM SIGMOD 1987.
- Richardson, C., _Microservices Patterns_, ch. 4.
- Microsoft Azure, _Compensating Transaction Pattern_.

---

## Throttling Gateway

**What it is / Intent.** A _global_ rate limiter at the ingress edge of the
system, applied per tenant / per user / per API key, before requests reach
individual services. Different from per-service `Bulkhead` (in
`reliability.md`): the Bulkhead isolates concurrency _within_ a service; the
Throttling Gateway caps _traffic into_ the platform.

**When to reach for it / How it manifests.**

- Multi-tenant SaaS — one noisy tenant must not starve others.
- Public APIs — abuse, DDoS, runaway clients must be capped before they reach
  internals.
- Cost protection — every request costs something (LLM tokens, GPU time); a
  runaway client is a runaway bill.

**Deployment topology.**

```
   Clients ──▶ Gateway / Edge ──▶ Per-tenant rate-limit check ──▶ Services
                  │                  (Redis token bucket)
                  ├── Rejected with 429 + Retry-After
                  │
                  └── Approved → forwarded
```

**Sketch (Redis-backed per-tenant token bucket as FastAPI middleware).**

```python
import time
from typing import Final

from fastapi import FastAPI, HTTPException, Request, Response, status
from redis.asyncio import Redis


# Lua script for atomic refill + check + decrement (Redis cluster-safe).
TOKEN_BUCKET_LUA: Final = """\
local key = KEYS[1]
local now = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local capacity = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])

local data = redis.call("HMGET", key, "tokens", "ts")
local tokens = tonumber(data[1]) or capacity
local ts = tonumber(data[2]) or now

local elapsed = math.max(0, now - ts)
tokens = math.min(capacity, tokens + elapsed * rate)

if tokens < cost then
  redis.call("HMSET", key, "tokens", tokens, "ts", now)
  redis.call("EXPIRE", key, math.ceil(capacity / rate) * 2)
  return {0, tokens}
end

tokens = tokens - cost
redis.call("HMSET", key, "tokens", tokens, "ts", now)
redis.call("EXPIRE", key, math.ceil(capacity / rate) * 2)
return {1, tokens}
"""


class ThrottleGateway:
    """Per-tenant token bucket; 429 with Retry-After on rejection."""

    def __init__(self, redis: Redis, *, rate_per_s: float, capacity: float) -> None:
        self._redis: Final = redis
        self._rate_per_s: Final = rate_per_s
        self._capacity: Final = capacity
        self._lua = redis.register_script(TOKEN_BUCKET_LUA)

    async def admit(self, tenant_id: str, *, cost: float = 1.0) -> tuple[bool, float]:
        result = await self._lua(
            keys=[f"throttle:{tenant_id}"],
            args=[time.time(), self._rate_per_s, self._capacity, cost],
        )
        ok_int, remaining = result
        return bool(ok_int), float(remaining)


def install(app: FastAPI, gateway: ThrottleGateway) -> None:
    @app.middleware("http")
    async def throttle(request: Request, call_next):
        tenant = request.headers.get("x-tenant-id", "anonymous")
        admitted, remaining = await gateway.admit(tenant)
        if not admitted:
            retry_after = max(1, int((1.0 / gateway._rate_per_s)))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="rate limit exceeded",
                headers={"Retry-After": str(retry_after)},
            )
        response: Response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = f"{remaining:.0f}"
        return response
```

**When NOT to use / What it costs.**

- _Tiny services that don't face the internet._ Internal-only services usually
  don't need a throttling gateway; a local circuit breaker / bulkhead suffices.
- _Local-only counters._ In a fleet of N gateway replicas, local counters give
  you Nx the configured limit. Use Redis (with Lua for atomicity) or a dedicated
  rate-limit service.
- _Never returning Retry-After._ Without it, well-behaved clients retry too
  aggressively and badly-behaved clients don't care.
- _Static limits in dynamic load._ Provide a path to raise/lower limits in real
  time (Configuration as a Service); a static config baked into a deploy is too
  slow during an incident.

**Real-world examples.**

- _AWS API Gateway usage plans + throttling_ — per-API-key buckets.
- _Cloudflare WAF rate-limiting rules_.
- _Stripe API_ — published per-account rate limits with `Retry-After`.

**References.**

- Microsoft Azure, _Throttling Pattern_.
- Brooker, M., _Caution: decreasing latency may increase error rate_,
  brooker.co.za.

---

## Bulkheading at the Infrastructure Level

**What it is / Intent.** The Bulkhead pattern applied at infrastructure
granularity: separate clusters, separate VPCs, separate availability zones,
separate cells. The in-process Bulkhead (`reliability.md`) caps _concurrency
within a process_; the infrastructure Bulkhead caps _blast radius across the
platform_.

**When to reach for it.**

- A bad deploy must not take down 100% of customers.
- A "noisy neighbor" customer must not starve other customers.
- A region-wide failure (AZ outage) must not take down the whole product.

**Forms.**

| Layer                   | What's isolated                               | Tools                                            |
| ----------------------- | --------------------------------------------- | ------------------------------------------------ |
| **Process**             | Threads / connections / sockets               | semaphores, separate executors                   |
| **Pod / VM**            | CPU / memory cgroups                          | k8s `resources.requests/limits`, dedicated nodes |
| **Cluster / namespace** | Control plane, networking                     | separate k8s clusters, namespaces                |
| **AZ**                  | Power, network fabric                         | multi-AZ deploy + zone-aware LB                  |
| **Region**              | Whole geography                               | multi-region active-active or active-standby     |
| **Cell**                | Functional partition (per tenant / per shard) | see below                                        |

**Sketch (k8s pod-level isolation between request classes).**

```yaml
# Two deployments, same image, different traffic classes — cannot starve each other.
apiVersion: apps/v1
kind: Deployment
metadata: { name: api-interactive }
spec:
    replicas: 8
    template:
        spec:
            containers:
                - name: api
                  image: registry/api:v1
                  env: [{ name: WORKLOAD_CLASS, value: "interactive" }]
                  resources:
                      requests: { cpu: "1", memory: "2Gi" }
                      limits: { cpu: "2", memory: "4Gi" }
---
apiVersion: apps/v1
kind: Deployment
metadata: { name: api-batch }
spec:
    replicas: 4
    template:
        spec:
            containers:
                - name: api
                  image: registry/api:v1
                  env: [{ name: WORKLOAD_CLASS, value: "batch" }]
                  resources:
                      requests: { cpu: "2", memory: "4Gi" }
                      limits: { cpu: "4", memory: "8Gi" }
```

**When NOT to use / What it costs.**

- _Cost._ Isolation costs money: you provision for _peak per partition_, not
  aggregate peak. The benefit is bounded blast radius; the cost is utilization
  that's strictly worse than a single shared pool.
- _Operational complexity._ More clusters → more upgrades, more monitoring, more
  certificates. Only isolate when the blast-radius gain pays for the operational
  tax.

**Real-world examples.**

- _AWS multi-AZ Application Load Balancer_ — zonal isolation by default.
- _Slack's Vitess sharding_ — per-team shards limit blast radius.
- _Salesforce "pods"_ — historical multi-tenant cell isolation.

**References.**

- Newman, S., _Building Microservices_, 2nd ed., ch. 13.
- AWS, _Reducing the Scope of Impact with Cell-Based Architecture_,
  docs.aws.amazon.com.

---

## Cell-Based Architecture

**What it is / Intent.** Partition the entire system into **cells**, where each
cell is a _complete, independent stack_ (load balancer, services, data store)
serving a _subset_ of users. A thin **cell router** sits in front and dispatches
each request to the right cell based on a _partition key_ (customer ID, tenant
ID, region). When a cell breaks, only the customers on that cell are affected.
AWS calls this "the bulkhead pattern at its logical extreme."

**When to reach for it.**

- A bad deploy must affect ≤ 10% of customers, not 100%.
- "Poison pill" requests (a malformed input that crashes a worker) must not
  propagate.
- A specific failure mode (DB corruption, OOM, infinite loop) is contained
  within one cell.
- You can find a _grain_: a partition key that naturally divides the workload
  with minimal cross-cell traffic (per-tenant, per-region, per-resource-id).

**Deployment topology.**

```
                         ┌─────────────────────┐
                         │   Cell Router       │
                         │  (thin, stateless)  │
                         └─────────┬───────────┘
                  ┌────────────────┼────────────────┐
                  ▼                ▼                ▼
          ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
          │   Cell 1    │  │   Cell 2    │  │   Cell N    │
          │ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌─────────┐ │
          │ │ LB      │ │  │ │ LB      │ │  │ │ LB      │ │
          │ │ App     │ │  │ │ App     │ │  │ │ App     │ │
          │ │ Cache   │ │  │ │ Cache   │ │  │ │ Cache   │ │
          │ │ DB      │ │  │ │ DB      │ │  │ │ DB      │ │
          │ └─────────┘ │  │ └─────────┘ │  │ └─────────┘ │
          └─────────────┘  └─────────────┘  └─────────────┘
            customers       customers        customers
            cohort 1        cohort 2         cohort N
```

**Sketch (cell router as routing logic, not infrastructure).**

```python
from dataclasses import dataclass
from typing import Final, Protocol


@dataclass(frozen=True, slots=True)
class Cell:
    cell_id: str
    base_url: str          # e.g. https://cell-04.region.platform.io
    healthy: bool = True


class CellRouter(Protocol):
    def route(self, partition_key: str) -> Cell: ...


@dataclass
class JumpHashCellRouter:
    """Map partition_key → cell via jump consistent hashing.

    Jump hash minimizes cell reassignment when cells are added/removed:
    only ~1/N of keys move when one cell joins.
    """

    cells: list[Cell]

    def route(self, partition_key: str) -> Cell:
        if not self.cells:
            raise RuntimeError("no cells registered")
        idx = self._jump_consistent_hash(self._fnv1a(partition_key), len(self.cells))
        return self.cells[idx]

    @staticmethod
    def _fnv1a(s: str) -> int:
        h = 0xCBF29CE484222325
        for byte in s.encode("utf-8"):
            h ^= byte
            h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
        return h

    @staticmethod
    def _jump_consistent_hash(key: int, num_buckets: int) -> int:
        b = -1
        j = 0
        while j < num_buckets:
            b = j
            key = (key * 2862933555777941757 + 1) & 0xFFFFFFFFFFFFFFFF
            j = int((b + 1) * ((1 << 31) / ((key >> 33) + 1)))
        return b
```

**Picking a partition key.** This is the single most important design decision:

- _Customer ID._ Most common. One customer's poison pill stays in their cell.
- _Tenant ID._ For multi-tenant SaaS.
- _Region._ For regulatory/jurisdictional partitioning.
- _Resource ID (rare)._ For systems where resources span customers (e.g. shared
  ledgers).

The grain must align with how the workload naturally divides. Cross-cell calls
are an anti-signal: if 30% of requests cross cells, the partition is wrong.

**Cell router properties.**

- _Thinnest possible._ The router is just a route table + load balancer. No
  business logic, no auth (auth happens in the cell). The router is the system's
  most-loaded service; complexity here is paid for in availability.
- _Stateless or near-stateless._ Cell membership lives in a config store;
  partition-key → cell-id is a deterministic hash or a lookup.
- _Multi-AZ deployment of the router_ — a router outage is a 100% outage.

**When NOT to use / What it costs.**

- _Small systems._ Cell-based architecture pays its way at scale. For a service
  with one database and ten thousand users, it is vast over-engineering.
- _Cross-cell hot keys._ If "the global feed" is a thing, you're back to a
  shared bottleneck. Cells work when each cell is genuinely independent.
- _Operational cost._ N cells × every-team's-deploy = N × the work. You amortize
  this with strong automation; without that, cell-based architecture eats your
  team's time.
- _Resharding cost._ Moving a customer between cells is the trickiest operation
  — schema-aware, online migration. Plan it from day one.

**Real-world examples.**

- _AWS Route 53 zonal endpoints, Route 53 ARC_ — cell-based isolation as a
  building block.
- _AWS Lambda_ — cells as the deployment substrate (documented in builders'
  library).
- _Slack's Vitess shards_ — cell-like isolation per team.
- _Stripe's API_ — multiple production "cells" with separate failure domains.

**References.**

- AWS, _Reducing the Scope of Impact with Cell-Based Architecture_,
  docs.aws.amazon.com.
- Vogels, W., _Cell-based architecture_, allthingsdistributed.com, 2023.
- Lampson, B., _Hints for Computer System Design_, 1983 — partitioning
  principle.

---

## Review Checklist

For any PR that adds or changes a structural pattern across services:

1. **Boundary.** Where does this concern live (in-process library, sidecar,
   ambassador, shared service)? Is the choice documented?
2. **Failure mode.** What happens to dependent services if this pattern's
   component is _down_? Fail open, fail closed, degraded mode?
3. **Scope.** Does this change the blast radius (cell, AZ, cluster)? Is the new
   blast radius smaller, larger, or unchanged?
4. **Backward compatibility.** Is this a strangler-fig step? If yes, is the
   route table versioned and is there a retirement date for the legacy?
5. **Idempotency.** For async-request-reply, claim-check, and saga steps — are
   submissions idempotent (idempotency-key, dedup ID)?
6. **Observability.** Can you tell _which cell / shard / replica_ served a
   request from the logs? If not, debugging will be a nightmare.
7. **Cost.** Is the operational tax paid for by a measurable benefit
   (blast-radius reduction, latency improvement, throughput)?

If two or more answers are "I don't know," the change is too speculative to
merge.

---

## References

**Books.**

- Newman, S., _Building Microservices_, 2nd ed., O'Reilly, 2021.
- Newman, S., _Monolith to Microservices_, O'Reilly, 2020.
- Richardson, C., _Microservices Patterns_, Manning, 2018.
- Kleppmann, M., _Designing Data-Intensive Applications_, O'Reilly, 2017 — chs.
  5–8.
- Burns, B., _Designing Distributed Systems_, O'Reilly, 2018.
- Evans, E., _Domain-Driven Design_, Addison-Wesley, 2003 — ch. 14.
- Hohpe, G., Woolf, B., _Enterprise Integration Patterns_, Addison-Wesley, 2003.
- Beyer, B. et al., _Site Reliability Engineering_, Google / O'Reilly, 2016.

**Papers.**

- Garcia-Molina, H., Salem, K., _Sagas_, ACM SIGMOD 1987.
- Lampson, B., _Hints for Computer System Design_, ACM SOSP 1983.

**Vendor / industry.**

- Microsoft Azure, _Cloud Design Patterns_,
  learn.microsoft.com/azure/architecture/patterns.
- AWS, _Builders' Library_, aws.amazon.com/builders-library.
- AWS, _Reducing the Scope of Impact with Cell-Based Architecture_.
- Werner Vogels, _All Things Distributed_, allthingsdistributed.com.
- Adrian Cockcroft, _Netflix Tech Blog_, netflixtechblog.com.
- microservices.io (Chris Richardson), microservices.io.
- Martin Fowler, _StranglerFigApplication_, martinfowler.com/bliki.
- Marc Brooker, brooker.co.za.
