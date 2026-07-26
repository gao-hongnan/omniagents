# Typed fixtures, factories, and test data

Scope: fixture discipline (scope, autouse, chains), the factory-fixture
pattern with a worked retry-policy example, and test-data builders. The
double vocabulary the example leans on lives in
`references/doubles-and-boundaries.md`.

## Typed fixtures and factories

Fixtures are typed like any API. Factory fixtures — a fixture returning a
typed callable — replace fixture explosion when tests need variations. The
canonical shape, including boundary fake and teardown:

```python
from collections.abc import Iterator
from typing import Protocol

import httpx
import pytest

from acme.users import fetch_user


class MakeClient(Protocol):
    def __call__(self, *outcomes: httpx.Response | Exception) -> httpx.Client: ...


@pytest.fixture
def sent_requests() -> list[httpx.Request]:
    return []


@pytest.fixture
def make_client(sent_requests: list[httpx.Request]) -> Iterator[MakeClient]:
    created: list[httpx.Client] = []

    def factory(*outcomes: httpx.Response | Exception) -> httpx.Client:
        remaining = list(outcomes)

        def handler(request: httpx.Request) -> httpx.Response:
            sent_requests.append(request)
            outcome = remaining.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        client = httpx.Client(
            transport=httpx.MockTransport(handler), base_url="https://api.test"
        )
        created.append(client)
        return client

    yield factory
    for client in created:
        client.close()


@pytest.mark.parametrize(
    ("failure", "expected_error", "expected_attempts"),
    [
        pytest.param(
            httpx.Response(404), httpx.HTTPStatusError, 1, id="client-error-final"
        ),
        pytest.param(
            httpx.Response(503), httpx.HTTPStatusError, 3, id="server-error-retried"
        ),
        pytest.param(
            httpx.ConnectTimeout("connect"), httpx.ConnectTimeout, 3, id="connect-timeout"
        ),
        pytest.param(
            httpx.ReadTimeout("read"), httpx.ReadTimeout, 3, id="read-timeout"
        ),
        pytest.param(
            httpx.ConnectError("name resolution"), httpx.ConnectError, 3, id="dns-failure"
        ),
        pytest.param(
            httpx.RemoteProtocolError("server closed mid-response"),
            httpx.RemoteProtocolError,
            1,
            id="protocol-error-final",
        ),
    ],
)
def test_fetch_user_retry_policy_per_failure_class(
    make_client: MakeClient,
    sent_requests: list[httpx.Request],
    failure: httpx.Response | Exception,
    expected_error: type[httpx.HTTPError],
    expected_attempts: int,
) -> None:
    client = make_client(*[failure] * expected_attempts)

    with pytest.raises(expected_error):
        fetch_user(client, "u-1")

    assert len(sent_requests) == expected_attempts
    assert {request.url.path for request in sent_requests} == {"/users/u-1"}
```

The fake *records*; the test *asserts on the recording in its body*. An
`assert` inside a handler or fake raises mid-call from inside the subject —
put invariants in the test where the failure reads as a failed expectation.

One table, one axis: **which failure classes are retried and which are
final**. A single happy-path test plus one arbitrary error is not a tested
boundary — the `protocol-error-final` row is the one that pays for the table,
because retrying a connection the server closed mid-response is how a
non-idempotent POST gets submitted twice. Where the error message is itself
part of the contract, keep `match=` on the individual case.

Fixture discipline:

- **Smallest scope that works.** Default `function`; widen only for
  expensive immutable resources, and say why. Session-scoped mutable state
  is order dependence on a timer.
- **`autouse=True` requires a stated justification** in the fixture
  docstring, and is reserved for cross-cutting guards (a fixture that fails
  the test on real network access, a log-level pin). Convenience autouse is
  invisible coupling: every test in scope inherits behavior it never asked
  for.
- **Fixture chains stay shallow.** More than two hops of fixture-depends-on-
  fixture and the arrange step has become unreadable; flatten into an
  explicit factory call in the test body.
- **Prefer a plain helper over a fixture when there is no teardown and no
  parametrization** — fixtures are for lifecycle, not for namespacing.

## Test data

- **Build test objects through typed builders, not literals repeated across
  the suite.** A builder — `make_order(**overrides)` returning a fully valid
  object, overriding only the field under test — localizes the blast radius
  when a required field is added: one builder changes, not forty literals.
  This is the Test Data Builder / Object Mother pattern; builders live in
  `tests/factories.py` and are typed like production code.
- **For pydantic models, generate with polyfactory.** A `ModelFactory[Order]`
  yields schema-valid instances and takes explicit overrides for the fields a
  test pins. Hand-built model literals rot the day a validator tightens —
  mirror this plugin's `pydantic` skill in the factories.
- **The value under test is never randomized.** Factories may randomize the
  fields a test ignores (which surfaces hidden coupling), but the asserted
  field is set explicitly. An expected value read back from a factory's random
  output asserts nothing.

## Sources

- [xUnit Test Patterns (Gerard Meszaros)](http://xunitpatterns.com/)
- [Software Engineering at Google, ch. 12 "Unit Testing"](https://abseil.io/resources/swe-book/html/ch12.html)
- [Avoid Nesting when you're Testing (Kent C. Dodds)](https://kentcdodds.com/blog/avoid-nesting-when-youre-testing)
- [pytest](https://docs.pytest.org/en/stable/)
- [polyfactory](https://polyfactory.litestar.dev/)

Freshness: pytest 9.1.1 verified against PyPI and current docs on 2026-07-26.
