---
name: performance-review
description: >-
  Use when reviewing code for performance issues: algorithmic complexity,
  N+1 queries, unnecessary allocations, unbounded concurrency, cache
  misuse, blocking I/O in async context, hidden materialization, ReDoS,
  cold-start cost, missing database indexes, connection pool exhaustion,
  or memory leaks.
when_to_use: >-
  Trigger for performance code review: O(n^2) loops, N+1 queries,
  missing database indexes, unbounded asyncio.gather, blocking I/O in
  async, hidden materialization (list/sorted/json on large inputs),
  cache without eviction, functools.lru_cache unbounded, ReDoS
  patterns, connection pool exhaustion, memory leaks from retained
  references, cold-start heavy imports, eager initialization, large
  payload serialization without streaming, regex backtracking,
  CPU-bound work in event loop.
disable-model-invocation: false
user-invocable: false
---

# Performance Review Checklist

The gap between "fine for small N" and "correct for large N" is where
performance bugs live. This checklist focuses on patterns that break at
scale, not micro-optimizations. A finding is only worth reporting if
the code path will realistically encounter the problematic input size.

## 1. Algorithmic Complexity

### Quadratic and Worse

- Nested loops over the same or correlated collections:
  `for x in items: for y in items:`
- Repeated linear search instead of set/dict lookup:
  `if x in large_list`
- String concatenation in a loop: `result += chunk`
  (O(n^2) in Python for large n)
- Sorting inside a loop:
  `for item in items: sorted_subset = sorted(...)`
- Repeated list insertion at index 0:
  `items.insert(0, x)` in a loop

### Hidden Complexity

- `in` operator on a list vs a set (O(n) vs O(1) per check)
- `list.remove(x)` is O(n) — doing it in a loop is O(n^2)
- `dict.values()` membership test is O(n) — use key lookup
- Regular expression with catastrophic backtracking (ReDoS):
  patterns with nested quantifiers like `(a+)+$`, `(a|b)*c`
- Recursive calls without memoization on overlapping subproblems

### When to Flag

- Flag if the collection can grow with user data or external
  input
- Skip if the collection is bounded by a known constant (e.g.,
  enum values)
- Use blast radius to prioritize: hot path with 200 callers >
  cold utility

## 2. Database and Query Patterns

### N+1 Queries

- Loop that executes a query per iteration:
  `for item in items: db.query(related)`
- ORM lazy loading inside iteration: accessing a relationship
  attribute in a loop
- Missing `select_related()` / `joinedload()` / `include()` on
  relationship traversal
- GraphQL resolvers that fetch per-field instead of batching

### Missing Indexes

- New `WHERE` clause on a column without an index
- New `ORDER BY` on a column without an index
- Composite query filtering on multiple columns — composite
  index needed?
- Full table scan indicators: `LIKE '%pattern'`, function calls
  on indexed columns

### Query Efficiency

- `SELECT *` when only a few columns are needed
- Fetching all rows when only count/exists is needed
- Missing `LIMIT` on queries that could return unbounded results
- Repeated identical queries in the same request (missing cache)
- Transaction held open across I/O operations (lock contention)

## 3. Memory and Allocation

### Hidden Materialization

- `list()` on a generator/iterator that could be large
- `sorted()` on a large iterable (materializes the full sequence)
- `.json()` / `.dict()` / `model_dump()` on large nested models
- `Path.read_text()` / `file.read()` on potentially large files
- `response.json()` on unbounded API responses
- Collecting all results before processing vs streaming

### Memory Leaks

- Growing collections without eviction: `cache = {}` that only
  adds, never removes
- `functools.lru_cache` / `functools.cache` without `maxsize`
  (unbounded growth)
- Event listeners registered but never removed
- Closures capturing large objects that outlive their useful
  lifetime
- Circular references preventing garbage collection (rare in
  Python, more common in JS)

### Allocation Patterns

- Creating objects in a hot loop that could be reused
- Copying large data structures unnecessarily (`deepcopy` in
  a loop)
- String formatting in a loop when the template is constant
- Repeated `re.compile()` of the same pattern (should compile
  once at module level)

## 4. Async and Concurrency

### Blocking in Async Context

- `open()` / `Path.read_text()` in an async function (blocks
  the event loop)
- `requests.get()` instead of `httpx`/`aiohttp` in async code
- `time.sleep()` in an async function (use `asyncio.sleep()`)
- CPU-bound computation in an async handler without
  `run_in_executor()`
- Synchronous database driver in async application

### Unbounded Concurrency

- `asyncio.gather(*[task() for item in unbounded_list])` — no
  concurrency limit
- Missing `asyncio.Semaphore` for rate-limiting concurrent
  operations
- Missing `maxsize` on `asyncio.Queue` (unbounded memory growth
  under backpressure)
- Thread pool with no max workers on user-controlled workload
- `Promise.all()` on unbounded array in TypeScript

### Async Anti-Patterns

- `await` in a loop when `gather`/`TaskGroup` would parallelize
- Creating a new connection per request instead of using a pool
- Missing timeout on external calls: `await client.get(url)`
  with no timeout
- Fire-and-forget tasks without error handling (silently dropped
  exceptions)

## 5. Caching

### Cache Without Eviction

- Dictionary used as cache without TTL, max size, or LRU policy
- `functools.cache` (unbounded) on functions with many distinct
  inputs
- Global cache that grows with request volume

### Cache Correctness

- Cache key doesn't include all parameters that affect the result
- Cached mutable object returned by reference (callers can
  corrupt cache)
- Cache not invalidated when underlying data changes
- Race condition: concurrent cache miss causes redundant
  computation

### Cache Overhead

- Caching results cheaper to compute than the cache lookup itself
- Cache with very low hit rate (adds memory pressure for no
  benefit)
- Serialization cost of cache values exceeds computation cost

## 6. I/O and Network

### Connection Management

- Connection created per request instead of pooled
- Pool exhaustion: `max_connections` too low for concurrent load
- Missing connection timeout (hanging connections consume pool
  slots)
- Connection not returned to pool on error (leak via exception
  path)

### Payload Size

- Large response bodies serialized without streaming
- Base64-encoding large binary data inline (use multipart or
  streaming)
- Logging full request/response bodies at DEBUG level (disk I/O
  plus allocation)
- Loading entire file into memory for line-by-line processing
  (use iterators)

### Retry and Timeout

- Missing timeout on HTTP client calls (can hang indefinitely)
- Retry without exponential backoff (thundering herd on failures)
- Retry on non-idempotent operations (duplicate side effects)
- No circuit breaker on repeatedly failing external services

## 7. Cold Start and Initialization

### Import-Time Cost

- Heavy computation at module import time (delays startup)
- Importing large libraries that aren't always needed (lazy
  import instead)
- Database connections established at import time
- Global regex compilation of many patterns at module level

### Eager vs Lazy Initialization

- Singleton that initializes all dependencies at construction,
  not first use
- Configuration validation that calls external services at
  startup
- Loading large data files into memory at import rather than
  on demand
