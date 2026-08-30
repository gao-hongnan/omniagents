# Deepening a module

When you keep bouncing between several small modules to follow one behaviour, or
a module's interface is nearly as wide as its implementation, the fix is usually
to merge them into one deeper module. Whether you _can_ depends on the
dependency sitting between them.

## Can you substitute the dependency?

- **Yes — it is in-process or locally substitutable.** Pure logic, or a
  dependency you can stand up for a test in-process (SQLite/PGLite, a temp
  filesystem, an in-memory queue). Merge the modules and test the deepened
  result against the real dependency or an in-memory fake. No port needed.
- **No — it is genuinely external.** A third-party API, or an owned service that
  runs out of process. Keep it at a boundary: define a narrow port (`Protocol`),
  inject it, and supply a test double. The port is the seam — see
  [`../../software/architectural.md`](../../software/architectural.md) for ports
  & adapters.

## Seam discipline

- **One adapter is a hypothetical seam; two make it real.** Introduce the port
  only when a second implementation exists — production plus a test fake that
  isolates a heavy dependency counts. A `Protocol` with a single implementation
  adds interface and hides nothing.
- **Keep internal seams internal.** A boundary you need _inside_ the
  implementation to exercise a sub-step does not belong on the public interface.
  Inject the collaborator privately, or assert through the public outcome — do
  not widen the module's interface for a test's convenience.

## Re-test at the new interface

- Write tests against the merged module's interface and assert observable
  outcomes.
- Do **not** port the old modules' unit tests. Tests that pinned the internal
  hand-offs between the now-deleted modules break on the refactor despite
  unchanged behaviour, and hold the old shallow shape in place.
- A behaviour worth keeping is expressible at the new interface. If it is not,
  it was implementation detail.

## Sketch — external dependency behind a real seam

```python
from collections.abc import Mapping
from typing import Protocol

import httpx


class QuoteSource(Protocol):
    def quote(self, sku: str, *, region: str) -> Money: ...


class HttpQuoteSource:
    """Production adapter: round-trip + bounded retry + timeout + parse."""

    def __init__(self, client: httpx.Client, *, timeout: float) -> None:
        self._client = client
        self._timeout = timeout

    def quote(self, sku: str, *, region: str) -> Money:
        ...  # the machinery the deep module exists to hide


class FakeQuoteSource:
    """Test adapter: the second implementation that makes the seam real."""

    def __init__(self, table: Mapping[tuple[str, str], Money]) -> None:
        self._table = table

    def quote(self, sku: str, *, region: str) -> Money:
        return self._table[sku, region]
```

`QuoteSource` is justified because two implementations exist. Had only the HTTP
adapter ever existed, the port would be speculative — inline it into the deep
module and add the seam the day a second implementation arrives.
