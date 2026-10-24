# library-patterns — Construction And Retries

Detail sections of `omniagents-python:library-patterns`; the hub's Non-negotiables govern. Load on demand.

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
