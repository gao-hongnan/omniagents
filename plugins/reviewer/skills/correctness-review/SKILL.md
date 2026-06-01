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

# Correctness Review Checklist

Walk every code path in the diff — not just the happy path. Every branch,
every exception handler, every early return. The goal is to find code that
will produce wrong results, crash, or silently corrupt state.

## When to Flag

- Flag a code path that produces wrong output, crashes, or corrupts state on
  a **reachable** input. If no realistic input triggers it, lower severity or
  skip.
- Skip defensive checks the type system already guarantees (e.g. a `None`
  guard on a non-`Optional` parameter).
- Skip behavior-identical stylistic variants — only flag when behavior differs.

## 1. Logic Errors

### Off-by-One and Boundary Errors

- Loop bounds: `<` vs `<=`, `range(n)` vs `range(n+1)`, fencepost
- Array/string indexing: last element is `len-1`, empty collection
- Slice semantics: Python `a[start:stop]` excludes `stop`
- Pagination: first page 0 or 1? Last page calculation correct?

### Arithmetic and Numeric

- Integer overflow in languages without arbitrary precision
  (TypeScript `Number.MAX_SAFE_INTEGER`)
- Floating-point comparison: never `==` on floats; use
  `math.isclose` or epsilon
- Division by zero: check divisor before dividing
- Negative numbers: does the code handle negative inputs where
  unsigned was assumed?
- Modulo with negative operands: behavior differs by language

### Boolean Logic

- De Morgan violations: `not (A and B)` vs `not A or not B`
- Short-circuit evaluation: side effects in conditions that may
  not execute
- Truthiness traps: `if x` when `x` could be `0`, `""`, or `[]`
  (all falsy but valid)
- Operator precedence: missing parentheses in compound conditions

### Control Flow

- Unreachable code after early returns
- Missing `break` in switch/match (TypeScript switch fallthrough)
- Exhaustiveness: `match`/`switch` missing a case; no
  `default`/`case _` handler
- `else` branch missing when both outcomes need handling

## 2. Type Safety

### Python

- `Any` leakage: function returns `Any`, callers lose type info
- `Optional` access without `None` check: `x.attr` when
  `x: T | None`
- `cast()` hiding real type errors instead of fixing them
- `dict.get()` returns `T | None` — is the `None` case handled?
- Mutable default arguments: `def f(items: list[str] = [])`
  shares state
- `isinstance` checks that miss subtypes or union members

### TypeScript

- Non-null assertion `!` hiding potential `undefined`
- Type assertion `as T` bypassing type checker
- Optional chaining `?.` returning `undefined` — handled
  downstream?
- Index access on arrays without bounds checking
- `unknown` narrowed with `as` instead of type guards
- Enum member comparison with `===` on string enums (correct)
  vs numeric enums (fragile)

### Cross-Language

- Return type doesn't match declared signature (especially in
  generic code)
- Generic type parameter unconstrained when it should be bounded
- Covariance/contravariance violations in collection types

## 3. Error Handling

### Exception Safety

- **Bare `except`** (Python) or **bare `catch`** (TypeScript):
  swallows everything including `KeyboardInterrupt`, `SystemExit`
- **Exception swallowing**: `except SomeError: pass` — silent
  failure
- **Missing re-raise**: catching, logging, but not re-raising or
  returning an error value
- **`finally` with `return`**: masks exceptions from `try` block
- **Wrong exception type**: catching too broad (`Exception`) or
  too narrow

### Error Propagation

- Function returns `Result[T, E]` but a code path raises instead
  of returning `Err`
- Error codes from subprocess/external call unchecked
- Promise/async errors: missing `.catch()`, missing `try/except`
  in `async` function
- Error context lost: re-raising without chaining
  (`raise NewError() from original`)

### Resource Cleanup

- File/connection/lock opened but not closed on error path
- Missing `async with` for async context managers
- `__del__` relied on for cleanup (non-deterministic in Python)
- Database transaction not rolled back on exception

## 4. Concurrency and State

### Race Conditions

- **TOCTOU** (time-of-check-to-time-of-use): checking file exists
  then opening it; checking dict key then accessing it (in
  concurrent code)
- **Data races**: shared mutable state accessed from multiple
  threads/tasks without synchronization
- **Atomicity violations**: compound operations
  (check-then-act, read-modify-write) that aren't atomic
- **Deadlock patterns**: acquiring locks in inconsistent order;
  holding a lock while awaiting

### Async/Await

- `await` missing on a coroutine call (coroutine created but
  never awaited)
- Blocking I/O in an async function (`open()`, `requests.get()`
  instead of async equivalents)
- `asyncio.gather` exceptions: default behavior swallows; need
  `return_exceptions=True` or `TaskGroup`
- Shared mutable state across concurrent tasks without protection

### State Management

- Mutable shared state modified without copy (aliasing bugs)
- Stale closure captures: lambda/callback capturing loop variable
  by reference
- Uninitialized variables: variable used before assignment on
  some code paths
- Use-after-close: using a resource (file, connection, session)
  after it's been closed/released

## 5. API Contract Compliance

### Function Contracts

- Preconditions: does the caller satisfy documented requirements?
- Postconditions: does the function deliver what its
  signature/docstring promises?
- Invariants: does the function preserve class/module invariants?
- Liskov Substitution: does a subclass override change behavior
  in ways callers don't expect?

### External API Usage

- Deprecated API usage: calling methods marked for removal
- Wrong argument order: positional args in wrong sequence
  (especially similar types)
- Missing required parameters: optional in old version, required
  in new
- Return value semantics changed between versions

## 6. Edge Cases

### Empty and Boundary Inputs

- Empty collection: `[]`, `{}`, `""`, `None` — handled?
- Single-element collection: different behavior than multi?
- Maximum size: what happens at `sys.maxsize`, `MAX_INT`?
- Zero-length strings, whitespace-only, embedded nulls

### Data Format

- Unicode: combining characters, surrogate pairs, zero-width
- Timezones: naive vs aware datetime; UTC vs local; DST
- Locale-sensitive operations: sorting, case conversion, numbers
- Path separators: `/` vs `\`; absolute vs relative; trailing `/`

### Concurrency Edge Cases

- First request (cold start, empty cache, uninitialized singleton)
- Simultaneous identical requests (thundering herd)
- Timeout during a multi-step operation (partial state)
- Graceful shutdown: in-flight requests handled or dropped?
