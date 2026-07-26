# Property-based testing

Scope: when an invariant over a domain, not an example table, is the right
test — hypothesis properties, `@example` regression pins, settings profiles,
and model-based state-machine testing. The example-table counterpart
(`parametrize`, `subtests`) lives in `references/unit.md`.

- **Hypothesis where an invariant exists**: round-trips (`parse(format(x))
  == x`), idempotence, commutativity, oracle-vs-fast-path. The oracle also
  covers refactors: when rewriting a function you trust, the old
  implementation is the oracle — the property asserts `new(x) == old(x)`,
  the PBT form of a characterization test. One property
  replaces dozens of examples and finds the case you did not enumerate.
  Pin every counterexample hypothesis finds as an `@example` so it becomes
  a permanent regression test:

```python
from hypothesis import example, given
from hypothesis import strategies as st

from acme.durations import format_duration, parse_duration


@given(seconds=st.integers(min_value=0, max_value=10**9))
@example(seconds=0)
@example(seconds=90 * 60)  # regression: collapsed to "1h" and lost 30m
def test_parse_duration_round_trips_formatted_values(seconds: int) -> None:
    assert parse_duration(format_duration(seconds)) == seconds
```

- **No oracle? Metamorphic relations still falsify.** When the expected
  output cannot be stated, transform the input and assert the outputs
  relate: double a clip's volume, same transcription; add an element, the
  mode's count cannot decrease. The relation is checked without ever
  knowing the right answer.
- **Budget for PBT's costs.** Constructive generators for interdependent
  data are real engineering effort, and `assume`/filtering is a trap at
  scale — the bad inputs are still generated, just discarded, and every
  assumption weakens what the property proves. Random inputs are also
  maximally unlike real usage: PBT buys edge-case discovery at the cost of
  realism, and complements the example suite, never replaces it.
- **Register a `dev` profile; extend the built-in `ci` profile.** Hypothesis
  ships a built-in `ci` profile (`derandomize=True`, `deadline=None`,
  `database=None`, `print_blob=True`) and auto-loads it when a CI
  environment is detected, so hand-registering a profile named `ci` silently
  replaces upstream's. Extend it instead —
  `settings.register_profile("ci", settings.get_profile("ci"), max_examples=1000)`
  — and keep deadlines off in CI: shared runners are noisy, and
  `deadline=None` there is upstream's deliberate default. An explicit
  `deadline` belongs in the `dev` profile, where the hardware is yours and
  local runs stay quick.
- **Model-based testing for stateful subjects.** When the unit is a state
  machine — a cache, a connection pool, a parser with modes — a hypothesis
  `RuleBasedStateMachine` drives random valid operation sequences against a
  simplified model and asserts they agree. It finds the ordering bug no
  hand-written sequence enumerates.

## Sources

- [Finding Property Tests (Hillel Wayne)](https://www.hillelwayne.com/post/contract-examples/)
- [Metamorphic Testing (Hillel Wayne)](https://www.hillelwayne.com/post/metamorphic-testing/)
- [Property Testing with Complex Inputs (Hillel Wayne)](https://www.hillelwayne.com/post/property-testing-complex-inputs/)
- [Hypothesis Testing with Oracle Functions (Hillel Wayne)](https://www.hillelwayne.com/post/hypothesis-oracles/)
- [Hypothesis documentation](https://hypothesis.readthedocs.io/en/latest/)
- [Hypothesis stateful testing](https://hypothesis.readthedocs.io/en/latest/stateful.html)

Freshness: hypothesis 6.161.5 verified against PyPI and current docs on
2026-07-26 — including the built-in `ci` profile (auto-loaded when CI is
detected; `derandomize=True`, `deadline=None`, `database=None`,
`print_blob=True`) that the profile rule above extends.
