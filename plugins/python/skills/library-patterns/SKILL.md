---
name: library-patterns
description: >-
  Use when writing or reviewing Python that wraps a network service or
  authors a client SDK: client construction, async lifecycle, granular
  timeouts, retry policy, idempotency keys, structured exception hierarchies,
  per-request overrides, structured outputs with Pydantic, streaming via
  async context managers, request-id propagation, or pagination.
when_to_use: >-
  Trigger when designing an HTTP/SDK client, wrapping openai / anthropic /
  stripe / httpx / requests, defining error classes, building a config
  object for a network call, threading a request_id through logs,
  implementing streaming with cancellation, parsing model output into
  Pydantic models, or reviewing any module owning an outbound connection.
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

## Client Construction

A client is a small typed object that holds (a) credentials, (b) transport
config, (c) retry/timeout policy, and (d) optional telemetry tags. Build it
once at process startup; pass it through.

```python
from typing import Annotated, Self

import httpx
from pydantic import BaseModel, ConfigDict, SecretStr


class ClientConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    base_url: str
    api_key: SecretStr
    max_retries: Annotated[int, "exponential backoff, bounded"] = 3
    timeout: httpx.Timeout = httpx.Timeout(
        60.0,        # total fallback
        connect=5.0,
        read=30.0,
        write=30.0,
        pool=5.0,    # wait for a free connection in the pool
    )
    user_agent: str = "my-service/1.0"

    @classmethod
    def from_env(cls: type[Self]) -> Self:
        from os import environ
        return cls.model_validate(
            {
                "base_url": environ["MY_SERVICE_BASE_URL"],
                "api_key": environ["MY_SERVICE_API_KEY"],
            },
        )


class ServiceClient:
    def __init__(self, config: ClientConfig) -> None:
        self._config = config
        self._http = httpx.AsyncClient(
            base_url=config.base_url,
            headers={
                "User-Agent": config.user_agent,
                "Authorization": (
                    f"Bearer {config.api_key.get_secret_value()}"
                ),
            },
            timeout=config.timeout,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self._http.aclose()
```

Notes:

- The config object is a frozen Pydantic model (see `python:pydantic` §
  *BaseModel Boundaries*). Mutating retry policy mid-process is rejected.
- `from_env` is a typed factory; the global is `ClientConfig.from_env()`
  *invoked once at startup*, not the client itself.
- `User-Agent` identifies the project so the upstream service can attribute
  traffic — matches Stripe's `appInfo` and OpenAI's `_strict_response_validation`
  conventions.

## Per-Request Overrides

Retry count, timeout, and headers are configured globally but **must** be
overridable per call. Pick one of two shapes consistently:

```python
# Fluent: a typed wrapper that returns a copy with overrides
response = await client.with_options(max_retries=0, timeout=5.0).create(...)

# Trailing options dict (Stripe-style, for stdlib SDKs)
response = await client.create(
    payload,
    options={"idempotency_key": "evt_2026_05_15_abc", "max_retries": 0},
)
```

Choose `with_options()` when the SDK is async-first and the override must
flow through `__aenter__`. Choose the options-dict when wrapping a sync SDK
or when the override is request-scoped. **Do not mix both forms in one
client.**

## Timeout Granularity

Single-number timeouts hide where time was actually spent. Always use the
structured form:

| Knob      | Triggers when                                 | Typical |
| --------- | --------------------------------------------- | ------- |
| `connect` | TCP / TLS handshake exceeds budget            | 3–5 s   |
| `read`    | Server stops sending bytes                    | 10–60 s |
| `write`   | Local socket buffer is full and not draining  | 10–30 s |
| `pool`    | All connection-pool slots are busy            | 2–5 s   |

```python
import httpx

timeout = httpx.Timeout(60.0, connect=5.0, read=30.0, write=30.0, pool=5.0)

async with httpx.AsyncClient(timeout=timeout) as client:
    response = await client.get("https://api.example.com/v1/items")
```

A `pool` timeout is the one most often forgotten and the one most often
masquerading as a "slow server": the request is queued client-side waiting
for a connection slot.

## Retry Policy

Retries are bounded, exponential, jittered, and classified. The decision of
*whether* to retry is independent of the decision of *how* to retry.

```python
import asyncio
import random
from collections.abc import Awaitable, Callable

import httpx


_RETRYABLE_STATUSES = frozenset({408, 409, 429, 500, 502, 503, 504})


def is_retryable(error: BaseException) -> bool:
    if isinstance(error, (httpx.ConnectError, httpx.ReadTimeout)):
        return True
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code in _RETRYABLE_STATUSES
    return False


async def with_backoff[T](
    call: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 30.0,
) -> T:
    for attempt in range(max_attempts):
        try:
            return await call()
        except Exception as error:
            if attempt == max_attempts - 1 or not is_retryable(error):
                raise
            # AWS "full jitter": uniform in [0, min(cap, base * 2**attempt)].
            ceiling = min(max_delay, base_delay * (2 ** attempt))
            await asyncio.sleep(random.uniform(0.0, ceiling))
    raise RuntimeError("unreachable")
```

Rules:

- **Cap attempts.** `max_retries=3` total, not unbounded. SDK defaults of 2
  (OpenAI, Stripe Node) or 3 (Anthropic) are the right neighbourhood.
- **Backoff is exponential with jitter.** Constant or linear backoff
  thunders herds — see `design-patterns:system` § *Retry*.
- **Classify retryable errors.** Network errors and `408 / 409 / 429 / 5xx`
  are retryable; `400 / 401 / 403 / 404 / 422` are not. Retrying a `400`
  hides a bug in the caller.
- **Retried writes need idempotency keys.** Either auto-generate a stable
  key per logical request (Stripe-style) or require the caller to pass one
  for any mutation. POST without an idempotency key + retries enabled =
  double charges.

```python
# Idempotency-key shape — generated once per logical operation, not per attempt
import uuid

idempotency_key = str(uuid.uuid4())  # stable across the retry loop

response = await stripe_client.charges.create(
    amount=2000,
    currency="usd",
    options={"idempotency_key": idempotency_key},
)
```

## Error Hierarchy

One base class, status-class subclasses, structured attributes. Every error
that crosses the API surface inherits from a single project-level base so
callers can `except OneBase` without listing twelve variants.

```python
from collections.abc import Mapping


class ServiceError(Exception):
    """Base for all errors from this service client."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        request_id: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.request_id = request_id
        self.headers = headers or {}


class APIConnectionError(ServiceError): ...
class AuthenticationError(ServiceError): ...   # 401
class PermissionDeniedError(ServiceError): ... # 403
class NotFoundError(ServiceError): ...          # 404
class UnprocessableEntityError(ServiceError): ... # 422
class RateLimitError(ServiceError): ...         # 429
class InternalServerError(ServiceError): ...   # 5xx
```

Required properties on every error:

- `status` — HTTP status code (or `None` for network/transport failures).
- `request_id` — value from the upstream `x-request-id` / `request-id`
  header. Without it, a customer-reported failure cannot be traced.
- `headers` — full response headers; rate-limit consumers need
  `retry-after` and `x-ratelimit-*`.
- `message` — human-readable summary suitable for logging. Not the place
  for stack traces.

Mapping HTTP status to a subclass is library-policy, but the **shape** is
non-negotiable: a `RateLimitError` is always a subclass of the service base,
not a bare exception with a `.code = 429` attribute.

## Structured Outputs

When an upstream API supports typed output (OpenAI's `.parse(response_format=)`,
Anthropic's `.parse(output_format=)`), use it. Do not hand-roll
`json.loads(...) → BaseModel.model_validate(...)` if the SDK can validate
inline.

```python
from typing import Annotated
from pydantic import BaseModel, Field
from openai import OpenAI


class Step(BaseModel):
    explanation: str
    output: str


class MathResponse(BaseModel):
    steps: list[Step]
    final_answer: str


client = OpenAI()
completion = client.chat.completions.parse(
    model="gpt-4o-2024-08-06",
    messages=[
        {"role": "system", "content": "You are a math tutor."},
        {"role": "user", "content": "Solve 8x + 31 = 2"},
    ],
    response_format=MathResponse,
)

message = completion.choices[0].message
if message.parsed is not None:
    for step in message.parsed.steps:
        ...
elif message.refusal is not None:
    raise ServiceError(f"Model refused: {message.refusal}")
else:
    raise ServiceError("Empty parse result")
```

Rules:

- **Always handle the refusal branch.** `message.parsed is None` does not
  imply a transport error — the model may have refused. Treat refusal as a
  domain-level signal, not a retry trigger.
- **Typed function tools, not raw JSON Schema.** When the SDK ships a typed
  tool helper (OpenAI's `openai.pydantic_function_tool(Model)`), use it.
  Hand-rolling `input_schema` dictionaries duplicates type information that
  Pydantic already owns.
- **Schema lives in `python:pydantic`-shape models.** Reuse the same
  `BaseModel` for request validation and structured-output parsing where
  possible.

## Streaming

LLM streams, server-sent events, and chunked downloads all share the same
shape: `async with` opens the stream, an async iterator yields typed events,
an accumulator method returns the final assembled value.

```python
from openai import AsyncOpenAI


async def stream_explanation(client: AsyncOpenAI, prompt: str) -> str:
    parts: list[str] = []
    async with client.chat.completions.stream(
        model="gpt-4o-2024-08-06",
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        async for event in stream:
            if event.type == "content.delta":
                parts.append(event.content)
            elif event.type == "error":
                # Stream error shape varies by SDK; surface message + status.
                raise ServiceError(f"stream error: {event.error}")
    return "".join(parts)
```

Rules:

- **Always inside `async with`.** Holding the stream object past the block
  leaks the underlying HTTP connection.
- **Iterate typed events, not raw bytes.** `event.type == "..."` is the
  contract; `event.delta` is the payload. Bare `for chunk in raw_response`
  loses the event taxonomy.
- **Accumulate explicitly.** If you need the final message, call the
  SDK-provided accumulator (`await stream.get_final_message()`,
  `stream.finalMessage()`) — don't reassemble fragments manually unless
  you have a streaming-specific reason.
- **Cancel by breaking.** Exiting the `async for` early closes the stream
  cleanly. Don't try to "drain" a stream you're done with.
- **Stream backpressure is real.** If the consumer is slower than the
  producer, the stream stalls. See `python:performance` § *Bounded async*
  for queue-based decoupling.

## Pagination

Cursor pagination is the default. Return an async iterator from the client
method; let the caller stop when they have enough.

```python
from collections.abc import AsyncIterator


async def list_items(
    client: ServiceClient,
    *,
    page_size: int = 100,
) -> AsyncIterator[Item]:
    cursor: str | None = None
    while True:
        response = await client.items.list(cursor=cursor, limit=page_size)
        for item in response.data:
            yield item
        if not response.has_more:
            return
        cursor = response.next_cursor
```

Rules:

- **Auto-paging by default; never materialize the full list inside the
  client.** A caller that wants all items can `[item async for item in ...]`.
- **Cursor over offset.** Offset pagination drifts when the underlying
  collection changes mid-iteration.
- **`limit` is a hint, not a hard cap.** The server may return fewer items;
  trust `has_more` and `next_cursor`.

## Observability

A client that fails silently is worse than one that fails loudly. Three
guarantees:

1. **Every request_id propagates to logs.** Either via `logging`
   `extra={"request_id": ...}` or via structured fields in your tracer.
2. **Errors are logged once, at the boundary that decides whether to
   continue.** Avoid `try/except → log → re-raise` chains: the outermost
   handler logs, inner code lets the exception fly.
3. **Secrets are redacted.** `SecretStr` is the type-system enforcement;
   structured logging configuration is the runtime enforcement. Never log
   `request.headers` raw — log the keys, redact the values.

`httpx` event hooks are the right seam for request/response logging:

```python
import logging

logger = logging.getLogger("my_service.client")


async def log_request(request: httpx.Request) -> None:
    logger.info(
        "request.send",
        extra={"method": request.method, "url": str(request.url)},
    )


async def log_response(response: httpx.Response) -> None:
    logger.info(
        "request.recv",
        extra={
            "status": response.status_code,
            "request_id": response.headers.get("x-request-id"),
            "elapsed_ms": int(response.elapsed.total_seconds() * 1000),
        },
    )


client = httpx.AsyncClient(
    event_hooks={"request": [log_request], "response": [log_response]},
)
```

For sync clients, hooks are sync functions; for `AsyncClient`, they **must
be async**. Mixing the two raises at request time, not at construction
time.

## Settings & Config

Configuration is a `BaseSettings` (see `python:pydantic` § *Settings*).
Loader is called once at startup, never at import time.

```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class OpenAISettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OPENAI_",
        env_file=".env",
        extra="forbid",
        validate_default=True,
    )

    api_key: SecretStr
    base_url: str = "https://api.openai.com/v1"
    max_retries: int = 3
```

Anti-pattern (avoid):

```python
# at module top — freezes env at import time, breaks tests
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
```

Correct shape: construct the client inside a `lifespan` / startup hook,
inject it as a dependency.

## Tool Use (LLM-specific)

When defining a tool for a model to call, use the SDK's typed-tool helper —
do not hand-roll `input_schema` dictionaries.

```python
from enum import StrEnum
import openai
from pydantic import BaseModel


class Table(StrEnum):
    orders = "orders"
    customers = "customers"


class Condition(BaseModel):
    column: str
    operator: str
    value: str | int


class Query(BaseModel):
    table_name: Table
    conditions: list[Condition]


completion = client.chat.completions.parse(
    model="gpt-4o-2024-08-06",
    messages=[...],
    tools=[openai.pydantic_function_tool(Query)],
)

tool_call = (completion.choices[0].message.tool_calls or [])[0]
# tool_call.function.parsed_arguments is typed as Query
```

For Anthropic, the typed-tool helper currently lives in the TypeScript SDK
only (`betaZodTool`); in Python, declare JSON Schema explicitly but pair
it with a `TypeAdapter` (see `python:pydantic` § *TypeAdapter*) for runtime
validation of the model's chosen arguments.

## Anti-Patterns

- **Module-globals that lazily create clients.** Hides the lifecycle, makes
  tests share state, and prevents typed dependency injection. Construct
  explicitly.
- **Single-number timeouts.** `timeout=30` hides which budget tripped.
  Always structured.
- **Retry-everything loops.** Retrying a `400` is wrong; retrying without
  jitter is a thundering herd; retrying a non-idempotent write without a
  key double-counts.
- **Catching the SDK's base exception, then re-raising `RuntimeError`.**
  Loses `status`, `request_id`, `headers`. Wrap into the project's error
  hierarchy or let the SDK error propagate.
- **`stream=True` without `async with`.** Leaks connections. Always inside
  a context manager.
- **Hand-rolling JSON Schema for tool calls when the SDK ships a typed
  helper.** Duplicates type information that already lives in your Pydantic
  models.
- **Logging raw headers.** `Authorization: Bearer ...` is a secret. Log the
  header names, redact the values.
- **Constructing the client at import time.** Breaks env-var overrides in
  tests, freezes config before the process is ready.
- **Materializing paginated responses inside the SDK wrapper.** Caller
  should decide whether to consume one page or all of them.
- **Catching `ValidationError` deep inside the client.** Convert at the
  boundary into a project error type; see `python:pydantic` *Validators*.

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
