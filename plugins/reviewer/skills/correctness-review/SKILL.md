---
name: correctness-review
description: >-
  Use when reviewing code for logic errors, type-safety violations,
  null/undefined handling, off-by-one, race conditions, incorrect API
  usage, broken contracts, missing error handling, edge-case gaps, or
  state-management bugs.
when_to_use: >-
  Trigger for correctness code review: logic bugs, type mismatches,
  unchecked Optional/None/null, off-by-one errors, fencepost errors,
  integer overflow, floating-point comparison, TOCTOU races, data races,
  deadlocks, bare except, exception swallowing, missing re-raise,
  finally-with-return, return-type violations, invariant breaks, Liskov
  violations, mutable shared state, uninitialized variables,
  use-after-close, empty collections, boundary values, Unicode handling,
  timezone issues.
disable-model-invocation: false
user-invocable: false
---

# Correctness Review — Hunt Protocols

Find code that produces wrong results, crashes, or silently corrupts state
on a **reachable** input. Walk every changed code path — every branch,
exception handler, and early return — by running the hunts whose triggers
match the diff.

## Hunts

Execute every hunt whose `When` matches; skip the rest. Exemplars are
calibration anchors, never templates — do not copy their wording into
reports.

### Hunt: Stale Call-Site

- **When**: the diff renames a symbol, changes a signature (parameters,
  return shape, types), or changes a function's semantic contract.
- **Protocol**:
    1. List consumers of each changed symbol — `query_graph_tool`
       `callers_of` / `importers_of`, plus Grep for the old name and for
       keyword-argument uses.
    2. Read each call site against the **new** contract: argument order,
       field names, return-value handling, exceptions raised.
    3. Grep the non-code surface too: configs, templates, docs, serialized
       fixtures that embed the old name.
- **Evidence bar**: a call site you have read that still uses the old
  contract.
- **Falsifiers**: a compatibility shim or alias keeps the old name working;
  the type checker already fails the build on it (CI territory); the stale
  use is deliberately pinned to an old version (migrations replaying
  history).
- **Exemplar**: BLOCKER 95 — "`audit/log.py:21` reads `event.actor_id`,
  which this diff renamed to `user_id`; AttributeError on every audit
  write." / **Noise twin**: the old column name inside an old migration
  file — pinned history, not a stale site.

### Hunt: Boundary Trace

- **When**: new or changed loop bounds, slicing, index arithmetic, page
  math, or size/length comparisons.
- **Protocol**:
    1. Execute the code mentally for n=0 (empty), n=1, and n=max; write
       down the actual indices touched.
    2. Check each `<` vs `<=` and each `range`/slice endpoint against the
       loop's exit purpose.
    3. For page math: first index 0 or 1, last-partial-chunk remainder,
       and the fencepost between a count and a last index.
- **Evidence bar**: a concrete input for which an index goes out of range,
  an element is skipped, or an extra iteration occurs.
- **Falsifiers**: an upstream guard rejects the boundary input; validation
  guarantees non-empty; an existing test pins the boundary.
- **Exemplar**: IMPORTANT 85 — "`batches = total // size` drops the final
  partial batch whenever `total % size != 0`; reachable on any non-multiple
  upload." / **Noise twin**: `items[0]` directly below
  `if not items: return` — guarded.

### Hunt: Two-Workers Trace

- **When**: the diff touches state shared across threads, tasks, processes,
  or requests — module globals, class attributes, caches, files, DB rows —
  or adds a check-then-act sequence on external state.
- **Protocol**:
    1. Name the shared state and every write point in the changed code.
    2. Write down two concurrent executions interleaved at the check/act
       (or read/modify/write) boundary: worker A passes the check, worker B
       mutates, A acts on stale truth.
    3. Identify what enforces atomicity or ordering — a lock, a
       transaction, an atomic primitive, single-threaded-by-design — or
       establish that nothing does.
- **Evidence bar**: a named interleaving that corrupts state or violates an
  invariant, plus the absence of an enforcing mechanism.
- **Falsifiers**: execution is single-threaded by framework contract; the
  state is request-/task-local; the operation is idempotent so the race is
  harmless; a lock or transaction found upstream.
- **Exemplar**: BLOCKER 90 — "module-level `hits[key] = hits.get(key, 0)+1`
  mutated by every request thread; concurrent increments lose counts — no
  lock anywhere in the module." / **Noise twin**: read-modify-write on a
  list built and consumed inside one handler call — never shared.

### Hunt: Abandoned Coroutine

- **When**: the diff adds or edits `async` code, coroutine calls, task
  creation, or async context managers.
- **Protocol**:
    1. Audit every coroutine invocation for a missing `await` — the bare
       call creates a coroutine object and silently does nothing.
    2. Check `gather`/`TaskGroup`/`Promise.all` error semantics: are
       exceptions collected, do they cancel siblings, or do they vanish?
    3. Check fire-and-forget tasks for exception handling and lifetime —
       does anything hold a reference, and who sees a crash?
- **Evidence bar**: the un-awaited call site, or the error path on which an
  exception is silently dropped.
- **Falsifiers**: the task is deliberately scheduled (`create_task` with a
  stored reference / done-callback); the framework awaits it; an async lint
  rule already enforced in CI catches it.
- **Exemplar**: BLOCKER 92 — "`session.commit()` un-awaited in
  `save_draft`; the coroutine is discarded and no draft ever persists." /
  **Noise twin**: `self._hb = asyncio.create_task(heartbeat())` with
  cancellation in `close()` — managed fire-and-forget.

### Hunt: Error-Path Walk

- **When**: new or changed `try/except/finally`, error returns, resource
  acquisition (files, locks, connections, transactions), or calls into
  functions that raise.
- **Protocol**:
    1. Pick each call in the changed block that can fail; trace that
       failure end-to-end: what is caught, what is swallowed, what is
       re-raised (with chaining?), what the caller observes.
    2. Verify cleanup on the **error** path: resource released, transaction
       rolled back, lock freed — or only on success?
    3. Check `finally` for `return`/`break` (masks in-flight exceptions)
       and `except` clauses broad enough to eat interrupt-class signals.
- **Evidence bar**: a nameable failure whose effect is silent loss, a
  leaked resource, or corrupted partial state.
- **Falsifiers**: a context manager guarantees release; the caller catches
  and reports; the swallow is logged and the operation is documented
  best-effort.
- **Exemplar**: IMPORTANT 84 — "`conn = pool.acquire()` sits above the
  `try:`; a parse failure leaks the connection — no context manager, and
  the pool caps at 10." / **Noise twin**:
  `except FileNotFoundError: return None` on an optional cache file whose
  callers handle `None`.

### Hunt: Exhaustiveness

- **When**: the diff adds an enum member, union variant, subclass, or
  message type — or adds/removes a branch in a dispatching construct.
- **Protocol**:
    1. Find every construct dispatching on the type: Grep for the enum
       name and `match`/`switch`/if-elif chains; `query_graph_tool`
       `inheritors_of` for class hierarchies.
    2. Verify each site handles the new case or lands in a default that is
       genuinely safe — not a silent pass-through.
    3. Reverse direction: for a removed variant, find callers still
       producing it.
- **Evidence bar**: a dispatch site you read that does not handle the new
  case, plus what happens there at runtime (raise? silent skip?).
- **Falsifiers**: exhaustiveness is checker-enforced (`assert_never`, a
  `never`-typed default) so the build fails instead; the default branch
  handles the new case correctly by design.
- **Exemplar**: BLOCKER 88 — "new `Status.SUSPENDED` unhandled in the
  export `match`; every suspended account hits `case _: raise
  ValueError`." / **Noise twin**: the TypeScript switch whose `default`
  assigns to a `never` — the compiler already rejects the gap.

### Hunt: Null-Path Trace

- **When**: the diff introduces or propagates `Optional`/`None`/`undefined`
  — `dict.get()`, optional chaining, nullable returns, `| None` parameters.
- **Protocol**:
    1. For each nullable production point, list its consumption points —
       same function first, then callers via `callers_of`.
    2. Verify a guard or type-narrowing on **every** path between
       production and use, not just the happy one.
    3. Inspect the guard's semantics: `if x:` also rejects `0`, `""`, `[]`
       — is falsy-vs-None conflation itself the bug?
- **Evidence bar**: a path from a None-producing expression to an unguarded
  attribute/index/method use.
- **Falsifiers**: the type system proves non-null on that path; the dict
  key is invariantly present (seeded at startup — name where); a caller
  validated already (name which).
- **Exemplar**: IMPORTANT 82 — "`cfg = registry.get(env)` then `cfg.url`
  eight lines later; `get` returns None for unknown env and two of three
  callers pass user input." / **Noise twin**: attribute access four lines
  below `if obj is None: raise` — narrowed.

## Severity Anchors

Grade with the contract's Severity Rubric and elevation rule. In this
dimension:

- **BLOCKER**: wrong results, crash, or corruption on a mainline path — a
  stale call site, an unhandled new variant in production dispatch, a race
  corrupting shared state.
- **IMPORTANT**: wrong behavior on a realistic edge — boundary input, error
  path, reachable None — or a latent race on a warm path.
- **SUGGESTION**: fragile-but-currently-correct with a concrete hardening
  (e.g. a truthiness check standing in for a None check today).

## Recall Sweep

After the hunts, sweep the diff once against these. Flag only what passes
the contract's Taste Test:

- Logic: De Morgan slips, operator precedence, short-circuit side effects,
  truthiness traps, unreachable code, missing `break`/fallthrough.
- Numerics: float `==`, division by zero, negatives where unsigned assumed,
  modulo of negatives, `MAX_SAFE_INTEGER` overflow.
- Python types: `Any` leakage, `cast()` hiding errors, mutable default
  arguments, `isinstance` missing union members.
- TypeScript types: `!` assertions, `as` bypassing the checker, unchecked
  index access, `unknown` narrowed with `as`.
- Contracts: pre/postconditions vs docstring, Liskov surprises in
  overrides, deprecated APIs, positional args swapped between same-typed
  parameters.
- Data: Unicode combining/surrogates, naive-vs-aware datetimes, DST,
  locale-sensitive sort/case, path separators and trailing slashes.
- Lifecycle: use-after-close, `__del__` as cleanup, stale closure capture
  of loop variables, uninitialized-on-some-path variables.
