# Property-based tests (fast-check)

When an invariant governs a domain of inputs, one property replaces dozens
of examples — and found counterexamples flow back into the example suite.
Case-table alternatives (`test.each`) and assertion style live in
`references/unit.md`.

- **Where an invariant exists, one property beats dozens of examples**:
  round-trips, idempotence, order-insensitivity, oracle comparison.

```typescript
import * as fc from "fast-check";

it("round-trips every non-negative duration", () => {
  fc.assert(
    fc.property(fc.integer({ min: 0, max: 10 ** 9 }), (seconds) => {
      expect(parseDuration(formatDuration(seconds))).toBe(seconds);
    }),
  );
});
```

- **Pin found counterexamples** as plain `test.each` cases so they survive
  as named regressions; record the failing seed from CI output when
  reproducing.
- **Model-based testing for stateful units.** For a store, cache, or reducer,
  `fc.commands` drives random valid operation sequences against a model and
  asserts agreement — it finds the ordering bug no hand-written sequence
  enumerates.

## Sources

- [Finding Property Tests (Hillel Wayne)](https://www.hillelwayne.com/post/contract-examples/)
- [Hypothesis Testing with Oracle Functions (Hillel Wayne)](https://www.hillelwayne.com/post/hypothesis-oracles/)
- [fast-check: getting started](https://fast-check.dev/docs/introduction/getting-started/)
- [fast-check: model-based testing](https://fast-check.dev/docs/advanced/model-based-testing/)

Freshness: verified 2026-07-26 — fast-check 4.9.0 (`fc.assert` /
`fc.property` / `fc.integer({ min, max })` and `fc.commands` all current
API; 3.x deprecated aliases dropped at the 4.0 boundary).
