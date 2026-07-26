# Unit tests

Rules for the unit layer: how the suite is layered into Vitest projects,
type-level tests for public APIs, and assertion/snapshot discipline. Test
doubles live in `references/doubles-and-boundaries.md`, timing and ambient
state in `references/determinism.md`, and the enforcing configuration in
`references/gates-and-ci.md`.

## Suite architecture

- **Layer by what can falsify the behavior.** Pure logic and services with
  injected fakes → unit (node environment). Components → Testing Library
  in the jsdom/browser project. Route handlers with a real database →
  integration behind a separate Vitest project and CI job. Do not re-prove
  unit-tested logic through the component layer. A unit test exercising
  real collaborators is still a unit test (sociable, Jay Fields's term via
  Fowler); solitary isolation behind doubles is for awkward or boundary
  collaborations, not the default.
- **Vitest `projects` (renamed from `workspace` in Vitest 3.2; Vitest 4
  removed the old name) encode the layers** — `unit` (node), `dom` (jsdom),
  `integration` (node + globalSetup for containers) — so environment
  choices are structural, not per-file pragmas scattered around the repo.
- **Test through the public import path.** Import the subject as consumers
  do — from the module's public surface, not deep paths into its internals.
  One labeled white-box test of a hairy algorithm is fine next to the
  black-box tests of the public surface.
- **A bugfix ships with its regression pin** — a test exercising the exact
  trigger that fails on the pre-fix code. "Covered by existing tests" means
  pointing at the test that would have failed.
- **Shared builders live in `src/testing/`** — typed factories with
  override parameters (`makeUser(overrides?: Partial<User>): User`) built
  on `satisfies`, so test data cannot drift from the real types. Seed any
  faker usage once, in setup, so generated data is reproducible. This is the
  Test Data Builder pattern: the field a test asserts on is always set
  explicitly, never left to the faker — a value that comes from random
  generation asserts nothing.

## Setup and reuse

- **Reuse setup through plain functions, not nested `describe`/`beforeEach`
  chains.** Mutable variables assigned in hooks and read in tests are the
  primary readability hazard — tracing their values means scanning the
  whole file. `beforeEach` earns its keep only for guaranteed cleanup.
- **Inline the arrange so each test is self-contained** — readable top to
  bottom without hunting for reassignments elsewhere in the file.
- **A little duplication is fine when it clarifies.** DAMP complements DRY:
  repeat the two lines that make the test's intent obvious rather than
  hide them in shared setup.

## Type-level tests

- **Public generics and inference-heavy APIs get `*.test-d.ts` files**, run
  via `vitest --typecheck` in CI: `expectTypeOf(parse).returns.
  toEqualTypeOf<Duration>()`. A library whose inference regresses compiles
  fine and breaks every consumer — only a type test catches it.
- **Negative type tests use `@ts-expect-error` with a code and reason** —
  `// @ts-expect-error TS2345: rejects numeric input by design` above the
  invalid call. When the API later (wrongly) accepts it, the unused
  expect-error fails the build.

## Assertions and snapshots

- **`toStrictEqual` is the default for objects** — it distinguishes
  `undefined` fields from missing ones and rejects extra keys `toEqual`
  ignores. `toMatchObject` is a deliberate, commented choice for wide
  objects where only a slice is the contract.
- **Error assertions pin type and message**:
  `toThrowError(DurationParseError)` plus message/regex — a bare
  `toThrowError()` passes when the wrong error comes from the wrong line.
- **Domain assertions become typed custom matchers.** A multi-line assertion
  block repeated across tests (`expect(result.ok).toBe(true); expect(result.
  value)…`) collapses into `expect.extend({ toBeOkWith })` — one matcher with
  a precise failure message beats a copied block whose diff nobody reads.
  Declare the matcher's types so `expect(x).toBeOkWith(…)` type-checks under
  the `typings` skill's no-`any` rule.
- **Inline snapshots only, and only for small stable artifacts** (a
  rendered SQL string, a serialized payload) where the whole artifact is
  the contract. A snapshot of a component tree with one meaningful value
  is an approve-anything test. CI fails on obsolete snapshots; snapshot
  updates are reviewed diffs, not `-u` reflexes.
- **Do not derive the expectation from the subject's inputs by the same
  formula the subject uses** — hardcode the independently-known answer.

## Sources

- [Unit Test (Martin Fowler)](https://martinfowler.com/bliki/UnitTest.html)
- [The Practical Test Pyramid (Ham Vocke)](https://martinfowler.com/articles/practical-test-pyramid.html)
- [Software Engineering at Google, ch. 12 "Unit Testing"](https://abseil.io/resources/swe-book/html/ch12.html)
- [Testing on the Toilet: Test Behavior, Not Implementation](https://testing.googleblog.com/2013/08/testing-on-toilet-test-behavior-not.html)
- [Avoid Nesting when you're Testing (Kent C. Dodds)](https://kentcdodds.com/blog/avoid-nesting-when-youre-testing)
- [Vitest: Testing Types](https://vitest.dev/guide/testing-types.html)
- [Vitest 4 migration guide](https://vitest.dev/guide/migration.html)

Freshness: verified 2026-07-26 — Vitest 4.1.10 (`projects` current;
`workspace` removed in 4), expect-type 1.4.0 (`expectTypeOf` API stable).
