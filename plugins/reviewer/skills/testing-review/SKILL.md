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

# Testing Review Checklist

Review whether changed behavior is protected by useful tests. Prefer focused
behavior assertions over implementation checks.

## Behavior Coverage

- New public behavior has no test
- Changed branch lacks a regression test
- Boundary values, empty inputs, and invalid inputs are untested
- Error paths and cleanup paths are untested
- Migration or compatibility behavior is not covered

## Assertion Quality

- Test only asserts that a mock was called, not the observable result
- Test has no meaningful assertion
- Assertion duplicates implementation details instead of user-visible behavior
- Snapshot is too broad to identify the intended contract
- Test name does not describe the behavior being protected

## Mock and Fixture Quality

- Mock bypasses the code path that should be exercised
- Fixture state hides setup required by real callers
- Shared fixture mutation can pollute later tests
- External boundary mocked at the wrong level
- Integration risk is high but only isolated unit tests changed

## Flake Risk

- Sleeps or fixed timeouts instead of condition-based waits
- Wall-clock time, timezone, or randomness not controlled
- Async tasks can outlive the test
- Network, filesystem, or database state is not isolated
- Order-dependent tests rely on global mutable state

## Severity

Grade with the shared severity rubric and elevation rule from the preloaded
`review-output` contract. Dimension calibration:

- BLOCKER only when a high-risk public contract change ships with no credible
  test signal.
- A material behavior or error path lacking coverage is IMPORTANT.
- A narrow edge case or assertion-quality nit is SUGGESTION.
