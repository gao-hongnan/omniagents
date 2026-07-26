# Resilience patterns under test

Scope: proving retry, circuit-breaker, and idempotency policies actually
fire — the cross-call state machines that single-call tests leave unproven.

A retry policy, a circuit breaker, and an idempotency key are state machines
whose interesting behavior only appears *across* calls — which is why a suite
full of single-call tests can leave all three unproven. The sibling
`omniagents-design-patterns:system` skill designs these patterns; this is how
you falsify them, using the fake clock and recording sleeper from
`references/determinism.md`.

- **Retry: assert the schedule and the termination separately.** Attempt
  count, delay sequence, and the exception that finally escapes are three
  contracts. `assert sleeps == pytest.approx([1.0, 2.0, 4.0])` kills the
  fixed-delay and dropped-jitter mutants; a test that retry *stops* kills the
  retry-forever mutant that "it eventually succeeded" never touches. Where
  the project uses stamina, `stamina.set_testing()` caps attempts and drops
  backoff sleep without hand-rolling a sleeper around every decorated call,
  and an autouse `stamina.set_active(False)` keeps retries out of the tests
  that are not about retrying.
- **Circuit breaker: assert the transition and the call that does not
  happen.** Drive real failures to the threshold, then assert the next call
  fails *without the collaborator being invoked at all* — the open circuit's
  entire value is the call it suppresses. Advance the fake clock past the
  reset timeout and assert half-open admits exactly one probe. A breaker
  nobody proved trips gets discovered during the incident it existed to
  contain.
- **Idempotency: replay the key, assert one effect.** Send the same request
  twice under one idempotency key; assert the downstream side effect occurred
  once and both responses agree. This is the double-charge bug, and no
  single-request test can see it.
- **Never patch the breaker or the retry decorator to test code that uses
  it.** That tests the patch. Drive the real policy with real failure counts
  against a fake collaborator — the subject's own internals stay unpatched,
  exactly as elsewhere in this skill.

## Sources

- [Software Engineering at Google, ch. 13 "Test Doubles"](https://abseil.io/resources/swe-book/html/ch13.html)
- [Testing on the Toilet: Testing State vs. Testing Interactions](https://testing.googleblog.com/2013/03/testing-on-toilet-testing-state-vs.html)
- [stamina](https://stamina.hynek.me/)

Freshness: stamina 26.1.0 verified against PyPI and current docs on
2026-07-26 (`set_testing()` caps attempts and drops backoff;
`set_active(False)` via an autouse fixture is the documented pytest shape).
Checked and rejected the same day: pytest-disrupt (2018) and chaostoolkit
(unmaintained since 2024, caps at Python 3.12) — see the chaos-engineering
boundary in the hub's "What this skill is NOT".
