# Determinism and hermeticity

Scope: the mechanisms that make G1 determinism real — clock, sleep, and
randomness control; hermeticity from the network down to ambient state; and
the async rules that keep event-loop tests from leaking. The resilience
patterns in `references/resilience.md` build on these controls.

## Time, sleep, and randomness

- **Wall clock:** inject a `now: Callable[[], datetime]` or clock protocol
  at design time. For code you cannot reshape, `time_machine.travel(...,
  tick=False)` freezes deterministically. Asserting "createdAt is within 5
  seconds of now" is a tolerance hiding a missing seam. A frozen wall clock
  does not fast-forward the event loop: asyncio schedules on the loop's
  monotonic clock, so `await asyncio.sleep(...)` still takes real time under
  `time_machine` (verified empirically, 2026-07-26) — async delays are the
  recording sleeper's job, not the freezer's.
- **Sleeps:** never real in unit tests. For backoff logic, substitute a
  recording sleeper and assert the schedule exactly —
  `assert sleeps == pytest.approx([1.5, 2.5, 4.5])` kills fixed-delay and
  dropped-jitter mutants that "it eventually retried" survives.
- **Polling:** sleep-then-assert is the canonical flake. Wait on the
  condition with a deadline (`asyncio.timeout` around an `Event.wait`, or a
  poll loop bounded by `time.monotonic()` budget), then assert.
- **Randomness:** the subject takes a `random.Random`; tests pass
  `random.Random(1729)`. Seeding the global `random` module is a
  process-wide side effect — acceptable only via pytest-randomly, whose
  printed seed makes any ordering/randomness failure reproducible.

## Hermeticity and ambient state

A hermetic test reads and writes nothing outside its own scope. Ambient state
is the hidden `parametrize` axis nobody declared — it is what makes a test pass
on your laptop and fail in CI, or pass alone and fail in the suite.

- **Network: `--disable-socket` in the baseline, not a code-review habit.**
  pytest-socket blocks real connections *and* DNS resolution at the socket
  layer, so a client constructed without a transport override fails loudly
  instead of quietly reaching the internet. The integration tier opts back in
  per test (`@pytest.mark.enable_socket`) or per host
  (`@pytest.mark.allow_hosts([...])`). Without it, "unit tests touch no real
  network" holds only until the first contributor who never read the rule,
  and the breach surfaces as a flake on a sandboxed runner, a burned vendor
  rate limit, or a live credential on the wire. Known edge: `allow_hosts`
  resolves names once at session start, so a client that re-resolves DNS per
  request can miss the allow-list — that is a tooling quirk, not an app bug.
- **Filesystem: `tmp_path` / `tmp_path_factory`, never a real path.** Any test
  touching disk gets a per-test temp directory; writing under the repo, into
  `/tmp` by hand, or a fixture's own directory couples tests through the
  filesystem and leaks across xdist workers. Never assert against a checked-in
  path the test also writes.
- **Environment: `monkeypatch.setenv` / `delenv`, always scoped.** Tests that
  read config from the environment set exactly the vars they need and let
  `monkeypatch` restore them. A test that depends on the developer's ambient
  `os.environ` is a failure waiting for a clean runner; clear the var under
  test explicitly to prove the default path, too.
- **Working directory and `sys.path` are not test canvases.** Do not `chdir`
  into a fixture directory or mutate `sys.modules` / `sys.path`; pass paths
  explicitly. If the subject depends on cwd, that is a seam to inject, not a
  fixture to set up.
- **Module singletons and caches reset at the boundary you own.** Global
  registries, `functools.cache`d functions, connection pools, and
  module-level clients retain state between tests. Provide a reset seam
  (`cache_clear()`, a `reset()` classmethod, dependency injection) and call it
  in teardown — do not let test N observe test N-1's warm cache.
- **Assert on emitted logs, spans, and metrics as contract, not noise.** Use
  `caplog` (with an explicit level) to assert a service logged the structured
  event an on-call engineer pages on, and `capsys` for CLI output. The same
  argument binds telemetry, and binds it harder — modern services page on
  spans, not grep. Wire an `InMemorySpanExporter` through a
  `SimpleSpanProcessor` and assert the span name plus the attributes a
  dashboard or alert actually reads. In enterprise services the log line and
  the span *are* monitored interfaces; an untested one is an alert that
  silently stops firing after a refactor no test noticed. Use
  `SimpleSpanProcessor`, never the production `BatchSpanProcessor` — the
  latter exports on a timer, so assertions race the flush and you have
  reinvented sleep-then-assert.

## Async tests

- **Nothing outlives the test.** Every task created is awaited or cancelled
  before the test returns — `asyncio.TaskGroup` inside the test scopes this
  structurally. A leaked task fails some *other* test with an unrelated
  traceback, or worse, passes while its exception is swallowed at loop
  teardown.
- **Waits are condition-based with deadlines**, exactly as in the section
  above; `await asyncio.sleep(0.1)` before an assert is the async spelling
  of the same flake.
- **Test the cancellation path** of any long-lived coroutine you ship:
  cancel it, assert cleanup ran, and assert `CancelledError` propagates.
  Cancellation is the least-tested branch and the one that runs at every
  deploy.
- **Async fixtures share the sync rules** — typed, smallest scope, teardown
  after `yield` — plus one: pin the loop scope deliberately in config
  rather than relying on plugin defaults that shift between majors.

## Sources

- [Software Engineering at Google, ch. 11 "Testing Overview"](https://abseil.io/resources/swe-book/html/ch11.html)
- [Just Say No to More End-to-End Tests (Google Testing Blog)](https://testing.googleblog.com/2015/04/just-say-no-to-more-end-to-end-tests.html)
- [xUnit Test Patterns (Gerard Meszaros)](http://xunitpatterns.com/)
- [pytest-socket](https://github.com/miketheman/pytest-socket)
- [time-machine](https://github.com/adamchainz/time-machine)
- [pytest-randomly](https://github.com/pytest-dev/pytest-randomly)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/en/latest/)
- [anyio testing](https://anyio.readthedocs.io/en/stable/testing.html)
- [OpenTelemetry Python](https://opentelemetry-python.readthedocs.io/)

Freshness: verified against PyPI and current docs on 2026-07-26 —
time-machine 3.2.0 (`travel(..., tick=False)` is current API),
pytest-randomly 4.1.0, pytest-asyncio 1.4.0 (set
`asyncio_default_fixture_loop_scope` explicitly; leaving it unset is
deprecated). freezegun 1.5.5 was checked and passed over: no Python 3.14
classifier, and it patches at the Python level where time-machine also
covers C-level callers.
