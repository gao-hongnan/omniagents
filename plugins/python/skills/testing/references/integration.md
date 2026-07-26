# Integration tests

Scope: the G2 integration tier — real infrastructure via testcontainers,
explicit network opt-in, migrations, per-worker isolation under xdist, and
cross-team contract tests. Unit-vs-integration routing lives in
`references/unit.md`; the doubles vocabulary in
`references/doubles-and-boundaries.md`.

- **Real infrastructure via testcontainers; isolation via transactions.**
  One container per session (the expensive part), migrations applied once,
  and per-test isolation by rollback — or truncation where the subject
  manages its own transactions:

```python
from collections.abc import Iterator

import pytest
from sqlalchemy import Connection, Engine, create_engine
from testcontainers.postgres import PostgresContainer

from acme.migrations import run_migrations  # project's alembic entrypoint


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    with PostgresContainer("postgres:17") as postgres:
        engine = create_engine(postgres.get_connection_url())
        run_migrations(engine)
        yield engine
        engine.dispose()


@pytest.fixture
def connection(engine: Engine) -> Iterator[Connection]:
    with engine.connect() as connection:
        transaction = connection.begin()
        yield connection
        transaction.rollback()
```

- **The integration tier opts back into the network explicitly.** With
  `--disable-socket` in the baseline `addopts`, an integration test cannot
  reach even its own container until it says so — `@pytest.mark.enable_socket`,
  or `@pytest.mark.allow_hosts([...])` for a narrower grant. The friction is
  the feature: touching the network becomes a reviewable declaration in the
  diff instead of a silent default.
- **The schema comes from migrations, not `metadata.create_all()`** —
  otherwise the suite validates a schema production never runs.
- **Under xdist, resources are per-worker.** Derive names from the worker id
  (one schema or database per worker); two workers truncating one table is
  a heisenbug factory.
- **Outbound HTTP:** unit tests fake the transport (`MockTransport` when you
  construct the client; respx when you need request-matching assertions on
  code that builds its own). Integration tests hit the real dependency or
  its official emulator — never a hand-maintained stub drifting from the
  real API.
- **Migration tests are integration tests**: apply head, assert round-trip
  of representative rows, and test the downgrade if you claim to support it.
- **Contract-test cross-team boundaries.** Where a service consumes or
  provides an API another team owns, a shared example is not a contract.
  Consumer-driven contract tests (Pact) pin the request/response shape both
  sides agree on and fail the provider's CI on drift; for an OpenAPI surface,
  schemathesis generates property-based cases from the spec and finds the
  inputs handwritten cases missed. Both catch the integration break that unit
  mocks structurally cannot.

## Sources

- [The Practical Test Pyramid (Ham Vocke)](https://martinfowler.com/articles/practical-test-pyramid.html)
- [Software Engineering at Google, ch. 14 "Larger Testing"](https://abseil.io/resources/swe-book/html/ch14.html)
- [Just Say No to More End-to-End Tests (Google Testing Blog)](https://testing.googleblog.com/2015/04/just-say-no-to-more-end-to-end-tests.html)
- [When to mock (Vladimir Khorikov)](https://enterprisecraftsmanship.com/posts/when-to-mock/)
- [testcontainers-python](https://testcontainers-python.readthedocs.io/)
- [respx](https://lundberg.github.io/respx/)
- [schemathesis](https://schemathesis.readthedocs.io/)
- [Pact](https://docs.pact.io/)

Freshness: verified against PyPI and current docs on 2026-07-26 —
testcontainers 4.15.0 (context-manager lifecycle is canonical; database
drivers are no longer bundled, declare your own), schemathesis 4.24.3 (new
examples must use the v4 namespaced loaders), pact-python 3.4.0 (new examples
must target the 3.x FFI API), respx 0.23.1, pytest-xdist 3.8.0. Checked and
rejected the same day: LocalStack's Community edition stopped receiving
regular updates in March 2026 and the unified image now requires an auth
token — prefer moto for boto3-level fakes and reserve containerized
emulation for wire-level fidelity.
