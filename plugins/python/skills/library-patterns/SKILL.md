---
name: library-patterns
description: >-
  Use when writing or reviewing Python that wraps a network service or
  authors a client SDK: client construction, async lifecycle, granular
  timeouts, retry policy, idempotency keys, exception hierarchies, Pydantic
  outputs, streaming via async context managers, request-id propagation, or
  pagination.
when_to_use: >-
  Trigger when designing an HTTP / SDK client, wrapping openai / anthropic /
  stripe / httpx, defining error classes, threading a request_id, streaming
  with cancellation, parsing output into Pydantic models, or reviewing a
  module owning an outbound connection.
disable-model-invocation: false
user-invocable: true
allowed-tools: []
model: inherit
paths:
  - "**/*.py"
  - "**/pyproject.toml"
shell: bash
---

# Python Library Patterns

This skill codifies the conventions that production-grade Python client
libraries — [openai-python](https://github.com/openai/openai-python),
[anthropic-sdk-python](https://github.com/anthropics/anthropic-sdk-python),
[stripe-python](https://github.com/stripe/stripe-python),
[httpx](https://github.com/encode/httpx), and the
[fastapi](https://github.com/fastapi/fastapi) request/response boundary —
have converged on. It is project policy for any module that owns an outbound
network connection or wraps a third-party SDK. It is not a tutorial on any
single library; it specifies which shapes are accepted and which are rejected
when the code in this repo crosses a process boundary.

This skill cross-references rather than duplicates:

- Data modelling at the boundary → `python:pydantic`
- Generic typing, `Protocol`, `ParamSpec`, narrowing → `python:typings`
- Streaming primitives, bounded concurrency, profiling → `python:performance`
- Retry / circuit-breaker / bulkhead theory → `design-patterns:system`
- Docstring shape on public surfaces → `python:docstrings`

When this document says *"see `python:pydantic`"*, it means follow that skill
verbatim — do not restate its rules here.

## Non-negotiables

- A single typed client class owns the connection lifecycle. Module-globals
  that lazily create clients on first use are rejected: the client is
  constructed explicitly, threaded as a dependency, and closed deterministically
  via `async with` or `await client.aclose()`.
- Timeouts are granular: separate `connect`, `read`, `write`, and `pool`
  budgets, not a single wall-clock number. A single `timeout=30.0` argument is
  a code smell — replace it with `httpx.Timeout(...)` or the SDK's structured
  timeout type.
- Retries are bounded, classified, and idempotency-keyed. Unbounded retry
  loops, retries on `4xx` other than `408 / 409 / 429`, and retries on
  non-idempotent operations without an idempotency key are rejected.
- Errors form a single hierarchy rooted at one project-level base. Every
  error exposes `status`, `request_id`, `headers`, and a human-readable
  `message`. Bare `RuntimeError` / `Exception` at boundaries is rejected.
- Untrusted input is validated through Pydantic at the boundary (see
  `python:pydantic`); inside trusted code, prefer plain typed objects.
- Domain identifiers are `NewType`s, not bare primitives. openai-python
  types every id that crosses its API this way (`FileId`, `BatchId`) so a
  `file_id` cannot be passed where a `batch_id` is expected; a client
  wrapper that models ids as plain `str` gives up that guarantee. Closed
  request-parameter sets are `Literal[...]`, promoted to `StrEnum` on
  second use. See `python:typings` § Aliases, NewTypes, and Closed Sets.
- Streaming responses are consumed inside `async with` blocks. Raw
  `stream=True` returns held past the lifetime of the `async with` are
  rejected — they leak file descriptors and event-loop tasks.
- Public functions that talk to a network service take a typed `Client` (or a
  `Protocol` describing it) as their first dependency — never reach for a
  module-level `client` inside the function body.
- Secrets are `SecretStr` until the call site that injects them into a header
  or query string. See `python:pydantic` § Secrets.
## Detail sections

The detail sections live in `references/` — load only what the task touches:

- [`construction-and-retries.md`](references/construction-and-retries.md) —
  client construction, per-request overrides, timeout granularity, retry
  policy (with idempotency-key shape)
- [`errors-and-outputs.md`](references/errors-and-outputs.md) — exception
  hierarchies, structured Pydantic outputs, settings & config
- [`streaming-and-pagination.md`](references/streaming-and-pagination.md) —
  streaming via async context managers, pagination, observability /
  request-id propagation, LLM tool-use parsing, anti-patterns

## References

Primary upstream sources for the patterns codified here:

- [openai-python](https://github.com/openai/openai-python) — client config,
  `.parse(response_format=...)`, `pydantic_function_tool`, streaming.
- [anthropic-sdk-python](https://github.com/anthropics/anthropic-sdk-python)
  — `client.messages.parse`, `stream.text_stream`, error hierarchy
  (`APIError`, `RateLimitError`, `AuthenticationError`).
- [stripe-python](https://github.com/stripe/stripe-python) — idempotency
  keys, structured error hierarchy with `user_message`, `should_retry`,
  `request_id`; per-request `options` dict.
- [httpx](https://github.com/encode/httpx) — `AsyncClient` lifecycle,
  `httpx.Timeout(connect, read, write, pool)`, `event_hooks`,
  `AsyncHTTPTransport(retries=...)`.
- [fastapi](https://github.com/fastapi/fastapi) — Pydantic at request /
  response boundaries, `@app.exception_handler(RequestValidationError)`,
  `HTTPException` with structured detail.
- [AWS Architecture Blog — exponential backoff and jitter](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)
  — canonical reference for the backoff formula used above.

Cross-references inside this repo:

- `python:pydantic` — `BaseModel`, `BaseSettings`, validators, `SecretStr`,
  `TypeAdapter`.
- `python:typings` — `Protocol`, `ParamSpec`, generics, `Self`.
- `python:performance` — bounded async, `asyncio.Queue`, backpressure.
- `python:docstrings` — public API surface documentation style.
- `design-patterns:system` — retry, circuit breaker, bulkhead theory.

## Freshness

This skill is project policy distilled from the libraries above. Pinned
versions at authorship: `openai-python 2.11`, `anthropic-sdk-python` main,
`stripe-python` v8+, `httpx` 0.27+, `fastapi` 0.118+.

When applying it to an unfamiliar API surface, version-specific behaviour, a
checker disagreement, or anything that may have moved since this was
written, verify against primary docs. Prefer Context7 MCP when available
(library IDs above resolve directly). If unavailable, restrict web search
to the upstream `github.com/<org>/<repo>/blob/main` and the official
documentation site.
