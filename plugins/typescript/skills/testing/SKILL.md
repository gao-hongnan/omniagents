---
name: testing
description: >-
  Use when writing or reviewing TypeScript tests: Vitest 4 suite architecture
  and projects config, typed mocks and vi.fn / vi.spyOn / vi.mock choices, MSW
  at the network boundary, fake timers and async assertion ordering, flaky or
  order-dependent tests, Testing Library component tests, fast-check
  property-based tests, expectTypeOf type-level tests, testcontainers
  integration suites, snapshots, coverage thresholds, or vitest.config /
  ESLint test-rule configuration.
when_to_use: >-
  Trigger for *.test.ts(x) / *.test-d.ts files, vitest.config.*, writing unit
  or integration tests, adding a regression test for a bugfix, test-only
  diffs, flaky tests, real setTimeout waits in tests, unawaited
  expect().rejects, unseeded randomness, vi.mock vs dependency injection
  decisions, mock restore/reset hygiene, jsdom vs node environment choices,
  snapshot bloat, coverage thresholds, vi.stubEnv / vi.stubGlobal isolation,
  vi.hoisted mock setup, test data builders, Pact contract testing,
  vitest-axe accessibility, or ESLint rules for test files.
paths:
  - "**/*.test.ts"
  - "**/*.test.tsx"
  - "**/*.test-d.ts"
  - "**/*.spec.ts"
  - "**/vitest.config.*"
  - "**/vitest.setup.*"
  - "**/package.json"
---

# TypeScript Testing Rules

A test earns its place by failing when the behavior it protects breaks. Every
rule below serves that property: a suite where each test kills a specific
wrong implementation, and where red always means a real defect — never a
flake, never a stale mock, never an ordering accident. Tests are production
code: they compile under the same `tsc --strict` project, they pass the same
type-aware ESLint config as `src/`, and they are reviewed against the same
bar. The `typings` skill's rules — no `any`, no bare `@ts-ignore`,
`satisfies` over `as` — apply inside test files without exemption.

This skill assumes **Vitest 4+ on TypeScript 6.0+**, with MSW 2 at the
network boundary, Testing Library + user-event for components, fast-check
for property-based tests, testcontainers for integration infrastructure, and
`@vitest/eslint-plugin` for test-specific lint rules. For version-sensitive
behavior, query Context7 MCP or the official docs before changing a rule.

This skill is rules, not a tutorial. It assumes familiarity with `describe`
/ `it`, `vi` mocking, and async testing. Scope boundaries:

- **The test-first process** (red-green-refactor) is not restated here.
  Where the superpowers plugin is installed, its `test-driven-development`
  skill governs the workflow; this skill governs what the tests look like.
- **Type-system conventions** come from this plugin's `typings` skill.
- **The review-side counterpart** is the omniagents-reviewer testing
  protocol (mutant survival, mock boundary, flake triggers). A suite that
  follows this skill should produce zero findings there.
- **Browser suites** (Playwright) are out of scope; this skill covers unit,
  component, and service-level integration tests. Playwright 1.62 also
  ships first-class
  [component testing](https://playwright.dev/docs/test-components) — a
  stories/galleries model with a built-in `mount()` fixture — but this
  skill still prefers Testing Library/jsdom for component tests: speed,
  hermeticity, and the Testing Library query discipline this skill already
  teaches. Playwright CT is the option when a real browser is required; see
  `references/components.md`.

## Non-negotiables

- **Tests type-check and lint like `src/`.** Test files are included in the
  type-checked project (`tsc --noEmit` covers them) and in the type-aware
  ESLint run. No `any` in test data — builders with `satisfies` instead of
  casts; no `@ts-expect-error` without an error code and reason (the one
  sanctioned use: negative type tests — see `references/unit.md`).
- **Every async assertion is awaited.** `await expect(promise).rejects.
  toThrowError(...)` — an unawaited `.rejects` is a test that passes before
  its assertion runs. `@typescript-eslint/no-floating-promises` stays on for
  test files precisely because of this failure mode.
- **Mock hygiene is config, not convention.** `restoreMocks: true`,
  `mockReset: true`, `unstubEnvs: true`, `unstubGlobals: true` in
  `vitest.config.ts` — a manual `afterEach(() => vi.restoreAllMocks())` in
  each file is the version of this that one file forgets. The pairing is
  mandatory: in Vitest 4, `restoreMocks` only restores spies created with
  `vi.spyOn` and no longer resets mock state, so `vi.fn()` call history and
  `mockResolvedValueOnce` queues leak between tests unless `mockReset` (or
  `clearMocks`) is also set. Fake timers are the exception:
  `vi.useFakeTimers()` is paired with `vi.useRealTimers()` in `afterEach`
  in the same file, because timer state is not covered by `restoreMocks`.
- **Deterministic by construction.** No real network (MSW with
  `onUnhandledRequest: "error"` — an unexpected request is a failure, not a
  passthrough), no real timer waits (fake timers advanced explicitly), no
  wall-clock reads (`vi.setSystemTime` or an injected clock), no unseeded
  randomness (seeded generators injected; `fc` manages its own seeds and
  reports them). `TZ` is pinned to UTC in config so date tests do not pass
  only in your timezone. Retrying flaky tests is rejected as a fix.
- **Order-independent and parallel-safe.** The suite passes with
  `sequence.shuffle` enabled. No test reads module state another test
  wrote; shared module-level state in the subject is reset via a designed
  seam, not `vi.resetModules()` folklore.
- **One behavior per test.** `describe(subject)` + behavior sentence:
  `it("rejects without retrying on 4xx", ...)`. Arrange, act, assert
  separated by blank lines; no branching or loops around assertions — a
  loop over cases is a `test.each` table that lost its names.
- **Focused and disabled tests do not merge.** CI fails on `.only` (Vitest
  defaults `allowOnly` to false in CI); `vitest/no-focused-tests` catches it
  at lint time before CI spends the minutes. `.skip` carries a reason.
- **Assert outcomes, not call traffic.** For every test, name the wrong
  implementation that still passes it — the mutant it fails to kill.
  `expect(client.push).toHaveBeenCalled()` alone survives pushing the wrong
  payload; assert the payload. Exception: when the interaction *is* the
  contract ("submits the trimmed name to `onSubmit`"), assert the call
  exactly — count and arguments.
- **No test-only methods on production classes.** Cleanup and construction
  helpers live in `src/testing/` utilities, not on the class under test.

## Suite architecture

Layer by what can falsify the behavior: pure logic and services with
injected fakes → unit (node environment); components → Testing Library in
the jsdom/browser project; route handlers with a real database →
integration behind a separate Vitest project and CI job. Do not re-prove
unit-tested logic through the component layer. Vitest `projects` — renamed
from `workspace` in Vitest 3.2; Vitest 4 removed the old name — encode the
layers so environment choices are structural, not per-file pragmas. Test
through the public import path, ship every bugfix with its regression pin,
and keep shared typed builders in `src/testing/`. Full rules:
`references/unit.md`.

## Where to look

| Symptom or question                                                          | Read                                                 |
| ---------------------------------------------------------------------------- | ---------------------------------------------------- |
| Should this Vitest suite mock the repository layer? DI vs `vi.mock` vs MSW   | `references/doubles-and-boundaries.md`               |
| Which double — stub, fake, spy, mock — and what never gets mocked            | `references/doubles-and-boundaries.md`               |
| Fake timers wedge `fetch`; retry/debounce/backoff tests; real-timer waits    | `references/determinism.md`                          |
| Env vars, globals, filesystem, or module singletons leak between tests       | `references/determinism.md`                          |
| `getByTestId` everywhere; query priority; user-event; vitest-axe             | `references/components.md`                           |
| Playwright component testing vs Testing Library/jsdom                        | `references/components.md`                           |
| Mock state leaks despite `restoreMocks`                                      | Non-negotiables above + `references/gates-and-ci.md` |
| When to reach for fast-check; pinning counterexamples; `fc.commands`         | `references/property-based.md`                       |
| Layering, public import path, test data builders, assertions, snapshots      | `references/unit.md`                                 |
| `expectTypeOf` / `*.test-d.ts` type-level tests                              | `references/unit.md`                                 |
| testcontainers, real HTTP layer, vendor emulators, Pact contract tests       | `references/integration.md`                          |
| Coverage thresholds, `vitest.config.ts` / ESLint reference, the CI stack     | `references/gates-and-ci.md`                         |

## Traps reviewers should catch

- **Testing the mock**: `vi.mock` on the subject's own module or internals,
  then asserting the mock was called — only glue is covered.
- **Unawaited async assertions**: `expect(p).rejects.toThrow(...)` without
  `await` — the test ends before the assertion runs.
- **Real-timer waits**: `await new Promise((r) => setTimeout(r, 500))` —
  green locally, red on loaded CI. Deadline-bounded `waitFor` or fake
  timers.
- **Per-file hygiene**: hand-rolled `restoreAllMocks` in `afterEach` across
  files instead of config — the file that forgets leaks spies suite-wide.
- **Shape-faked platform objects**: `{ ok: false, status: 500 }` standing in
  for `Response` — drifts from the contract the day a header is read.
- **`any`-typed builders and `as User` casts in test data** — the test can
  feed the subject values production types forbid.
- **Snapshot bloat**: whole-tree snapshots where one field is the contract;
  updates rubber-stamped with `-u`.
- **Order dependence**: module-level mutable state shared across tests;
  passes under file order, fails under shuffle.
- **Retry-the-flake**: `retry:` config or rerun actions instead of removing
  the nondeterminism source. The flake is a bug — in the test or the code.

## When in doubt

- **DI vs `vi.mock` vs MSW** → injectable parameter → typed fake, no
  mocking machinery. Network boundary → MSW. Module you cannot inject and
  cannot reach over the wire → `vi.mock` with `importOriginal`, last
  resort.
- **Unit vs component vs integration for X** → the cheapest layer whose
  failure falsifies X: pure logic → unit; "the user can see/do" →
  component; "the route + DB really do it" → integration.
- **`test.each` vs fast-check** → enumerable meaningful cases → `test.each`
  with named cases; invariant over a domain → fast-check, with
  counterexamples pinned back into `test.each`.
- **Fake timers vs `vi.waitFor`** → subject schedules time (retry,
  debounce, TTL) → fake timers with boundary advances; genuinely
  concurrent completion → `waitFor`/`findBy*` with deadline.
- **jsdom vs node environment** → components and DOM APIs → jsdom project;
  everything else node.
- **Snapshot vs explicit asserts** → snapshot only when the whole artifact
  is the contract and its diff is reviewable; otherwise assert the fields.
- Matcher choices (`toStrictEqual` vs `toMatchObject`) live in
  `references/unit.md`; clock choices (`vi.setSystemTime` vs injected
  clock) in `references/determinism.md`.

## What this skill is NOT

- **Not the TDD process skill.** Red-green-refactor discipline lives in
  superpowers' `test-driven-development` (where installed); this skill
  defines the quality bar of the artifacts that process produces.
- **Not the review protocol.** The omniagents-reviewer testing skill
  defines how findings are hunted and graded; this skill exists so there is
  nothing for it to find.
- **Not an e2e skill.** Playwright browser suites have their own tooling
  and tradeoffs; this skill stops at service-level integration. The
  boundary is the runtime, not the test type: Playwright 1.62's first-class
  [component testing](https://playwright.dev/docs/test-components) — a
  stories/galleries model with a built-in `mount()` fixture — is the
  sanctioned route when a component test needs a real browser, while
  Testing Library/jsdom stays the default for speed, hermeticity, and its
  query discipline; `references/components.md` draws the line.
- **Not a Vitest/MSW/Testing Library tutorial.** Mechanics live in official
  docs; this skill records which patterns projects using it have chosen and
  which they have rejected.
- **Not the source of truth for tool configuration.** The consuming
  project's `vitest.config.ts` and `eslint.config.*` are; the reference
  blocks in `references/gates-and-ci.md` are the shape to converge on.
- **Not exhaustive.** New testing opinions earn an entry when they recur.

## Freshness

This skill is project policy, not a complete upstream reference. Package
versions cited across this skill were verified 2026-07-26; each file under
`references/` carries its own freshness note. When applying it to
unfamiliar APIs or version-sensitive behavior (Vitest config keys, MSW
handler forms, coverage semantics), verify against primary docs — prefer
Context7 MCP; otherwise web search restricted to official sources.

- [Vitest](https://vitest.dev/) — config reference, `projects`, fake
  timers, mocking, `--typecheck`, coverage.
- [Vitest 4 migration guide](https://vitest.dev/guide/migration.html) —
  `workspace` → `projects` (renamed in Vitest 3.2; Vitest 4 removed the
  old name), coverage `include` semantics, `restoreMocks` narrowing.
- [MSW](https://mswjs.io/docs/) — `setupServer`, handler overrides,
  `onUnhandledRequest`.
- [Testing Library](https://testing-library.com/docs/queries/about#priority)
  — query priority; [user-event](https://testing-library.com/docs/user-event/intro).
- [fast-check](https://fast-check.dev/) — properties, arbitraries, seeds.
- [@vitest/eslint-plugin](https://github.com/vitest-dev/eslint-plugin-vitest)
  — test lint rules.
- [testcontainers-node](https://node.testcontainers.org/) — container
  lifecycle for integration suites.
- [Playwright component testing](https://playwright.dev/docs/test-components)
  — the real-browser option for component tests.
- [vitest-axe](https://github.com/chaance/vitest-axe) — accessibility
  assertions; [Pact JS](https://docs.pact.io/implementation_guides/javascript)
  — consumer-driven contracts.
