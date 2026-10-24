# library-patterns — Errors And Outputs

Detail sections of `omniagents-python:library-patterns`; the hub's Non-negotiables govern. Load on demand.

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
