# Test doubles and boundary control

Scope: choosing and placing test doubles — the dummy/fake/stub/spy/mock
vocabulary, seams over patching, autospec discipline, vendor adapters, and
the remote-failure ledger every HTTP boundary owes. The determinism controls
these rules lean on (clock, sleeper, rng) live in `references/determinism.md`.

Name the double you are reaching for — the vocabulary disciplines the choice.
A **stub** returns canned answers; a **fake** is a working lightweight
implementation (in-memory repository, `MockTransport`); a **spy** records calls
for later assertion; a **mock** is a spy with built-in expectations; a **dummy**
only fills a parameter slot. Prefer fakes and stubs; reserve mocks for the thin
interaction contracts where the call *is* the behavior. Reaching for a mock
where a fake would serve is how a suite ends up asserting on traffic instead of
outcomes.

- **Design the seam before reaching for the patcher.** The subject takes its
  collaborators — client, clock, rng, sleeper — as parameters or constructor
  arguments, so tests substitute them without patching:
  `httpx.Client(transport=MockTransport(...))` swaps the wire, an injected
  `random.Random(1729)` pins jitter, an injected sleeper records backoff. If
  a test *must* patch module globals to isolate the subject, that is design
  feedback about the subject, not a testing technique to institutionalize.
- **When patching is unavoidable, use `monkeypatch` and patch where the name
  is looked up**, not where it is defined. Patching `acme.users.time.sleep`
  mutates the `time` module process-wide (with teardown, but globally while
  the test runs); patching a name the subject imported directly
  (`monkeypatch.setattr("acme.users.sleep", ...)`) is scoped to the subject.
  A mispatched target tests nothing and fails never.
- **Every `Mock` pins its interface.** `create_autospec(Adapter,
  spec_set=True)` or `Mock(spec_set=Adapter)` — a bare `Mock()` accepts any
  call, any attribute, forever, and keeps passing after the real interface
  changes. Better than a specced mock is a hand-written fake implementing
  the same `Protocol` as the real collaborator: fakes hold state, survive
  refactors, and never assert-by-accident.
- **Do not mock what you do not own.** Wrap the vendor SDK in an adapter
  that speaks your domain types; unit tests fake the adapter; one
  integration test verifies the adapter against the real service (or its
  official emulator). Mocking a vendor client's method signatures couples
  the suite to an interface you cannot stabilize.
- **Never patch the subject's own internals.** Patching a private method of
  the class under test means the test exercises the patch, not the code.
  If a step is too expensive to run, that step is a collaborator — extract
  the seam.
- **Mock at the outermost boundary you do not control, run everything you
  do.** Over-mocking one layer up (the repository instead of the driver, the
  service instead of the HTTP transport) silently exempts your own glue code
  from testing. The real-database tier this implies — testcontainers,
  migrations, marker gating — is specified in `references/integration.md`.
- **Every remote call carries a sad-path ledger.** `httpx` raises a
  hierarchy, and each branch is a policy decision the subject is making
  whether or not anyone tested it: `ConnectTimeout` / `ReadTimeout` /
  `WriteTimeout` / `PoolTimeout`; `ConnectError` / `ReadError` / `WriteError`
  / `CloseError`; `RemoteProtocolError` / `LocalProtocolError`; plus
  `ProxyError`, `TooManyRedirects`, and `HTTPStatusError` for 4xx/5xx. Every
  one of them raises straight from a `MockTransport` handler with no new
  dependency, so a boundary whose only tested failure is the one from the
  last incident is a choice. Cover at minimum the timeout, the reset
  mid-response, the 429 with `Retry-After`, and the 5xx storm.
- **Synthesized faults are not real ones, and that boundary is worth
  knowing.** `MockTransport` never opens a socket, so raising
  `RemoteProtocolError` from a handler asserts your handling of that
  exception — not the socket-read loop underneath httpx. When the real wire
  behavior is the thing under test, a WireMock container
  (`CONNECTION_RESET_BY_PEER`, `MALFORMED_RESPONSE_CHUNK`) is the integration
  answer. That is the honest ceiling of a G1 fake, not a reason to skip it.

## Sources

- [Test Double (Martin Fowler)](https://martinfowler.com/bliki/TestDouble.html)
- [xUnit Test Patterns (Gerard Meszaros)](http://xunitpatterns.com/)
- [Software Engineering at Google, ch. 13 "Test Doubles"](https://abseil.io/resources/swe-book/html/ch13.html)
- [Testing on the Toilet: Testing State vs. Testing Interactions](https://testing.googleblog.com/2013/03/testing-on-toilet-testing-state-vs.html)
- [When to mock (Vladimir Khorikov)](https://enterprisecraftsmanship.com/posts/when-to-mock/)
- [The Merits of Mocking (Kent C. Dodds)](https://kentcdodds.com/blog/the-merits-of-mocking)
- [Mock Roles, not Objects (Freeman, Pryce, Mackinnon, Walnes)](http://jmock.org/oopsla2004.pdf)
- [Working Effectively with Legacy Code (Michael Feathers) — ch. 4, the Seam Model](https://www.informit.com/articles/article.aspx?p=359417&seqNum=2)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
- [httpx transports](https://www.python-httpx.org/advanced/transports/)
- [respx](https://lundberg.github.io/respx/)

Freshness: verified against PyPI on 2026-07-26 — respx 0.23.1 (the
request-matching DSL for httpx; responses 0.26.2 remains the requests-stack
counterpart). Checked and rejected the same day: betamax (caps at Python
3.11 — vcrpy is the live record-replay option).
