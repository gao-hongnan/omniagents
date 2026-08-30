---
name: testing
description: >-
  Use when writing or reviewing Python tests: pytest suite architecture and
  gate tiers, fixtures and conftest layering, parametrize and subtests, mock /
  monkeypatch boundaries, httpx.MockTransport / respx and the remote-failure
  taxonomy, retry / circuit-breaker / idempotency assertions, flaky or
  order-dependent tests, sleep-based waits, time and randomness control,
  network hermeticity enforcement, pytest-asyncio / anyio, hypothesis
  property-based tests, testcontainers integration suites, syrupy snapshots,
  type-level tests, log and OpenTelemetry span assertions, coverage and
  mutation gates, memory and benchmark gates, LLM eval boundaries, or pytest
  configuration in pyproject.toml.
when_to_use: >-
  Trigger for test files (test_*.py, conftest.py), writing unit or
  integration tests, adding a regression test for a bugfix, test-only diffs,
  flaky tests, sleep in tests, unseeded randomness, mock or patch target
  choices, autospec, fixture scope and autouse decisions, async test hangs,
  mutation testing (mutmut), xdist parallelization, filterwarnings,
  tmp_path / env-var isolation, caplog / capsys log assertions, test data
  factories (polyfactory), Pact / schemathesis contract testing,
  assert_type / pytest-mypy-plugins,
  benchmark or performance-regression gates (pytest-benchmark, codspeed),
  memory limits and leak detection (memray), tests reaching the real network,
  deadlocks or thread-race stress, fuzzing, chaos or fault-injection requests,
  LLM / agent eval suites (deepeval), or pytest config changes.
disable-model-invocation: false
user-invocable: true
allowed-tools: []
model: inherit
paths:
  - "**/tests/**"
  - "**/test_*.py"
  - "**/conftest.py"
  - "**/pyproject.toml"
shell: bash
---

# Python Testing Rules

A test earns its place by failing when the behavior it protects breaks. Every
rule below serves that one property: a suite where each test would catch a
specific wrong implementation, and where a red run always means a real defect
— never a flake, never a stale mock, never an ordering accident. Tests are
production code. They pass the same type checkers and the same linters as
`src/`, and they are reviewed against the same bar.

This skill assumes **Python 3.14+ and pytest 9+**, familiarity with fixtures,
`parametrize`, `pytest.raises`, and `unittest.mock`, and is rules, not a
tutorial. This hub holds the tiers, the non-negotiables, and a routing table;
the detailed rules live in `references/`. Scope boundaries:

- **The test-first process** (red-green-refactor) belongs to superpowers'
  `test-driven-development` where installed; this skill governs what the
  resulting tests look like.
- **Annotation rules** come from this plugin's `typings` skill; async
  runtime primitives from `performance`.
- **The review-side counterpart** is the omniagents-reviewer testing
  protocol; a suite that follows this skill produces zero findings there.

## Gate tiers: name the gate before naming the test

Not every worthwhile check can be deterministic, and pretending otherwise is
how a suite acquires muted alarms. Three gates, distinguished by what a red
run *means*:

| Property        | G1 blocking gate                 | G2 gated job                                                | G3 scheduled canary                                          |
| --------------- | -------------------------------- | ----------------------------------------------------------- | ------------------------------------------------------------ |
| Runs on         | every commit and PR              | every PR, separate job                                      | cron, or path-gated                                          |
| Determinism     | total — same input, same verdict | total verdict, noisy measurement                            | statistical; the verdict is a distribution                   |
| A red run means | a defect, always                 | a defect, always                                            | investigate — never auto-blocks a merge                      |
| Flake policy    | zero; a flake is a bug to remove | zero on the verdict, tolerance on the number                | expected; report bands, not booleans                         |
| Budget          | seconds                          | minutes                                                     | unbounded — it is off the merge path                         |
| Members         | unit tests, type-level tests     | integration tests, memory limits, benchmarks, mutation runs | LLM evals, fuzzing, dependency-upgrade canaries, race stress |

Every gate names its tier and its pain. **A test in the wrong tier is worse
than a missing test**: a noisy check on the blocking gate gets muted within
two sprints and protects nothing afterwards, while a deterministic check
exiled to a nightly job stops being read at all. Place a new kind of test
before you write it.

The non-negotiables below bind **G1**. G2 relaxes the runtime budget and the
*measurement* only — a benchmark number varies, its pass/fail rule must not.
G3 is the only tier where red means "investigate" rather than "defect," which
is precisely why nothing in it may block a merge.

The tiers restate Google's test-size axis: G1 ≈ small tests (hermetic,
single-process), G2 ≈ medium and large tests (resource-gated), and G3 covers
nondeterministic subjects the size taxonomy never named. Size is distinct
from scope — the unit-vs-integration routing lives in `references/unit.md`
and `references/integration.md`.

## Non-negotiables

- **Tests are typed and linted like `src/`.** Every test function is
  annotated (`-> None`), every fixture carries its real return type
  (`Iterator[X]` for yield fixtures), and mypy/pyright strict includes
  `tests/`. Lint relaxations are a scoped `per-file-ignores` list
  (`S101`, `PLR2004`), never a blanket exclude of the test tree, and
  ruff's flake8-pytest-style (`PT`) rules stay on.
- **Warnings are errors.** `filterwarnings = ["error"]`. Each allowlisted
  warning names its source and its removal condition. A deprecation that can
  scroll past unread is a future breakage with a disabled alarm.
- **Strict pytest config.** `strict = true` — the pytest 9 umbrella covering
  `strict_config`, `strict_markers`, `strict_parametrization_ids`, and
  `strict_xfail`, so a separate `xfail_strict = true` is redundant. An xfail
  that unexpectedly passes is a finding, not a bonus. On pytest 8, spell the
  set out: `--strict-markers --strict-config` plus `xfail_strict = true`.
- **Deterministic by construction, and enforced.** G1 tests touch no real
  network, no real sleep, no wall clock, and no unseeded randomness. Each
  source of nondeterminism has a named control: transport fake for network,
  recorded sleeper for backoff, injected or frozen clock for time, seeded
  `random.Random` for randomness. Determinism is a *mechanism*, not a
  convention — `--disable-socket` makes the network rule fail closed (see
  `references/determinism.md`). A test that cannot flake is one that never
  needs a retry plugin — retrying flaky tests is rejected as a fix on G1
  and G2 alike.
- **Order-independent and parallel-safe.** The suite passes under
  pytest-randomly (any order) and `pytest -n auto` (xdist). No test reads
  state another test wrote; anything session-scoped is immutable or
  per-worker. Same caveat as pytest-timeout: pytest-xdist 3.8.0 publishes no
  Python 3.14 classifier — verify it against the pinned interpreter before
  relying on it in a 3.14+ project (checked 2026-07-26).
- **One behavior per test.** Name it `test_<subject>_<scenario>_<expected>`
  (`test_fetch_user_client_error_is_not_retried`). Arrange, act, assert —
  separated by blank lines. No branching or loops around assertions; a loop
  over cases is a `parametrize` table that lost its ids.
- **`pytest.raises` takes the narrowest type and `match=`.** A bare
  `pytest.raises(Exception)` passes when the wrong error is raised from the
  wrong line. Assert on `excinfo.value` attributes when the error carries
  structured context.
- **Assert outcomes, not call traffic.** For every test, name the wrong
  implementation that would still pass it — that is the mutant the test
  fails to kill. `assert client.push.called` alone survives a mutant that
  pushes the wrong payload; assert the payload. The exception: when the
  interaction *is* the contract ("sends exactly one email"), the call count
  is the outcome — assert it exactly, with its arguments.
- **No test-only methods on production classes.** Cleanup and construction
  helpers live in test utilities or fixtures, not on the class under test.

## Suite architecture

Full rules and rationale: `references/unit.md`.

- Split hermetic, sub-second `tests/unit/` from `tests/integration/` — real
  infrastructure behind the registered `integration` marker, separate CI job.
- Route behavior to the cheapest layer that can falsify it; never re-prove
  unit-tested logic through the integration stack.
- Layer `conftest.py` by blast radius: a fixture lives in the narrowest file
  that covers its users.
- Test through the public import path, not `_privates`.
- A bugfix ships with the regression pin that fails on the pre-fix code.

## Routing table

| Symptom or question                                            | Read                                                                 |
| -------------------------------------------------------------- | -------------------------------------------------------------------- |
| Retry/backoff schedule, circuit breaker, idempotency-key proof | `references/resilience.md`                                           |
| Freeze time in an async test; sleep, clock, or rng in a test   | `references/determinism.md`                                          |
| Flaky or order-dependent tests; real network, disk, env access | `references/determinism.md`                                          |
| Real Postgres or mock the repository?                          | `references/doubles-and-boundaries.md` + `references/integration.md` |
| Mock vs fake vs stub; patch target choice; autospec            | `references/doubles-and-boundaries.md`                               |
| Tempted to patch the subject's own internal helper             | `references/doubles-and-boundaries.md`                               |
| Which remote failure modes need tests                          | `references/doubles-and-boundaries.md`                               |
| Where do factories live; fixture scope, autouse, chains        | `references/fixtures-and-factories.md`                               |
| testcontainers, migrations, Pact / schemathesis contracts      | `references/integration.md`                                          |
| Unit/integration split; parametrize ids; subtests; snapshots   | `references/unit.md`                                                 |
| `assert_type` pins and other type-level tests                  | `references/unit.md`                                                 |
| Hypothesis vs parametrize; finding properties; stateful models | `references/property-based.md`                                       |
| Chasing 100% coverage; what runs in CI; pytest config          | `references/gates-and-ci.md`                                         |
| Benchmark or memory gates; mutation testing                    | `references/gates-and-ci.md`                                         |
| Testing an LLM-backed function; judge scores flicker           | `references/evals.md`                                                |

## Traps reviewers should catch

- **Testing the mock**: the subject (or its internals) is patched, and the
  test asserts the patch was called — only glue is covered.
- **Sleep-then-assert**: `time.sleep(0.5)` before checking an async result;
  slower CI turns it red. Replace with a deadline-bounded condition wait.
- **Bare `Mock()` drift**: no `spec_set`, so interface changes never break
  the test — it passes forever, protecting nothing.
- **Assertion-free paths**: a test whose name promises behavior but whose
  body only checks "no exception"; a `parametrize` case no assertion
  distinguishes.
- **Blanket lint/type excludes on `tests/`**: the suite silently becomes
  the least-reviewed, least-typed code in the repo.
- **Autouse creep**: behavior-changing autouse fixtures in a root conftest;
  every test inherits magic it never declared.
- **Order dependence**: mutation of session/module-scoped state; passes
  today because of alphabetical accident, fails under `-p randomly`.
- **Retry-the-flake**: rerun plugins or `@flaky` markers instead of removing
  the nondeterminism source. The flake is a bug — in the test or the code.
- **Fixture doing the asserting**: invariants buried in fixtures/handlers
  fail as setup errors mid-call instead of as failed expectations.
- **Tier confusion**: a judged or timing-based check sitting on the blocking
  gate. It goes red for reasons that are not defects, gets muted within two
  sprints, and whatever it measured is now unmonitored.
- **Benchmarks that never ran**: `pytest-benchmark` disables itself under
  `-n auto`, so the job is green because nothing was measured.
- **Hermeticity by convention**: the suite declares "no real network" and no
  mechanism enforces it; one client built without a transport override
  reaches the internet, and nobody learns until CI moves to a sandbox.
- **One sad path**: a boundary whose only failure test is a 404, leaving the
  timeout, the reset mid-response, and the 429 unexercised.
- **Telemetry asserted through `BatchSpanProcessor`**: spans export on a
  timer, so the assertion races the flush — sleep-then-assert in a costume.
- **Type tests that pin inference**: `assert_type` against whatever the
  checker infers today, breaking on the next checker improvement while
  protecting no real contract.

## When in doubt

- Fake vs mock vs real → real when cheap and deterministic; hand-written
  fake at boundaries you own; autospec mock only for thin interaction
  contracts.
- Which gate → deterministic in seconds → G1; deterministic but slow or
  resource-shaped → G2; verdict is a distribution → G3, off the merge path.
- Eval vs test → reads identically against a stubbed model → G1 harness
  test; needs the real model's words → G3 eval.
- `parametrize` vs `subtests` → known at collection time → parametrize with
  ids; discovered at runtime from data → subtests.
- `pytest-asyncio` vs `anyio` → asyncio-only → pytest-asyncio; Trio or dual
  backend → anyio. Never enable both plugins' auto modes.
- Fixture vs helper → teardown or parametrization → fixture; otherwise a
  plain typed helper.
- `xfail` vs skip → xfail (strict) for known bugs; skip only for genuinely
  inapplicable environments, via `skipif`.
- Benchmark vs memory gate → affording only one, gate memory — time is
  noisy, allocation is stable.

## What this skill is NOT

- **Not the TDD process skill.** Red-green-refactor discipline, when to
  write the test, and delete-and-restart rules live in superpowers'
  `test-driven-development` (where installed). This skill defines the
  quality bar of the artifacts that process produces.
- **Not the review protocol.** The omniagents-reviewer testing skill defines
  how findings are hunted and graded; this skill exists so there is nothing
  for it to find.
- **Not a pytest/hypothesis/testcontainers tutorial.** Mechanics live at
  their official docs; this skill records which patterns projects using it
  have chosen, and which they have rejected.
- **Not the broad end-to-end tier.** Prefer the narrow integration test
  that catches the same bug, plus consumer-driven contract tests across
  team boundaries. A larger test that survives must name the fidelity gap
  no smaller tier can close — stale doubles, deployment configuration,
  load, emergent behavior — per Google's SWE book ch. 14.
- **Not chaos engineering.** Killing containers, severing networks, and
  injecting latency into a live topology is a staging or pre-prod practice,
  run against deployed infrastructure and gated like a release. It does not
  belong in a pytest session, and its absence here is a decision rather than
  an oversight. The pytest-shaped version of that request is synthesizing the
  *symptom* at a boundary you control — the exception taxonomy in
  `references/doubles-and-boundaries.md`, or WireMock's real-socket faults in
  an integration test — and asserting your retry, breaker, and idempotency
  code answers correctly. Tools that operate on containers or clusters
  (pumba, chaos-mesh) have no pytest surface by design; chaostoolkit is
  additionally unmaintained.
- **Not a profiling workflow.** scalene, py-spy, austin, and interactive
  `cProfile` sessions belong to this plugin's `performance` skill, which owns
  measurement and runtime shape. This skill owns only what a suite can
  *assert*: a memory ceiling, a leak check, a benchmark comparison.
  Discovering *why* a number moved is the other skill's job.
- **Not the source of truth for tool configuration.** The consuming
  project's `pyproject.toml` is; the reference block in
  `references/gates-and-ci.md` is the shape to converge on, not a file to
  copy blindly.
- **Not exhaustive.** New testing opinions earn an entry when they recur.

## Freshness

This skill is project policy, not a complete upstream reference: verify
version-sensitive behavior (pytest ini options, hypothesis profiles, plugin
loop-scope defaults) against primary docs — prefer Context7 MCP; otherwise
web search restricted to official sources. Tooling versions were verified
against PyPI and official docs on 2026-07-26; each reference file ends with
its own sources and a freshness note, including the packages checked and
rejected for its area.
