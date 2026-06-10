# System-Level Reliability Patterns

> Cross-process boundary patterns for production systems: timeouts, retries,
> circuit breakers, bulkheads, rate limiters, idempotency, hedging,
> backpressure, dead-letter handling, and the small set of related controls that
> turn brittle distributed code into something you can run without a pager going
> off every night.

## How to use this file

Treat the patterns below as a **menu**, not a checklist. Most services need
three or four of these, not all of them. Reach for a pattern when its **failure
mode** matches one you have either observed in production or have a credible
reason to fear. If you cannot describe the failure mode in one sentence, you do
not yet have a reason to add the pattern.

Each entry has the same shape: _intent → when to reach for it → strict-typed
sketch → type-safety notes → when not to use → real-world examples →
anti-pattern variant → references._ The sketches use Python 3.13+, `httpx`,
`tenacity`, `pybreaker`, `aiolimiter`, and PEP 695 generics. Every block is
written to target `mypy --strict` and `pyright --strict` with no `Any` and the
annotation-evaluation policy in `SKILL.md` conventions. The `python:typings`
sister skill has the full canonical reference if it is also loaded.

Conventions used in every sketch:

- `Protocol` over `ABC` for boundaries.
- PEP 695 generics — `class Foo[T]:`, never `Generic[T]`.
- PEP 604 unions — `int | None`, never `Optional[int]`; `list[int]`, never
  `List[int]`.
- `Self`, `Final`, `@override`, no `Any`, and the annotation-evaluation policy
  in `SKILL.md` conventions.

---

## The default posture

Anything that crosses a process boundary — network, disk, subprocess, queue,
database — will fail. The job of these patterns is to _contain_ that failure.
The default posture is **fail fast, fail explicitly, recover deliberately**.
Concretely:

- No silent fallbacks. Every degraded path emits a metric.
- No unbounded retries. Every retry has a budget.
- No exception swallowing. Every caught exception is either reraised, logged at
  WARN+, or counted on a metric — usually all three.
- Every remote call has a timeout. Library defaults are almost always "infinity"
  — verify and override.
- Every pattern is **observable**: a counter for outcomes (`ok`, `timeout`,
  `error`, `circuit_open`, `throttled`, `fallback_taken`, `dlq_sent`), and a
  histogram for latency.

If a pattern below cannot be observed, it is not in production yet. Ship the
metric with the pattern.

---

## Timeout

**Intent.** Bound the amount of time a single remote attempt is allowed to run.
Without a timeout, a slow or hung dependency silently consumes caller threads,
connections, sockets, and event-loop slots until the caller itself falls over.

**When to reach for it.**

- Any HTTP, gRPC, database, queue, cache, or subprocess call.
- Any `await` on a coroutine that does I/O.
- Any blocking acquisition of a lock, connection-pool slot, or semaphore that
  could be held by a hung peer.

In short: every remote call. Not "every remote call we suspect of being slow" —
_every_ remote call. The "no library default" rule is non-negotiable: most HTTP,
gRPC, and database client libraries default to no timeout, an absurdly high
timeout, or read-only timeout. Verify and override.

**Sketch.** Strict-typed Python 3.13+:

```python
import asyncio
import httpx
from collections.abc import Awaitable, Callable
from typing import Final, NewType, Self


UserId = NewType("UserId", str)


class Profile:
    def __init__(self, user_id: UserId, display_name: str) -> None:
        self.user_id: Final[UserId] = user_id
        self.display_name: Final[str] = display_name

    @classmethod
    def from_json(cls, payload: dict[str, str]) -> Self:
        return cls(
            user_id=UserId(payload["user_id"]),
            display_name=payload["display_name"],
        )


# Phase-broken timeout. Connect failure, slow read, slow write, and pool
# exhaustion all have different operational signatures.
TIMEOUT: Final[httpx.Timeout] = httpx.Timeout(
    connect=2.0,
    read=5.0,
    write=5.0,
    pool=2.0,
)


async def fetch_profile(client: httpx.AsyncClient, user_id: UserId) -> Profile:
    response = await client.get(f"/users/{user_id}", timeout=TIMEOUT)
    response.raise_for_status()
    return Profile.from_json(response.json())


# Structured-concurrency variant. asyncio.timeout() is the right shape because
# it propagates TimeoutError through the structured boundary cleanly.
async def with_total_deadline[T](
    deadline_s: float,
    op: Callable[[], Awaitable[T]],
) -> T:
    async with asyncio.timeout(deadline_s):
        return await op()
```

**Type-safety notes.** Returning `Self` from `from_json` lets subclasses inherit
the constructor without losing the precise return type — `mypy` and `pyright`
both reject calls that lose covariance. `Final` on the timeout prevents
accidental mutation of a shared module-level config. Do **not** type the timeout
as `int | float | httpx.Timeout`; pin it to `httpx.Timeout`. If a callsite needs
a different shape, write a different timeout — uniformity here is a feature.

**When NOT to use.** There is no "when not to use" for timeouts. The question is
only what value, not whether. The only time you legitimately omit a timeout is
on an inbound long-poll or streaming response that you control end to end and
where the connection will be closed by an explicit signal — and even there you
want a heartbeat.

**Real-world examples.**

- AWS SDKs ship with both a connect (~10s) and read (~50s) timeout, and the
  builders' library explicitly recommends _justifying_ the value rather than
  defaulting to the SDK number for high-volume workloads.
- gRPC deadlines propagate across hops via the `grpc-timeout` header — a hard
  budget the entire call tree shares.
- Postgres' `statement_timeout` is the database-side complement: even if the
  client times out, the server kills the query.

**Anti-pattern variant.**

- "Just bump the timeout." Whenever a timeout fires, the immediate temptation is
  to raise it. Resist. The right move is to measure the dependency's actual
  latency distribution and pick a value at p99 + headroom, _and_ to add retries
  / hedging / circuit-breaking around it. Pushing the timeout to 60s just delays
  the failure and amplifies the resource hold.
- Setting only a `read` timeout. Pool exhaustion (no free connection slot) and
  connect timeouts (TCP SYN never gets SYN/ACK) are different failure modes;
  ignoring them is how a single bad host quietly takes a service down.

**References.**

- Marc Brooker, _Timeouts, Retries, and Backoff with Jitter_, AWS Builders'
  Library.
- Michael Nygard, _Release It!_, 2nd ed., Chapter 5 ("Stability Patterns").

---

## Retry with Exponential Backoff and Full Jitter

**Intent.** Recover from transient failures (brief network blips, leader
elections, rate-limit spikes, SSL handshake glitches) without amplifying load
when the dependency is genuinely overloaded. The combination matters: pure retry
kills the dependency on a bad day; pure backoff kills latency on a good day.

**When to reach for it.**

- The operation is **idempotent** (`GET`, `PUT`, `DELETE`) or has been made
  idempotent via an idempotency key (see below).
- The error is **classifiable** as retryable — typically `5xx`, `429`,
  connection reset, timeout. _Never_ retry a `4xx` (other than `408` and `429`).
- The operation has a **bounded budget**: max attempts × max delay must fit
  inside the caller's own deadline.

**Sketch.** Strict-typed Python 3.13+ using stdlib only, then with `tenacity`:

```python
import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_s: float = 0.2
    cap_s: float = 5.0
    retryable_excs: tuple[type[BaseException], ...] = (
        TimeoutError,
        ConnectionError,
    )


def _full_jitter_delay(policy: RetryPolicy, attempt: int) -> float:
    # AWS Architecture Blog formula. Sample uniformly from [0, capped_exp].
    capped = min(policy.cap_s, policy.base_delay_s * 2 ** (attempt - 1))
    return random.uniform(0.0, capped)


async def with_retry[T](
    policy: RetryPolicy,
    op: Callable[[], Awaitable[T]],
) -> T:
    last_exc: BaseException | None = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return await op()
        except policy.retryable_excs as exc:
            last_exc = exc
            if attempt == policy.max_attempts:
                break
            await asyncio.sleep(_full_jitter_delay(policy, attempt))
    assert last_exc is not None
    raise last_exc
```

Or, with `tenacity` — same shape, less boilerplate, type-safe via decorators:

```python
import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)


WAIT_FULL_JITTER: Final = wait_random_exponential(multiplier=0.2, max=5.0)


async def fetch_with_retry(client: httpx.AsyncClient, url: str) -> bytes:
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=WAIT_FULL_JITTER,
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        reraise=True,
    ):
        with attempt:
            response = await client.get(url)
            response.raise_for_status()
            return response.content
    raise RuntimeError("unreachable")
```

**Why "full jitter" wins.** The four common backoff shapes, in increasing order
of robustness against thundering herds:

1. **No jitter, fixed delay.** Worst. Every retrying client retries at exactly
   the same wall-clock instant; the dependency is hit by a synchronous wave on
   every cycle.
2. **Exponential backoff, no jitter.** Better but still synchronized:
   `delay = base * 2 ** attempt`. The wave gets longer between retries but stays
   a wave.
3. **Equal jitter** (half deterministic, half random):
   `delay = capped/2 + random(0, capped/2)`. Reduces collisions but keeps a
   floor.
4. **Full jitter:** `delay = random(0, capped)`. Spreads retries uniformly
   across the window; on average each retry sees only 1/N of the synchronized
   load. AWS's measurement showed full jitter as the sweet spot for client work
   and server pressure.
5. **Decorrelated jitter:** `delay = min(cap, random(base, prev * 3))`. AWS
   originally recommended this for write-heavy workloads. Subsequent analysis
   (Thom Wright, 2024) shows it suffers from clamping at the cap — once
   `prev * 3 > cap`, you get only a 1/3 chance of jitter on a given retry, so in
   practice **full jitter is the safer default** unless you have a specific
   reason to pick decorrelated.

**Retry budget.** A retry policy without a budget is an outage amplifier. Define
both:

- **Per-call budget**: `max_attempts × cap_s ≤ caller_deadline`. If the outer
  caller will time out at 10s and your retry policy can sleep 15s before its
  third attempt, the retry effort is wasted _and_ you delay surfacing the error.
- **Aggregate budget** (Google SRE workbook): retries are limited to a small
  fraction (e.g. 10%) of the request rate. Implemented as a "retry token bucket"
  — every successful request adds a token, every retry consumes one. When the
  bucket empties, retries stop _even if individual retries would be legal_.
  Prevents a fully-broken downstream from amplifying load by retry factor.

**Idempotency precondition.** Retry only when one of the following is true:

- The HTTP method is intrinsically idempotent (`GET`, `PUT`, `DELETE`, `HEAD`,
  `OPTIONS`).
- The operation is non-mutating.
- The operation accepts an idempotency key the server uses to dedupe (see
  [idempotency-keys](#idempotency-keys)).

**Type-safety notes.** Generic `[T]` propagates the operation's return type to
the wrapper, so callers retain full inference. `tuple[type[BaseException], ...]`
rather than `list[...]` because the policy is frozen and we want covariance over
a fixed shape — `mypy --strict` will reject mutating `retryable_excs` after
construction.

**When NOT to use.**

- Non-idempotent writes without an idempotency key.
- 4xx errors (validation, auth, not-found) — the next attempt will give the same
  answer.
- Inside a tight loop where the caller is itself retrying. Retry at exactly one
  layer; nesting compounds (3 layers × 3 attempts = 27× downstream).

**Real-world examples.**

- AWS SDK (v2) ships with full-jitter exponential backoff, capped at 20s, 3
  attempts standard / 7 attempts adaptive.
- Stripe API: clients are encouraged to retry with exponential backoff, with
  Stripe's idempotency keys preventing dupes.
- Google Cloud SDK: full-jitter exponential backoff is the default in
  google-api-core.

**Anti-pattern variant.**

- _Retry-without-budget_: `while True: try / except: sleep(1)`. Hammers a
  failing dependency, prevents recovery, looks fine in code review until you
  take down a downstream.
- _Retry-on-Exception_: catching `Exception` rather than a classified set
  silently retries genuine bugs (a `ValueError` from your own code) along with
  the real transient failures.
- _Lockstep retries_: same delay across all clients (no jitter). The retry storm
  becomes the outage.

**References.**

- Marc Brooker, _Exponential Backoff and Jitter_, AWS Architecture Blog, 2015.
- _Site Reliability Engineering_ (Google), Chapter 22 ("Addressing Cascading
  Failures") on retry budgets.
- Thom Wright, _The problem with decorrelated jitter_, 2024.

---

## Circuit Breaker

**Intent.** When a dependency is broken — not slow, not flaky, _broken_ — stop
calling it. Calls that will fail anyway are pure cost: they pin caller threads,
fill connection pools, prevent the downstream from recovering, and slow your own
error-handling path. The breaker fails fast on the caller side and probes
periodically to see when the downstream is healthy again.

**When to reach for it.**

- A downstream dependency that you cannot replace at runtime and whose failure
  would otherwise occupy caller resources for the full timeout.
- A downstream that, when failing, cannot recover under load (a database pegged
  at 100% CPU; a service whose dead-letter queue is overflowing).
- Any cross-process call where you have a `(service, operation)` granularity
  fine enough that one bad endpoint shouldn't poison the others.

**Sketch.** Strict-typed Python 3.13+:

```python
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Self


class BreakerState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpen(Exception):
    """Raised by a breaker that refuses a call because it is open."""


@dataclass(slots=True)
class CircuitBreaker:
    failure_threshold: int
    cooldown_s: float
    state: BreakerState = BreakerState.CLOSED
    failures: int = 0
    opened_at: float = field(default=0.0)

    def _allow(self) -> bool:
        match self.state:
            case BreakerState.CLOSED:
                return True
            case BreakerState.OPEN:
                if time.monotonic() - self.opened_at >= self.cooldown_s:
                    self.state = BreakerState.HALF_OPEN
                    return True
                return False
            case BreakerState.HALF_OPEN:
                return True

    def _on_success(self) -> None:
        self.state = BreakerState.CLOSED
        self.failures = 0

    def _on_failure(self) -> None:
        self.failures += 1
        if (
            self.state is BreakerState.HALF_OPEN
            or self.failures >= self.failure_threshold
        ):
            self.state = BreakerState.OPEN
            self.opened_at = time.monotonic()

    async def call[T](self, op: Callable[[], Awaitable[T]]) -> T:
        if not self._allow():
            raise CircuitOpen
        try:
            result = await op()
        except Exception:
            self._on_failure()
            raise
        self._on_success()
        return result

    @classmethod
    def with_defaults(cls) -> Self:
        return cls(failure_threshold=20, cooldown_s=30.0)
```

For production use, prefer a battle-tested library:

- **`pybreaker`** — synchronous, classic implementation; Redis state-store
  add-on lets multiple processes share a breaker.
- **`purgatory`** — async-native, integrates cleanly with `httpx`.
- **`circuitbreaker`** — small decorator-based library, good for prototypes.

**State machine.**

- **Closed** — normal operation. Count failures in a rolling window. If the
  failure rate exceeds the threshold (e.g. ≥50% of ≥20 calls in 10s, or ≥N
  consecutive failures), trip to **Open**.
- **Open** — all calls fail fast with `CircuitOpen`. After the cooldown,
  transition to **Half-Open**.
- **Half-Open** — allow a small number of _probe_ calls. If they succeed, go
  **Closed** and reset counters. If any fail, snap back to **Open** with a
  longer cooldown.

The half-open state is the load-bearing piece. A breaker that goes from open
straight back to closed will oscillate: it floods the recovering downstream with
the queued backlog the moment the cooldown expires. Always probe.

**Error-rate vs error-count triggers.** Both are valid; pick by traffic volume.

- **Error count.** "5 consecutive failures." Cheap. Right for low-volume
  endpoints where 5 errors is unambiguous.
- **Error rate over a window.** "≥50% errors in 10s with ≥20 samples." More
  robust at scale; the minimum-sample floor prevents a single failed request
  during quiet periods from tripping the breaker.

**Type-safety notes.** `match` over `StrEnum` is exhaustive — both
`mypy --strict` and `pyright --strict` will reject the function if a new state
is added without a `case`. The generic `[T]` keeps the call typesafe; `T` cannot
leak into the breaker's own state. `Self` on `with_defaults` lets subclasses
return their own type.

**When NOT to use.**

- One breaker per _service_ is usually wrong granularity. A single breaker means
  one hot endpoint takes the whole breaker open, blocking healthy endpoints.
  Granularity should match failure domains: `(service, operation)`, or
  per-shard, or per-tenant.
- Inside a retry loop. The retry will burn attempts hitting an open breaker; the
  breaker will re-open from the failed attempts. Put the breaker _outside_ the
  retry.
- For local in-process calls. The whole machinery exists because a remote call
  can hang. A function call to your own module shouldn't be wrapped.

**Real-world examples.**

- Netflix Hystrix (now archived but conceptually canonical) standardised the
  closed/open/half-open state machine across the JVM ecosystem.
- Polly (.NET) and Resilience4j (JVM) implement breakers with the rolling
  window + half-open pattern.
- AWS App Mesh exposes circuit-breaking config (`maxConnections`,
  `maxPendingRequests`, `maxRequests`) via Envoy.

**Anti-pattern variant.**

- **Breaker without a half-open state.** "If 10 errors, fail for 5 minutes."
  After 5 minutes, full traffic resumes — the recovering downstream gets
  hammered the moment the timer expires. Always probe.
- **Global breaker.** "One breaker per service." A single failing endpoint
  starves healthy ones.
- **Breaker inside retries.** The retry burns attempts; the breaker re-opens.
  Order matters — see [stacking-the-patterns](#stacking-the-patterns).

**References.**

- Michael Nygard, _Release It!_, 2nd ed., Chapter 5.
- Martin Fowler, _Circuit Breaker_ (martinfowler.com), 2014.
- Netflix, _Fault Tolerance in a High Volume, Distributed System_ (Hystrix
  retrospective).

---

## Bulkhead

**Intent.** Isolate resource pools so that exhaustion of one pool cannot starve
the others. Named for the watertight compartments of a ship hull: a breach in
one compartment floods that compartment, not the whole vessel. In software,
"bulkhead" means: don't share a single thread pool, connection pool, or
semaphore across unrelated workloads.

**When to reach for it.**

- A service that fans out to multiple downstreams with different latency
  characteristics (one fast, one slow).
- An API that handles both interactive (low-latency) and batch (long-running)
  requests.
- A multi-tenant service where one tenant's traffic spike must not starve others
  — the canonical "noisy neighbour" problem.

**Sketch.** Strict-typed Python 3.13+:

```python
import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final


@dataclass(slots=True)
class Bulkhead:
    name: str
    semaphore: asyncio.Semaphore

    async def run[T](self, op: Callable[[], Awaitable[T]]) -> T:
        async with self.semaphore:
            return await op()


# Resource-class budgets. Reports can exhaust their 10 slots — and only their
# 10 slots — without touching billing's 50.
BILLING_BULKHEAD: Final = Bulkhead("billing", asyncio.Semaphore(50))
REPORTS_BULKHEAD: Final = Bulkhead("reports", asyncio.Semaphore(10))
INTERNAL_ADMIN_BULKHEAD: Final = Bulkhead("admin", asyncio.Semaphore(2))
```

For thread-pool isolation between CPU-bound and I/O-bound work, use distinct
`concurrent.futures.ThreadPoolExecutor` instances:

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Final


CPU_POOL: Final = ThreadPoolExecutor(max_workers=4, thread_name_prefix="cpu")
IO_POOL: Final = ThreadPoolExecutor(max_workers=64, thread_name_prefix="io")


async def hash_password(plaintext: str) -> str:
    loop = asyncio.get_running_loop()
    # CPU-bound, so it goes to the small CPU pool — not the default executor,
    # which is shared with everything that calls asyncio.to_thread().
    return await loop.run_in_executor(CPU_POOL, _bcrypt_hash, plaintext)
```

**Type-safety notes.** Generic `[T]` on `run` preserves the operation's return
type; `Final` prevents accidental rebinding of module-level pools.
`asyncio.Semaphore` does not parametrise its acquired count statically — if you
need typed permits, build a wrapper that returns a permit object on `__aenter__`
and consumes it on `__aexit__`.

**When NOT to use.**

- A single-call-path service. Bulkheading needs at least two workloads; with
  one, you're just building a slower path to the same pool exhaustion.
- When the bulkhead size equals the underlying pool size. You've moved the
  bottleneck without separating it. Bulkhead size must be _smaller_ than the
  pool it draws from; that's the entire point.

**Real-world examples.**

- Netflix Hystrix's _thread isolation_ mode wrapped each downstream in its own
  thread pool — explicitly bulkheaded.
- AWS Lambda _reserved concurrency_: per-function caps so one function can't
  consume the account's entire concurrency limit.
- Postgres connection pools per service or per workload class (PgBouncer pools
  sized differently for OLTP vs reporting).

**Anti-pattern variant.**

- **Single thread pool for everything.** The classic Python `asyncio.to_thread`
  trap: it uses the loop's default executor (10 workers by default). One slow
  blocking call (e.g. a hung `requests.get()`) saturates the executor and every
  subsequent `to_thread` waits.
- **Bulkhead-as-rate-limit.** "We bulkhead at 10 concurrent." Concurrency caps
  and rate caps are different. If the downstream throttles by RPS, a concurrency
  cap can still produce arbitrary RPS for a fast downstream. Pair the bulkhead
  with a rate limiter when the downstream's contract is rate-based.

**References.**

- Michael Nygard, _Release It!_, 2nd ed., Chapter 5.
- _Hystrix Wiki_, "Bulkhead Pattern".
- Sam Newman, _Building Microservices_, 2nd ed., Chapter 12.

---

## Rate Limiting

**Intent.** Cap the rate of operations to a defined quota. Two failure modes,
two perspectives:

- **Outbound.** You overwhelm a downstream and trip its rate limit (HTTP 429).
  The downstream now penalises _all_ your callers — not just the ones with
  bursty traffic. Self-throttling beats getting throttled.
- **Inbound.** A single caller floods your service. Without a limiter,
  legitimate traffic is starved.

**When to reach for it.**

- Any outbound call to a third-party API that publishes a rate limit (Stripe:
  100 rps prod, 25 rps test; GitHub: 5000 req/h authed; OpenAI: model-specific
  TPM).
- Any public-facing endpoint where unauthenticated abuse is plausible.
- Any per-tenant operation where one tenant could starve others.

**The four common shapes.**

| Algorithm                              | Allows bursts?       | Smooths? | Memory                             | Notes                                                                                                  |
| -------------------------------------- | -------------------- | -------- | ---------------------------------- | ------------------------------------------------------------------------------------------------------ |
| **Fixed window**                       | Yes (at boundaries)  | No       | O(1) per key                       | Naïve. Two requests in adjacent ms across a window boundary doubles the limit.                         |
| **Sliding window**                     | Limited              | Yes      | O(window) per key                  | Costly to compute precisely; common approximation is "weighted average of two adjacent fixed windows." |
| **Token bucket**                       | Yes (up to capacity) | Yes      | O(1) per key                       | The canonical choice. Refills at fixed rate; a full bucket allows a burst of `capacity`.               |
| **Leaky bucket**                       | No                   | Strictly | O(1) per key                       | Smooths to a constant rate; queues incoming requests up to a max queue depth.                          |
| **GCRA** (generic cell rate algorithm) | Yes (up to capacity) | Yes      | O(1) per key, **single timestamp** | Mathematically equivalent to leaky bucket, but stores only the next-allowed-time. Used by Redis-cell.  |

**Sketch.** Strict-typed token bucket:

```python
import asyncio
import time
from dataclasses import dataclass, field


@dataclass(slots=True)
class TokenBucket:
    capacity: float
    refill_per_s: float
    tokens: float = field(init=False)
    last_refill: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        self.tokens = self.capacity

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_s)
        self.last_refill = now

    def try_consume(self, cost: float = 1.0) -> bool:
        self._refill()
        if self.tokens >= cost:
            self.tokens -= cost
            return True
        return False

    async def acquire(self, cost: float = 1.0, deadline_s: float = 5.0) -> None:
        async with asyncio.timeout(deadline_s):
            while True:
                self._refill()
                if self.tokens >= cost:
                    self.tokens -= cost
                    return
                deficit = cost - self.tokens
                await asyncio.sleep(deficit / self.refill_per_s)
```

Or with `aiolimiter` (a drop-in leaky-bucket):

```python
from aiolimiter import AsyncLimiter
from typing import Final


# Throttle outbound to Stripe to 80 req/s — 80% of the 100 req/s prod limit.
STRIPE_LIMITER: Final = AsyncLimiter(max_rate=80, time_period=1.0)


async def charge_card(amount_cents: int) -> str:
    async with STRIPE_LIMITER:
        return await _do_charge(amount_cents)
```

For server-side, FastAPI users typically reach for **`slowapi`** (Flask limiter
wrapper) or **`fastapi-limiter`** (Redis-backed). For globally enforced limits
across N replicas, use **`redis-cell`** — a Redis module implementing GCRA
atomically in a single Lua script, eliminating race conditions across replicas.

**Token bucket vs leaky bucket vs GCRA.**

- **Token bucket.** Refills at rate `r`, holds up to `B` tokens. _Allows bursts
  up to `B`_; smooths the average to `r`. Used when occasional bursts are fine
  and only the long-run rate matters.
- **Leaky bucket.** Drains at rate `r`. Inputs are queued; if the queue exceeds
  depth `D`, requests are rejected. _Strictly smooth_ — output is exactly `r`
  regardless of input. Used when downstream cannot handle bursts.
- **GCRA.** Same admission decisions as leaky bucket, but stored as a
  _theoretical arrival time_ (TAT) rather than a queue. O(1) state per key — a
  single timestamp. Used for distributed limiters where every byte of state
  matters (Redis-cell stores 1 key per `(tenant, endpoint)`).

**Distributed rate limiting.** Local buckets across N replicas yield N× the
intended rate — the single-replica rate limit is meaningless if you have 10
replicas. Options:

- **Redis-cell** — atomic GCRA in Redis. Single source of truth, one round-trip
  per check.
- **Redis Lua scripts** — your own token bucket via `EVAL`. Brittle but
  flexible.
- **Stripe's approach** (publicly described): a hierarchical limiter — a fast
  local check rejects most overage, a slower global check enforces the hard
  ceiling. The local check is permissive; the global check is the source of
  truth.
- **Dedicated services** — Kong, Envoy with rate-limit service, AWS API Gateway
  throttling.

**Type-safety notes.** `Final` on the module-level limiter prevents reseat;
`asyncio.timeout()` on `acquire` prevents the deadlock-by-throttle anti-pattern
(the bucket never refills enough; the caller hangs forever). Always pair limiter
waits with a deadline.

**When NOT to use.**

- For inbound _DOS protection_. Rate limiting is not DDoS protection — it runs
  _after_ a request hits your process. Pair with edge protections (CDN, WAF, ALB
  rules) for L3/L4 attacks.
- When the downstream limit is enforced by _concurrency_, not rate (e.g.
  database connection caps). Use a bulkhead instead.

**Real-world examples.**

- Stripe publishes a hard rate limit (100 rps live, 25 rps test) and recommends
  client-side limiting + idempotency keys to handle 429s gracefully.
- GitHub API: 5000 req/h authenticated, with a `X-RateLimit-Remaining` header
  for client-driven backoff.
- Netflix EVCache uses GCRA-style limiters for per-key request shaping.

**Anti-pattern variant.**

- **Sleep-forever-when-empty.** A naïve token bucket without a deadline: caller
  sleeps until the bucket refills, but the request that's waiting itself has a
  1s deadline upstream. Result: deadlock-by-throttle. _Always pair `acquire()`
  with a timeout._
- **Per-replica only.** "Each replica caps to N rps." With M replicas, you cap
  to M×N rps and the downstream still 429s.
- **Naïve fixed window.** Requests at t=999ms and t=1001ms double the limit. Use
  sliding window or token bucket.

**References.**

- Stripe Engineering, _Scaling your API with rate limiters_, 2017.
- Brandur Leach, _Rate Limiting, Cells, and GCRA_, brandur.org.
- Redis Labs, _redis-cell: a Rate Limiting Redis Module_.

---

## Adaptive Concurrency Limits

**Intent.** Replace static, hand-tuned thread/connection limits with a limiter
that _measures_ the dependency's actual capacity in real time and adjusts.
Static limits are obsolete the moment the downstream's behaviour shifts (deploy,
GC pause, neighbour traffic). Adaptive limits use the same control-loop
machinery TCP uses: measure latency, infer queueing, increase limit when latency
is stable, decrease when latency rises.

**When to reach for it.**

- A downstream whose capacity varies (autoscaling, spot instances, multi-tenant
  noisy neighbours).
- A service-mesh or API-gateway sidecar that fronts heterogeneous backends and
  cannot have a static limit.
- High-fan-out clients (e.g. mobile apps) where a static "max 10 concurrent"
  wastes capacity on a fast day and overwhelms on a slow one.

**Sketch.** Strict-typed minimal AIMD limiter (Vegas-style, simplified):

```python
import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass


@dataclass(slots=True)
class AdaptiveLimit:
    """
    Vegas-style adaptive concurrency limit.

    Increases by 1 when observed RTT is close to the historical minimum
    (no queueing inferred); decreases by 1 when RTT exceeds min by an
    AIMD threshold (queue forming).
    """

    initial_limit: int = 10
    min_limit: int = 1
    max_limit: int = 1000
    alpha: float = 3.0   # increase if queue size estimate < alpha
    beta: float = 6.0    # decrease if queue size estimate > beta

    limit: int = 0
    rtt_min: float = float("inf")
    semaphore: asyncio.Semaphore = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.limit = self.initial_limit
        self.semaphore = asyncio.Semaphore(self.limit)

    def _record(self, rtt_s: float) -> None:
        # Track the lower envelope of observed RTT (proxy for no-queue latency).
        self.rtt_min = min(self.rtt_min, rtt_s)
        # Little's Law: estimated_queue = limit * (1 - rtt_min/rtt).
        queue_est = self.limit * (1.0 - self.rtt_min / max(rtt_s, 1e-9))
        if queue_est < self.alpha and self.limit < self.max_limit:
            self._adjust(self.limit + 1)
        elif queue_est > self.beta and self.limit > self.min_limit:
            self._adjust(self.limit - 1)

    def _adjust(self, new_limit: int) -> None:
        # Adjust by replacing the semaphore. Existing waiters carry over
        # because the new semaphore starts at the new limit.
        self.limit = new_limit
        self.semaphore = asyncio.Semaphore(self.limit)

    async def call[T](self, op: Callable[[], Awaitable[T]]) -> T:
        async with self.semaphore:
            t0 = time.monotonic()
            try:
                return await op()
            finally:
                self._record(time.monotonic() - t0)
```

Production use should pull from a hardened library:

- **Netflix `concurrency-limits`** (JVM) — the canonical implementation; its
  algorithms (Vegas, Gradient2, AIMD) are documented in code.
- **Envoy** ships an _adaptive concurrency filter_ implementing a Gradient-style
  limiter at the proxy.
- **`limits`** (Python) — fixed-window/sliding/leaky/token; not adaptive but a
  good base.

**Little's Law and BBR.** The math under the hood is Little's Law: `L = λW`,
where `L` is the in-flight count, `λ` is throughput, `W` is mean latency.
Rearranging, _concurrency limit ≈ desired throughput × latency_. The trick is
that latency depends on concurrency (queues form). BBR-style algorithms
(Bottleneck Bandwidth and RTT, from TCP) measure the _minimum_ RTT — a proxy for
"no queueing" — and infer queue depth as the gap between observed and minimum
RTT. Adjust limit until queue depth sits in a target band.

**Type-safety notes.** The `# type: ignore[assignment]` on the semaphore field
is regrettable but unavoidable: dataclasses can't construct `asyncio.Semaphore`
lazily from `__post_init__` without a placeholder. Cleaner shapes use `__init__`
directly. The generic `[T]` on `call` preserves the call's return type.

**When NOT to use.**

- Low-fan-out, low-traffic services. The control loop needs traffic to learn;
  with 1 req/s, an adaptive limit just oscillates between min and initial.
- When the downstream's capacity is _known_ and _stable_ (e.g. a single Postgres
  with a connection limit). A static limit is simpler and correct.

**Real-world examples.**

- Netflix uses adaptive concurrency limiters in Zuul (their API gateway) and
  Hollow (their data-distribution mesh).
- Envoy's adaptive concurrency filter is deployed at scale at Lyft.
- Netflix open-sourced `concurrency-limits` after the team replaced static
  per-service caps with adaptive ones across the stack.

**Anti-pattern variant.**

- **Adaptive limit + static retry.** The limiter reduces concurrency in response
  to latency; the retry loop pumps it back up by retrying failed attempts. Net
  effect: the adaptive limit is meaningless. Either the retry is _also_ adaptive
  (retry budget shrinks as the limit shrinks), or the retry sits _outside_ the
  limiter and shares the same budget.
- **Tuning the algorithm before measuring.** People reach for adaptive limits,
  then tune `alpha` and `beta` blindly. The right starting point is _measure
  latency under realistic load_, then pick parameters that produce a queue of
  0–N for the SLO you care about.

**References.**

- Netflix, _Performance Under Load — Adaptive Concurrency Limits_, Tech
  Blog, 2018.
- Will Sewell & David Greenway (Netflix), `concurrency-limits` GitHub.
- Cardwell et al., _BBR: Congestion-Based Congestion Control_, ACM Queue, 2016.

---

## Idempotency Keys

**Intent.** Make non-idempotent operations safe to retry. The client supplies a
unique key with each request; the server stores `key → result` and replays the
stored result on duplicate keys. The retry-after-network-blip case stops
duplicating writes.

**When to reach for it.**

- Any state-changing API (`POST`, `PATCH`) that may be retried by the caller, by
  a queue, or by the user (refresh button, double-click).
- Webhook receivers: the sender will retry; you must dedupe.
- Background workers consuming from at-least-once queues — the same message
  _will_ be redelivered, sometimes hours later.

**Sketch.** Strict-typed Python 3.13+:

```python
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from typing import NewType, Protocol


IdempotencyKey = NewType("IdempotencyKey", str)


class AlreadyInProgress(Exception):
    """Raised when a key is currently being processed by another caller."""


@dataclass(frozen=True, slots=True)
class StoredResult:
    request_fingerprint: str  # SHA-256 of the canonical request body
    response_json: str
    completed_at: datetime


class IdempotencyStore(Protocol):
    async def try_begin(
        self, key: IdempotencyKey, fingerprint: str, ttl: timedelta
    ) -> None: ...

    async def get_completed(
        self, key: IdempotencyKey
    ) -> StoredResult | None: ...

    async def complete(
        self, key: IdempotencyKey, response_json: str
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class ChargeRequest:
    idempotency_key: IdempotencyKey
    amount_cents: int
    customer_id: str

    def fingerprint(self) -> str:
        # Canonical fingerprint: sorted-keys JSON + SHA-256.
        import hashlib
        import json
        body = json.dumps(
            {
                "amount_cents": self.amount_cents,
                "customer_id": self.customer_id,
            },
            sort_keys=True,
        )
        return hashlib.sha256(body.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ChargeResult:
    charge_id: str
    status: str


class FingerprintMismatch(Exception):
    """Same key, different request body — almost always a client bug."""


async def charge(
    request: ChargeRequest,
    store: IdempotencyStore,
    do_charge: Callable[[ChargeRequest], Awaitable[ChargeResult]],
    ttl: timedelta = timedelta(hours=24),
) -> ChargeResult:
    key = request.idempotency_key
    fingerprint = request.fingerprint()

    if (existing := await store.get_completed(key)) is not None:
        if existing.request_fingerprint != fingerprint:
            raise FingerprintMismatch(key)
        # Replay the stored response — same key, same body, same answer.
        import json
        return ChargeResult(**json.loads(existing.response_json))

    await store.try_begin(key, fingerprint, ttl)
    try:
        result = await do_charge(request)
    except Exception:
        # On failure, the begun row is left so a retry sees AlreadyInProgress
        # until the lock TTL expires; consider also rolling it back if the
        # error is classified as terminal.
        raise

    import json
    await store.complete(
        key,
        json.dumps({"charge_id": result.charge_id, "status": result.status}),
    )
    return result
```

**Stripe's documented approach.** Stripe's idempotency key implementation (per
their engineering blog) has these properties:

- **Client-supplied UUIDs.** Up to 255 characters; the client picks the key
  format. UUIDv4 is the recommended shape because it's collision-resistant
  without coordination.
- **24-hour TTL.** Long enough for the typical client retry window; short enough
  to bound storage. Some endpoints use longer TTLs for one-time high-stakes ops.
- **Request fingerprint check.** If the same key is sent with a different body,
  Stripe returns 400 and refuses the call. Same-key/different-body is almost
  always a client bug.
- **Atomic `try_begin`.** A row is created with a status of `processing` before
  the work starts. A second request with the same key gets a _409 Conflict_ (or
  waits, depending on endpoint) until the first completes.
- **Stored response, not stored success-fact.** A retry must see the _same
  response_, byte for byte — not just "you already did this" (which would let
  the client end up unable to know what charge ID it got).

**Storage schema.** Minimal viable schema:

```sql
CREATE TABLE idempotency (
    key             TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    endpoint        TEXT NOT NULL,
    fingerprint     TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('processing', 'completed')),
    response_json   TEXT,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ NOT NULL
);

CREATE INDEX ix_idempotency_expires ON idempotency (expires_at);
```

Key is scoped to `(user, endpoint)` — never accept the same key across
endpoints. A janitor process deletes rows where `expires_at < now()`.

**Type-safety notes.** `NewType` for `IdempotencyKey` so a `str` accidentally
passed somewhere fails the type check. The `Protocol` boundary lets test doubles
satisfy the interface without inheriting from a concrete class.
`frozen=True, slots=True` on dataclasses is the default in this house style.

**When NOT to use.**

- Naturally-idempotent operations (`PUT /users/123`, `DELETE /orders/456`). The
  HTTP method is already the dedup mechanism.
- _Read_ operations. Idempotency keys for `GET` solve nothing.
- One-shot consumers of an exactly-once-pretending broker. Use the broker's
  built-in dedup if it exists (Kafka transactional producers, RabbitMQ publisher
  confirms with `correlation-id`); reach for app-level idempotency keys only
  when the broker can't.

**Real-world examples.**

- **Stripe**: `Idempotency-Key` header, 24h TTL, fingerprint check, documented
  since 2017.
- **AWS DynamoDB**: `ClientRequestToken` for transactional writes —
  same-token-same-body returns the original response for 10 min.
- **PayPal**: `PayPal-Request-Id` header on payment endpoints.
- **GitHub Actions**: workflow run keys for "skip if already running."

**Anti-pattern variant.**

- **Storing only "success", not the response.** A retry sees "yes, you did this"
  but never knows the original `charge_id`. The client has to call a separate
  "find my charge" endpoint to recover. Store the _response_.
- **Server-generated keys.** The whole point is _client_ control. If the server
  generates the key, the network-loss case can't dedupe — the client has no key
  to send on retry.
- **No fingerprint check.** Same key, different body → silently process the
  second body and overwrite the result. Now you have a bug that looks like data
  corruption. _Always_ fingerprint.

**References.**

- Stripe Engineering, _Designing robust and predictable APIs with
  idempotency_, 2017.
- AWS, _DynamoDB ClientRequestToken_, official docs.
- IETF draft: _The Idempotency-Key HTTP Header Field_.

---

## Dead-Letter Queue

**Intent.** A _terminal_ failure sink for messages that cannot be processed
after a bounded number of attempts. Without a DLQ, a poison message either loops
forever (blocking the queue, inflating attempt counts, exhausting consumer
threads) or gets dropped (silent data loss). With a DLQ, the message is moved
out of the live path with full context, the consumer keeps making progress on
the rest of the queue, and a human (or replay tool) decides what to do next.

**When to reach for it.**

- Any worker reading from a message broker with at-least-once delivery semantics
  (SQS, RabbitMQ, Kafka, Redis Streams, etc.).
- Any retry policy with bounded attempts — past the budget, the message has to
  _go somewhere_.
- Any pipeline with downstream schema drift; a payload that used to validate may
  suddenly not.

**Sketch.** Strict-typed Python 3.13+:

```python
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Message[TPayload]:
    payload: TPayload
    attempts: int
    first_seen_at: datetime
    correlation_id: str


@dataclass(frozen=True, slots=True)
class DeadLettered[TPayload]:
    payload: TPayload
    error: str
    attempts: int
    first_seen_at: datetime
    last_error_at: datetime
    correlation_id: str
    error_class: str


class DeadLetterSink[TPayload](Protocol):
    async def send(self, dlq: DeadLettered[TPayload]) -> None: ...


async def process_with_dlq[TPayload](
    message: Message[TPayload],
    processor: Callable[[TPayload], Awaitable[None]],
    dlq: DeadLetterSink[TPayload],
    max_attempts: int = 5,
) -> None:
    try:
        await processor(message.payload)
    except Exception as exc:
        if message.attempts >= max_attempts:
            await dlq.send(
                DeadLettered(
                    payload=message.payload,
                    error=repr(exc),
                    attempts=message.attempts,
                    first_seen_at=message.first_seen_at,
                    last_error_at=datetime.now(UTC),
                    correlation_id=message.correlation_id,
                    error_class=type(exc).__qualname__,
                )
            )
            return
        # Re-raise so the broker redelivers (NACK) and increments attempt count.
        raise
```

**The DLQ-as-observability framing.** A DLQ that nobody reads is a landfill. The
DLQ's _primary_ output is operational signal:

- **Depth** — alert on growth. `depth > 0 && d/dt(depth) > 0` means an
  undiagnosed bug is producing dead letters faster than humans drain them.
- **Class breakdown** — group by `error_class`. Five thousand `JSONDecodeError`s
  tell a different story than two hundred `IntegrityError`s.
- **Age distribution** — old DLQ messages may not be replayable (referenced
  entities have been deleted; tokens have rotated).

**Replay UX.** Build re-drive tooling _before_ you need it. Minimum viable
replay:

- A CLI / endpoint that pulls N messages from the DLQ, optionally filtered by
  error class or correlation ID.
- An idempotent re-publish to the original queue (so messages dropped during
  replay due to a fresh bug end up back in DLQ, not lost).
- Audit log of what was replayed, by whom, when, with what result.

A DLQ without re-drive forces operators to copy-paste payloads back into the
producer — guaranteed source of further bugs.

**Type-safety notes.** PEP 695 `Message[TPayload]` and `DeadLettered[TPayload]`
carry the payload type forward, so `mypy --strict` catches a DLQ wired to the
wrong message type. The `Protocol` boundary lets SQS, Kafka, and in-memory test
sinks all satisfy `DeadLetterSink` without sharing a base class.

**When NOT to use.**

- A best-effort fire-and-forget pipeline. If the message is genuinely
  disposable, dropping is correct and a DLQ is overhead.
- A pipeline with no consumer SLA. DLQs require operational ownership; if nobody
  will look at the depth metric, you don't have a DLQ, you have a trash
  compactor.

**Real-world examples.**

- **AWS SQS** ships native DLQ support: configure
  `redrivePolicy.maxReceiveCount`; SQS moves the message after that many
  visibility-timeout expirations. AWS Lambda integrates this end-to-end.
- **RabbitMQ** dead-letter exchanges (DLX): configure `x-dead-letter-exchange`
  on the source queue; `nack` with `requeue=false` routes to the DLX.
- **Kafka** doesn't ship a built-in DLQ; consumers like Spring Cloud Stream
  publish failed records to a `*.dlq` topic.

**Anti-pattern variant.**

- **DLQ-as-graveyard.** No alert, no dashboard, no re-drive tool. Messages go
  in; nothing comes out. Effectively the same as data loss with extra storage
  cost.
- **Infinite retry without DLQ.** "Just keep retrying." The poison message
  blocks the queue, the consumer's lag grows, every other message gets delayed.
  The most common production cause of "the queue caught fire."
- **DLQ in the same blast radius as the source queue.** If your queue cluster is
  what's failing, your DLQ goes with it. DLQs in a separate failure domain
  (different cluster, different region for the very paranoid) survive the
  underlying outage.

**References.**

- David Yanacek, _Avoiding insurmountable queue backlogs_, AWS Builders'
  Library.
- Sam Newman, _Building Microservices_, 2nd ed., Chapter 6.
- _AWS SQS Dead-Letter Queues_ documentation.

---

## Hedged Requests

**Intent.** Reduce _tail_ latency by issuing a duplicate request after a short
delay (typically near the dependency's p95 latency). The first response wins;
the loser is cancelled. This trades a small fraction of extra load for
dramatically lower p99 / p99.9 latency. Jeff Dean and Luiz Barroso described the
technique in _The Tail at Scale_ (CACM 2013).

**When to reach for it.**

- Idempotent, read-mostly operations where tail latency hurts (interactive UIs,
  fan-out queries to N shards).
- A dependency with stable median latency but a fat tail (GC pauses, JIT warmup,
  occasional disk seeks).
- Any case where you have spare capacity downstream and the tail pain outweighs
  the duplicate cost.

**Sketch.** Strict-typed Python 3.13+:

```python
import asyncio
from collections.abc import Awaitable, Callable


async def hedged[T](
    op: Callable[[], Awaitable[T]],
    hedge_after_s: float,
    overall_deadline_s: float,
) -> T:
    """
    Issue a duplicate after `hedge_after_s`; cancel the loser.
    Both attempts share `overall_deadline_s`.
    """
    async with asyncio.timeout(overall_deadline_s):
        async with asyncio.TaskGroup() as tg:
            first = tg.create_task(op())

            try:
                async with asyncio.timeout(hedge_after_s):
                    return await asyncio.shield(first)
            except TimeoutError:
                # First attempt is still running; launch the hedge.
                pass

            second = tg.create_task(op())

            done, _ = await asyncio.wait(
                {first, second},
                return_when=asyncio.FIRST_COMPLETED,
            )
            winner = done.pop()
            for task in (first, second):
                if task is not winner and not task.done():
                    task.cancel()
            return winner.result()
```

**Cost analysis.** With `hedge_after_s = p95`, only 5% of requests issue the
hedge. The dependency sees ~5% extra load. Provided the dependency has the
headroom, the p99/p99.9 latency drops dramatically — because the hedge has a
near-95% chance of finishing before the original would have.

**When duplication wins.**

- The dependency is _stochastically slow_, not _broken_. A slow request is not
  necessarily a failed one; the original may complete shortly after the hedge
  starts.
- The downstream has spare capacity. ~5% extra load is fine on a 70%-utilised
  cluster; not fine on a 95%-utilised one.
- The operation is genuinely idempotent (`GET`, `HEAD`, idempotent-keyed POST).

**When duplication pours fuel on the fire.**

- The downstream is _overloaded_. Every hedge adds load to a cluster that's
  already failing. Hedging accelerates the death spiral.
- The operation is non-idempotent. Hedged charges = double charges.
- Behind a rate limiter. The hedge consumes another token, accelerating
  exhaustion.

**The "tied requests" variant.** A refinement from Dean and Barroso: send both
requests immediately, but tag them so that whichever server picks one up _first_
tells the other server to drop the duplicate. Lower duplicate load than naïve
hedging, but requires server-side cooperation — feasible in homogeneous internal
stacks, rarely available across third-party APIs.

**Type-safety notes.** Generic `[T]` carries the operation's return type
through. `asyncio.TaskGroup` (Python 3.11+) is the structured-concurrency shape
— child task cancellation propagates cleanly on exit. `asyncio.shield` on the
first attempt is necessary; without it, the inner timeout cancels the first
attempt and the hedge has nothing to race.

**When NOT to use.**

- Non-idempotent writes (already covered).
- Highly utilised downstreams.
- Below the latency floor (a 5ms request hedged at 4ms doesn't help and doubles
  load).

**Real-world examples.**

- **Google's Spanner** uses hedged reads internally for cross-region
  consistency-aware queries.
- **Cassandra's** `speculative_retry` setting hedges to a different replica
  after the configured percentile.
- **Envoy** supports `retry_policy.host_selection_retry_max_attempts` combined
  with hedging primitives in its HTTP retry filter.
- **DynamoDB SDKs** offer adaptive retry that approximates hedging for
  read-heavy access patterns.

**Anti-pattern variant.**

- **Hedge with `hedge_after = 0`.** That's not a hedge — it's always-duplicate,
  doubling load for no gain.
- **Hedge a non-idempotent op.** Double payments, double emails, double posts.
  Always check the contract.
- **Hedge through an open circuit breaker.** Both attempts fail-fast; nothing
  was bought; the breaker counts both. Pair the hedge with the _outermost_
  breaker, not an inner one.

**References.**

- Jeff Dean & Luiz Barroso, _The Tail at Scale_, Communications of the ACM, Vol.
  56, No. 2, 2013.
- Cassandra documentation: _Speculative retry_.
- Marc Brooker, _Tail Latency Might Matter More Than You Think_, AWS
  Architecture Blog.

---

## Fallback and Graceful Degradation

**Intent.** When a _non-critical_ dependency is down, return a useful response
anyway — empty list, default value, last-known-good cache, feature flag-gated
alternative — instead of failing the whole request. Distinguish **critical**
dependencies (request cannot complete without them) from **enhancing**
dependencies (request can complete, just less rich) and treat them differently.

**When to reach for it.**

- A page that aggregates multiple downstreams where one is "the data" and others
  are "decorations" (recommendations, related products, social proof).
- A read path where stale data is _better_ than no data, within a defined
  staleness bound.
- A feature behind a kill switch — the ability to turn off a problem-feature
  without redeploying.

**Sketch.** Strict-typed Python 3.13+:

```python
import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final

logger: Final = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Product:
    sku: str
    name: str


@dataclass(frozen=True, slots=True)
class ProductPage:
    product: Product
    recommendations: list[Product]
    degraded: bool  # observable; rendered in metrics, optionally in UI


async def render_product_page[T](
    product_id: str,
    fetch_product: Callable[[str], Awaitable[Product]],
    fetch_recs: Callable[[str], Awaitable[list[Product]]],
) -> ProductPage:
    # Critical: cannot fall back. If this fails, the whole request fails.
    product = await fetch_product(product_id)

    # Enhancing: degrade if it fails, surface degraded=True to caller.
    try:
        async with asyncio.timeout(0.2):
            recommendations = await fetch_recs(product_id)
        return ProductPage(product=product, recommendations=recommendations, degraded=False)
    except (TimeoutError, Exception) as exc:  # noqa: BLE001 - deliberate scope
        logger.warning(
            "fallback_taken",
            extra={
                "fallback": "recommendations",
                "reason": type(exc).__qualname__,
                "product_id": product_id,
            },
        )
        return ProductPage(product=product, recommendations=[], degraded=True)
```

**The "loud fallback" rule.** Every fallback path emits an observable signal.
The minimum:

- **Counter:** `fallback_taken{path="recommendations", reason="timeout"}`.
- **Log line at WARN:** with the reason and a correlation ID.
- **Caller-visible flag:** `degraded=True` propagated up so dashboards and
  (sometimes) UIs can render the degradation.

A silent fallback that quietly serves empty data is worse than an error because
users — and on-call engineers — cannot tell they are in degraded mode.
Stale-cache hits served as fresh data is the canonical example: by the time
someone notices, hours of users have made decisions on stale information.

**Feature toggles.** A _kill switch_ is a fallback paired with a feature flag.
Build them in to anything that talks to a fragile dependency:

```python
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class FeatureFlags:
    recommendations_enabled: bool


async def render_with_kill_switch(
    product_id: str,
    flags: FeatureFlags,
    fetch_product: Callable[[str], Awaitable[Product]],
    fetch_recs: Callable[[str], Awaitable[list[Product]]],
) -> ProductPage:
    product = await fetch_product(product_id)
    if not flags.recommendations_enabled:
        return ProductPage(product=product, recommendations=[], degraded=True)
    # ... as above
```

A flag service like LaunchDarkly, OpenFeature, or even a Redis key flipped by
ops, lets you disable a flapping feature in seconds without a deploy.

**Last-known-good cache.** Cache the most recent successful response with a
_staleness bound_. On dependency failure, serve stale up to the bound; past the
bound, fall through to the actual error. Implement with `aiocache`,
`cachetools`, or a Redis layer with explicit TTL.

**When NOT to use.**

- For _critical_ paths where a wrong answer is worse than no answer. Falling
  back to "$0.00" instead of the real charge total because the pricing service
  is down is a bug, not degradation.
- For correctness-bound reads. A shopping cart count that silently drops to zero
  because the cart service is down is a fallback that lies to the user.

**Real-world examples.**

- **Netflix** treats "show the Netflix homepage even if 3 of 5 backends are
  down" as a first-class requirement; non-personalised fallbacks exist for every
  personalised section.
- **Amazon's product page** falls back through layers — full personalised →
  popular-in-category → category default → brand default — with metrics on each
  step.
- **GitHub** serves a static "we're degraded" banner driven by a feature flag
  flipped from a Slack command.

**Anti-pattern variant.**

- **Silent stale-cache fallback.** Serves the cached version forever when the
  source is down, no metric, no flag. Stripe-canonical bug shape.
- **`try/except Exception: return default`.** Wraps every call; turns every bug
  — null pointer, key error, validation — into silent default-data loss.
  Fallbacks must be _deliberate_ and scoped to _specific known_ failure modes.
- **No staleness bound on the LKG cache.** Stale 6-month-old data served as
  current. Bound staleness; past the bound, fail loudly.

**References.**

- Michael Nygard, _Release It!_, 2nd ed., Chapter 5 (Stability Patterns).
- Netflix Tech Blog, _Mastering Chaos — Microservices_, 2017.
- Pete Hodgson, _Feature Toggles (aka Feature Flags)_, martinfowler.com.

---

## Health Checks

**Intent.** A standardised endpoint a load balancer / orchestrator uses to
decide whether to (a) restart this instance, or (b) route traffic to it. The two
questions are different and need different answers — that's the liveness /
readiness split.

**When to reach for it.**

- Any service deployed under an orchestrator (Kubernetes, ECS, Nomad, Cloud
  Run).
- Any service behind a load balancer (ALB, NLB, HAProxy, Envoy).
- Any service whose start-up time is non-trivial (warm caches, JIT, model load).

**Sketch.** Strict-typed FastAPI healthchecks:

```python
import asyncio
from dataclasses import dataclass
from typing import Final

from fastapi import APIRouter, Response, status


@dataclass(frozen=True, slots=True)
class HealthStatus:
    name: str
    ok: bool
    detail: str


router: Final = APIRouter()


# Liveness: "is this process alive?" — should NEVER fail because of a
# downstream. Failing liveness ⇒ kubelet restart loop ⇒ outage on a
# downstream blip.
@router.get("/healthz")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


# Readiness: "should I get traffic?" — fails if any *required* downstream
# is unreachable. Failing readiness ⇒ traffic stops, but pod stays up;
# recovery just needs the dep to come back.
@router.get("/readyz", status_code=status.HTTP_200_OK)
async def readiness(response: Response) -> list[HealthStatus]:
    checks = await asyncio.gather(
        _check_postgres(),
        _check_redis(),
        return_exceptions=False,
    )
    if any(not c.ok for c in checks):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return list(checks)


async def _check_postgres() -> HealthStatus:
    try:
        async with asyncio.timeout(0.5):
            # SELECT 1 — minimal query.
            await _db_ping()
        return HealthStatus("postgres", True, "ok")
    except Exception as exc:
        return HealthStatus("postgres", False, repr(exc))


async def _check_redis() -> HealthStatus:
    try:
        async with asyncio.timeout(0.2):
            await _redis_ping()
        return HealthStatus("redis", True, "ok")
    except Exception as exc:
        return HealthStatus("redis", False, repr(exc))
```

**Liveness vs readiness.**

- **Liveness.** "Is this process alive enough to be worth keeping?" Should
  return 200 unless the process is _internally_ broken (deadlock, OOM recovery
  loop, corrupted in-memory state). **Never check downstreams in liveness.** A
  liveness probe that pings the database fails when the DB fails, kubelet
  restarts the pod, the new pod fails the same probe — you have engineered a
  service-wide crash loop.
- **Readiness.** "Should this instance receive traffic right now?" Routinely
  fails for legitimate reasons: just-started, downstream unavailable, draining
  for shutdown. The pod stays up; traffic stops; the pod recovers when the dep
  does.
- **Startup probe.** "Has initialisation completed yet?" Disables the other
  probes until it succeeds. Right for slow-starting services (ML model load,
  large cache warm-up) where a generous startup window is the only way to avoid
  liveness false positives during boot.

**Deep vs shallow probes.**

- **Shallow.** "Process is up" — no I/O. Fastest, cheapest, never blocks. Right
  for liveness.
- **Deep.** "Process is up _and_ can do its job" — verifies downstream
  reachability. Right for readiness, _with caveats_: must be cheap (a
  `SELECT 1`, not a real query), must time out aggressively, and must be served
  on a path the load balancer can hit without going through the ordinary
  application stack.

The "smart but not too smart" middle ground: readiness checks **connectivity**
(can I open a connection to my DB?) but **not behaviour** (does this query plan
look good?). The latter is the job of metrics, not probes.

**The "shared thread pool" pitfall.** A common bug: probes hit the same HTTP
server / thread pool that handles real traffic. Under load, the probe queues
behind real requests and times out, kubelet restarts the pod, the new pod still
has the same load, repeat. Mitigations:

- Serve probes on a _separate_ port and `gunicorn`/`uvicorn` worker.
- Use a lightweight separate framework for the probe server.
- For gRPC, use the gRPC Health Checking Protocol (separate service path).

**Type-safety notes.** `frozen=True, slots=True` on `HealthStatus` keeps the
response shape stable (no accidental field mutation). The probe endpoints return
well-typed shapes that FastAPI auto-documents in OpenAPI — callers can codegen
against the contract.

**When NOT to use.**

- A serverless function (Lambda, Cloud Run) where the platform handles health
  implicitly. A `/healthz` is ignored.
- A daemon with no inbound HTTP. Use the platform's liveness signal (systemd
  `Type=notify`, K8s exec probe).

**Real-world examples.**

- **Kubernetes** ships three probes: `livenessProbe`, `readinessProbe`,
  `startupProbe` with `initialDelaySeconds`, `periodSeconds`,
  `failureThreshold`, `successThreshold`. The K8s docs explicitly recommend the
  liveness/readiness split.
- **AWS ELB target groups** support custom health-check paths and thresholds.
- **Envoy health-check filter** can probe upstreams _and_ expose its own.
- **gRPC Health Checking Protocol** standardises a `Check` RPC that returns
  `SERVING`, `NOT_SERVING`, `UNKNOWN`.

**Anti-pattern variant.**

- **Liveness probe checks Postgres.** As above — a DB blip becomes a
  cluster-wide crash loop.
- **Readiness probe runs the full request path.** Now the probe is the most
  expensive endpoint; it fails first under load and the LB removes every pod
  from the pool.
- **Single `/health` endpoint for both probes.** Loses the distinction; liveness
  inherits readiness's failure modes.

**References.**

- _Kubernetes — Configure Liveness, Readiness and Startup Probes_, official
  docs.
- _gRPC Health Checking Protocol_, gRFC L1.
- Sandy Mamoli, _Probing Production_, SRE-con 2019.

---

## Heartbeat

**Intent.** A periodic "I'm alive" signal between two communicating parties,
used to detect failure of a long-lived connection or task that doesn't have
natural request/response traffic. Where health checks are _pulled_ by an
orchestrator from outside, heartbeats are _pushed_ by the participants
themselves over the live channel.

**When to reach for it.**

- Long-lived connections (WebSocket, SSE, gRPC streaming) where TCP keepalive
  alone is insufficient (NAT timeouts, intermediary load balancers with silent
  connection drops).
- Distributed coordination (lease-based locking — "I still hold the lock";
  consumer-group membership in Kafka, Redis Streams).
- Background workers reporting "I'm still working on this task," needed for
  visibility-timeout extension on long-running messages.

**Sketch.** Strict-typed Python 3.13+ — sender-driven heartbeat over a
WebSocket-like channel:

```python
import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Final


@dataclass(slots=True)
class HeartbeatSender:
    interval_s: float
    send: Callable[[bytes], Awaitable[None]]
    _task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self.interval_s)
            timestamp = datetime.now(UTC).isoformat().encode()
            try:
                await self.send(b"hb:" + timestamp)
            except Exception:
                # Send failure ⇒ connection is gone. Let the caller's read loop
                # discover and react. Suppress here so the heartbeat task
                # doesn't crash the whole connection prematurely.
                return


@dataclass(slots=True)
class HeartbeatMonitor:
    timeout_s: float
    _last_seen: datetime = datetime.now(UTC)
    _task: asyncio.Task[None] | None = None
    _on_stale: Callable[[], Awaitable[None]] | None = None

    def saw_heartbeat(self) -> None:
        self._last_seen = datetime.now(UTC)

    async def start(self, on_stale: Callable[[], Awaitable[None]]) -> None:
        self._on_stale = on_stale
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self.timeout_s / 2)
            age = (datetime.now(UTC) - self._last_seen).total_seconds()
            if age > self.timeout_s and self._on_stale is not None:
                await self._on_stale()
                return
```

**Sender-driven vs receiver-polled.**

- **Sender-driven.** The active party periodically sends a heartbeat; the
  passive party sets a deadline timer that resets on each receipt. Right for
  asymmetric channels (server pushes to client) or where receiver polling is
  expensive.
- **Receiver-polled.** The receiver actively pings; the sender responds.
  Effectively the application-level shape of TCP keepalive. Right when the
  receiver has more state and wants to control the cadence.

Most production systems pick one and document it. Mixed systems (both sides
heartbeating) are common but double the traffic for marginal benefit.

**The false-positive problem.** A heartbeat declared "stale" might not mean the
peer is dead — the heartbeat itself might have been delayed by a GC pause, a CPU
pin, or a transient network jitter. Mitigations:

- **Threshold larger than interval.** A 30s timeout for a 10s interval tolerates
  a single missed heartbeat; one missed beat is the most common benign cause.
- **Multiple consecutive failures.** "Declare dead after 3 missed heartbeats" —
  the same logic K8s `failureThreshold` uses.
- **Combine with explicit RST detection.** A TCP RST or socket close is a
  faster, more authoritative death signal than a heartbeat timeout. Use
  whichever fires first.

**Type-safety notes.** `Callable[[bytes], Awaitable[None]]` precisely types the
wire-side send. The `_task` is `Task[None]` because the run loops return
implicitly; pin the result type to catch accidental return-value drift.

**When NOT to use.**

- Short-lived connections. The connection's natural lifetime is shorter than a
  sensible heartbeat interval.
- Inside a single process. You don't need to heartbeat between threads unless
  you're simulating distributed state for testing.

**Real-world examples.**

- **Kafka consumer groups** — heartbeat to the coordinator at
  `heartbeat.interval.ms`; consumer is removed from the group after
  `session.timeout.ms`.
- **Redis Streams** consumer groups (`XAUTOCLAIM`) reassign messages whose
  consumer hasn't acked within `min-idle-time`.
- **etcd / ZooKeeper / Consul** session heartbeats keep ephemeral leases alive —
  the basis of leader election and distributed locks.
- **WebSocket ping/pong frames** (RFC 6455) are protocol-level heartbeats.

**Anti-pattern variant.**

- **Timeout = interval.** No tolerance for jitter; one slow GC pause kills the
  connection.
- **Heartbeat over the application's main thread.** Heartbeat blocks behind real
  work; a busy server is misdiagnosed as dead.
- **Heartbeat with no observability.** "Connections drop sometimes." If you
  can't see heartbeat-driven disconnect rate, you can't tune the timeout.

**References.**

- _Kafka Consumer — heartbeat.interval.ms_, official docs.
- _RFC 6455 §5.5.2 — Ping_.
- Pat Helland, _Heartbeats and Failure Detectors_, ACM Queue, 2003 — the classic
  on the false-positive problem.

---

## Backpressure

**Intent.** When a producer is faster than a consumer, _push back_ on the
producer rather than letting work queue up unboundedly. Without backpressure,
the queue grows until you exhaust memory, hit OOM, swap, and take the service
down. Backpressure is the explicit signal — "slow down, or I'll reject" — that
turns an implicit collapse mode into an explicit one.

**When to reach for it.**

- Anywhere a producer can outpace a consumer: ingestion pipelines, streaming
  joins, async handlers reading from a high-volume queue.
- Any internal queue with a producer that doesn't share fate with the consumer
  (HTTP API → background worker; user input → async writer).
- Async iterators / streams between components.

**The two backpressure shapes.**

1. **Bounded queue + reject (load shedding).** When the queue is full, refuse
   new work. Producer sees an explicit error (HTTP 429, queue-full exception).
   Most appropriate when the producer can decide what to do (retry later,
   persist for replay, surface to the user).
2. **Bounded queue + block (flow control).** When the queue is full, the
   producer's `enqueue()` blocks until space frees up. Pull-based async iterator
   / generator semantics. Right when the producer must not lose data but can
   wait.

**Sketch.** Strict-typed Python 3.13+:

```python
import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass


class QueueFull(Exception):
    """Raised by a bounded-and-rejecting queue when capacity is exceeded."""


@dataclass(slots=True)
class BoundedQueueWithReject[T]:
    """Reject excess work — the load-shedding shape of backpressure."""

    capacity: int
    _queue: asyncio.Queue[T] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._queue = asyncio.Queue(maxsize=self.capacity)

    def try_put(self, item: T) -> None:
        try:
            self._queue.put_nowait(item)
        except asyncio.QueueFull as exc:
            raise QueueFull from exc

    async def get(self) -> T:
        return await self._queue.get()


@dataclass(slots=True)
class BoundedQueueWithBlock[T]:
    """Block excess work — the flow-control shape of backpressure."""

    capacity: int
    _queue: asyncio.Queue[T] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._queue = asyncio.Queue(maxsize=self.capacity)

    async def put(self, item: T) -> None:
        await self._queue.put(item)  # blocks when full

    async def get(self) -> T:
        return await self._queue.get()


# Pull-based async iterator: consumer drives the rate by deciding when to
# `__anext__`. Producer cannot outpace consumer because the producer is
# only invoked when the consumer asks.
async def pull_based_stream[T](
    fetch_batch: Callable[[], Awaitable[list[T]]],
) -> AsyncIterator[T]:
    while True:
        batch = await fetch_batch()
        if not batch:
            return
        for item in batch:
            yield item
```

**Async iterator pull-based model.** Python's `async for` and `AsyncIterator`
are inherently pull-based: the consumer drives the rate by deciding when to call
`__anext__`. The producer is only invoked when asked. This is _the_ idiomatic
backpressure shape in Python — when you can express your pipeline as a chain of
`async for` over async generators, you get backpressure for free.

**Inverse-throttle backpressure.** Per AWS Builders' Library on queue backlogs:
as the downstream queue depth grows, the upstream gateway _lowers_ its accept
rate proportionally. The math is
`accept_rps = max_rps × (1 - depth / max_depth)`. A near-empty queue passes
traffic at full rate; a near-full queue rejects nearly everything. Result: the
gateway shifts pain to _new_ requests (which can be retried) rather than letting
the existing backlog grow until the system collapses.

**The "what does the producer do?" question.** Backpressure is only as useful as
the producer's response to it. If the producer ignores the 429, or if "block"
produces an unbounded waiting line of producer threads, you've moved the queue
without bounding it. Always ask:

- On reject, does the producer have a sane behaviour? (User-visible error?
  Retry-after? Dead-letter?)
- On block, is the producer's own queue bounded? (If not, the queue is just in
  the producer process now.)

**Type-safety notes.** PEP 695 `[T]` propagates the queue's element type;
`mypy --strict` rejects mixed-type queues. The `# type: ignore[assignment]`
comments on `_queue` are a known dataclass-with-`asyncio.Queue` papercut
identical to the adaptive-limit case.

**When NOT to use.**

- A pipeline where producer and consumer share a process and an event loop. An
  unbounded `asyncio.Queue` is fine when both halves cooperate; the producer
  naturally yields when the consumer doesn't.
- A best-effort fire-and-forget pipeline where dropping is correct.

**Real-world examples.**

- **AWS SQS** with `ApproximateNumberOfMessages` driving an upstream Lambda
  reserved concurrency cap is the canonical inverse-throttle pattern.
- **Reactive Streams** (RxJava, Project Reactor, Mutiny) standardise
  backpressure-aware pub/sub with `request(N)` semantics.
- **Kafka consumer** `max.poll.records` and `pause()` / `resume()` give the
  consumer explicit backpressure handles.
- **gRPC streaming** uses HTTP/2 flow control — built-in, byte-level
  backpressure for streaming RPCs.

**Anti-pattern variant.**

- **Unbounded queue.** "It'll be fine, traffic isn't that bursty." Until it is.
  OOM. Restart. Restart again. The queue refills as soon as the service is back,
  repeat.
- **Producer ignores the reject.** "We rejected, but the producer keeps retrying
  immediately." That's not backpressure, that's a tight loop. Pair the reject
  with a `Retry-After` header or an explicit exponential backoff.
- **Block without timeout.** Producer hangs forever waiting on a queue; upstream
  caller times out; producer thread is now leaked. Always pair blocking puts
  with a deadline.

**References.**

- David Yanacek, _Avoiding insurmountable queue backlogs_, AWS Builders'
  Library.
- _Reactive Streams Specification 1.0.4_, reactive-streams.org.
- Roman Elizarov, _Backpressure in Coroutines_ (Kotlin Flow), JetBrains blog.

---

## Stacking the patterns

These patterns compose in a conventional order on an outbound call.
Top-to-bottom on a single attempt:

```
[ Adaptive Limiter ]   ← measure-and-adjust capacity bound
[ Rate Limiter ]       ← stay under downstream quota
[ Circuit Breaker ]    ← stop calling a dead dependency
[ Bulkhead ]           ← cap concurrency for THIS workload
[ Retry ]              ← transient fault recovery
[ Hedging ]            ← tail-latency mitigation, idempotent only
[ Timeout ]            ← per-attempt deadline
[ the actual call ]
```

**Why this order.**

- Timeout is innermost because it bounds a _single attempt_.
- Hedging is just outside the timeout — the hedge is itself bounded by the same
  per-attempt timeout.
- Retry sits outside hedging — a retry composes new attempts, each of which
  hedges and times out.
- Bulkhead is outside retries because retries share the bulkhead's budget. An
  open breaker should not occupy a bulkhead slot.
- Circuit breaker is outside the bulkhead so an open breaker fails fast without
  ever taking a slot.
- Rate limiter is outside the breaker because you want to throttle _before_
  deciding whether to call.
- Adaptive limiter (when present) is outermost — it gates _whether_ there is
  capacity at all.

**Budget accounting.** The non-negotiable rule:

```
per_attempt_timeout × max_attempts ≤ caller_deadline
```

If your retry budget can sleep + retry past the caller's deadline, the caller
times out mid-retry and the retry effort is wasted. Worse, the caller may itself
retry — multiplying the load.

**Patterns that should not stack.**

- **Breaker inside a retry.** The retry burns attempts hitting the open breaker;
  the breaker re-opens from the failed attempts. Always `retry(breaker(call))`,
  never `breaker(retry(call))`.
- **Hedge inside a retry.** Two attempts × two retries = four downstream calls
  per logical request. If both hedge and retry are wired naïvely, you've
  quadrupled load.
- **Retries at multiple layers.** Client retries → API gateway retries → service
  retries → DB driver retries. Three layers × three attempts each = 27×
  downstream calls. Pick _one_ layer to own retries and document it.

---

## Review checklist

For any code that crosses a process boundary:

1. Is there a timeout? What value, and how was it chosen?
2. Are timeouts split into connect / read / pool?
3. Is this call idempotent? If not, is there an idempotency key?
4. Are errors classified into `retryable` / `terminal` / `client-error`?
5. If retried: bounded attempts, full jitter, capped delay, total budget ≤
   caller deadline?
6. Is there a metric for `outcome` and `latency`?
7. If this dependency goes down, what happens to this code path? Full failure,
   fallback, circuit-broken?
8. Is the retry / breaker / bulkhead / limiter granularity per
   `(service, operation)`, not per service?
9. If this is a queue consumer: bounded attempts, DLQ, alert on DLQ depth?
10. If this is a long-lived connection: heartbeat with threshold > 1?
11. If this is a producer to an internal queue: bounded queue, explicit
    backpressure shape?
12. If this exposes a probe: liveness shallow, readiness deep, on a separate
    thread pool?

If any answer is "don't know" or "library default," stop and decide.

---

## References

### Books

- Michael T. Nygard. _Release It!: Design and Deploy Production-Ready Software._
  2nd ed. Pragmatic Bookshelf, 2018. The canonical text for the pattern set
  above; the chapter on Stability Patterns alone is worth the price of
  admission.
- Martin Kleppmann. _Designing Data-Intensive Applications._ O'Reilly, 2017.
  Chapters 8–9 on distributed-system fault models.
- Sam Newman. _Building Microservices._ 2nd ed. O'Reilly, 2021. Chapter 12 on
  resiliency in service-to-service communication.
- Chris Richardson. _Microservices Patterns._ Manning, 2018, plus the companion
  site microservices.io.
- Niall Richard Murphy, Betsy Beyer, Chris Jones, Jennifer Petoff. _Site
  Reliability Engineering._ O'Reilly, 2016. Chapter 22 on retry budgets and
  cascading failures.

### Papers and articles

- Jeff Dean & Luiz André Barroso. "The Tail at Scale." _Communications of the
  ACM_ 56, no. 2 (Feb 2013): 74–80.
- Marc Brooker. "Exponential Backoff and Jitter." _AWS Architecture Blog_,
  Mar 2015.
- Marc Brooker. "Timeouts, Retries, and Backoff with Jitter." _AWS Builders'
  Library_.
- David Yanacek. "Avoiding Insurmountable Queue Backlogs." _AWS Builders'
  Library_.
- Stripe Engineering. "Designing Robust and Predictable APIs with
  Idempotency." 2017.
- Stripe Engineering. "Scaling Your API with Rate Limiters." 2017.
- Brandur Leach. "Rate Limiting, Cells, and GCRA." brandur.org.
- Thom Wright. "The Problem with Decorrelated Jitter." 2024.
- Pete Hodgson. "Feature Toggles (aka Feature Flags)." martinfowler.com.
- Pat Helland. "Heartbeats and Failure Detectors." _ACM Queue_, 2003.
- Cardwell, Cheng, Gunn, Yeganeh, Jacobson. "BBR: Congestion-Based Congestion
  Control." _ACM Queue_, 2016.

### Specifications and tooling

- _Kubernetes — Configure Liveness, Readiness and Startup Probes._ Official
  documentation.
- _gRPC Health Checking Protocol._ gRFC L1.
- _Reactive Streams Specification 1.0.4._ reactive-streams.org.
- _RFC 6455 — The WebSocket Protocol._ IETF.
- _redis-cell — A Rate Limiting Redis Module._ redis.io.
- Netflix `concurrency-limits`. github.com/Netflix/concurrency-limits.

### Python libraries referenced

- `httpx` — async/sync HTTP with proper timeout primitives.
- `tenacity` — composable retry policies (sync + async).
- `pybreaker` — classic circuit breaker, optional Redis state.
- `purgatory` — async-native circuit breaker.
- `circuitbreaker` — decorator-style breaker.
- `aiolimiter` — leaky-bucket async rate limiter.
- `slowapi` — Flask-Limiter port for Starlette/FastAPI.
- `aiocache` — async caching with TTL primitives.
