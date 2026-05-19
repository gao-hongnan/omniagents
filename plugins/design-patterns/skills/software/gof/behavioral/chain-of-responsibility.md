# Chain of Responsibility

## Intent

Avoid coupling the sender of a request to its receiver by giving more than one object a chance to handle the request. Chain the receiving objects and pass the request along until one handles it.

## Use When

- Middleware pipelines: HTTP request handling, log filtering, command preprocessing.
- Permission checks where guards each may accept, reject, or defer.
- Any "try several handlers in order" workflow where the set is configuration-driven.

## Prefer A Simpler Python Shape When

Use a plain function when the sequence is fixed and never varies. Chain of Responsibility is for configurable sequences; a hard-coded one is just a function. If every handler always runs with no early termination, call the shape a Pipeline instead.

## Structure

The request walks the chain forward; the response walks back. Each layer can short-circuit by not calling `nxt(req)`.

```mermaid
sequenceDiagram
    participant C as Client
    participant A as authenticate
    participant R as rate_limit
    participant T as trace
    participant H as terminal handler
    C->>A: request
    A->>R: nxt(req)
    R->>T: nxt(req)
    T->>H: nxt(req)
    H-->>T: response
    T-->>R: response (with x-trace-elapsed)
    R-->>A: response
    A-->>C: response
    Note over A,R: a 401 from authenticate or 429 from rate_limit short-circuits; H is never reached
```

## Strict-Typed Python Sketch

A list of middlewares composed into a single handler. Do not build a linked-list-of-nodes class; Python has lists.

```python
import time
from collections.abc import Callable


type Request = dict[str, object]
type Response = dict[str, object]
type Next = Callable[[Request], Response]
type Middleware = Callable[[Request, Next], Response]


def authenticate(req: Request, nxt: Next) -> Response:
    if "token" not in req:
        return {"status": 401, "body": "missing token"}
    return nxt(req)


def rate_limit(req: Request, nxt: Next) -> Response:
    if _over_limit(req):
        return {"status": 429, "body": "slow down"}
    return nxt(req)


def trace(req: Request, nxt: Next) -> Response:
    start = time.monotonic()
    response = nxt(req)
    response["x-trace-elapsed"] = time.monotonic() - start
    return response


def compose(middlewares: list[Middleware], terminal: Next) -> Next:
    def build(index: int) -> Next:
        if index == len(middlewares):
            return terminal
        downstream = build(index + 1)
        return lambda req: middlewares[index](req, downstream)

    return build(0)


handler = compose(
    [authenticate, rate_limit, trace],
    terminal=lambda req: {"status": 200, "body": "ok"},
)
```

For the alternative-chain variant, find the first handler that can handle the request:

```python
from typing import Protocol


class CommandHandler(Protocol):
    def can_handle(self, command: str) -> bool: ...
    def handle(self, command: str) -> str: ...


def dispatch(command: str, handlers: list[CommandHandler]) -> str:
    for handler in handlers:
        if handler.can_handle(command):
            return handler.handle(command)
    raise ValueError(f"no handler for: {command}")
```

When the request crosses a trust boundary, type it with a `BaseModel` so the first middleware validates the inbound payload and every middleware downstream can trust the request shape.

```python
from collections.abc import Callable
from pydantic import BaseModel, ConfigDict, Field
from typing import Annotated, Literal


class HttpRequestModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    method: Literal["GET", "POST", "PUT", "DELETE"]
    path: Annotated[str, Field(min_length=1)]
    token: str | None = None
    body: bytes | None = None


type Next = Callable[[HttpRequestModel], Response]
type Middleware = Callable[[HttpRequestModel, Next], Response]


def authenticate(req: HttpRequestModel, nxt: Next) -> Response:
    if req.token is None:
        return {"status": 401, "body": "missing token"}
    return nxt(req)
```

## Type-Safety Notes

Typing middleware as `Callable` with a consistent next-handler signature keeps composition type-safe. Avoid making middleware generic over request type unless the pipeline genuinely carries that abstraction. A single request type per pipeline is easier to reason about than a generic `Middleware[RequestT]` threaded through five layers. If you have two pipelines for two request types, make two middleware aliases.

## Common Misuse

A chain where every handler runs unconditionally and the "chain" is a glorified `for` loop with no early termination. That is a Pipeline, not Chain of Responsibility. Name it accurately so callers know whether a handler may stop traversal.

## Real-World Examples

- `logging.Logger` propagation up the logger hierarchy: each parent may handle or defer.
- WSGI and ASGI middleware: Starlette, Django, and `BaseHTTPMiddleware` form chains over the request/response.
- `argparse` subparser chains: each subparser inspects the args and may handle the rest.

## References

- Gamma et al., *Design Patterns* (1994), pp. 223-232.
- Refactoring Guru, [Chain of Responsibility](https://refactoring.guru/design-patterns/chain-of-responsibility).
