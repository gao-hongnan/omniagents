# Python Type-Safety Canonical Examples

These examples show the accepted shape of code under `../SKILL.md`. They are
not a typing tutorial. Each block is a compact pattern to copy from when a
review asks "what should this look like here?"

Prefer examples that encode a boundary, invariant, or checker behavior. Avoid
examples that only demonstrate syntax.

## Protocol Boundary With Runtime Admission

Use this when a plugin loader receives unknown objects at runtime but internal
code should depend on structural behavior. Keep `@runtime_checkable` at the
boundary, not on every Protocol.

```python
from dataclasses import dataclass
from typing import Protocol, TypeIs, runtime_checkable


@dataclass(frozen=True)
class JobRequest:
    job_id: str
    payload: dict[str, object]


@dataclass(frozen=True)
class JobResult:
    job_id: str
    status: str


@runtime_checkable
class JobPlugin(Protocol):
    name: str

    def run(self, request: JobRequest) -> JobResult: ...


def is_job_plugin(candidate: object) -> TypeIs[JobPlugin]:
    return isinstance(candidate, JobPlugin)


def load_plugin(candidate: object) -> JobPlugin:
    if is_job_plugin(candidate):
        return candidate
    raise TypeError(f"Invalid job plugin: {candidate!r}")
```

## Generic Result With Type Defaults

Use this when the common case has an obvious type parameter but callers can
still specialize it. Do not add defaults when they hide an ambiguous API.

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Ok[ValueT]:
    value: ValueT


@dataclass(frozen=True)
class Err[ErrorT = Exception]:
    error: ErrorT


type Result[ValueT, ErrorT = Exception] = Ok[ValueT] | Err[ErrorT]


def parse_int(raw: str) -> Result[int, ValueError]:
    try:
        return Ok(int(raw))
    except ValueError as exc:
        return Err(exc)
```

## ParamSpec Decorator Preserving Signature

Use this for wrappers that return a callable with the same call signature. Do
not use `Callable[..., Any]` for package code that can be typed with
`ParamSpec`.

```python
import time
from collections.abc import Callable
from functools import wraps


def timed[**P, ReturnT](
    label: str,
) -> Callable[[Callable[P, ReturnT]], Callable[P, ReturnT]]:
    def decorate(func: Callable[P, ReturnT]) -> Callable[P, ReturnT]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> ReturnT:
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - start
                print(f"{label}.{func.__name__} took {elapsed:.4f}s")

        return wrapper

    return decorate
```

## TypeIs For Bidirectional Narrowing

Use `TypeIs` for predicates whose `False` result also carries information.
Fall back to `TypeGuard` only when the narrowed type is not a subtype of the
input type or the negative branch cannot be narrowed soundly.

```python
from dataclasses import dataclass
from typing import Literal, TypeIs, assert_never


@dataclass(frozen=True)
class Started:
    kind: Literal["started"]
    job_id: str


@dataclass(frozen=True)
class Finished:
    kind: Literal["finished"]
    job_id: str
    exit_code: int


type JobEvent = Started | Finished


def is_finished(event: JobEvent) -> TypeIs[Finished]:
    return isinstance(event, Finished)


def summarize(event: JobEvent) -> str:
    if is_finished(event):
        return f"{event.job_id} exited with {event.exit_code}"

    match event:
        case Started(job_id=job_id):
            return f"{job_id} is running"
        case _:
            assert_never(event)
```

## TypedDict Boundary With ReadOnly Keys

Use `TypedDict` for trusted dictionary-shaped data and `ReadOnly` for fields a
consumer may inspect but must not rewrite. Use Pydantic instead when runtime
validation is part of the boundary.

```python
from typing import NewType, NotRequired, ReadOnly, TypedDict, Unpack


JobId = NewType("JobId", str)


class JobPayload(TypedDict):
    job_id: ReadOnly[JobId]
    queue: ReadOnly[str]
    retries: int
    trace_id: NotRequired[str]


def enqueue(**payload: Unpack[JobPayload]) -> None:
    payload["retries"] += 1
    # payload["job_id"] = JobId("other")  # rejected: read-only key
```

## Pydantic Boundary With Annotated Metadata

Use `Annotated` when validation metadata belongs to the type. Avoid
`field: T = Field(...)` for new boundary models.

```python
from typing import Annotated

from pydantic import BaseModel, Field


class TaskRequest(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=64)]
    retries: Annotated[int, Field(ge=0, le=10)] = 0
    tags: Annotated[list[str], Field(default_factory=list, max_length=20)]
```

## Alias Versus NewType Versus LiteralString

Use `type` aliases for readability, `NewType` for nominal IDs, and
`LiteralString` for command/query fragments that must not contain untrusted
runtime strings.

```python
from typing import LiteralString, NewType


type EmailAddress = str
UserId = NewType("UserId", str)


def select_user(
    table: LiteralString,
    id_column: LiteralString,
    user_id: UserId,
) -> tuple[LiteralString, tuple[str]]:
    query = f"SELECT * FROM {table} WHERE {id_column} = ?"
    return query, (str(user_id),)
```

## Type Aliases For Recursive Data

Use the `type` statement for aliases, including generic and recursive aliases.
Do not introduce `TypeAlias` assignments in new Python 3.14+ code.

```python
from collections import OrderedDict


type Cache[KeyT, ValueT] = OrderedDict[KeyT, tuple[ValueT, float]]
type JSONValue = (
    str | int | float | bool | None | list[JSONValue] | dict[str, JSONValue]
)


def object_keys(value: JSONValue) -> list[str]:
    if isinstance(value, dict):
        return list(value)
    return []
```

## StrEnum For Shared Closed Sets

Use `Literal[...]` for a closed set used once. Promote to `StrEnum` when the
set appears in multiple signatures or needs iteration.

```python
from enum import StrEnum, auto
from typing import assert_never


class TaskStatus(StrEnum):
    PENDING = auto()
    RUNNING = auto()
    SUCCEEDED = auto()
    FAILED = auto()


def is_terminal(status: TaskStatus) -> bool:
    match status:
        case TaskStatus.PENDING | TaskStatus.RUNNING:
            return False
        case TaskStatus.SUCCEEDED | TaskStatus.FAILED:
            return True
        case _:
            assert_never(status)
```

## Override For Base-Class Contracts

Use `@override` on every method that intentionally replaces a base method.
This catches drift when the base class changes.

```python
from typing import override


class Encoder:
    def content_type(self) -> str:
        return "application/octet-stream"

    def encode(self, value: object) -> bytes:
        return repr(value).encode()


class JsonEncoder(Encoder):
    @override
    def content_type(self) -> str:
        return "application/json"

    @override
    def encode(self, value: object) -> bytes:
        import json

        return json.dumps(value).encode()
```

## Context Managers Use Generator Types

Use `Generator[YieldT]` and `AsyncGenerator[YieldT]` for contextmanager
functions. Do not annotate these as `Iterator` / `AsyncIterator`.

```python
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from os import environ


@contextmanager
def temporary_env(name: str, value: str) -> Generator[None]:
    previous = environ.get(name)
    environ[name] = value
    try:
        yield
    finally:
        if previous is None:
            environ.pop(name, None)
        else:
            environ[name] = previous


class Service:
    async def start(self) -> None: ...
    async def stop(self) -> None: ...


@asynccontextmanager
async def running(service: Service) -> AsyncGenerator[Service]:
    await service.start()
    try:
        yield service
    finally:
        await service.stop()
```

## Annotation Introspection In Python 3.14

Use `annotationlib` when runtime code reads annotations. Pick the format
explicitly so unresolved forward references behave intentionally.

```python
from annotationlib import Format, get_annotations
from collections.abc import Callable


def annotation_source(func: Callable[..., object]) -> dict[str, str]:
    annotations = get_annotations(func, format=Format.STRING)
    return {name: str(value) for name, value in annotations.items()}


def unresolved_annotations(func: Callable[..., object]) -> dict[str, object]:
    return get_annotations(func, format=Format.FORWARDREF)
```
