# TypeScript Type-Safety — Decision Trees

Reach-for guides for the recurring "which form do I use here?" questions
inside TypeScript code that the consuming project type-checks under
`tsc --strict` plus type-aware ESLint rules such as `strictTypeChecked`.
Companion to `../SKILL.md`; the rules there are non-negotiable, the choices
below are decision pairs.

## When in doubt

- **`interface` vs `type`** → `interface` for object shapes (extendable,
  declaration-mergeable). `type` for unions, primitives, mapped types,
  conditional types, and tuple types. The two are not interchangeable for
  these cases.
- **`null` vs `undefined`** → `undefined` for "not set" / optional /
  "field never assigned". `null` only when "explicitly empty" carries
  semantics distinct from "not set" (e.g., a JSON column that the database
  returns as `null`, not absent). When in doubt, `undefined`.
- **`Result<T, E>` vs `throw`** → throw at API boundaries where the caller is
  expected to handle exceptions; `Result` when the caller wants pattern-matched
  outcomes (typically internal pipelines, parsing, validation). Throw across
  package boundaries; return `Result` within them.
- **Branded type vs class wrapper for IDs** → branded type when string
  operations on the ID still matter (formatting, comparison, serialization,
  URL building). Class wrapper when behavior is attached to the identifier
  (validation, normalization on construction).
- **Inferred vs explicit return types** → explicit on public surfaces;
  inferred on private one-liners. Inference for non-trivial bodies leaks
  implementation detail into the type signature and breaks consumer types
  when the implementation changes.
- **`enum` vs `as const` object** → always `as const` object. The reasons
  (runtime cost, tree-shaking, reverse mappings on numeric enums) are not
  tradeoffs to balance — they are language-design problems with `enum`. The
  `as const` form is strictly better for almost every case.
- **`as` vs `satisfies`** → `satisfies` unless you are deliberately narrowing
  a wider type to a specific value (rare). `as Foo` widens the erasure and
  silences the checker; `satisfies Foo` validates without losing the
  narrower inferred type.
- **Type guard (`x is T`) vs assertion function (`asserts x is T`)** →
  type guard when the caller wants to *branch* on the result; assertion
  function when the caller wants a runtime invariant that *throws* on
  violation. The two are not interchangeable.
- **`using` declaration vs manual `try/finally`** → `using` whenever the
  acquired value implements (or can implement) `Disposable` /
  `AsyncDisposable`. Reserve `try/finally` for interop with third-party APIs
  that cannot be modified to add `[Symbol.dispose]()`. If you control the
  resource type, implementing `Symbol.dispose` is always preferable to
  scattering `try/finally` at every acquisition site.
- **NodeNext vs bundler module resolution** → `nodenext` when emitted code runs
  directly in Node.js and must follow Node's package exports / extension
  rules. `bundler` when Vite, Next.js, esbuild, Rollup, Webpack, Bun, or
  another bundler resolves imports. Never use `node`, `node10`, or `classic`
  in new TS 6.0 configs.
- **`paths` with `baseUrl` vs explicit path targets** → explicit path targets.
  Write `"@app/*": ["./src/app/*"]`; do not use `"baseUrl": "./src"` as a
  lookup root. A catch-all `"*": ["./src/*"]` is a migration-only choice when
  preserving old baseUrl behavior is deliberate.
- **Explicit `types` vs implicit globals** → explicit `types`. TS 6.0 defaults
  `types` to `[]`, so list only ambient packages used by the project:
  `["node"]`, `["vitest/globals"]`, `["jest"]`, etc. Use `["*"]` only as a
  temporary migration escape hatch.
- **Explicit `rootDir` vs inferred emit root** → explicit `rootDir` for
  emitting projects, usually `"./src"`. TS 6.0 defaults `rootDir` to the
  tsconfig directory, so relying on old common-source-directory inference can
  change output layout.
- **Import attributes `with` vs import assertions `assert`** → `with`.
  `import data from "./data.json" with { type: "json" }` is the TS 6.0 shape;
  `assert { type: "json" }` is deprecated.
- **Explicit type predicate (`x is T`) vs inferred predicate** →
  omit the annotation and let TypeScript infer it whenever the predicate
  body is a narrowing expression (`typeof`, `instanceof`, discriminant check).
  Add an explicit `x is T` annotation when: (a) the function is on a public
  API surface whose predicate signature must not change under refactors,
  (b) inference produces a different type than intended, or (c) the compiler
  version target is TS 5.4 or older. Never add explicit predicates for
  documentation only — they add a type assertion that drifts if the body
  changes.
