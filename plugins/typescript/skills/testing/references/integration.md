# Integration tests

Rules for the integration layer: real infrastructure via testcontainers,
exercising the real HTTP stack, and cross-team contracts. The layering
decision — what belongs here versus unit or component — lives in
`references/unit.md`; the doubles vocabulary in
`references/doubles-and-boundaries.md`.

- **Real infrastructure via testcontainers in a dedicated Vitest project**:
  the container starts once in `globalSetup`, migrations apply once, and
  per-test isolation comes from transactions/truncation. Under parallel
  workers, resources are per-worker (derive schema/database names from
  `VITEST_POOL_ID`); two workers truncating one table is a heisenbug
  factory.
- **Exercise the real HTTP layer** — inject requests into the framework
  (`app.inject`, `fetch` against an ephemeral-port listener), so routing,
  middleware, serialization, and error mapping run for real. The schema
  comes from migrations, not from an ORM `sync()` production never runs.
- **External vendors in integration tests** hit the official emulator or a
  recorded contract — never a hand-maintained stub that drifts from the
  real API.
- **Contract-test cross-team boundaries.** A shared example is not a contract.
  Consumer-driven contract tests (Pact) pin the request/response shape both
  services agree on and fail the provider's CI on drift; for an OpenAPI
  surface, schema-based fuzzing generates cases from the spec. Both catch the
  integration break that a `vi.mock` of your own client structurally cannot.

## Sources

- [The Practical Test Pyramid (Ham Vocke)](https://martinfowler.com/articles/practical-test-pyramid.html)
- [Just Say No to More End-to-End Tests (Google Testing Blog)](https://testing.googleblog.com/2015/04/just-say-no-to-more-end-to-end-tests.html)
- [Software Engineering at Google, ch. 14 "Larger Testing"](https://abseil.io/resources/swe-book/html/ch14.html)
- [testcontainers-node: containers](https://node.testcontainers.org/features/containers/)
- [testcontainers-node: wait strategies](https://node.testcontainers.org/features/wait-strategies/)

Freshness: verified 2026-07-26 — testcontainers 12.0.4 (per-module
`@testcontainers/*` packages, `.withReuse()`), Vitest 4.1.10 (`projects` +
`globalSetup`).
