# Unit tier: architecture, parametrize, type-level tests, assertions

Scope: the unit layer of the suite — how it is laid out, how enumerable cases
become tables, how annotations are tested, and what an assertion must pin.
The hub `SKILL.md` holds the non-negotiables these rules assume; doubles live
in `references/doubles-and-boundaries.md`, invariant-driven testing in
`references/property-based.md`.

## Suite architecture

- **Split `tests/unit/` from `tests/integration/`.** Unit tests are hermetic
  and sub-second: pure logic, fakes at boundaries. Integration tests exercise
  real infrastructure (containers, migrations, real wire formats) behind the
  registered `integration` marker and run as a separate CI job. A test that
  needs Docker does not hide among tests that need nothing.
- **Route behavior to the cheapest layer that can falsify it.** Parsing,
  policy, and arithmetic → unit tests of pure functions. Wiring, SQL, and
  serialization compatibility → integration through the public API. Do not
  re-prove unit-tested logic through the integration stack; do not "unit
  test" SQL by asserting the query string.
- **conftest.py is layered by blast radius.** A fixture lives in the
  narrowest `conftest.py` that covers its users, and is promoted only when a
  second consumer appears. A root conftest full of app-specific fixtures is
  a coupling bus: every test file inherits invalidation from fixtures it
  never uses.
- **Test through the public import path.** Tests import the subject the way
  consumers do. Reaching into `_privates` couples the suite to the
  implementation — the next refactor breaks tests without breaking behavior.
  One white-box test of a genuinely hairy internal algorithm is fine;
  label it as such next to the black-box tests of the public surface.
- **A bugfix ships with its regression pin.** The test exercises the exact
  trigger input and fails on the pre-fix code. "Covered by existing tests"
  requires pointing at the test that would have failed.

## Parametrize and subtests

- **`parametrize` is the edge-case ledger.** Cases carry ids (`ids=` or
  `pytest.param(..., id="leading-zeros")`) so a failure names its input
  without decoding a tuple. Standing families to cover: empty, boundary
  (the 499/500 of the domain), malformed, unicode, and the
  characterization cases that pin *current* permissive behavior — labeled
  as characterization so tightening them later is a deliberate act. Under
  pytest 9's strict mode, `strict_parametrization_ids` turns a duplicate id
  into an error instead of silently disambiguating it to `id0` / `id1` —
  which is how two cases quietly become indistinguishable in a report.
- **Stack `parametrize` for a genuine matrix; use `indirect=` to vary
  fixtures per case.** Two stacked decorators run the Cartesian product —
  reach for it only when the axes are truly independent, and collapse to
  explicit `pytest.param` rows when most cells are meaningless.
  `indirect=["client"]` routes a parameter through a fixture so setup differs
  per case (a client built against each backend) without branching in the
  test body.
- **`subtests` for cases not known at collection time.** pytest 9 merged
  pytest-subtests into core, so `with subtests.test(path=str(path)):` reports
  each iteration's failure individually instead of halting at the first — one
  run names every offending case rather than one case per CI cycle. Reserve
  it for cases genuinely derived from runtime data (files on disk,
  fixture-supplied rows); a statically known case list is a `parametrize`
  table and keeps its ids. Add no dependency — the standalone plugin is
  archived. Upstream still marks the feature experimental: usage is stable,
  failure *reporting* may change.

Where an invariant over a domain, not an enumerable case list, is the right
shape, switch to `references/property-based.md`.

## Type-level tests

Annotations are a contract with callers, and no runtime suite falsifies them:
a function that silently starts returning `Any` still runs, still passes, and
still degrades every consumer downstream. This plugin's `typings` skill
designs the annotations; these tests prove the design survives a refactor.
They run in the type checker, on G1, alongside the suite.

- **Public generic and inference-heavy APIs get `assert_type` pins.**
  `assert_type(parse_duration("90m"), timedelta)` fails the *checker* when
  inference regresses to `Any` or widens past the documented type — the
  failure mode no runtime assertion can see.
- **Negative cases assert the error, not merely its absence.** A
  `# type: ignore[arg-type]` over a deliberately invalid call, paired with
  `warn_unused_ignores = true`, fails the build the day the API wrongly
  starts accepting that call. For exact error codes and messages,
  `pytest-mypy-plugins` drives YAML-defined checker cases.
- **Shipping `py.typed` means gating on `pyright --verifytypes`**, which
  scores the public surface for type completeness and names the un-annotated
  export that silently degrades consumers to `Unknown`.
- **Pin contracts, not inference accidents.** `assert_type(x, list[int])`
  where the real contract is "some sequence of ints" locks in a detail that a
  checker improvement will break for no behavioral reason. Same discipline as
  characterization cases: if the pin is provisional, label it as one.
- **Runtime enforcement is a different tool, not a substitute.** typeguard
  and beartype check annotations at call time and earn their place at trust
  boundaries where data arrives untyped; neither replaces a checker pass.

## Assertions and snapshots

- **Exact values over shape checks.** `assert result == expected_user`
  (whole-object equality on frozen dataclasses / pydantic models) beats
  field-by-field, which silently ignores the field you forgot.
  `assert result is not None` alone is a smoke test — label it as one or
  strengthen it.
- **Floats through `pytest.approx`**, never `round()` gymnastics.
- **Do not compare a value to the fixture that computed it** — deriving the
  expectation from the subject's own inputs by the same formula reproves
  the implementation. Hardcode the independently-known answer.
- **Snapshots (syrupy) only for stable serialized artifacts** — rendered
  SQL, generated config, wire payloads — where the whole artifact is the
  contract. A snapshot of a big object with one meaningful field is an
  approve-anything test; assert the field. Snapshot updates are reviewed
  diffs, not `--snapshot-update` reflexes.

## Sources

- [Unit Test (Martin Fowler)](https://martinfowler.com/bliki/UnitTest.html)
- [The Practical Test Pyramid (Ham Vocke)](https://martinfowler.com/articles/practical-test-pyramid.html)
- [Software Engineering at Google, ch. 12 "Unit Testing"](https://abseil.io/resources/swe-book/html/ch12.html)
- [Testing on the Toilet: Test Behavior, Not Implementation](https://testing.googleblog.com/2013/08/testing-on-toilet-test-behavior-not.html)
- [Styles of unit testing (Vladimir Khorikov)](https://enterprisecraftsmanship.com/posts/styles-of-unit-testing/)
- [Working Effectively with Legacy Code (Michael Feathers) — ch. 13, characterization tests](https://www.informit.com/articles/article.aspx?p=359417&seqNum=2)
- [pytest configuration reference](https://docs.pytest.org/en/stable/reference/customize.html)
- [pytest subtests](https://docs.pytest.org/en/stable/how-to/subtests.html)
- [Testing type annotations](https://typing.python.org/en/latest/reference/quality.html)
- [pytest-mypy-plugins](https://github.com/typeddjango/pytest-mypy-plugins)
- [syrupy](https://github.com/syrupy-project/syrupy)

Freshness: pytest 9.1.1 verified against PyPI and current docs on 2026-07-26
— subtests merged into core with the experimental-reporting caveat, and
`strict_parametrization_ids` confirmed as part of the `strict` umbrella.
