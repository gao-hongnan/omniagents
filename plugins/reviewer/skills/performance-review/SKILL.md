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

# Performance Review — Hunt Protocols

The gap between "fine for small N" and "broken at scale" is where
performance bugs live. Every finding needs a **growth story**: name where N
comes from and why it grows, or the finding is speculation. Micro-
optimizations on cold, bounded paths are noise.

## Hunts

Execute every hunt whose `When` matches; skip the rest. Exemplars are
calibration anchors, never templates — do not copy their wording into
reports.

### Hunt: Growth Variable

- **When**: a new loop, comprehension, or recursion over a collection, or
  any operation whose cost scales with data (sort, `in` on a list, string
  `+=` in a loop).
- **Protocol**:
    1. Name N's source: request payload, table, file, user count — or a
       constant you can point at.
    2. Establish growth: does N scale with users/data/time, or is it
       bounded (enum, config list, pagination cap)?
    3. For nested loops, establish whether the two collections correlate
       (same data, joined data) — that is what makes it quadratic.
    4. Grade by cost × call frequency (impact radius), never by shape
       alone.
- **Evidence bar**: the named growth source plus the superlinear operation
  over it.
- **Falsifiers**: N is constant-bounded; the code runs once at startup or
  in an offline job; an upstream cap (pagination, batch size) bounds it.
- **Exemplar**: IMPORTANT 84 — "`if sku in seen` with `seen` a list inside
  the import loop — quadratic over a 50k-row upload; a set lookup is the
  one-line fix." / **Noise twin**: a nested loop over weekdays × locales —
  both constant-bounded.

### Hunt: Database Round-Trip

- **When**: a DB/ORM/HTTP call lexically inside an iteration body, or
  reachable from one through a helper.
- **Protocol**:
    1. Read the loop body **and its callees one level down**
       (`callees_of`, Read) for query/fetch calls — the N+1 usually hides
       in the helper.
    2. Confirm per-iteration execution: nothing batches, caches, or
       eager-loads it.
    3. Check whether a batch API already exists (a `WHERE … IN` method,
       `joinedload`/`select_related`, a dataloader) — that is the fix to
       name.
- **Evidence bar**: the per-item call site plus an iteration source that
  scales.
- **Falsifiers**: the iterable is constant-bounded; the relationship is
  eager-loaded upstream (point at the query options); a request-scoped
  cache dedupes the calls.
- **Exemplar**: IMPORTANT 85 — "`enrich(ticket)` runs `SELECT … WHERE
  id=?` per ticket in the listing loop — page size 100 means 101 queries;
  the repo class already has a `WHERE id IN` variant." / **Noise twin**:
  a per-item query in an offline one-shot backfill script.

### Hunt: New Query Shape

- **When**: a new or changed `WHERE`, `ORDER BY`, `JOIN`, or `GROUP BY` —
  or a first query against a table.
- **Protocol**:
    1. Grep `migrations/` and schema files for an index on the
       filtered/sorted columns **before** flagging.
    2. For composite predicates, apply the leftmost-prefix rule: does an
       existing index actually cover this combination?
    3. Spot full-scan shapes: leading-wildcard `LIKE`, a function call on
       an indexed column, implicit type casts.
    4. Check `LIMIT` on potentially unbounded results and `SELECT *` on
       wide tables.
- **Evidence bar**: the query, the absent index or scan shape, and the
  table's growth story.
- **Falsifiers**: the index exists in an earlier migration; the table is
  bounded by design (config/lookup table); the query belongs to an
  offline batch where a scan is acceptable.
- **Exemplar**: IMPORTANT 82 — "new `ORDER BY created_at` on `events`
  with no index — `events` grows unbounded, so every page view pays a
  full sort." / **Noise twin**: an unindexed filter on a 12-row
  feature-flag table.

### Hunt: Materialization

- **When**: `list()`, `sorted()`, `.read()`, `.json()`, `model_dump()`, or
  a spread over data of unknown size; collecting everything before
  processing anything.
- **Protocol**:
    1. Trace the size source: request body, table, file, third-party
       response?
    2. Check for the streaming alternative at that boundary: iterators,
       cursors, chunked reads, streaming responses.
    3. Confirm no upstream bound (LIMIT, max-size validation, pagination)
       already caps the data.
- **Evidence bar**: the materializing call plus the unbounded size source.
- **Falsifiers**: an upstream cap exists; the data is config-scale; the
  algorithm genuinely needs the full set (then the missing upstream bound
  is the finding, if anything).
- **Exemplar**: IMPORTANT 83 — "`rows = list(cursor)` before the CSV loop
  buffers the entire table in memory; the cursor already streams
  row-by-row." / **Noise twin**: `sorted(enabled_plugins)` — a
  config-bounded list.

### Hunt: Unbounded Fan-out

- **When**: `gather`/`Promise.all`, thread/process pools, or queue
  producers in the diff.
- **Protocol**:
    1. Find the bound: semaphore, capped `TaskGroup`, pool `max_workers`,
       queue `maxsize` — or establish there is none.
    2. Trace the input list's size source (request-controlled is the red
       flag).
    3. Check each fanned-out call for a timeout — one stuck task stalls
       the whole gather.
- **Evidence bar**: fan-out over an input that scales with no concurrency
  bound on the path.
- **Falsifiers**: the input is bounded (fixed endpoint list, page-capped
  batch); a semaphore or pool cap exists upstream — name it.
- **Exemplar**: IMPORTANT 85 — "`asyncio.gather(*(probe(u) for u in
  urls))` with `urls` from the request body — a 10k-URL payload opens 10k
  concurrent sockets." / **Noise twin**: `gather` over exactly three
  fixed health-check endpoints.

### Hunt: Event-Loop Stall

- **When**: new code inside `async def` (or on a Node request path).
- **Protocol**:
    1. Scan the body and its **sync callees** for blocking calls:
       `open()`/`Path.read_text`, `requests.*`, `time.sleep`, sync DB
       drivers, heavy CPU work (parsing, compression, crypto).
    2. Check for the async equivalent or an executor handoff
       (`asyncio.to_thread`, `run_in_executor`).
    3. Estimate the stall: a 200 ms blocking call in a handler freezes
       every coroutine on the loop for 200 ms.
- **Evidence bar**: the blocking call inside the async path, named.
- **Falsifiers**: the call is constant microseconds (tiny local read at
  startup); the code provably runs in a worker thread, not on the loop
  (verify, don't assume).
- **Exemplar**: IMPORTANT 86 — "`requests.get(url)` inside the async
  webhook handler blocks the loop for the full round-trip; `httpx` is
  already a dependency." / **Noise twin**: `json.loads` on a small,
  schema-capped payload — trivial bounded CPU.

### Hunt: Cache & Retention Audit

- **When**: a new cache, memo, `lru_cache`, module-level collection, or
  listener/callback registration.
- **Protocol**:
    1. Find the eviction policy — `maxsize`, TTL, LRU — or establish there
       is none.
    2. Check key cardinality: does the key space grow with
       users/requests/time?
    3. Check key completeness: every parameter that affects the result is
       in the key (a missing one is a *correctness* hand-off, still flag
       the staleness).
    4. Find the deregistration for every registration — the leak is the
       listener nobody removes. Mutable values returned by reference can
       be corrupted by callers.
- **Evidence bar**: an unbounded cardinality source, or a concrete
  staleness/retention story.
- **Falsifiers**: `maxsize`/TTL is set; the key space is provably small
  (enum-keyed); the process is short-lived (CLI) so retention dies at
  exit.
- **Exemplar**: IMPORTANT 84 — "module-level `_results[job_id] = …` with
  no eviction — one entry per job forever; the worker OOMs on long
  uptimes." / **Noise twin**: `@lru_cache(maxsize=256)` on a pure parser —
  bounded by construction.

## Severity Anchors

Performance severity is **cost × frequency**. Grade with the contract's
Severity Rubric and elevation rule, calibrated by blast radius:

- Hot path (50+ callers or user-facing request path): lean IMPORTANT or
  BLOCKER.
- Moderate path (10–50 callers): lean IMPORTANT.
- Cold path (< 10 callers): SUGGESTION unless egregious (whole-table
  buffering, unbounded fan-out).
- **BLOCKER**: superlinear work or unbounded memory on a hot path that
  breaks at realistic scale.
- **IMPORTANT**: N+1, missing index, blocking-in-async, or unbounded
  retention on a path that ships to production.
- **SUGGESTION**: the same shapes on cold, bounded paths where the fix is
  cheap and the payoff is real.

## Recall Sweep

After the hunts, sweep the diff once against these. Flag only what passes
the contract's Taste Test:

- ReDoS: nested quantifiers (`(a+)+$`), alternation with overlap, on
  user input.
- Loop allocations: `re.compile` per iteration, string `+=`, `deepcopy`,
  repeated identical queries per request.
- Collections: `in` on a list where a set is warranted, `list.remove` in
  a loop, `dict.values()` membership.
- Connections: created per request instead of pooled, not returned on the
  error path, pool size vs concurrency, missing HTTP timeout.
- Retries: no backoff (thundering herd), retrying non-idempotent calls.
- Payloads: base64-ing large blobs inline, logging full bodies, loading a
  whole file for line-by-line work.
- Cold start: heavy import-time computation, eager init of all
  dependencies, module-level connection setup.
