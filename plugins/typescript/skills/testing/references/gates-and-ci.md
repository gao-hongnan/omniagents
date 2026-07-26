# Coverage, CI gates, and configuration

Coverage policy, the CI stack, and the reference `vitest.config.ts` /
ESLint blocks the suite converges on — including the mock-hygiene pairing
the hub's non-negotiables mandate. Layering (which projects exist and why)
is in `references/unit.md`.

## Coverage and CI gates

- **V8 provider with explicit `include` and thresholds.** Vitest 4 counts
  only loaded files unless `coverage.include` is set — without it, an
  entirely-untested module simply vanishes from the report. Thresholds are
  a ratcheted floor (raise as coverage grows, never lower to merge), and a
  floor is all they are: 100% lines with outcome-free assertions proves
  nothing.
- **Mutation testing mechanizes the mutant-kill question.**
  `@stryker-mutator/vitest-runner` (verified 9.6.1, peer `vitest >=2.0.0`)
  runs the suite against generated mutants — the tool that answers "name
  the wrong implementation that still passes" at scale.
- **CI runs the full strict stack**: `tsc --noEmit` over tests,
  type-aware ESLint over tests, `vitest run` with shuffle, `--typecheck`
  for the `test-d` suite, and the integration project as its own job.

## Configuration reference

```typescript
// vitest.config.ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // Vitest 4: restoreMocks only restores vi.spyOn spies and no longer
    // resets mock state — mockReset is the mandatory pairing, or vi.fn()
    // call history and one-shot impls leak between tests.
    restoreMocks: true,
    mockReset: true,
    unstubEnvs: true,
    unstubGlobals: true,
    sequence: { shuffle: true }, // order dependence fails now, not in prod
    env: { TZ: "UTC" },
    projects: [
      { test: { name: "unit", environment: "node", include: ["src/**/*.test.ts"] } },
      { test: { name: "dom", environment: "jsdom", include: ["src/**/*.test.tsx"] } },
    ],
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"], // Vitest 4: unset include = untested files vanish
      exclude: ["src/**/*.test.*", "src/**/*.test-d.ts", "src/testing/**"],
      thresholds: { lines: 90, branches: 85, functions: 90, statements: 90 },
    },
  },
});
```

```typescript
// eslint.config.ts — tests get *additional* rules, never looser type rules
import vitest from "@vitest/eslint-plugin";

export default [
  // ...project config (typescript-eslint strictTypeChecked)...
  {
    files: ["**/*.test.ts", "**/*.test.tsx"],
    plugins: { vitest },
    rules: {
      ...vitest.configs.recommended.rules,
      "vitest/no-focused-tests": "error",
      "vitest/expect-expect": "error",
    },
  },
];
```

Prefer explicit `import { describe, expect, it, vi } from "vitest"` over
`globals: true`; if a project opts into globals, declare
`"types": ["vitest/globals"]` explicitly per the `typings` skill's rule.

## Sources

- [Software Engineering at Google, ch. 11 "Testing Overview"](https://abseil.io/resources/swe-book/html/ch11.html)
- [The Practical Test Pyramid (Ham Vocke)](https://martinfowler.com/articles/practical-test-pyramid.html)
- [Unit Testing: Principles, Practices, and Patterns, ch. 1 excerpt (Vladimir Khorikov)](https://enterprisecraftsmanship.com/files/Unit-Testing-Chapter-1-Excerpt.pdf)
- [StrykerJS: configuration](https://stryker-mutator.io/docs/stryker-js/configuration/)
- [Vitest 4 migration guide](https://vitest.dev/guide/migration.html)
- [Vitest: allowOnly config](https://vitest.dev/config/#allowonly)

Freshness: verified 2026-07-26 — Vitest 4.1.10 (`coverage.all` /
`coverage.extensions` removed in v4; unset `coverage.include` reports only
loaded files; `restoreMocks` narrowed to `vi.spyOn` spies; `allowOnly`
defaults to `!process.env.CI`).
