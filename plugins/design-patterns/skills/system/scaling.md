---
paths:
  - "**/*.py"
  - "**/*.tf"
  - "**/Dockerfile"
  - "**/k8s/**"
---

# Scaling and Caching Patterns

> Patterns for keeping a service fast and available as load grows. Each entry frames the
> *workload signal that triggers it*, the *minimal correct shape*, the *operational cost*,
> and the *failure mode that arrives when you tune it wrong*.

Scaling is not a single decision; it is a stack of decisions that interact. A cache hides a
slow database, a load balancer spreads traffic across replicas, an autoscaler adds replicas
when traffic spikes, and a backpressure signal tells the autoscaler the right thing to scale
on. Tune any one without the others and the system degrades in a predictable, embarrassing
way: stampedes when caches misfire, retry storms when load balancers misbehave, cold-start
walls when autoscalers trail demand.

The default posture in this document is **measure, then scale; cache only what survives
invalidation; stretch one axis before splitting; and never stack without a budget**.

## Table of Contents

- [How to use this file](#how-to-use-this-file)
- [Cache-Aside (Lazy Loading)](#cache-aside-lazy-loading)
- [Read-Through](#read-through)
- [Write-Through](#write-through)
- [Write-Behind / Write-Back](#write-behind--write-back)
- [Refresh-Ahead](#refresh-ahead)
- [Cache Invalidation](#cache-invalidation)
- [CDN and Edge Caching](#cdn-and-edge-caching)
- [Vertical vs Horizontal Scaling](#vertical-vs-horizontal-scaling)
- [Auto-scaling](#auto-scaling)
- [Load Balancing](#load-balancing)
- [Connection Pooling](#connection-pooling)
- [Backpressure-aware Scaling](#backpressure-aware-scaling)
- [Stacking Caches](#stacking-caches)
- [Review Checklist](#review-checklist)
- [References](#references)

---

## How to use this file

Read this file when you are about to add a cache, a load balancer, or an autoscaling rule —
*before* you reach for a library. Each entry tells you the smallest version of the pattern
that is still honest, what it costs, and the misuses that turn it into an outage.

Code is Python 3.13+ and written to target mypy `--strict` and pyright
`--strict`: `Protocol` over `ABC`, PEP 695 generics, PEP 604 unions, no
`Any`, and the annotation-evaluation policy in `SKILL.md` conventions.
Examples use `redis-py`, `aiocache`, `cachetools`, and `httpx` as representative
libraries; adapt them to the consuming project's stack.

If a pattern is *necessary* but not described here in detail (e.g. the failure-isolation
patterns: bulkhead, circuit breaker, hedged requests), see `reliability.md`.
If a pattern is structural across services (sidecar, ambassador, strangler fig), see
`cloud.md`.

---

## Cache-Aside (Lazy Loading)

**What it is / Intent.** The application reads from the cache first; on a miss, it loads
from the source of truth, populates the cache, and returns the value. The cache is treated
as a hint, not as a contract. The source-of-truth always wins.

**When to reach for it / How it manifests.**

- Reads dominate; writes are infrequent or tolerable to invalidate by deletion.
- Brief staleness is acceptable. The TTL bounds the staleness window.
- The cache library does not transparently fetch on miss (Redis, Memcached, in-process
  dict). If the library does (`functools.lru_cache`, Caffeine), prefer Read-Through.
- "First-byte" requests get a slow path; subsequent requests are fast.

**Sketch.** Cache-aside is six lines if you ignore the failure modes. The interesting
shape is the *stampede-protected* version, which coalesces concurrent misses to a single
upstream load.

```python
import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final, Protocol, Self

from redis.asyncio import Redis


class Cache(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, *, ttl_s: int) -> None: ...


@dataclass(frozen=True, slots=True)
class CachePolicy:
    ttl_s: int = 300
    negative_ttl_s: int = 30
    stampede_lock_ttl_s: int = 5


class CacheAside[K, V]:
    """Cache-aside with single-flight stampede protection.

    The first miss for a key acquires a Redis lock, loads from source, populates
    the cache, and releases. Concurrent misses await the lock; when it releases,
    they re-read the cache and find the freshly populated value.
    """

    def __init__(
        self,
        cache: Cache,
        redis: Redis,
        loader: Callable[[K], Awaitable[V | None]],
        encode: Callable[[V], str],
        decode: Callable[[str], V],
        key_for: Callable[[K], str],
        policy: CachePolicy = CachePolicy(),
    ) -> None:
        self._cache: Final = cache
        self._redis: Final = redis
        self._loader: Final = loader
        self._encode: Final = encode
        self._decode: Final = decode
        self._key_for: Final = key_for
        self._policy: Final = policy

    async def get(self, identifier: K) -> V | None:
        key = self._key_for(identifier)
        cached = await self._cache.get(key)
        if cached is not None:
            return None if cached == "__null__" else self._decode(cached)

        lock_key = f"lock:{key}"
        acquired = await self._redis.set(
            lock_key, "1", nx=True, ex=self._policy.stampede_lock_ttl_s
        )
        if not acquired:
            await asyncio.sleep(0.05)
            cached = await self._cache.get(key)
            if cached is not None:
                return None if cached == "__null__" else self._decode(cached)
            return await self._loader(identifier)

        try:
            value = await self._loader(identifier)
            payload = "__null__" if value is None else self._encode(value)
            ttl = self._policy.negative_ttl_s if value is None else self._policy.ttl_s
            await self._cache.set(key, payload, ttl_s=ttl)
            return value
        finally:
            await self._redis.delete(lock_key)

    @classmethod
    def with_redis_only(
        cls,
        redis: Redis,
        loader: Callable[[K], Awaitable[V | None]],
        encode: Callable[[V], str],
        decode: Callable[[str], V],
        key_for: Callable[[K], str],
        policy: CachePolicy = CachePolicy(),
    ) -> Self:
        adapter = _RedisCacheAdapter(redis)
        return cls(adapter, redis, loader, encode, decode, key_for, policy)


@dataclass(frozen=True, slots=True)
class _RedisCacheAdapter:
    redis: Redis

    async def get(self, key: str) -> str | None:
        raw = await self.redis.get(key)
        return None if raw is None else raw.decode("utf-8") if isinstance(raw, bytes) else raw

    async def set(self, key: str, value: str, *, ttl_s: int) -> None:
        await self.redis.set(key, value, ex=ttl_s)


# Usage:
# loader = lambda uid: user_repo.get(uid)
# cache  = CacheAside.with_redis_only(redis, loader, json.dumps, json.loads, lambda u: f"user:{u}")
```

**When NOT to use / What it costs.**

- *Strong-consistency reads.* Cache-aside is eventually consistent on writes — there is a
  window where the source has the new value and the cache still has the old one. If a user
  writes and then reads in the same request, route the read past the cache.
- *Hot keys without stampede protection.* When a hot key expires, every concurrent reader
  misses, and the source is hit by N parallel loads. The stampede crashed Reddit's
  Memcached fleet in 2008 and has crashed something at every company since. Always
  coalesce.
- *Mutable data with no invalidation strategy.* If you set TTL = 1 day and the underlying
  row changes every minute, your "cache" is now a stale-data weapon. See
  [Cache Invalidation](#cache-invalidation).
- *Negative results without negative caching.* If `get(missing_id)` returns `None`, cache
  the `None` (with a *short* TTL) — otherwise an attacker spraying random IDs becomes a
  denial-of-service against your DB.

**Real-world examples.**

- *Reddit*. Memcached + cache-aside + thundering-herd lock-and-load on hot post lookups.
- *Stack Overflow*. Two-tier in-process L1 + Redis L2 for question pages; documented in
  Nick Craver's posts.
- *Pinterest*. Per-user feed cache with cache-aside semantics fronting MySQL.

**References.**

- Microsoft Azure, *Cache-Aside Pattern*, learn.microsoft.com/azure/architecture/patterns.
- Brad Fitzpatrick, *Distributed Caching with Memcached*, Linux Journal, 2004.
- Facebook, *Scaling Memcache at Facebook*, NSDI 2013 — § lease tokens for stampede.

---

## Read-Through

**What it is / Intent.** The cache library owns the "read miss → fetch from source → fill
cache" flow. The application sees a single API: `cache.get(key)`. On a hit it is fast; on
a miss it is slow but correct, with no application-level branching.

**When to reach for it / How it manifests.**

- The application has many call sites and you do not want each to repeat the
  if-miss-then-load dance.
- You are using a library that supports it natively: `aiocache.cached`,
  `cachetools.cachedmethod`, `dogpile.cache`, AWS DAX in front of DynamoDB.
- You want a uniform place to add stampede protection, metrics, and timeouts.

**Sketch.**

```python
import asyncio
from collections.abc import Awaitable, Callable, Hashable
from dataclasses import dataclass, field
from typing import Final


@dataclass(slots=True)
class ReadThroughCache[K: Hashable, V]:
    """In-process read-through cache with single-flight coalescing.

    Concurrent misses for the same key share one upstream call.
    """

    loader: Callable[[K], Awaitable[V]]
    ttl_s: float
    _entries: dict[K, tuple[V, float]] = field(default_factory=dict, init=False)
    _inflight: dict[K, asyncio.Future[V]] = field(default_factory=dict, init=False)
    _clock: Callable[[], float] = field(default_factory=lambda: asyncio.get_event_loop().time)

    async def get(self, key: K) -> V:
        now = self._clock()
        if (entry := self._entries.get(key)) is not None and entry[1] > now:
            return entry[0]
        if (existing := self._inflight.get(key)) is not None:
            return await existing
        future: asyncio.Future[V] = asyncio.get_running_loop().create_future()
        self._inflight[key] = future
        try:
            value = await self.loader(key)
            self._entries[key] = (value, now + self.ttl_s)
            future.set_result(value)
            return value
        except BaseException as exc:
            future.set_exception(exc)
            raise
        finally:
            self._inflight.pop(key, None)
```

**When NOT to use / What it costs.**

- *Coupling between cache and source.* If the cache is in-process, restarting the process
  warms cold every time. Pair with a remote layer (Redis) when warmth matters.
- *Loader exceptions.* A read-through that caches the *exception* turns one outage into a
  TTL-long outage. By default, do not cache failures; cache only successful loads. (The
  exception is *negative caching* of `not-found`, which is a successful load returning
  `None`.)
- *Async vs sync mismatch.* `cachetools` is sync; `aiocache` is async. Mixing them
  through `asyncio.to_thread` works but adds latency that defeats the cache's point.

**Real-world examples.**

- *AWS DAX* in front of DynamoDB — read-through, write-through, microsecond latency.
- *Caffeine* (JVM) — Guava successor; stampede protection via `AsyncLoadingCache`.
- *Django ORM `cache_alias`* with `dogpile.cache` for read-through method caches.

**References.**

- Caffeine docs, github.com/ben-manes/caffeine — § Population.
- AWS, *Amazon DynamoDB Accelerator (DAX) Developer Guide*.

---

## Write-Through

**What it is / Intent.** A write goes to the cache and the source-of-truth in one
synchronous step. After the write returns, both layers see the new value. Reads from the
cache are guaranteed fresh.

**When to reach for it / How it manifests.**

- Reads must see the latest write *immediately* after it returns (e.g. read-your-writes).
- Writes are infrequent enough that the extra cache-write latency does not dominate.
- The cache and source can be updated atomically (or near-atomically) — same DB
  transaction, two-phase write with rollback, or write-then-invalidate-on-miss.

**Sketch.**

```python
from typing import Final, Protocol


class UserRepository(Protocol):
    async def upsert(self, user_id: str, user: dict[str, object]) -> None: ...


class WriteThroughCache:
    """Write to source-of-truth first, then to cache. Reads are read-through."""

    def __init__(self, redis: Redis, repo: UserRepository, ttl_s: int = 300) -> None:
        self._redis: Final = redis
        self._repo: Final = repo
        self._ttl_s: Final = ttl_s

    async def upsert(self, user_id: str, user: dict[str, object]) -> None:
        # 1. Source first. If this fails, neither side advances.
        await self._repo.upsert(user_id, user)
        # 2. Cache second. If this fails, the cache is stale until TTL or next write.
        try:
            await self._redis.set(f"user:{user_id}", json.dumps(user), ex=self._ttl_s)
        except Exception:  # noqa: BLE001 — cache failure is non-fatal here
            await self._redis.delete(f"user:{user_id}")  # invalidate to force reload
            raise
```

**When NOT to use / What it costs.**

- *Two-step partial failure.* If the source write succeeds and the cache write fails, the
  cache is stale. The only safe recovery is *invalidate on failure*: delete the key so the
  next read goes to source. Never set cache *before* source — a source-write failure then
  leaves the cache permanently wrong.
- *Write latency penalty.* Every write pays cache + source latency. If cache writes are
  slow (sharded Redis with quorum, encrypted set), this dominates.
- *Multi-replica caches.* Replicating writes across cache replicas adds another window of
  divergence. Use Redis's `WAIT` command or a single-master cache.

**Real-world examples.**

- *Linkedin Voldemort* (historical) — write-through to memcache + source.
- *AWS DAX* — both read-through and write-through to DynamoDB.

**References.**

- Microsoft Azure, *Caching Guidance*, learn.microsoft.com/azure/architecture/best-practices/caching.

---

## Write-Behind / Write-Back

**What it is / Intent.** Writes go to the cache and acknowledge immediately; a background
flusher drains writes to the source-of-truth asynchronously. Throughput at the cost of
durability — a crashed cache loses writes that never made it to source.

**When to reach for it / How it manifests.**

- Write throughput is the bottleneck; the source-of-truth cannot keep up.
- Brief data loss on cache failure is acceptable (counters, telemetry, click streams).
- The flush can be batched, deduplicated, or coalesced (e.g. counter increments).

**Sketch.**

```python
import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Final


@dataclass
class WriteBehindBuffer[K, V]:
    """Coalesce writes by key; flush in batches.

    Lossy by design: a crash before flush drops the in-memory buffer.
    """

    flush: Callable[[dict[K, V]], Awaitable[None]]
    flush_interval_s: float = 1.0
    max_pending: int = 1000
    _pending: dict[K, V] = field(default_factory=dict, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    _task: asyncio.Task[None] | None = field(default=None, init=False)

    async def write(self, key: K, value: V) -> None:
        async with self._lock:
            self._pending[key] = value  # last-writer-wins coalescing
            if len(self._pending) >= self.max_pending:
                await self._drain_locked()

    async def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
        async with self._lock:
            await self._drain_locked()

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self.flush_interval_s)
            async with self._lock:
                await self._drain_locked()

    async def _drain_locked(self) -> None:
        if not self._pending:
            return
        batch = self._pending
        self._pending = {}
        try:
            await self.flush(batch)
        except Exception:
            self._pending |= batch  # restore on failure; bounded by max_pending
            raise
```

**When NOT to use / What it costs.**

- *Money / orders / audit data.* Lost writes mean lost revenue or lost compliance.
  Anything where a missing record is a bug, not a metric, is wrong for write-behind.
- *Process restarts.* Crashes, deploys, OOM kills — all drop the buffer. WAL-on-disk
  buffering (SQLite, RocksDB) reduces but does not eliminate the loss window.
- *Ordering guarantees.* Coalescing breaks "the last write wins" if downstream cares
  about the *sequence* of writes (event sourcing). Use append-only logs there, not
  write-behind.

**Real-world examples.**

- *Cassandra commit log + memtable* — fast writes ack'd from memtable, drained to SSTable.
- *Kafka producer batching* — `linger.ms` is write-behind for the network.
- *Redis with AOF / RDB* — durability is configurable; "write-behind" describes the
  in-memory phase.

**References.**

- Kleppmann, *DDIA*, ch. 3 (storage engines), ch. 5 (replication).

---

## Refresh-Ahead

**What it is / Intent.** Refresh a cache entry *before* its TTL expires, so a hot key
never has a "miss window." A background task (or probabilistic decision on read) refreshes
the value while the existing entry is still valid; readers always see the freshest
non-stale value.

**When to reach for it / How it manifests.**

- Predictable hot keys (homepage, dashboard, leaderboard top-N).
- Source-of-truth load spike at TTL expiry is the dominant pain point.
- You can predict access patterns well enough that prefetching is mostly correct.

**Sketch.** Probabilistic early refresh (XFetch, Vattani et al.):

```python
import math
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Final


@dataclass(frozen=True, slots=True)
class RefreshAheadEntry[V]:
    value: V
    delta_s: float        # expected load latency, EMA
    expires_at: float     # absolute deadline


@dataclass
class XFetchCache[K, V]:
    """Probabilistic early refresh: refresh chance grows as expiry nears.

    Hits with probability p = exp(-delta * beta * ln(rand)) refresh the value.
    """

    loader: Callable[[K], Awaitable[V]]
    ttl_s: float
    beta: float = 1.0
    _entries: dict[K, RefreshAheadEntry[V]] = field(default_factory=dict, init=False)
    _clock: Callable[[], float] = field(default_factory=lambda: __import__("time").monotonic)

    async def get(self, key: K) -> V:
        now = self._clock()
        entry = self._entries.get(key)
        if entry is None or entry.expires_at <= now:
            return await self._reload(key, now)
        # Probabilistic early refresh
        roll = -entry.delta_s * self.beta * math.log(random.random())  # noqa: S311
        if now + roll >= entry.expires_at:
            return await self._reload(key, now)
        return entry.value

    async def _reload(self, key: K, started_at: float) -> V:
        value = await self.loader(key)
        elapsed = self._clock() - started_at
        self._entries[key] = RefreshAheadEntry(
            value=value, delta_s=elapsed, expires_at=started_at + self.ttl_s
        )
        return value
```

**When NOT to use / What it costs.**

- *Cold caches.* Refresh-ahead does nothing for keys that are not yet warm. Cold keys
  still need cache-aside or read-through.
- *Cost of speculative load.* Every refresh hits the source, even if no one would have
  asked. For long-tail keys, this wastes more than it saves.
- *Mutability.* If the value can change *between* prefetches, you serve a stale-but-fresh
  value confidently. Pair with explicit invalidation.

**Real-world examples.**

- *Twitter timeline cache* — historical reload-ahead for celebrity timelines.
- *Cloudflare* — refresh-ahead for hot edge content; "stale-while-revalidate" header is
  the request-driven cousin.

**References.**

- Vattani, A., Chierichetti, F., Lowenstein, K., *Optimal Probabilistic Cache Stampede
  Prevention*, VLDB 2015.

---

## Cache Invalidation

**What it is / Intent.** The discipline of removing or replacing cached entries when the
underlying truth changes, so that future reads see new data and not the stale ghost. "There
are only two hard things in computer science: cache invalidation and naming things." —
Phil Karlton.

**When to reach for it / How it manifests.**

- A write changes data that is cached elsewhere.
- A schema migration shifts the meaning of an existing key.
- A rollback or fix means the *current* cached value is wrong even if the row didn't
  change.

**Strategies.**

| Strategy | When | Cost |
| --- | --- | --- |
| **TTL** | Always have one as a safety net. Bounds staleness without coordination. | Tail-of-bell-curve staleness up to TTL. |
| **Versioned keys** (`user:42:v7`) | When the *shape* of the cached value changes; cheap rollback. | Old keys leak until eviction; evict explicitly on deploy. |
| **Pub/sub invalidation** | Multi-instance caches; writes far from reads. | Lost messages → permanent staleness; needs idempotent re-sub. |
| **Write-then-delete** (cache-aside post-write) | Single-writer per key; simplest and most common. | Race: read between write and delete, then writes back stale value. Mitigation: short post-write lock, or set with new value instead of delete. |
| **Tag-based / surrogate-keys** | CDN edge; one upstream change purges many cached URLs. | Implementation complexity; vendor-specific. |

**Sketch (versioned keys).**

```python
from typing import Final, Protocol


SCHEMA_VERSION: Final[int] = 7  # bump on any cached-value shape change


class VersionedCache:
    """Versioned-key cache. Bumping SCHEMA_VERSION leaves old data to expire naturally.

    No explicit purge — old keys evict on TTL or LRU pressure.
    """

    def __init__(self, redis: Redis, ttl_s: int = 300) -> None:
        self._redis: Final = redis
        self._ttl_s: Final = ttl_s

    def _key(self, base: str) -> str:
        return f"{base}:v{SCHEMA_VERSION}"

    async def get(self, base: str) -> str | None:
        raw = await self._redis.get(self._key(base))
        if raw is None:
            return None
        return raw.decode() if isinstance(raw, bytes) else raw

    async def set(self, base: str, value: str) -> None:
        await self._redis.set(self._key(base), value, ex=self._ttl_s)
```

**The race nobody mentions.** Cache-aside with delete-on-write has a subtle bug:

```
T0: writer commits row.value = NEW
T1: reader misses cache, reads row, gets NEW
T2: writer deletes cache key
T3: reader sets cache key to NEW         ← lucky, fine
```

vs.

```
T0: reader misses cache, reads row, gets OLD (about to be replaced)
T1: writer commits row.value = NEW
T2: writer deletes cache key
T3: reader sets cache key to OLD         ← stale, lasts a TTL
```

Mitigations: (a) short post-write *lock* on the key while the cache is being purged, or
(b) write-through (set the cache with the new value, don't just delete). Facebook's
"leases" paper formalizes this.

**When NOT to use / What it costs.**

- *Skipping TTL because "we always invalidate explicitly."* You will miss one. Always
  back invalidation with TTL.
- *Pub/sub without idempotence.* A duplicate invalidation is harmless; a *missed* one is
  permanent staleness. Subscribers must reconnect and re-sync on disconnect.

**References.**

- Facebook, *Scaling Memcache at Facebook*, NSDI 2013 — leases.
- Phil Karlton, attributed (the "two hard things" line is folklore).
- Microsoft Azure, *Cache-Aside Pattern* — § ordering of write and delete.

---

## CDN and Edge Caching

**What it is / Intent.** Push static and semi-static responses to caches geographically
close to users. The origin only sees cache misses and writes. Latency drops; bandwidth
costs drop; origin scales sub-linearly with users.

**When to reach for it / How it manifests.**

- Public content (assets, public pages, public API responses) where the same response
  serves many users.
- Latency from network distance to origin is dominant.
- Bursty traffic (product launches, news cycles) where origin would be overwhelmed.

**Headers cheat sheet.**

| Header | Effect |
| --- | --- |
| `Cache-Control: public, max-age=300` | Browser + shared caches may store for 5 min. |
| `Cache-Control: s-maxage=300, max-age=0` | CDN caches 5 min; browsers re-validate. |
| `Cache-Control: no-store` | Never cache. (Not the same as `no-cache`, which means revalidate.) |
| `Vary: Accept-Encoding` | Different cache entry per encoding (gzip vs br vs none). |
| `Vary: Authorization` | Per-user cache key — almost never what you want; defeats CDN. |
| `Cache-Control: stale-while-revalidate=30` | Serve stale up to 30s while async revalidating. |
| `Cache-Control: stale-if-error=86400` | If origin errors, serve stale up to 24h. |
| `Surrogate-Key: product-42` (Fastly) | Tag the response; `purge by key product-42` removes all entries with that tag. |

**Sketch (FastAPI emitting cache-aware responses).**

```python
from typing import Final
from fastapi import FastAPI, Response
from pydantic import BaseModel


app = FastAPI()


class Product(BaseModel):
    id: int
    name: str
    price_cents: int


PRODUCT_CACHE_HEADERS: Final[dict[str, str]] = {
    "Cache-Control": "public, max-age=60, s-maxage=300, stale-while-revalidate=30, stale-if-error=86400",
    "Vary": "Accept-Encoding",
}


@app.get("/products/{product_id}")
async def get_product(product_id: int, response: Response) -> Product:
    product = await _load_product(product_id)
    for k, v in PRODUCT_CACHE_HEADERS.items():
        response.headers[k] = v
    response.headers["Surrogate-Key"] = f"product-{product_id} all-products"
    return product


async def _load_product(product_id: int) -> Product:
    raise NotImplementedError
```

**stale-while-revalidate is the operational lever.** It turns a slow origin into a fast
edge: when the cached response is stale-but-not-expired, the edge serves it *and* fires a
background revalidation. The next request gets the fresh response. This eliminates the
"first request after TTL is slow" problem without giving up correctness windows.

**When NOT to use / What it costs.**

- *Personalized responses.* Per-user content cannot be cached at the CDN unless you key
  per user (which defeats the cache). Move personalization to the client (template +
  client-side fetch) or to the edge worker (Cloudflare Workers, Lambda@Edge).
- *Authorization-sensitive data.* `Vary: Authorization` is technically correct and
  practically useless. Don't put auth-gated content behind a public CDN.
- *Cache-key explosions.* `Vary: User-Agent` makes every browser get a separate cache
  entry. Normalize headers (e.g. `Accept-Encoding` to "gzip" or absent) before caching.
- *Purge latency.* Even tag-based purge takes seconds-to-minutes to propagate globally.
  Critical security purges (revoked content) need shorter TTL, not faster purge.

**Real-world examples.**

- *Fastly + GitHub Pages* — surrogate keys; `purge product-42` clears all variants.
- *Cloudflare + Wordpress* — long s-maxage, purge on publish webhook.
- *Akamai + ESPN* — multi-tier edge, used to handle sports-event spikes.

**References.**

- Fastly, *Best practices using the Vary header*, fastly.com/blog.
- RFC 5861, *HTTP Cache-Control extensions for stale content*.
- Chrome DevTools, *Cache-Control HTTP headers*, web.dev/articles/http-cache.

---

## Vertical vs Horizontal Scaling

**What it is / Intent.**

- *Vertical (scale-up).* One bigger machine: more cores, more RAM, faster disks.
- *Horizontal (scale-out).* More machines, each running an identical replica.

**When to reach for it / How it manifests.**

- *Scale up first* when:
  - The workload is single-process or shares an in-process state (Postgres primary,
    Redis primary).
  - Replication is non-trivial (single-writer DBs, sticky-state services).
  - Operating one big box is cheaper to reason about than five small ones.
- *Scale out* when:
  - The workload is genuinely embarrassingly parallel (stateless HTTP).
  - You need fault tolerance (one machine dying ≠ outage).
  - The single biggest available machine is no longer big enough.

**The pragmatic argument for scaling up first.** Adam D'Angelo (Quora), Stack Overflow,
GitHub: *modern* hardware is enormous (96+ cores, terabytes of RAM, NVMe at GB/s). Many
"need to go distributed" claims are actually "need to delete the n+1 query" claims.
Scaling up keeps the system simple; scaling out adds network, partial failure,
distributed-state, and observability tax.

**Sketch.** Not code; a decision matrix.

```
                       │ stateless HTTP │ DB primary │ Redis │ ML training │
─────────────────────  ┼────────────────┼────────────┼───────┼─────────────┤
add cores              │ marginal       │ huge       │ huge  │ huge        │
add memory             │ marginal       │ huge       │ huge  │ medium      │
add replicas (read)    │ huge           │ medium     │ huge  │ none        │
add shards (write)     │ N/A            │ surgery    │ medium│ none        │
horizontal partition   │ huge (autoscale)│ surgery   │ medium│ huge        │
```

**When NOT to use scale-up.** When the largest available instance is still under-resourced
and *increases* in size are no longer available. AWS r6i.32xlarge (128 vCPU, 1 TiB RAM) is
the practical ceiling for most workloads as of 2026. Past that, you must shard or replicate.

**When NOT to use scale-out.** When the workload's bottleneck is *coordination*, not
parallelism. Adding replicas to a system whose hot path is a single mutex multiplies
contention.

**Real-world examples.**

- *Stack Overflow.* ~9 web servers + 4 SQL Server boxes for tens of millions of monthly
  visitors; classic scale-up posture (Nick Craver's blog).
- *Postgres at scale.* Primary scales up; replicas scale out for reads.
- *Cassandra.* Scale-out from day one — designed for it.

**References.**

- Adam D'Angelo, posts on scaling Quora, 2010s.
- Nick Craver, *Stack Overflow: How We Do Deployment*, nickcraver.com.

---

## Auto-scaling

**What it is / Intent.** Automatically add or remove replicas in response to load,
preserving SLO at minimum cost. Three flavors: *reactive* (CPU/RAM/queue triggers),
*scheduled* (known traffic curves), and *predictive* (forecast-based).

**When to reach for it / How it manifests.**

- Load is bursty or diurnal.
- Cost matters; you cannot afford to provision for peak 24/7.
- Replicas are stateless and start fast (containerized HTTP services).

**The cold-start tax.** Reactive autoscaling has a lag: trigger fires → provision starts
→ image pulls → service warms → traffic shifts. Even with pre-warmed AMIs, this is tens
of seconds; with cold containers, minutes; with VMs, longer. During the lag, the existing
fleet absorbs the spike — or fails to. Three mitigations:

1. *Predictive scaling* (forecast + scale ahead of the curve). AWS Predictive Scaling,
   GCP recommendations.
2. *Scheduled scaling* (you know peak is at 10am Mondays).
3. *Buffer headroom* (target 60% utilization, not 80%; the extra 20% is the cold-start
   cushion).

**Sketch (Kubernetes HPA, conceptual).**

```yaml
# k8s/hpa.yaml — backpressure-aware autoscale on queue depth, not CPU
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: order-worker
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: order-worker
  minReplicas: 4
  maxReplicas: 200
  metrics:
    - type: External
      external:
        metric:
          name: rabbitmq_queue_messages_ready
          selector:
            matchLabels:
              queue: orders
        target:
          type: AverageValue
          averageValue: "30"  # ~30 messages per replica steady state
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
        - type: Percent
          value: 100
          periodSeconds: 30
    scaleDown:
      stabilizationWindowSeconds: 300  # asymmetric: scale up fast, down slow
      policies:
        - type: Percent
          value: 25
          periodSeconds: 60
```

The asymmetric stabilization window matters: scale up *fast* (30s window so a burst is
not lost), scale down *slow* (5 min window so a momentary lull does not kill capacity
that's about to be needed again).

**When NOT to use / What it costs.**

- *Stateful services.* Adding a stateful replica is not free — re-sharding, re-replication,
  warm-up. Do not autoscale databases reactively.
- *Replica startup > spike duration.* If your image takes 2 minutes to start and your
  spikes last 90 seconds, the autoscaler will scale you up *after* the spike is over.
  Use buffer headroom instead.
- *Unbounded `maxReplicas`.* A bug in upstream load can autoscale you to your billing
  ceiling. Always cap.

**Real-world examples.**

- *Netflix Atlas + Spinnaker* — predictive scaling for region-level traffic curves.
- *AWS Application Auto Scaling* — across ECS, Lambda concurrency, DynamoDB.
- *KEDA* — Kubernetes event-driven autoscaling on queue depth, Kafka lag, etc.

**References.**

- AWS, *Predictive scaling for Amazon EC2 Auto Scaling*, docs.aws.amazon.com.
- Google SRE, ch. 22 (cascading failures) — § overload.

---

## Load Balancing

**What it is / Intent.** Distribute incoming requests across replicas so that no replica
is overwhelmed and no replica is idle. Layer 4 (TCP/UDP) is fast and protocol-blind; Layer
7 (HTTP) is richer (path-based routing, header-based routing, retries, hedging).

**Algorithms.**

| Algorithm | Mental model | When |
| --- | --- | --- |
| **Round-robin** | "Next replica in the list." | Replicas are uniform; requests are uniform. Toy default. |
| **Least-connections** | "Send to the replica with fewest in-flight requests." | Long-lived connections, request mix is heterogeneous. |
| **Power-of-two-choices (P2C)** | "Pick 2 random replicas; send to whichever has fewer in-flight." | Provably near-optimal load with O(1) cost. The default for Linkerd, Envoy, Finagle. |
| **EWMA** | "Send to replica with lowest exponentially-weighted moving average latency." | Long-tail-sensitive (interactive APIs). Used by Envoy, Linkerd. |
| **IP-hash / consistent hashing** | "Same client always lands on same replica." | Stateful caches (sharded Redis), session affinity *when actually needed*. |
| **Least-request + outlier ejection** | "P2C, plus eject replicas that exceed error rate threshold." | Production default. Envoy's default. |

**Why round-robin is wrong by default.** Two replicas; one is a slow outlier (GC pause,
deploy-in-progress). Round-robin sends 50% of traffic to the slow replica. Latency is
dominated by the slowest. P2C re-routes most traffic away from it within seconds.

**Sketch (P2C, illustrative).**

```python
import random
from dataclasses import dataclass, field
from typing import Final


@dataclass
class Replica:
    name: str
    in_flight: int = 0
    healthy: bool = True


@dataclass
class P2CBalancer:
    """Power-of-two-choices: pick 2 random replicas, prefer the one with fewer in-flight."""

    replicas: list[Replica] = field(default_factory=list)

    def pick(self) -> Replica:
        healthy = [r for r in self.replicas if r.healthy]
        if not healthy:
            raise RuntimeError("no healthy replicas")
        if len(healthy) == 1:
            return healthy[0]
        a, b = random.sample(healthy, 2)  # noqa: S311
        return a if a.in_flight <= b.in_flight else b


# Round-robin is one line; included only for contrast.
@dataclass
class RoundRobinBalancer:
    replicas: list[Replica] = field(default_factory=list)
    _index: int = 0

    def pick(self) -> Replica:
        if not self.replicas:
            raise RuntimeError("no replicas")
        replica = self.replicas[self._index % len(self.replicas)]
        self._index += 1
        return replica
```

**Sticky sessions.** Affinity that locks a client to a replica. Used to be common; now
mostly an anti-pattern (see anti-patterns.md). The honest case for stickiness is when
*per-client local state* (an ML model, a streaming connection, a partial result) is
expensive to rebuild on a different replica. The dishonest case is when in-memory session
state should have been in Redis.

**When NOT to use particular algorithms.**

- *Round-robin in production.* Default to P2C, EWMA, or least-connections. Round-robin's
  worst case (one slow replica) is too easy to hit.
- *IP-hash with NAT.* All clients behind one NAT collapse onto one replica.
- *Consistent hashing without rebalancing.* Adding/removing replicas reshuffles all keys
  unless you use rendezvous or jump-consistent hashing.

**Real-world examples.**

- *Envoy / Istio* — P2C + outlier ejection.
- *Linkerd* — EWMA + P2C.
- *NGINX* — `least_conn`, `ip_hash`; consistent hash with `consistent` keyword.
- *AWS NLB* — Layer 4, flow-hash by default.
- *AWS ALB* — Layer 7, round-robin or least outstanding requests.

**References.**

- Mitzenmacher, M., *The Power of Two Choices in Randomized Load Balancing*, 2001.
- Marc Brooker, *Heuristics, anomalies, and pitfalls in load balancing*, brooker.co.za.
- Envoy docs, *Load balancers*, envoyproxy.io.

---

## Connection Pooling

**What it is / Intent.** Reuse a small number of long-lived connections instead of opening
a new one per request. Connection setup (TCP handshake, TLS, auth) is *expensive*; pooling
amortizes it.

**The arithmetic.** For a service with `N` replicas talking to a Postgres primary, the
pool math is:

```
total_connections = N_replicas * pool_size_per_replica
```

If `N=50` and pool size is `20`, you have potentially `1000` connections to one Postgres
primary — which is more than the default `max_connections=100`. The fix is *not* to
increase Postgres `max_connections` indefinitely (Postgres allocates ~10MB per backend);
the fix is to use a connection pooler (PgBouncer, pgcat, RDS Proxy) that multiplexes
client connections onto a small pool of server connections.

**HikariCP / Postgres rule of thumb.** Hikari's official guide: pool size = `((core_count
* 2) + effective_spindle_count)` is a good starting point for OLTP. For most cloud
Postgres, this lands at ~10–20 per replica. More is usually wrong.

**Sketch (asyncpg + pool).**

```python
import asyncpg
from typing import Final


class DBPool:
    """Per-process Postgres pool. Replicas multiply this number."""

    def __init__(self, dsn: str, *, min_size: int = 2, max_size: int = 10) -> None:
        self._dsn: Final = dsn
        self._min_size: Final = min_size
        self._max_size: Final = max_size
        self._pool: asyncpg.Pool | None = None

    async def start(self) -> None:
        self._pool = await asyncpg.create_pool(
            self._dsn,
            min_size=self._min_size,
            max_size=self._max_size,
            command_timeout=5.0,            # SLO budget; tune per query class
            max_inactive_connection_lifetime=300.0,
            statement_cache_size=100,
        )

    async def stop(self) -> None:
        if self._pool is not None:
            await self._pool.close()

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("DBPool not started")
        return self._pool
```

**Per-instance vs shared pool.**

- *Per-instance.* Simpler. Each replica owns its pool. Total connections grow with
  replicas.
- *Shared (PgBouncer, RDS Proxy).* Fixed-size server pool; client pools talk to the
  pooler. Scales replicas without scaling DB connections. *Tradeoff:* pooled mode breaks
  some Postgres features (advisory locks, prepared statements in transaction-pool mode).

**When NOT to use / What it costs.**

- *Pool too large.* Postgres above ~200 active connections degrades — context switching
  and lock contention dominate.
- *Pool too small.* Connection-acquisition latency p99 spikes; requests queue.
- *No timeout on `acquire`.* A starved pool starves the *caller* indefinitely. Always
  set `timeout=` on acquire.
- *Long-running queries holding pool slots.* One slow query blocks the whole replica's
  pool. Bulkhead by query class (`heavy_pool` separate from `oltp_pool`).

**Real-world examples.**

- *PgBouncer* — Postgres reference pooler.
- *AWS RDS Proxy* — managed pooler with auto-failover.
- *HikariCP* — JVM gold standard; Brett Wooldridge's docs are required reading even for
  non-JVM systems.

**References.**

- HikariCP, *About Pool Sizing*, github.com/brettwooldridge/HikariCP.
- PgBouncer docs, *transaction* vs *session* vs *statement* pooling modes.

---

## Backpressure-aware Scaling

**What it is / Intent.** Scale on signals that *predict* customer-visible degradation —
queue depth, queue age, oldest-message lag — *not* on lagging signals like CPU.
Backpressure-aware scaling is the difference between "we autoscaled because the queue is
30s deep" (good) and "we autoscaled because CPU was 80% for 5 minutes" (too late).

**When to reach for it / How it manifests.**

- Worker pool draining a queue (Kafka consumers, SQS workers, Celery).
- The latency-sensitive metric is *time-in-queue*, not CPU.
- CPU stays low while latency degrades — the workload is IO-bound; CPU-based autoscaling
  is blind.

**Sketch (KEDA-style queue-depth scaling).**

```python
"""Conceptual: emit a scale signal based on queue age, not depth.

Queue *depth* is misleading because two queues with depth=1000 can have very
different ages: one drains in 1 second, the other in 10 minutes.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True, slots=True)
class QueueHealth:
    depth: int
    oldest_message_age: timedelta
    drain_rate_per_s: float  # measured over last minute


def desired_replicas(
    health: QueueHealth,
    *,
    target_age: timedelta = timedelta(seconds=10),
    per_replica_throughput: float = 50.0,
    min_replicas: int = 1,
    max_replicas: int = 100,
) -> int:
    """Right-size the worker fleet to keep oldest-message age below target."""
    if health.depth == 0:
        return min_replicas
    # Throughput needed to drain in target_age:
    needed_per_s = max(1.0, health.depth / target_age.total_seconds())
    raw = int(needed_per_s / per_replica_throughput) + 1
    return max(min_replicas, min(max_replicas, raw))
```

**The age-vs-depth distinction.** Queue depth alone misleads: a queue with 10,000
messages but a 1,000-msg/s drain rate is healthier than a queue with 100 messages and a
0.5-msg/s drain rate. Scale on *projected drain time* (depth / drain_rate) or *oldest
message age*.

**When NOT to use / What it costs.**

- *Stateless services with no queue.* CPU + request-rate is fine for stateless HTTP.
- *Per-key skew.* If 90% of messages target one shard, adding workers does not help —
  see partition pattern in `cloud.md`.
- *Cold-start tax.* Same as autoscaling generally; if startup > target_age, the system
  oscillates.

**Real-world examples.**

- *KEDA* (Kubernetes Event-Driven Autoscaler) — supports Kafka lag, RabbitMQ depth, SQS
  age, Prometheus queries.
- *AWS Application Auto Scaling on SQS* — `ApproximateAgeOfOldestMessage`.
- *Spotify's queue-age-based autoscaler* — written up in their backstage blog.

**References.**

- KEDA docs, keda.sh.
- AWS, *Auto-scaling SQS-based applications*, docs.aws.amazon.com.

---

## Stacking Caches

A real system has more than one cache. Reading from inside-out:

```
[ Browser cache ]              ← Cache-Control max-age
[ CDN edge cache ]             ← s-maxage, stale-while-revalidate, surrogate keys
[ Application L1 (in-process) ]← lru_cache, cachetools — microseconds, per-replica
[ Application L2 (shared) ]    ← Redis / Memcached — sub-ms cluster-wide
[ DB query plan cache ]        ← Postgres prepared statements
[ DB row cache ]               ← shared_buffers
[ source-of-truth disk ]       ← single durable copy
```

Each layer is a (latency, staleness, cost) tradeoff. Two ironclad rules:

1. **Inner layer's TTL ≤ outer layer's TTL.** If the CDN holds a value for 5 minutes, the
   in-process cache holding it for 1 hour serves stale-stale data when the CDN
   revalidates. Inner layers must expire first.
2. **Invalidation must propagate outward.** Invalidating the DB row does nothing if the
   L2 cache, then the L1 cache, then the CDN, are all serving the old value. Either
   shorten outer TTLs *or* add explicit purge — not both with mismatched policies.

If a stack of caches makes the dependency graph too complex to reason about, it usually
means one of the layers is not earning its keep — measure hit rates per layer; remove the
ones that hit < 50%.

---

## Review Checklist

For any PR that adds a cache or changes scaling behavior:

1. **Stampede protection.** Is there single-flight, lock-and-load, or
   stale-while-revalidate? Or is the pattern "if this key gets hot, the DB falls over"?
2. **Negative caching.** What happens for missing keys? Is there a short negative TTL?
3. **TTL.** Is there a TTL? Is it shorter than the outer cache's TTL?
4. **Invalidation order.** On write, does the source update before the cache invalidates?
5. **Cold-start.** What is the first-request latency on a cold cache? On a fresh
   replica?
6. **Pool sizing.** `replicas * pool_size ≤ DB max_connections * 0.8`? Pooler in front?
7. **Autoscaling signal.** Is the metric a *leading* indicator (queue age, request rate)
   or a *lagging* one (CPU)?
8. **Replica state.** Are replicas truly stateless? If sticky sessions are required, is
   the reason documented?
9. **Cache failure mode.** If the cache is *down*, does the system fail open (fall back
   to source) or fail closed (refuse requests)? Both are valid; the choice must be
   deliberate.

If any answer is "I don't know," the PR is not ready.

---

## References

**Books.**

- Kleppmann, M., *Designing Data-Intensive Applications*, O'Reilly, 2017 — chs. 5–6, 8.
- Newman, S., *Building Microservices*, 2nd ed., O'Reilly, 2021.
- Nygard, M., *Release It!*, 2nd ed., Pragmatic Bookshelf, 2018.
- Beyer, B. et al., *Site Reliability Engineering*, Google / O'Reilly, 2016 — chs. 21
  (handling overload), 22 (cascading failures).
- Majors, C. et al., *Observability Engineering*, O'Reilly, 2022.

**Papers.**

- Nishtala, R. et al., *Scaling Memcache at Facebook*, NSDI 2013.
- Vattani, A., et al., *Optimal Probabilistic Cache Stampede Prevention*, VLDB 2015.
- Mitzenmacher, M., *The Power of Two Choices in Randomized Load Balancing*, 2001.
- Bronson, N., et al., *TAO: Facebook's Distributed Data Store for the Social Graph*,
  USENIX ATC 2013.

**Vendor / industry.**

- Microsoft Azure, *Cloud Design Patterns*, learn.microsoft.com/azure/architecture/patterns.
- AWS, *Builders' Library*, aws.amazon.com/builders-library.
- Marc Brooker, *brooker.co.za* — load balancing, retries, metastability.
- Nick Craver, *Stack Overflow architecture posts*, nickcraver.com.
- Werner Vogels, *All Things Distributed*, allthingsdistributed.com.
