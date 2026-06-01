# Concurrency Patterns

> In-process and intra-service patterns for getting many things done at once
> without losing your mind, your data, or your error context.

This document covers concurrency patterns that fit inside a single OS process or
a single service: actors, producers/consumers, pipelines, in-process pub/sub,
locks, futures, async event loops, structured concurrency, channels, and
fork-join. Cross-service messaging (Kafka, RabbitMQ, queues-as-architecture)
belongs in `system/communication.md`.

The bias of this document is toward Python 3.11+ idioms — `asyncio.TaskGroup`
(PEP 654), `async def` cooperative multitasking, `concurrent.futures` for
thread/process pools — but several patterns are best illustrated in other
languages where the idiom is native. You'll see one **Go** snippet (channels)
and one **Erlang/Elixir** snippet (actor mailbox) alongside the Python version.

## How to use this file

- **Pick the patterns you have a real need for.** Concurrency is the easiest
  place in software engineering to invent a problem and a solution at the same
  time. If your code is single-threaded and works, do not introduce concurrency.
- **Per-pattern shape.** Each entry has _Intent · How it manifests · Sketch ·
  Type-safety notes · When NOT to use · Real-world examples · References_.
- **Strict typing.** Every Python sketch is written to target mypy `--strict`
  and pyright `--strict`: no `Any`, PEP 604 unions, PEP 695 generics, `Self`,
  `Final`, `@override`, and the annotation-evaluation policy in `SKILL.md`
  conventions. The `python:typings` sister skill has the full canonical
  reference if it is also loaded.

## the-cooperative-vs-preemptive-axis

Before any pattern, internalize the two axes you choose along.

**Concurrency vs parallelism.** Concurrency is _being able to switch between
tasks_; parallelism is _running tasks simultaneously_. A single-CPU async event
loop is concurrent but not parallel. A `multiprocessing.Pool` is both. A
`ThreadPoolExecutor` in CPython is concurrent for I/O-bound work but rarely
parallel for CPU-bound work because of the GIL (until PEP 703 free-threading
lands universally).

**Cooperative vs preemptive.**

- **Cooperative** (`asyncio`, Trio, AnyIO, Erlang processes for the most part):
  a task yields control only at `await` points. No surprise context switches.
  You reason about atomicity between any two `await`s.
- **Preemptive** (OS threads, `multiprocessing` workers): the scheduler can
  switch tasks anywhere. Every memory access is potentially interleaved with
  another thread.

```python
# Cooperative: this is atomic with respect to other coroutines.
counter += 1
# Preemptive: this is a read-modify-write race in a multithreaded context.
counter += 1
```

**The blocking-call rule.** In cooperative concurrency, _do not call blocking
I/O on the event loop_. Use `asyncio.to_thread(...)` (3.9+) for one-off blocking
calls and `run_in_executor(...)` for hot paths. Skipping this rule makes one
slow request stall the whole loop. (Beazley, _Python Concurrency from the Ground
Up_, PyCon 2015, the demo where one `time.sleep` in a coroutine blocks every
connected client.)

---

## actor-model

**What it is / Intent.** Each unit of work ("actor") is an isolated process with
private state, a mailbox, and a handler that consumes messages one at a time.
Actors communicate _only_ by sending messages. No shared memory. (Hewitt et al.,
1973; popularized by Erlang and Akka.)

The model's invariant: an actor's state can only be mutated by the actor itself,
in response to a message it pulled off its own mailbox. Two actors cannot race
on a shared variable because there is no shared variable.

**When to reach for it / How it manifests.**

- A natural many-conversations workload: each chat connection, game session, IoT
  device, or trading symbol owns its state and processes its own message stream.
- You need supervision: actors crash; a supervisor restarts them. (Erlang/OTP's
  "let it crash" philosophy.)
- The system must isolate failures — one actor blowing up doesn't take down the
  others.
- Anti-signal: a request/response API where the response must be returned to a
  specific caller. Actors handle that with explicit `reply_to` references; if
  every interaction is request/response, you've reinvented function calls with
  extra steps.

**Sketch — Erlang/Elixir mailbox semantics (the canonical version).**

```elixir
# Elixir — a counter actor with native mailbox + pattern-matched handler.
defmodule Counter do
  def start(initial \\ 0) do
    spawn(fn -> loop(initial) end)
  end

  defp loop(state) do
    receive do
      {:incr, by}        -> loop(state + by)
      {:get, reply_to}   -> send(reply_to, {:counter, state}); loop(state)
      :stop              -> :ok
    end
  end
end

pid = Counter.start()
send(pid, {:incr, 5})
send(pid, {:get, self()})
receive do {:counter, n} -> IO.puts("count is #{n}") end
```

The `receive do ... end` block is the actor's mailbox processing: pull one
message, pattern-match, recurse with new state. No shared memory; no locks; the
runtime schedules millions of these processes.

**Sketch — Python with `asyncio.Queue` per actor.**

```python
import asyncio
from dataclasses import dataclass
from typing import Final, Self

@dataclass(frozen=True, slots=True)
class Incr:
    by: int

@dataclass(frozen=True, slots=True)
class Get:
    reply_to: asyncio.Future[int]

@dataclass(frozen=True, slots=True)
class Stop: ...

CounterMessage = Incr | Get | Stop

class CounterActor:
    """Actor: one async task, one mailbox, private state. Never share `self._state`."""

    def __init__(self, initial: int = 0) -> None:
        self._state: int = initial
        self._mailbox: asyncio.Queue[CounterMessage] = asyncio.Queue(maxsize=1024)
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> Self:
        self._task = asyncio.create_task(self._run(), name="counter-actor")
        return self

    async def _run(self) -> None:
        while True:
            msg = await self._mailbox.get()
            match msg:
                case Incr(by=by):
                    self._state += by
                case Get(reply_to=fut):
                    if not fut.done():
                        fut.set_result(self._state)
                case Stop():
                    return

    async def tell(self, msg: CounterMessage) -> None:
        await self._mailbox.put(msg)

    async def ask(self) -> int:
        fut: asyncio.Future[int] = asyncio.get_running_loop().create_future()
        await self._mailbox.put(Get(reply_to=fut))
        return await fut
```

```python
async def main() -> None:
    actor = await CounterActor().start()
    await actor.tell(Incr(by=5))
    await actor.tell(Incr(by=2))
    print(await actor.ask())  # 7
```

**Type-safety / static-analysis notes.** The message type is a tagged union
(`Incr | Get | Stop`); `match` is exhaustive when every variant is named, and
pyright reports unreachable cases. Each actor's state is encapsulated in `self`;
the only public surface is `tell` (fire-and-forget) and `ask` (request/reply).
Never expose mutators on the actor.

**When NOT to use.** Workloads dominated by shared computation over shared state
with infrequent contention (use locks). Pure data pipelines (use
channels/queues). One-shot fan-out (use `asyncio.gather`). Actors are the right
answer when the _unit of state_ maps naturally to an isolated process.

**Real-world examples.** WhatsApp's chat backend (Erlang). Discord's voice
servers (Elixir). MMO game servers built on Akka. Twitter's Manhattan database
used Akka actors. Pykka and Thespian provide actor frameworks for Python.

**References.** Hewitt, Bishop & Steiger, "A Universal Modular Actor Formalism
for Artificial Intelligence," IJCAI 1973. Armstrong, _Programming Erlang_, 2nd
ed., Pragmatic Bookshelf, 2013, ch. 8 ("Concurrency"), ch. 13 ("Errors in
Concurrent Programs"). Vernon, _Reactive Messaging Patterns with the Actor
Model_, Addison-Wesley, 2015.

---

## producer-consumer

**What it is / Intent.** A producer puts work items onto a bounded queue; one or
more consumers pull and process them. The queue's _bound_ is the only thing
keeping memory finite when the producer outpaces the consumers.

**Bounded vs unbounded.** A bounded queue applies _backpressure_: when full,
`queue.put()` blocks the producer. An unbounded queue is a memory leak that
takes longer to manifest. Always cap the queue.

**When to reach for it / How it manifests.**

- One source of work fanning out to N workers (web scraper → parsers, request
  log → index writers).
- Smoothing a bursty producer with a steady consumer.
- Decoupling stages of a transformation that have different throughputs.
- Anti-signal: producer and consumer are the same task — you don't need a queue,
  you need a function call.

**Sketch — `asyncio.Queue` with bounded backpressure.**

```python
import asyncio
from dataclasses import dataclass
from typing import Final

@dataclass(frozen=True, slots=True)
class WorkItem:
    payload: bytes
    job_id: str

QUEUE_CAPACITY: Final[int] = 100
NUM_WORKERS: Final[int] = 8

async def producer(q: asyncio.Queue[WorkItem | None], source: list[bytes]) -> None:
    for i, payload in enumerate(source):
        await q.put(WorkItem(payload=payload, job_id=f"job-{i}"))
    # Sentinel: one None per worker so each can shut down cleanly.
    for _ in range(NUM_WORKERS):
        await q.put(None)

async def consumer(q: asyncio.Queue[WorkItem | None], worker_id: int) -> None:
    while True:
        item = await q.get()
        try:
            if item is None:
                return
            await _process(item, worker_id)
        finally:
            q.task_done()

async def _process(item: WorkItem, worker_id: int) -> None:
    # Real work here. Handle errors per-item, never let one bad item kill the consumer.
    print(f"worker={worker_id} job={item.job_id} bytes={len(item.payload)}")

async def main(source: list[bytes]) -> None:
    q: asyncio.Queue[WorkItem | None] = asyncio.Queue(maxsize=QUEUE_CAPACITY)
    async with asyncio.TaskGroup() as tg:
        tg.create_task(producer(q, source), name="producer")
        for w in range(NUM_WORKERS):
            tg.create_task(consumer(q, w), name=f"consumer-{w}")
        # TaskGroup waits for all tasks; backpressure is enforced by maxsize.
```

**Sentinel pattern for shutdown.** The `None` sentinel is the canonical "no more
work" signal. One per consumer, so each shuts down independently. Alternative:
`asyncio.Event` for "everyone wrap up now."

**Type-safety / static-analysis notes.** `asyncio.Queue[WorkItem | None]` makes
the sentinel type-visible: consumers know to check for `None`. mypy/pyright flag
accidentally `put`-ing the wrong type. Mark `WorkItem` `frozen=True` to prevent
accidental in-place mutation while it's on the queue.

**When NOT to use.** When the producer and consumer have the same throughput and
you don't need batching — direct calls are simpler. When the queue depth is
always 1 — that's just a function call wrapped in ceremony.

**Real-world examples.** Sidekiq workers (Ruby). Celery pipelines (Python).
RabbitMQ consumers. Kafka consumer groups (across services, but the in-service
pattern is identical). Almost every web scraper.

**References.** Hoare, _Communicating Sequential Processes_, Prentice Hall, 1985
— the theoretical roots. Lea, _Concurrent Programming in Java_, 2nd ed.,
Addison-Wesley, 1999, ch. 4 ("Creating Threads"). Beazley, _Python Concurrency
from the Ground Up_, PyCon 2015.

---

## pipeline-dataflow

**What it is / Intent.** Chained stages, each consuming from the previous
stage's queue and producing to the next. Each stage is a producer/consumer; the
pipeline is the composition. Useful when work decomposes into ordered
transformations with different throughputs (parse → enrich → write).

```text
  source ──▶ [stage 1] ──▶ Q1 ──▶ [stage 2] ──▶ Q2 ──▶ [stage 3] ──▶ sink
                              (bounded)            (bounded)
```

**When to reach for it / How it manifests.**

- ETL: extract → transform → load.
- Inference pipelines: download → preprocess → infer → postprocess → upload.
- Streaming analytics: parse → window → aggregate → emit.
- Anti-signal: each stage is so cheap that the queue overhead dominates. Profile
  first.

**Sketch.**

```python
import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Final

@dataclass(frozen=True, slots=True)
class RawEvent:
    raw: bytes

@dataclass(frozen=True, slots=True)
class Parsed:
    user_id: str
    action: str

@dataclass(frozen=True, slots=True)
class Enriched:
    user_id: str
    action: str
    country: str

STAGE_CAPACITY: Final[int] = 64

async def stage_parse(
    inp: asyncio.Queue[RawEvent | None],
    out: asyncio.Queue[Parsed | None],
) -> None:
    while True:
        item = await inp.get()
        if item is None:
            await out.put(None)
            return
        # Per-item error handling — never propagate exceptions through the queue.
        try:
            parsed = _parse(item)
        except ValueError:
            inp.task_done()
            continue
        await out.put(parsed)
        inp.task_done()

async def stage_enrich(
    inp: asyncio.Queue[Parsed | None],
    out: asyncio.Queue[Enriched | None],
    geo: "GeoLookup",
) -> None:
    while True:
        item = await inp.get()
        if item is None:
            await out.put(None)
            return
        country = await geo.country_for(item.user_id)
        await out.put(Enriched(user_id=item.user_id, action=item.action, country=country))
        inp.task_done()

async def stage_sink(inp: asyncio.Queue[Enriched | None]) -> int:
    count = 0
    while True:
        item = await inp.get()
        if item is None:
            return count
        await _write(item)
        count += 1
        inp.task_done()

class GeoLookup:
    async def country_for(self, user_id: str) -> str: ...

def _parse(event: RawEvent) -> Parsed: ...
async def _write(item: Enriched) -> None: ...

async def run_pipeline(source: AsyncIterator[bytes], geo: GeoLookup) -> int:
    q1: asyncio.Queue[RawEvent | None] = asyncio.Queue(maxsize=STAGE_CAPACITY)
    q2: asyncio.Queue[Parsed | None] = asyncio.Queue(maxsize=STAGE_CAPACITY)
    q3: asyncio.Queue[Enriched | None] = asyncio.Queue(maxsize=STAGE_CAPACITY)

    total = 0
    async with asyncio.TaskGroup() as tg:
        async def feeder() -> None:
            async for raw in source:
                await q1.put(RawEvent(raw=raw))
            await q1.put(None)

        tg.create_task(feeder(), name="feeder")
        tg.create_task(stage_parse(q1, q2), name="parse")
        tg.create_task(stage_enrich(q2, q3, geo), name="enrich")
        sink_task = tg.create_task(stage_sink(q3), name="sink")
    total = sink_task.result()
    return total
```

**Backpressure.** Bounded queues at every stage. If `stage_enrich` is slow,
`stage_parse` blocks on `out.put` and stops pulling, which blocks `feeder`. The
whole pipeline self-throttles to the slowest stage's rate.

**Type-safety / static-analysis notes.** Each queue is
`asyncio.Queue[Stage | None]` — the type makes the boundary between stages
legible. pyright catches passing the wrong queue between stages. `frozen=True`
dataclasses prevent accidental mutation between stages.

**When NOT to use.** When the throughput difference between stages is small and
queue overhead dominates. When stages have very different fan-out (a 10× fan-out
at stage 2 needs a different shape — multiple stage-2 workers on the same
queue). When error handling needs to span stages — pipelines hide cross-stage
state.

**Real-world examples.** Apache Beam / Dataflow (cross-process; same shape).
NumPy vectorized pipelines. PyTorch DataLoader (samplers → transforms →
batches). FastStream's in-process flow.

**References.** Hoare, _Communicating Sequential Processes_, 1985. Akidau et
al., _Streaming Systems_, O'Reilly, 2018, ch. 1–3 (Apache Beam model). Beazley,
_Python Cookbook_, 3rd ed., O'Reilly, 2013, recipe 12.13 ("Polling Multiple
Thread Queues").

---

## pub-sub-in-process

**What it is / Intent.** A publisher emits a message; zero or more subscribers
receive it. The publisher doesn't know who's listening. _In-process_ pub/sub is
a thin event bus inside one runtime; _cross-service_ pub/sub is a separate
document (`system/communication.md`).

The contract is loose: order is not guaranteed (or only within a topic),
delivery is typically at-least-once or fire-and-forget, subscribers are
independent.

**When to reach for it / How it manifests.**

- One state change has multiple consequences (`OrderPlaced` → bill, ship,
  notify).
- Modules want to react to each other without knowing each other's interfaces.
- Anti-signal: pub/sub used as RPC. If you wait for a reply, it's
  request/response.

**Sketch.**

```python
import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Final, NewType

EventId = NewType("EventId", str)

@dataclass(frozen=True, slots=True)
class OrderPlaced:
    event_id: EventId
    order_id: str
    total_cents: int
    placed_at: datetime
    version: Final[int] = 1

class EventBus:
    """In-process pub/sub. Errors in one subscriber do not affect the others."""

    def __init__(self) -> None:
        self._subs: dict[type[object], list[Callable[[object], Awaitable[None]]]] = (
            defaultdict(list)
        )

    def subscribe[Ev](
        self, event_type: type[Ev], handler: Callable[[Ev], Awaitable[None]]
    ) -> None:
        # Internal storage is type-erased to object; this is the one cast we accept.
        self._subs[event_type].append(handler)  # type: ignore[arg-type]

    async def publish[Ev](self, event: Ev) -> None:
        handlers = list(self._subs[type(event)])
        results = await asyncio.gather(
            *(self._safe_call(h, event) for h in handlers),
            return_exceptions=True,
        )
        for r in results:
            if isinstance(r, BaseException):
                # Log per-handler failures; do not let one bad subscriber kill the others.
                print(f"subscriber raised: {r!r}")

    @staticmethod
    async def _safe_call[Ev](
        h: Callable[[Ev], Awaitable[None]], event: Ev
    ) -> None:
        await h(event)
```

**Difference from cross-service pub/sub.** In-process: handlers see Python
objects directly; failure semantics are governed by exception handling; the bus
is a `dict`. In cross-service (Kafka, Pub/Sub, NATS): messages are serialized,
delivered over the wire, governed by broker semantics (acks, partitions,
retention, dead-letter queues). Treat in-process pub/sub as a _prototype
boundary_ — the day you split a module to a service, the bus call becomes an
outbox publish.

**Type-safety / static-analysis notes.** Use PEP 695 generics on `subscribe` and
`publish` so handlers are type-checked against their event type. The internal
`dict` carries an unavoidable `object` (the type-erasure cost of dynamic
dispatch on `type(event)`); keep that single ignore narrow.

**When NOT to use.** When there's exactly one known subscriber and the producer
expects that specific behavior — that's a direct call. When ordering matters
across handlers (use a pipeline). When you need at-least-once delivery across
process restarts (need persistence; use an outbox).

**Real-world examples.** Django signals. Flask `signals_blueprint`. Apache
Camel's in-process routes. The internal event buses inside Shopify's Rails
monolith.

**References.** Vernon, _Implementing Domain-Driven Design_, Addison-Wesley,
2013, ch. 8 ("Domain Events"). Khononov, _Learning Domain-Driven Design_,
O'Reilly, 2021, ch. 9 ("Communication Patterns").

---

## reader-writer-lock

**What it is / Intent.** A lock that allows many concurrent _readers_ but only
one _writer_; readers and writers are mutually exclusive. Optimization for
read-heavy shared state. (Courtois, Heymans & Parnas, "Concurrent Control with
Readers and Writers," _Communications of the ACM_, 1971.)

**When to reach for it / How it manifests.**

- Read-heavy in-memory cache shared by threads, where readers vastly outnumber
  writers.
- Configuration or routing tables read on every request, mutated rarely.
- Anti-signal: any async code. There's no preemption; you don't need RW locks
  for cooperative tasks.

**Why "almost always wrong in async code."** In `asyncio` (or Trio, or AnyIO), a
coroutine cannot be interrupted between `await` points. Two coroutines reading a
`dict` in non-`await` code don't race. The only contention is across `await`s —
and at that point, what you actually want is a _queue_ or an _actor_, not a
lock. RW locks are for preemptive concurrency (threads, multiprocessing).

**Sketch — Python (threads).**

```python
import threading
from typing import Final, TypeVar

K = TypeVar("K")
V = TypeVar("V")

class RWDict[K, V]:
    """A dict guarded by a writer-preferred reader/writer lock.

    The implementation is intentionally explicit; CPython does not ship a native RW lock.
    """

    def __init__(self) -> None:
        self._data: dict[K, V] = {}
        self._readers: int = 0
        self._readers_lock: threading.Lock = threading.Lock()
        self._write_lock: threading.Lock = threading.Lock()

    def read(self, key: K) -> V | None:
        with self._readers_lock:
            self._readers += 1
            if self._readers == 1:
                self._write_lock.acquire()
        try:
            return self._data.get(key)
        finally:
            with self._readers_lock:
                self._readers -= 1
                if self._readers == 0:
                    self._write_lock.release()

    def write(self, key: K, value: V) -> None:
        with self._write_lock:
            self._data[key] = value
```

**Type-safety / static-analysis notes.** PEP 695 generics: `RWDict[K, V]` types
both keys and values. mypy/pyright catch most misuse. What they cannot catch:
forgetting to release the lock on an exception path. Always use `with` or
`try/finally`. ruff `B904` flags some re-raise issues.

**When NOT to use.**

- Asyncio / Trio code. Use a queue or actor; there's no benefit.
- Workloads where contention is so low that a regular `Lock` is fine. Profile
  before switching.
- When you can replace shared mutable state with copy-on-write
  (`MappingProxyType`, `tuple`, `frozenset`).

**Real-world examples.** PostgreSQL's MVCC implements an effective reader-writer
model in the database itself. Java's `ReentrantReadWriteLock` is the canonical
implementation. Go's `sync.RWMutex` (often misused — see Cox & Pike's
commentary).

**References.** Courtois, Heymans & Parnas, "Concurrent Control with Readers and
Writers," _CACM_ 14(10), 1971. Lea, _Concurrent Programming in Java_, 2nd ed.,
1999, ch. 3 ("Using Synchronization"). Pike, "Concurrency Is Not Parallelism,"
Heroku Waza 2012.

---

## future-promise

**What it is / Intent.** A handle to a value that is being computed elsewhere.
The _producer_ fulfills it; the _consumer_ awaits it. (Liskov & Shrira,
"Promises: Linguistic Support for Efficient Asynchronous Procedure Calls," PLDI
1988.)

In Python: `concurrent.futures.Future` (threads/processes) and `asyncio.Future`
(coroutines).

**When to reach for it / How it manifests.**

- Submitting work to a pool and getting a handle to the eventual result.
- Bridging callback APIs to `await` (`loop.create_future()` and `set_result`
  from a callback).
- Composing parallel work where each task is independent.
- Anti-signal: creating an `asyncio.Future` manually when `asyncio.Task` would
  do — Tasks are Futures with a coroutine to drive them.

**Sketch — `concurrent.futures` (threads).**

```python
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Final

@dataclass(frozen=True, slots=True)
class FetchResult:
    url: str
    status: int
    body: bytes

def fetch(url: str) -> FetchResult:
    # Real impl: httpx, requests, etc. Blocking on purpose for the example.
    ...

URLS: Final[list[str]] = ["https://a", "https://b", "https://c"]

def fetch_all(urls: list[str]) -> list[FetchResult]:
    results: list[FetchResult] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures: dict[Future[FetchResult], str] = {pool.submit(fetch, u): u for u in urls}
        for fut in as_completed(futures):
            try:
                results.append(fut.result())
            except OSError as exc:
                # Per-future error: do not let one failure kill the batch.
                url = futures[fut]
                print(f"fetch failed for {url}: {exc}")
    return results
```

**Sketch — bridging a callback API to `await`.**

```python
import asyncio
from typing import Final

def legacy_with_callback(on_done: "Callable[[int], None]") -> None:
    """Imagine this is a third-party library that takes a callback."""
    ...

async def asyncify_legacy() -> int:
    loop = asyncio.get_running_loop()
    fut: asyncio.Future[int] = loop.create_future()
    legacy_with_callback(lambda result: loop.call_soon_threadsafe(fut.set_result, result))
    return await fut
```

**Chaining via `await`.** In `asyncio`, you don't need explicit `.then(...)`
chaining — `await` _is_ chaining.
`result = await first(); also = await second(result)` is the JavaScript-promise
equivalent of `first().then(second)`.

**Type-safety / static-analysis notes.** `Future[FetchResult]` makes the result
type visible. `as_completed` returns futures in completion order;
`concurrent.futures.wait` gives done/pending sets when you need different
semantics. Always handle exceptions in each future's `.result()`; an unraised
exception in a Future is silent.

**When NOT to use.** When you're already in an `async def` and writing
`await some_coroutine()` — there's no need to create a Future explicitly. When
you find yourself chaining `.then(.then(.then()))` style — switch to
async/await.

**Real-world examples.** JavaScript Promises. Java's `CompletableFuture`.
Scala's `Future`. Python's `concurrent.futures.Future` is the proximate ancestor
of `asyncio`'s.

**References.** Liskov & Shrira, "Promises: Linguistic Support for Efficient
Asynchronous Procedure Calls," PLDI 1988. _Python docs_, "concurrent.futures —
Launching parallel tasks,"
<https://docs.python.org/3/library/concurrent.futures.html>.

---

## async-await-event-loop

**What it is / Intent.** Cooperative multitasking on a single OS thread. An
_event loop_ runs one coroutine at a time; the coroutine yields control at
`await` points; the loop schedules the next ready coroutine. Concurrency without
preemption, locks, or memory races on Python state. (PEP 492, 2015; PEP 3156,
2012.)

**Why it works for I/O-bound work.** Most server work is waiting — for the
database, for HTTP, for Redis. While one request is waiting, the loop can drive
thousands of others. For **CPU-bound** work, async is a trap: a CPU-bound
coroutine starves every other task until it `await`s.

**The cooperative-concurrency rules.**

1. **No `asyncio.run()` inside libraries.** Libraries expose `async def`
   functions and let the application's entrypoint own the loop. A library that
   calls `asyncio.run()` makes itself impossible to compose.

2. **No blocking calls on the loop.** `time.sleep`, `requests.get`,
   `psycopg2.execute`, `subprocess.run` — every blocking call freezes the loop.
   Use the async equivalent (`asyncio.sleep`, `httpx.AsyncClient`, `asyncpg`,
   `asyncio.create_subprocess_exec`), or, for one-off blocking calls,
   `asyncio.to_thread(blocking_fn, *args)`.

3. **Don't mix loops.** One process, one loop. `asyncio.new_event_loop()` is a
   footgun for advanced cases; the default `asyncio.run()` is correct.

4. **Cancellation is cooperative.** `CancelledError` is delivered at `await`
   points. A coroutine that doesn't `await` for a long time cannot be cancelled.

**Sketch.**

```python
import asyncio
import time
from typing import Final

async def io_bound(name: str, ms: int) -> str:
    await asyncio.sleep(ms / 1000)
    return f"{name} done after {ms}ms"

def cpu_bound(n: int) -> int:
    # Blocking on purpose: factorial is pure CPU.
    total = 1
    for i in range(2, n + 1):
        total *= i
    return total

async def main() -> None:
    # I/O-bound work: many tasks, all overlap.
    io_results = await asyncio.gather(
        io_bound("a", 100),
        io_bound("b", 100),
        io_bound("c", 100),
    )
    print(io_results)

    # CPU-bound work: must go to a thread (or a process for true parallelism).
    cpu_result = await asyncio.to_thread(cpu_bound, 10_000)
    print(f"factorial of 10_000 has {len(str(cpu_result))} digits")

if __name__ == "__main__":
    asyncio.run(main())
```

**Type-safety / static-analysis notes.** `async def f() -> T` is a
`Coroutine[Any, Any, T]`; awaiting it produces `T`. mypy and pyright check that
you `await` coroutines — forgetting `await` returns a coroutine object you never
run, and ruff `RUF006`/`ASYNC*` rules catch many of the common mistakes
(`asyncio.create_task` without keeping a reference). Use `asyncio.TaskGroup`
(PEP 654, 3.11+) instead of bare `create_task` to avoid orphaned tasks.

**When NOT to use.** CPU-bound workloads (use processes). Workloads that don't
have multiple concurrent things to do. Code that genuinely needs preemption —
async won't preempt a runaway loop.

**Real-world examples.** FastAPI / Starlette servers. aiohttp clients.
trio-based networking tools. Every async DB driver (`asyncpg`, `aiosqlite`,
`motor`).

**References.** PEP 492, "Coroutines with async and await syntax," 2015. PEP
3156, "Asynchronous IO Support Rebooted," 2012. Beazley, _Python Concurrency
from the Ground Up_, PyCon 2015 — the foundational talk on the asyncio model.
_Python docs_, "asyncio — Asynchronous I/O,"
<https://docs.python.org/3/library/asyncio.html>.

---

## structured-concurrency

**What it is / Intent.** Make concurrent task lifetimes match lexical scopes. A
block that spawns N tasks does not return until all N tasks have finished (or
all have been cancelled and finished cleanly). Errors in any task propagate;
cancellation propagates. The shape mirrors how exception handling tames `goto` —
structured concurrency tames "go statements." (Smith, "Notes on structured
concurrency, or: Go statement considered harmful," 2018.)

> "go statements are a form of goto statement … whenever you call a function, it
> might or might not spawn some background task … any function can open a
> nursery and run multiple concurrent tasks, but the function can't return until
> they've all finished." — Smith, _Notes on structured concurrency_, 2018.

In Python: `asyncio.TaskGroup` (3.11+, PEP 654). In Trio: nurseries (the
original).

**Why this matters.** The "go statement considered harmful" argument is not a
stylistic preference; it's the same argument Dijkstra made against `goto`.
Without structure:

- A function may secretly spawn tasks that outlive it.
- An exception in a background task is silently dropped.
- Resources opened in the parent are released while children are still using
  them.
- Cancellation from above doesn't reach children.

With `TaskGroup`/nursery:

- Tasks cannot outlive the block. The `async with` waits for all of them.
- Exceptions are aggregated into `ExceptionGroup` (PEP 654) and raised at the
  block's end.
- An exception in any child cancels its siblings, then re-raises at the
  boundary.
- A `CancelledError` from outside cancels every child.

**Sketch.**

```python
import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

@dataclass(frozen=True, slots=True)
class FetchSpec:
    name: str
    url: str

@dataclass(frozen=True, slots=True)
class FetchResult:
    name: str
    status: int

async def fetch_one(spec: FetchSpec) -> FetchResult:
    # Real: httpx.AsyncClient. Mocked here for type-correctness.
    await asyncio.sleep(0.01)
    return FetchResult(name=spec.name, status=200)

async def fetch_all(specs: Sequence[FetchSpec]) -> list[FetchResult]:
    results: list[FetchResult] = []
    # async with TaskGroup: lifetimes are bounded by the block.
    # If any child raises, ALL siblings are cancelled and the error re-raises here.
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(fetch_one(s), name=f"fetch-{s.name}") for s in specs]
    # On normal exit, all tasks completed.
    for t in tasks:
        results.append(t.result())
    return results
```

**Cancellation propagation.** If a `CancelledError` arrives at the parent, the
`TaskGroup` cancels every running child and waits for them to clean up before
re-raising at the boundary.

```python
async def with_timeout() -> None:
    try:
        async with asyncio.timeout(5.0):
            async with asyncio.TaskGroup() as tg:
                tg.create_task(slow_op())
                tg.create_task(another_slow_op())
        # If we reach here, both completed within 5 seconds.
    except TimeoutError:
        # Both children were cancelled cleanly when the timeout fired.
        ...
```

**Error aggregation.** When two children raise, you get an `ExceptionGroup`
containing both — not just the first.

```python
import asyncio

async def boom() -> None:
    raise RuntimeError("boom")

async def main() -> None:
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(boom())
            tg.create_task(boom())
    except* RuntimeError as eg:
        # PEP 654 except*: handle ExceptionGroup branches separately.
        for exc in eg.exceptions:
            print(f"caught: {exc!r}")
```

**Type-safety / static-analysis notes.** `tg.create_task(coro)` returns
`asyncio.Task[T]` where `T` is the coroutine's return type — pyright and mypy
infer this correctly. PEP 654's `except*` is checked: a non-exception-group
target raises a type error. ruff has rules to flag bare `asyncio.create_task`
outside a `TaskGroup`.

**When NOT to use.** A single fire-and-forget task whose lifetime really must
outlive the caller (a long-running daemon). Even then, the daemon should be
supervised — typically by another `TaskGroup` at the application root.

**Real-world examples.** Trio (the original — Smith's library). PEP 654's
`TaskGroup` in the Python stdlib. Kotlin's `coroutineScope`. Swift 5.5+
structured concurrency.

**References.** Smith, Nathaniel J., "Notes on structured concurrency, or: Go
statement considered harmful," 2018,
<https://vorpus.org/blog/notes-on-structured-concurrency-or-go-statement-considered-harmful/>.
PEP 654, "Exception Groups and except*," 2021. PEP 671 (rejected — but see the
discussion on async-context managers and structured cancellation). *Trio docs\*,
"Tasks and Nurseries," <https://trio.readthedocs.io>.

---

## channels-go-style

**What it is / Intent.** A typed, optionally-bounded conduit between concurrent
senders and receivers. Originated in Hoare's _Communicating Sequential
Processes_ (1978); popularized by Go. The shape: `ch <- v` (send) and
`v := <-ch` (receive). Closed channels signal end-of-stream.

**Channels vs queues.** In Python, `asyncio.Queue` _is_ a channel — almost. The
differences:

|                               | Go channel               | `asyncio.Queue`       | `aiochannel` |
| ----------------------------- | ------------------------ | --------------------- | ------------ |
| Typed                         | yes                      | yes (PEP 695 generic) | yes          |
| Bounded                       | yes (capacity)           | yes (`maxsize`)       | yes          |
| Closeable                     | yes (`close(ch)`)        | no — sentinel pattern | yes          |
| `select`-able                 | yes (`select` statement) | no — manual           | partial      |
| Receive on closed signals end | yes                      | sentinel `None`       | yes          |

If you need close + select semantics, use `aiochannel`. For simple
producer/consumer in asyncio, `asyncio.Queue` with a sentinel is idiomatic.

**Sketch — Go (the canonical version).**

```go
package main

import (
    "fmt"
    "time"
)

func producer(ch chan<- int, n int) {
    for i := 0; i < n; i++ {
        ch <- i             // send; blocks if buffered channel is full
    }
    close(ch)               // signal end-of-stream
}

func consumer(ch <-chan int, done chan<- bool) {
    for v := range ch {     // ranges until ch is closed AND drained
        fmt.Println("got", v)
    }
    done <- true
}

func main() {
    ch := make(chan int, 8) // bounded buffer of 8
    done := make(chan bool)
    go producer(ch, 100)
    go consumer(ch, done)
    <-done
    _ = time.Now
}
```

The Go shape uses _direction-typed channels_ (`chan<- int` send-only,
`<-chan int` receive-only) for static safety, plus `for v := range ch` which
exits cleanly on close.

**Sketch — Python with `aiochannel`.**

```python
import asyncio
from typing import Final
from aiochannel import Channel

CAPACITY: Final[int] = 8

async def producer(ch: Channel[int], n: int) -> None:
    for i in range(n):
        await ch.put(i)
    ch.close()  # signals end-of-stream to receivers

async def consumer(ch: Channel[int]) -> int:
    total = 0
    async for v in ch:  # iterates until close + drain
        total += v
    return total

async def main() -> None:
    ch: Channel[int] = Channel(maxsize=CAPACITY)
    async with asyncio.TaskGroup() as tg:
        tg.create_task(producer(ch, 100))
        consumer_task = tg.create_task(consumer(ch))
    print(consumer_task.result())
```

**Sketch — Python with vanilla `asyncio.Queue` + sentinel.**

```python
import asyncio
from typing import Final

CAPACITY: Final[int] = 8

async def producer(q: asyncio.Queue[int | None], n: int) -> None:
    for i in range(n):
        await q.put(i)
    await q.put(None)  # sentinel = "channel closed"

async def consumer(q: asyncio.Queue[int | None]) -> int:
    total = 0
    while True:
        v = await q.get()
        if v is None:
            return total
        total += v

async def main() -> None:
    q: asyncio.Queue[int | None] = asyncio.Queue(maxsize=CAPACITY)
    async with asyncio.TaskGroup() as tg:
        tg.create_task(producer(q, 100))
        consumer_task = tg.create_task(consumer(q))
    print(consumer_task.result())
```

**Type-safety / static-analysis notes.** PEP 695 generics make `Channel[int]` /
`Queue[int]` type-precise. Direction-typing (Go's send-only/receive-only channel
types) isn't expressible in Python; if you need that discipline, encapsulate the
channel inside a class that exposes only `put` or only `get`.

**When NOT to use.** When you don't have multiple concurrent
producers/consumers. When the buffer is always 1 — that's a `Future`. When you
need fan-out broadcast (one send to many receivers): channels don't do that
natively. Use pub/sub.

**Real-world examples.** Go's stdlib pervasively (every concurrent Go program).
Python: `aiochannel` for a faithful port; `janus` for thread/asyncio bridging.
Erlang processes internally use mailboxes that resemble unbuffered channels.

**References.** Hoare, _Communicating Sequential Processes_, Prentice Hall, 1985
— the theoretical basis. Pike, "Concurrency Is Not Parallelism," 2012,
<https://go.dev/talks/2012/concurrency.slide>. _Go documentation_, "A Tour of
Go: Channels," <https://go.dev/tour/concurrency/2>.

---

## fork-join

**What it is / Intent.** Split a problem into independent subtasks (fork), run
them in parallel, combine results (join). The fundamental shape of every
divide-and-conquer parallel algorithm. (Lea, "A Java Fork/Join Framework,"
2000.)

**When to reach for it / How it manifests.**

- Embarrassingly parallel work: each item is independent, each task computes its
  piece.
- A single batch of N independent calls (fan-out N HTTP requests, fan-out N
  CPU-bound computations).
- Anti-signal: subtasks share state and need synchronization. That's not
  fork-join — use a different shape (actors, channels).

**Sketch — `concurrent.futures.ThreadPoolExecutor` for I/O-bound work.**

```python
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable
from typing import Final

WORKERS: Final[int] = 16

def fetch(url: str) -> int:
    # Real: httpx, requests, etc.
    return 200

def fetch_all(urls: list[str]) -> list[int]:
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        return list(pool.map(fetch, urls))
```

**Sketch — `concurrent.futures.ProcessPoolExecutor` for CPU-bound work.**

```python
from concurrent.futures import ProcessPoolExecutor
from typing import Final

CPU_WORKERS: Final[int] = 8

def compute(n: int) -> int:
    total = 1
    for i in range(2, n + 1):
        total *= i
    return total

def compute_all(values: list[int]) -> list[int]:
    with ProcessPoolExecutor(max_workers=CPU_WORKERS) as pool:
        return list(pool.map(compute, values))
```

**Sketch — `asyncio.gather` (cooperative fork-join).**

```python
import asyncio

async def fetch_one(url: str) -> int:
    await asyncio.sleep(0.01)
    return 200

async def fetch_all(urls: list[str]) -> list[int]:
    return await asyncio.gather(*(fetch_one(u) for u in urls))
```

**`gather` vs `TaskGroup`.** Prefer `TaskGroup` for new code: it propagates
exceptions as `ExceptionGroup` rather than the first-error-only behavior of
`gather`, and it cancels siblings on failure. Use
`gather(..., return_exceptions=True)` only when you want the error-as-result
shape (rare; prefer per-task `try`).

**Type-safety / static-analysis notes.** `pool.map(fetch, urls)` — pyright
infers `Iterator[int]`. `asyncio.gather(a(), b())` is typed via overloads up to
~6 positional arguments; for variadic, the return is `list[Awaitable[T]]` where
`T` is the common type. mypy is strict here; pyright is more permissive. PEP 695
helps when you wrap fork-join in your own helper.

**When NOT to use.** When subtasks aren't independent. When there's only one
task — not fork-join, just a function call. When the join step is a complex
combine that needs streaming (use a pipeline). For very small tasks where pool
overhead dominates (tune `chunksize` in `pool.map`).

**Real-world examples.** MapReduce. Hadoop. Java's `ForkJoinPool`. Every
parallel `map` in NumPy / pandas. Most ML inference batchers.

**References.** Lea, Doug, "A Java Fork/Join Framework," ACM Java Grande, 2000.
Mattson, Sanders & Massingill, _Patterns for Parallel Programming_,
Addison-Wesley, 2004, ch. 3 ("Algorithm Structure"). _Python docs_,
"concurrent.futures."

---

## picking-a-primitive

**Decision flow.**

1. **Is the work CPU-bound?** Use `ProcessPoolExecutor` (or a separate process).
   Async doesn't parallelize CPU.
2. **Is the work I/O-bound and the codebase async?** Use `asyncio.TaskGroup` +
   per-task coroutines. Use `asyncio.to_thread` for blocking calls.
3. **Is the work I/O-bound and the codebase sync?** Use `ThreadPoolExecutor`.
   Don't drag a sync codebase into asyncio for a single feature.
4. **Are there many isolated stateful entities?** Actor model. One actor per
   entity, message-passing only.
5. **Is it a clean producer → consumer or chained stages?** Producer/consumer
   with bounded queues, or a pipeline.
6. **Is it broadcast (one event, many reactions)?** In-process pub/sub.

**Defaults.** Reach for `asyncio.TaskGroup` first for I/O-bound concurrency in
async code; `ThreadPoolExecutor` for I/O in sync code; `ProcessPoolExecutor` for
CPU in either. Other primitives are answers to specific shapes — bring them in
when the shape demands it, not preemptively.

---

## common-failure-modes

A short list of bugs you will see, and the pattern that prevents each.

- **The `asyncio.run()` in a library.** Pattern: never call `asyncio.run`
  outside the application's main entrypoint. Expose `async def`.
- **Blocking I/O on the loop.** Pattern: `asyncio.to_thread`, or use the async
  version of the library.
- **Unbounded queue.** Pattern: bound every queue. The bound is your
  backpressure.
- **Tasks orphaned by `create_task` without keeping a reference.** Pattern:
  `TaskGroup`.
- **Errors silently dropped from background tasks.** Pattern: `TaskGroup` +
  `except*`, not `gather(return_exceptions=True)`.
- **Cancellation not propagating.** Pattern: structured concurrency. Don't catch
  `CancelledError` and swallow it; re-raise.
- **RW lock in async code.** Pattern: there is no race; remove the lock and use
  a queue if there's contention across `await`s.
- **Producer outpaces consumer; memory grows.** Pattern: bounded queue applies
  backpressure to the producer.
- **Pub/sub used as RPC.** Pattern: it's a command, not an event. Call directly.
- **CPU-bound coroutine starves the loop.** Pattern: `asyncio.to_thread` for
  one-off, `ProcessPoolExecutor` for hot CPU paths.

---

## references

**Books.**

- Armstrong, Joe. _Programming Erlang_, 2nd ed. Pragmatic Bookshelf, 2013. ch.
  8, ch. 13.
- Hoare, C.A.R. _Communicating Sequential Processes_. Prentice Hall, 1985.
- Lea, Doug. _Concurrent Programming in Java: Design Principles and Patterns_,
  2nd ed. Addison-Wesley, 1999.
- Mattson, Sanders & Massingill. _Patterns for Parallel Programming_.
  Addison-Wesley, 2004.
- Beck, Kent. _Implementation Patterns_. Addison-Wesley, 2008.
- Akidau, Chernyak & Lax. _Streaming Systems_. O'Reilly, 2018. ch. 1–3.
- Vernon, Vaughn. _Reactive Messaging Patterns with the Actor Model_.
  Addison-Wesley, 2015.
- Beazley & Jones. _Python Cookbook_, 3rd ed. O'Reilly, 2013. ch. 12.

**Talks and articles.**

- Beazley, David. _Python Concurrency from the Ground Up_. PyCon 2015,
  <https://www.youtube.com/watch?v=MCs5OvhV9S4>.
- Smith, Nathaniel J. "Notes on structured concurrency, or: Go statement
  considered harmful." 2018,
  <https://vorpus.org/blog/notes-on-structured-concurrency-or-go-statement-considered-harmful/>.
- Pike, Rob. "Concurrency Is Not Parallelism." Heroku Waza 2012,
  <https://go.dev/talks/2012/concurrency.slide>.
- Hewitt, Bishop & Steiger. "A Universal Modular Actor Formalism for Artificial
  Intelligence." IJCAI 1973.
- Liskov, Barbara, and Liuba Shrira. "Promises: Linguistic Support for Efficient
  Asynchronous Procedure Calls." PLDI 1988.
- Courtois, Heymans & Parnas. "Concurrent Control with Readers and Writers."
  _CACM_ 14(10), 1971.

**PEPs and language docs.**

- PEP 492, "Coroutines with async and await syntax," 2015.
- PEP 3156, "Asynchronous IO Support Rebooted," 2012.
- PEP 654, "Exception Groups and except\*," 2021.
- PEP 695, "Type Parameter Syntax," 2022.
- _Python docs_, "asyncio," <https://docs.python.org/3/library/asyncio.html>.
- _Python docs_, "concurrent.futures,"
  <https://docs.python.org/3/library/concurrent.futures.html>.
- _Trio docs_, <https://trio.readthedocs.io>.
- _Go docs_, <https://go.dev/tour/concurrency/2>.
