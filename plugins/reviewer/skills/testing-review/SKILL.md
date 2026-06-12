---
name: testing-review
description: >-
  Use when reviewing code for test adequacy issues such as missing regression
  coverage, weak assertions, brittle mocks, fixture misuse, untested edge
  cases, snapshot overuse, flaky timing, or tests that miss user-visible
  behavior.
when_to_use: >-
  Trigger for testing review: missing tests, no regression test, weak
  assertion, assert called not outcome, brittle mock, over-mocking, fixture
  pollution, snapshot-only test, flaky async test, sleep in test, time-based
  flake, randomness, missing error path, missing edge case, untested public API.
disable-model-invocation: false
user-invocable: false
---

# Testing Review — Hunt Protocols

Judge whether changed behavior is protected by tests that would actually
**fail if it broke**. Coverage that cannot fail is ceremony; the question is
always "what regression would this suite catch, and what slips through?"

**The shared falsifier — search before "untested".** Before flagging any
behavior as untested, search the whole suite: Grep the changed symbol across
all test directories, and read parametrized cases, fixtures, integration and
e2e tests. Filename conventions miss most real coverage. Record where you
searched in the finding's `why`.

## Hunts

Execute every hunt whose `When` matches; skip the rest. Exemplars are
calibration anchors, never templates — do not copy their wording into
reports.

### Hunt: Regression Pin

- **When**: the change intent says "fix" (commit subject, PR title), or the
  diff visibly corrects behavior.
- **Protocol**:
    1. State the fixed behavior from the commit message plus the diff.
    2. Hunt the test that would have **failed before the fix** —
       `query_graph_tool` `tests_for` on the fixed symbol, Grep the symbol
       and the bug's trigger condition across the suite.
    3. If found, read it: does it exercise the failing input, or merely
       touch the function? If absent after the whole-suite search, that
       absence is the finding.
- **Evidence bar**: the fix identified, plus the documented-and-empty
  search or the test that fails to pin it.
- **Falsifiers**: a parametrized or integration case covers the exact
  trigger (read it first); the regression test arrives in this same diff;
  the project exempts the layer (e.g. generated code).
- **Exemplar**: IMPORTANT 85 — "commit says 'fix: TZ offset applied twice'
  but nothing pins single application — searched tests/ for the symbol and
  for 'offset'; the bug can return silently." / **Noise twin**: the bugfix
  diff itself adds `test_offset_applied_once` — pinned.

### Hunt: New-Branch Coverage

- **When**: the production diff adds a conditional, error branch, or early
  return.
- **Protocol**:
    1. For each new branch, find the tests that reach the enclosing
       function (`tests_for`, Grep on imports).
    2. Read them: do any test's **inputs** drive execution into the new
       branch? Reaching the function is not reaching the branch.
    3. Weight by what the branch guards: error handling, money, and
       permission branches first.
- **Evidence bar**: the new branch, the tests you read, and none entering
  it.
- **Falsifiers**: an existing parametrized case already includes the new
  input class; an integration path exercises it; the branch is
  debug-only and the project exempts it.
- **Exemplar**: IMPORTANT 80 — "new `except QuotaExceeded` branch returns
  a partial result; all three tests of this function stay under quota — the
  degraded shape ships unverified." / **Noise twin**: a new input branch
  that an existing `parametrize` table already drives.

### Hunt: Mutant Survival

- **When**: the diff adds or changes tests.
- **Protocol**:
    1. For each test, name a **wrong implementation that still passes
       it** — that is the mutant the test fails to kill.
    2. The usual survivors: asserting a mock was called without asserting
       the outcome; asserting only not-None/no-exception; snapshotting
       everything when the contract is one field; comparing a value to
       the fixture that produced it.
    3. Check the test name states the protected behavior, so a failure
       reads as a broken contract.
- **Evidence bar**: the named wrong implementation the test would pass.
- **Falsifiers**: a sibling test in the same module asserts the outcome
  (pairs are fine); the interaction **is** the contract — "sends exactly
  one email" is an outcome for a notifier.
- **Exemplar**: IMPORTANT 78 — "`test_sync` asserts only
  `client.push.called` — pushing the wrong payload, or deletions as
  creations, still passes." / **Noise twin**: asserting `send` was called
  exactly once where duplicate-suppression is the behavior under test.

### Hunt: Mock Boundary

- **When**: the diff adds a mock, patch, stub, or fake.
- **Protocol**:
    1. Place the mock relative to the unit under test: it should replace
       an external boundary (network, clock, DB, filesystem) — never the
       logic being tested.
    2. Compare the mock's shape to the real API — signature, return
       shape, exceptions. A stale mock passes forever after the real
       interface changes.
    3. Python patch targets: patched where **looked up**, not where
       defined — a mispatched target silently tests nothing.
- **Evidence bar**: a mock that replaces the system under test, diverges
  from the real interface, or patches the wrong lookup site.
- **Falsifiers**: `autospec`/`spec=` pins the interface; the heavy
  dependency fake is injected at a real boundary — that is what fakes are
  for.
- **Exemplar**: IMPORTANT 79 — "the parser under test is itself patched
  in `test_ingest` — the test exercises the mock; only the glue code is
  covered." / **Noise twin**: an injected fake clock at the time
  boundary.

### Hunt: Flake Trigger

- **When**: new or changed tests touch time, sleeps, async tasks,
  randomness, network, or shared fixture state.
- **Protocol**:
    1. For each nondeterminism source, find its control: frozen/injected
       clock, seeded RNG, condition-wait with deadline instead of sleep,
       isolated tmp/DB per test.
    2. Async: every task awaited or cancelled before test exit — nothing
       outlives the test.
    3. Shared fixtures: does any test mutate module-/session-scoped state
       another test reads? Order dependence is a flake on a timer.
- **Evidence bar**: the nondeterminism source plus its missing control.
- **Falsifiers**: the sleep is a documented test of real wall-clock
  behavior (rate-limiter window); the fixture is function-scoped, fresh
  per test.
- **Exemplar**: IMPORTANT 81 — "`sleep(0.5)` then assert the job
  finished — slower CI makes this fail; poll the status with a
  deadline." / **Noise twin**: a sleep inside the rate-limiter's own
  window test, commented as such.

### Hunt: Contract Surface

- **When**: a public or exported API changed, and tests changed with it.
- **Protocol**:
    1. Check the tests exercise the symbol the way real consumers do —
       through the public import path, not private internals.
    2. For a breaking change: a test must state the **new** contract, and
       tests pinning the old one must go with it.
    3. Tests reaching into `_privates` or monkeypatching internals couple
       the suite to the implementation — the next refactor breaks tests
       without breaking behavior.
- **Evidence bar**: public behavior tested only via internals, or a
  changed contract no test states.
- **Falsifiers**: the internal access is a documented test seam; a
  characterization suite elsewhere covers the public path (point at it).
- **Exemplar**: IMPORTANT 76 — "tests for the new export call
  `_build_rows` directly; nothing runs `export()` end-to-end, so wiring
  bugs pass silently." / **Noise twin**: one white-box test of a hairy
  internal algorithm alongside black-box tests of the public API.

## Severity Anchors

Grade with the contract's Severity Rubric and elevation rule. In this
dimension:

- **BLOCKER**: a high-risk public contract change ships with no credible
  test signal at all.
- **IMPORTANT**: material new or changed behavior — especially an error
  path — with no covering test after the whole-suite search.
- **SUGGESTION**: assertion strength, narrow edge cases, test naming.

## Recall Sweep

After the hunts, sweep the diff once against these. Flag only what passes
the contract's Taste Test:

- Boundary, empty, and invalid inputs for new behavior; missing negative
  tests for validators.
- Migration/compatibility behavior untested; cleanup paths untested.
- Snapshot breadth: one giant snapshot where targeted assertions define
  the contract.
- Fixture pollution: mutation of session-/module-scoped state; tests that
  depend on execution order.
- Isolation: network, filesystem, or database state shared across tests.
