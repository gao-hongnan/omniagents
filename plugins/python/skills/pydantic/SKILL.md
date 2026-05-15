---
name: pydantic
description: >-
  Use when writing or reviewing modern Pydantic v2 or pydantic-settings code:
  BaseModel boundaries, SettingsConfigDict, BaseSettings, nested environment
  configuration, Annotated Field constraints, validators, computed fields,
  TypeAdapter, RootModel, discriminated unions, SecretStr, serialization, or
  production validation patterns.
when_to_use: >-
  Trigger for API payload models, CLI/config models, env var settings,
  .env/secrets loading, discriminated event payloads, nested settings via
  env_nested_delimiter, strict validation, extra field policy, model_validate,
  model_dump, model_copy, field_validator, model_validator, computed_field,
  TypeAdapter, RootModel, SecretStr, and reviews where dict/Any/untyped
  config should become explicit Pydantic models.
disable-model-invocation: false
user-invocable: true
allowed-tools: []
model: inherit
paths:
  - "**/*.py"
  - "**/pyproject.toml"
  - "**/.env*"
shell: bash
---

# Pydantic Production Patterns

Use Pydantic for runtime validation at boundaries: API payloads, config,
settings, event envelopes, CLI inputs, third-party responses, and persisted
JSON. Inside trusted domain logic, prefer plain typed objects unless runtime
validation, serialization, or schema generation is part of the contract.

This skill assumes **[Pydantic v2](https://pydantic.dev/docs/validation/latest/concepts/models)**
and **[pydantic-settings v2](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)**.
If code uses v1 APIs such as `parse_obj`, `dict()`, `json()`, class `Config`,
or `@validator`, migrate to v2 forms.

## Baseline Rules

- Model external data as explicit
  [`BaseModel`](https://pydantic.dev/docs/validation/latest/concepts/models) /
  [`BaseSettings`](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
  classes, not `dict[str, Any]`.
- Use [`Annotated[T, Field(...)]`](https://pydantic.dev/docs/validation/latest/concepts/fields)
  for constraints and metadata.
- Use [`model_validate()`](https://pydantic.dev/docs/validation/latest/concepts/models)
  for untrusted input and
  [`model_dump()` / `model_dump_json()`](https://pydantic.dev/docs/validation/latest/api/pydantic/base_model)
  for serialization.
- Use [`model_copy(update=...)`](https://pydantic.dev/docs/validation/latest/concepts/models)
  for immutable update flows.
- When writing classmethod factories or validators that mention `cls`, type it
  as `cls: type[Self]`. Do not fall back to `cls: type[BaseModel]` or the
  concrete base class when subclass-preserving returns matter.
- Set [`extra="forbid"`](https://pydantic.dev/docs/validation/latest/api/pydantic/config)
  for closed inbound schemas. Use `extra="allow"` only when unknown keys are
  part of the product contract.
- Use [`strict=True`](https://pydantic.dev/docs/validation/latest/api/pydantic/config)
  for security-sensitive and configuration models where coercion would hide
  deployment mistakes.
- Use `frozen=True` for value objects and settings snapshots that should not
  mutate after validation.
- Keep [`field_validator`](https://pydantic.dev/docs/validation/latest/api/pydantic/functional_validators)
  and [`model_validator`](https://pydantic.dev/docs/validation/latest/concepts/validators)
  methods pure and deterministic. Do not perform network, database,
  filesystem, or environment reads inside validators.
- Treat `ValidationError` as a boundary error. Convert it into project error
  types at API/CLI/service edges; do not let random internals handle it.

## BaseModel Boundaries

Use closed, frozen models when an inbound payload has a known schema and should
not be mutated after validation.

```python
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field


class CreateUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    email: Annotated[str, Field(min_length=3, max_length=320)]
    display_name: Annotated[str, Field(min_length=1, max_length=80)]
    tags: Annotated[list[str], Field(default_factory=list, max_length=20)]

    @classmethod
    def from_payload(cls: type[Self], raw: object) -> Self:
        return cls.model_validate(raw)


def parse_request(raw: object) -> CreateUserRequest:
    return CreateUserRequest.from_payload(raw)
```

## Self-Typed Classmethod Factories

Use `cls: type[Self]` when a factory returns `cls`. This preserves subclass
return types and keeps Pydantic factory helpers aligned with
[`typing.Self`](https://docs.python.org/3/library/typing.html#typing.Self).

```python
from typing import Self

from pydantic import BaseModel, ConfigDict


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    @classmethod
    def from_raw(cls: type[Self], raw: object) -> Self:
        return cls.model_validate(raw)


class UserIdentity(FrozenModel):
    user_id: str
    email: str
```

## Serialization Policy

Choose serialization shape explicitly. Prefer `mode="json"` for API output
and `exclude_none=True` when absent fields should not appear on the wire.

```python
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict


class UserView(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: str
    created_at: datetime
    nickname: str | None = None


def to_response(view: UserView) -> dict[str, object]:
    return view.model_dump(mode="json", exclude_none=True)


view = UserView(user_id="u_123", created_at=datetime.now(timezone.utc))
```

## Validators

Use `field_validator` for single-field normalization or checks. Use
`model_validator` for cross-field invariants. Keep both side-effect free.

```python
from typing import Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class RetryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    attempts: int
    backoff_seconds: float
    timeout_seconds: float

    @field_validator("attempts")
    @classmethod
    def attempts_must_be_positive(cls: type[Self], value: int) -> int:
        if value < 1:
            raise ValueError("attempts must be at least 1")
        return value

    @model_validator(mode="after")
    def timeout_must_cover_backoff(self) -> Self:
        if self.timeout_seconds <= self.backoff_seconds:
            raise ValueError("timeout must be greater than backoff")
        return self
```

## Computed Fields

Use [`computed_field`](https://pydantic.dev/docs/validation/latest/concepts/fields)
for derived serialization fields. Do not store redundant derived state unless
the model needs to accept it from input.

```python
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, computed_field


class InvoiceLine(BaseModel):
    model_config = ConfigDict(frozen=True)

    quantity: int
    unit_price: Decimal

    @computed_field
    @property
    def subtotal(self) -> Decimal:
        return self.unit_price * self.quantity
```

## Discriminated Unions

Use [discriminated unions](https://pydantic.dev/docs/validation/latest/concepts/unions)
for event or webhook envelopes. Put the discriminator at the field that
receives the union so validation chooses a variant before business logic runs.

```python
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class UserCreated(BaseModel):
    type: Literal["user.created"]
    user_id: str
    email: str


class UserDeleted(BaseModel):
    type: Literal["user.deleted"]
    user_id: str
    reason: str | None = None


type UserEvent = Annotated[
    UserCreated | UserDeleted,
    Field(discriminator="type"),
]


class WebhookEnvelope(BaseModel):
    event: UserEvent


def parse_event(raw: object) -> WebhookEnvelope:
    return WebhookEnvelope.model_validate(raw)
```

## TypeAdapter

Use [`TypeAdapter`](https://pydantic.dev/docs/validation/latest/api/pydantic/type_adapter)
when validating a type that is not naturally a model: lists, mappings,
unions, literals, or aliases.

```python
from typing import Annotated

from pydantic import Field, TypeAdapter


type NonEmptyTags = Annotated[list[str], Field(min_length=1, max_length=20)]

tag_adapter = TypeAdapter(NonEmptyTags)


def parse_tags(raw: object) -> list[str]:
    return tag_adapter.validate_python(raw)
```

## RootModel

Use [`RootModel`](https://pydantic.dev/docs/validation/latest/concepts/models)
when the payload is itself a list, mapping, scalar, or alias. Do not wrap the
value in an artificial `items` field just to satisfy `BaseModel`.

```python
from pydantic import RootModel


class UserIds(RootModel[list[str]]):
    def contains(self, user_id: str) -> bool:
        return user_id in self.root


ids = UserIds.model_validate(["u_1", "u_2"])
```

## Settings

Use [`BaseSettings`](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
for process configuration. Keep nested settings as `BaseModel` subclasses,
use an app prefix, and use `env_nested_delimiter="__"` for structured
environment variables.

```python
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseModel):
    host: str
    port: int = 5432
    name: str
    password: SecretStr


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_nested_delimiter="__",
        env_file=".env",
        secrets_dir="/run/secrets",
        env_ignore_empty=True,
        validate_default=True,
        extra="forbid",
    )

    environment: str = "local"
    debug: bool = False
    database: DatabaseSettings
    allowed_origins: list[str] = Field(default_factory=list)


def load_settings() -> AppSettings:
    return AppSettings()
```

With that model, these variables map to nested fields:

```bash
APP_DATABASE__HOST=db.internal
APP_DATABASE__PORT=5432
APP_DATABASE__NAME=app
APP_DATABASE__PASSWORD=secret
```

## Settings Testing

Do not instantiate settings at import time in modules under test. Provide a
loader function and test it with isolated environment changes.

```python
from collections.abc import Mapping


def load_test_settings(env: Mapping[str, str]) -> AppSettings:
    return AppSettings.model_validate(
        {
            "environment": env.get("APP_ENVIRONMENT", "test"),
            "database": {
                "host": env["APP_DATABASE__HOST"],
                "name": env["APP_DATABASE__NAME"],
                "password": env["APP_DATABASE__PASSWORD"],
            },
        },
    )
```

## Secrets

Use [`SecretStr` / `SecretBytes`](https://pydantic.dev/docs/validation/latest/api/types/)
for values that must not appear in reprs or logs. Convert with
`get_secret_value()` only at the call site that needs the raw secret.

```python
from pydantic import BaseModel, SecretStr


class ApiCredentials(BaseModel):
    token: SecretStr


def auth_header(credentials: ApiCredentials) -> dict[str, str]:
    token = credentials.token.get_secret_value()
    return {"Authorization": f"Bearer {token}"}
```

## Anti-Patterns

- **Global settings instances at import time.** They freeze environment state
  before tests or process bootstrap can configure it.
- **Validators doing I/O.** Validate shape and invariants only; perform I/O in
  services after validation.
- **`dict[str, Any]` as a boundary.** Replace with `BaseModel`, `TypedDict`,
  or `TypeAdapter` depending on whether runtime validation is needed.
- **Silent coercion for config.** Prefer strict settings when deployment
  mistakes should fail fast.
- **Nested settings that are plain classes.** Sub-settings should inherit from
  `BaseModel` so nested env parsing and validation are predictable.
- **Mixing v1 and v2 APIs.** Do not introduce `parse_obj`, `.dict()`, `.json()`,
  class `Config`, `@validator`, or `@root_validator` in new code.
- **Catching `ValidationError` everywhere.** Catch it at the boundary and
  convert once into the project's error model.
- **Serializing secrets accidentally.** Do not call `get_secret_value()` until
  the API client or credential provider boundary.

## References

- [Pydantic models](https://pydantic.dev/docs/validation/latest/concepts/models):
  `BaseModel`, `model_validate`, `model_copy`, generic models, `RootModel`.
- [Pydantic configuration](https://pydantic.dev/docs/validation/latest/api/pydantic/config):
  `ConfigDict`, `extra`, `strict`, `frozen`, default validation behavior.
- [Pydantic fields](https://pydantic.dev/docs/validation/latest/concepts/fields):
  `Field`, constraints, aliases, computed fields, discriminators.
- [Pydantic validators](https://pydantic.dev/docs/validation/latest/concepts/validators)
  and [functional validator API](https://pydantic.dev/docs/validation/latest/api/pydantic/functional_validators):
  `field_validator`, `model_validator`, validation modes, `ValidationInfo`.
- [Pydantic unions](https://pydantic.dev/docs/validation/latest/concepts/unions):
  discriminated unions, callable discriminators, tagged variants.
- [Pydantic TypeAdapter](https://pydantic.dev/docs/validation/latest/api/pydantic/type_adapter):
  validation and serialization for non-model types.
- [Pydantic serialization](https://pydantic.dev/docs/validation/latest/api/pydantic/base_model):
  `model_dump`, JSON mode, inclusion/exclusion behavior.
- [Pydantic standard and secret types](https://pydantic.dev/docs/validation/latest/api/types):
  `SecretStr`, `SecretBytes`, DSNs, constrained standard types.
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/):
  `BaseSettings`, `SettingsConfigDict`, env prefixes, nested env delimiters,
  dotenv files, secrets directories, and CLI/settings sources.

## Freshness

This skill is project policy, not a complete upstream reference. When applying
it to unfamiliar APIs, version-sensitive behavior, tool/checker disagreement,
or anything that may have changed since the skill was written, verify current
behavior against primary docs. Prefer Context7 MCP when available. If it is
unavailable, use web search restricted to official sources.

Primary sources:

- [Pydantic v2 docs](https://pydantic.dev/docs/validation/latest/)
- [pydantic-settings docs](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
