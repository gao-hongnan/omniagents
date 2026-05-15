---
name: performance
description: >-
  Use when Python code may fail at scale: profiling hot paths, memory
  pressure, unbounded async fan-out, backpressure, queue design, hidden
  materialization, cache growth, expensive logging, timeouts, cancellation,
  cProfile, tracemalloc, or performance reviews that need measurement before
  refactoring.
when_to_use: >-
  Trigger for Python hot paths, memory pressure, streaming large files or
  iterables, bounded async fan-out, asyncio.TaskGroup / gather choices,
  asyncio.Queue backpressure, timeout and cancellation behavior, cache
  lifetime design, functools cache usage, TTL caches, profiling, tracemalloc
  allocation snapshots, cProfile, logging runtime metrics, or reviews where
  performance changes need measurement before refactoring.
disable-model-invocation: false
user-invocable: true
allowed-tools: []
model: inherit
paths:
  - "**/*.py"
  - "**/pyproject.toml"
shell: bash
---

# Python Runtime Patterns - Scale, Memory, Concurrency, Caching

Reach for the patterns below when measurements or boundaries demand them, not
preemptively. A `for`-loop that materialises a list of 10,000 items is
unremarkable; the same loop over 10,000,000 starves the process. A bare
`asyncio.gather` is fine over a known-bounded set; the same call over a
user-supplied iterable is a denial-of-service against your own runtime. The
patterns here address the gap between "fine for small N" and "correct for
large N".

This skill is conventions, not non-negotiables. Most code does not need any
of them. The point is to know which pattern to reach for *when* the need
arises, and to apply it the same way every time.

This skill assumes **Python 3.14+**. It relies on current stdlib behavior from
`asyncio.TaskGroup`, `asyncio.timeout`, `asyncio.Queue`, `itertools.batched`
with `strict`, `functools.cache` / `lru_cache` / `cached_property`,
`logging.Logger.isEnabledFor`, `cProfile`, `pstats`, `tracemalloc`,
`time.perf_counter`, and `time.monotonic`. For version-sensitive behavior,
query Context7 MCP or the official Python docs before changing the rule.

## Principles

- **Measure before changing shape.** Start with `cProfile` / `pstats` for CPU
  time, `tracemalloc` for Python allocation growth, realistic input size, or a
  production metric. A reviewer should be able to see the symptom that
  justifies the complexity.
- **Stream large iterables; do not materialise unless indexing or sizing
  requires it.** The default shape is `for item in source` and `yield`, not
  `list(...)`. Forced materialisation is a deliberate choice; document why.
- **Bound concurrency.** Any `asyncio.gather` / `TaskGroup` over a
  user-supplied or otherwise unbounded iterable uses a bounded task window or
  a bounded `asyncio.Queue`. A semaphore around already-created tasks limits
  execution, not memory growth.
- **Apply backpressure.** Producer / consumer pipelines use queues with
  `maxsize`. An unbounded queue just moves the memory leak from a list into an
  event-loop object.
- **Set timeouts at external boundaries.** Network, subprocess, queue, and IPC
  waits use `asyncio.timeout` / `asyncio.wait_for` or the library's timeout
  option. A missing timeout is a resource leak under partial failure.
- **Handle cancellation deliberately.** Long-lived tasks have an owner,
  propagate `CancelledError` after cleanup, and are awaited during shutdown.
  Fire-and-forget tasks are rejected unless a supervisor owns their lifetime.
- **Cache with explicit lifetime.** Pure-function caches use
  `functools.cache` / `lru_cache`; instance caches use `cached_property`;
  externally-bounded state (TTL, size cap) uses an explicit cache class.
  Never an unbounded module-level `dict` keyed by user input.
- **Prefer stdlib over hand-rolled equivalents.** `itertools.batched` (3.12+)
  supersedes the legacy `chunked` helper; `functools.cache` /
  `cached_property` supersede most `Lazy[T]` wrappers;
  `tempfile.TemporaryDirectory` supersedes hand-rolled temp-dir context
  managers. When the stdlib covers the case, use the stdlib.
- **No `print` for runtime metrics in library code.** Use `logging`. `print`
  is acceptable only in scripts, tests, and one-off CLIs.
- **Guard expensive log arguments.** `logger.debug("x %s", value)` is lazy
  about formatting, but any function call used to compute `value` still runs.
  Use `logger.isEnabledFor(logging.DEBUG)` before expensive diagnostics.

## Scale Traps Reviewers Should Catch

- **Hidden materialisation.** `list(source)`, `tuple(source)`,
  `sorted(source)`, `"\n".join(source)`, `Path.read_text()`, response
  `.json()`, and `sum([expr for ...])` all hold the full result. Use
  streaming parsers, iterators, `sum(expr for ...)`, or chunked processing
  unless the full collection is required.
- **Semaphore-only fan-out.** `asyncio.gather(*(limited(x) for x in items))`
  still creates one task/coroutine per item. For unbounded input, keep a fixed
  task window or use worker tasks plus a bounded queue.
- **Unbounded caches.** `@cache`, `lru_cache(maxsize=None)`, and dict caches
  are safe only when the key space is naturally small. User IDs, URLs, search
  queries, and request bodies require max size, TTL, or no cache.
- **Per-item observability.** Logging or metric emission inside a tight loop
  can dominate runtime and I/O. Aggregate counters or sample when cardinality
  is high.
- **Retry amplification.** Retrying every failed item concurrently can turn a
  partial outage into a traffic spike. Combine retries with concurrency
  limits, jitter, and an overall deadline.
- **Generator reuse.** A generator is single-pass. If two consumers need the
  same data, decide explicitly between materialising once, `itertools.tee`
  with its buffering cost, or changing the API.
- **Retained references.** Callback registries, closures over large objects,
  global lists, `ExceptionGroup` storage, and caches can keep memory alive
  long after the work finishes. Use `tracemalloc` snapshots to prove leaks.

## Reference patterns

The patterns below pass the configured type checkers clean. They use the
same suffix-T TypeVar convention as the `typings` skill (`ItemT`,
`KeyT`, `ValueT`, `ResultT`).

### Sliding window over an iterable

`itertools.pairwise` covers N=2; for N>2:

```python
import itertools
from collections.abc import Iterable, Iterator


def sliding_window[ItemT](
    items: Iterable[ItemT], size: int
) -> Iterator[tuple[ItemT, ...]]:
    iterator = iter(items)
    window = tuple(itertools.islice(iterator, size))
    if len(window) == size:
        yield window
    for item in iterator:
        window = window[1:] + (item,)
        yield window
```

### Bounded async map without unbounded task creation

This keeps at most `max_concurrent` tasks alive. It returns results in
completion order; preserve input order only when callers require it.

```python
import asyncio
from collections.abc import Awaitable, Callable, Iterable


async def map_bounded[ItemT, ResultT](
    items: Iterable[ItemT],
    worker: Callable[[ItemT], Awaitable[ResultT]],
    max_concurrent: int = 10,
) -> list[ResultT]:
    if max_concurrent < 1:
        raise ValueError("max_concurrent must be at least 1")

    iterator = iter(items)
    pending: set[asyncio.Task[ResultT]] = set()
    results: list[ResultT] = []

    def schedule_next() -> bool:
        try:
            item = next(iterator)
        except StopIteration:
            return False
        pending.add(asyncio.create_task(worker(item)))
        return True

    for _ in range(max_concurrent):
        if not schedule_next():
            break

    try:
        while pending:
            done, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                results.append(task.result())
                schedule_next()
    except BaseException:
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        raise

    return results
```

### Producer / consumer with backpressure

Use this shape when producers can outrun consumers. `asyncio.Queue` methods do
not take timeout parameters directly; wrap operations with `asyncio.wait_for`
or `asyncio.timeout` when a deadline is part of the contract.

```python
import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class QueueItem[ItemT]:
    value: ItemT


@dataclass(frozen=True)
class Stop:
    pass


type QueueMessage[ItemT] = QueueItem[ItemT] | Stop


async def consume_with_backpressure[ItemT](
    source: AsyncIterator[ItemT],
    handle: Callable[[ItemT], Awaitable[None]],
    *,
    workers: int = 4,
    max_queue: int = 100,
) -> None:
    queue: asyncio.Queue[QueueMessage[ItemT]] = asyncio.Queue(maxsize=max_queue)

    async def producer() -> None:
        async for item in source:
            await queue.put(QueueItem(item))
        for _ in range(workers):
            await queue.put(Stop())

    async def consumer() -> None:
        while True:
            message = await queue.get()
            try:
                match message:
                    case Stop():
                        return
                    case QueueItem(value=item):
                        await handle(item)
            finally:
                queue.task_done()

    async with asyncio.TaskGroup() as tg:
        tg.create_task(producer())
        for _ in range(workers):
            tg.create_task(consumer())
```

### Managed task group - cancel-on-exit

For Python ≥ 3.11, prefer `asyncio.TaskGroup`. Use the helper below only when
you need cancel-on-exit semantics without `TaskGroup`'s exception-propagation
behaviour — typically long-lived background tasks where one failure should
not cancel siblings.

```python
import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any


@asynccontextmanager
async def managed_task_group() -> AsyncGenerator[list[asyncio.Task[Any]]]:
    tasks: list[asyncio.Task[Any]] = []
    try:
        yield tasks
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
```

### TTL cache with size cap

`time.monotonic` rather than `time.time` — wall-clock can step backwards.

```python
import time
from collections import OrderedDict
from collections.abc import Hashable


class TTLCache[KeyT: Hashable, ValueT]:
    def __init__(self, maxsize: int = 128, ttl: float = 600.0) -> None:
        self.maxsize = maxsize
        self.ttl = ttl
        self._cache: OrderedDict[KeyT, tuple[ValueT, float]] = OrderedDict()

    def get(self, key: KeyT) -> ValueT | None:
        if key not in self._cache:
            return None
        value, timestamp = self._cache[key]
        if time.monotonic() - timestamp > self.ttl:
            del self._cache[key]
            return None
        self._cache.move_to_end(key)
        return value

    def set(self, key: KeyT, value: ValueT) -> None:
        self._cache[key] = (value, time.monotonic())
        self._cache.move_to_end(key)
        if len(self._cache) > self.maxsize:
            self._cache.popitem(last=False)
```

### Streaming line processor

For files larger than memory, or where downstream wants a generator:

```python
from collections.abc import Callable, Iterator
from itertools import islice
from pathlib import Path


def stream_lines[ItemT](
    path: Path,
    parse: Callable[[str], ItemT],
    chunk_size: int = 1000,
) -> Iterator[ItemT]:
    with path.open(encoding="utf-8") as handle:
        while True:
            batch = list(islice(handle, chunk_size))
            if not batch:
                return
            for line in batch:
                yield parse(line)
```

### Timed-operation context manager

For ad-hoc perf measurement; production metrics emit through `logging`, not
`print`.

```python
import logging
import time
from collections.abc import Generator
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@contextmanager
def timed_operation(name: str) -> Generator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        logger.info("%s took %.4fs", name, elapsed)
```

### Guarded expensive debug logging

```python
import logging

logger = logging.getLogger(__name__)


def build_expensive_summary(items: list[object]) -> str:
    return ", ".join(type(item).__name__ for item in items)


def emit_debug_summary(items: list[object]) -> None:
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("items summary: %s", build_expensive_summary(items))
```

### cProfile cumulative-time helper

Use this before refactoring CPU-bound paths. Sort by cumulative time first so
callers that hide expensive callees are visible.

```python
import cProfile
import io
import pstats
from collections.abc import Callable
from pstats import SortKey


def profile_call[ResultT](fn: Callable[[], ResultT]) -> tuple[ResultT, str]:
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        result = fn()
    finally:
        profiler.disable()

    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream).sort_stats(SortKey.CUMULATIVE)
    stats.print_stats(30)
    return result, stream.getvalue()
```

### tracemalloc snapshot diff

Use this when memory grows between two points and object ownership is unclear.
Start tracing before the suspected allocation path runs.

```python
import tracemalloc


def top_allocation_diffs(
    before: tracemalloc.Snapshot,
    after: tracemalloc.Snapshot,
    limit: int = 10,
) -> list[tracemalloc.StatisticDiff]:
    return after.compare_to(before, "lineno")[:limit]
```

## When in doubt

- **Hand-rolled `chunked` vs `itertools.batched`** → `itertools.batched`
  (3.12+). Use `strict=True` when incomplete final batches are data
  corruption, not a valid shorter batch.
- **`asyncio.gather` vs bounded task window vs queue** → `gather` only for a
  known-small collection. Use a bounded task window when each item is
  independent. Use `asyncio.Queue(maxsize=...)` when producers and consumers
  run at different speeds.
- **`functools.cache` vs `TTLCache`** → `cache` when the call space is small
  and entries never go stale; `TTLCache` when entries expire or the unbounded
  `cache` would grow without limit.
- **`asyncio.gather` vs `asyncio.TaskGroup`** → `TaskGroup` (3.11+) when you
  want structured cancellation: one failure cancels siblings, all errors
  surface as an `ExceptionGroup`. `gather(..., return_exceptions=True)` only
  when you genuinely want to collect every outcome including failures.
- **Generator vs list** → generator unless the consumer needs `len()`,
  indexing, or multi-pass iteration. Each forced `list(...)` is a deliberate
  choice — call it out in review when it appears.
- **`Lazy[T]` wrapper vs `cached_property` vs `functools.cache`** →
  `cached_property` for instance state computed once. `cache` for pure
  module-level functions. A bespoke `Lazy[T]` wrapper is justified only when
  the thing being deferred is neither (e.g., shared across instances but not
  module-global).
- **`time.time` vs `monotonic` vs `perf_counter`** → `monotonic` for elapsed
  deadlines and TTLs because wall-clock can move backwards. `perf_counter` for
  short interval measurement. `time.time` only for wall-clock timestamps.
- **`tracemalloc` vs `cProfile`** → `tracemalloc` answers "where are Python
  allocations growing?" `cProfile` answers "where is CPU time going?" They are
  complementary, not substitutes.
- **Thread or process pool vs async** → async helps I/O waits. CPU-bound Python
  code usually needs algorithm changes, vectorized/native code, or a process
  pool; adding more asyncio tasks will not bypass the GIL.

## What this skill is NOT

- **Not a substitute for measurement.** These patterns address known shapes
  of runtime cost; they do not predict where your code is hot. Profile
  first; reach for the pattern second.
- **Not a stdlib reference.** `asyncio`, `functools`, `itertools`,
  `contextlib`, `logging`, `cProfile`, `pstats`, `tracemalloc`, and `time`
  are documented at docs.python.org. This skill records which primitives
  projects using this skill prefer, not how they work.
- **Not exhaustive.** New runtime opinions earn an entry here when they
  recur. One-off patterns live with the code that uses them.

## Freshness

This skill is project policy, not a complete upstream reference. When applying
it to unfamiliar APIs, version-sensitive behavior, tool/checker disagreement,
or anything that may have changed since the skill was written, verify current
behavior against primary docs. Prefer Context7 MCP when available. If it is
unavailable, use web search restricted to official sources.

Primary sources:

- [Python 3.14 `asyncio` tasks](https://docs.python.org/3/library/asyncio-task.html):
  `TaskGroup`, cancellation, `gather`, and `asyncio.timeout`.
- [Python 3.14 `asyncio` queues](https://docs.python.org/3/library/asyncio-queue.html):
  queue backpressure, `maxsize`, and timeout guidance through `wait_for`.
- [Python 3.14 `asyncio` synchronization primitives](https://docs.python.org/3/library/asyncio-sync.html):
  `Semaphore` / `BoundedSemaphore` behavior.
- [Python 3.14 `itertools`](https://docs.python.org/3/library/itertools.html):
  `batched`, `pairwise`, `islice`, `tee`, and iterator building blocks.
- [Python 3.14 `functools`](https://docs.python.org/3/library/functools.html):
  `cache`, `lru_cache`, `cached_property`, and cache instrumentation.
- [Python logging HOWTO](https://docs.python.org/3/howto/logging.html):
  lazy formatting and `Logger.isEnabledFor` for expensive diagnostics.
- [Python profilers](https://docs.python.org/3/library/profile.html):
  `cProfile`, `profile`, `pstats`, and `SortKey.CUMULATIVE`.
- [Python `tracemalloc`](https://docs.python.org/3/library/tracemalloc.html):
  allocation tracing, snapshots, and snapshot comparisons.
- [Python `time`](https://docs.python.org/3/library/time.html):
  `monotonic` and `perf_counter` clocks for elapsed-time work.
- Official docs for any non-stdlib tools.
