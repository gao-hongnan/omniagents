# library-patterns — Streaming And Pagination

Detail sections of `omniagents-python:library-patterns`; the hub's Non-negotiables govern. Load on demand.

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
