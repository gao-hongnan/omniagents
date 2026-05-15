---
name: typings
description: >-
  Use when writing or reviewing TypeScript 6.0+ with strict type-safety:
  tsconfig defaults and deprecations, explicit global types, rootDir / paths /
  moduleResolution, import attributes, generics with T-prefix names, branded
  types, discriminated unions with `never` exhaustiveness, Result types, Zod
  boundaries, `satisfies`, assertion functions, inferred type predicates,
  `using`, standard decorators, `unknown` vs `any`, or `// @ts-expect-error`.
when_to_use: >-
  Trigger for TypeScript files, tsconfig.json, eslint.config.* — typing
  design, TS 6.0 migration, strict checker failures, deprecation warnings,
  generics, branded types, discriminated unions, Result vs throw, Zod schema
  boundaries, `using` / Disposable, standard decorators, inferred type
  predicates, `satisfies`, assertion functions, const type parameters,
  template literal types, or public API typing reviews.
paths:
  - "**/*.ts"
  - "**/*.tsx"
  - "**/tsconfig*.json"
  - "**/package.json"
  - "**/eslint.config.*"
  - "**/.eslintrc.*"
---

# TypeScript Type-Safety Rules

TypeScript code in projects using this skill targets strict-by-default
type-checking — `tsc --strict`, ESLint with type-aware rules such as
`strictTypeChecked`, and Zod for runtime validation at boundaries. The bar is
not chosen for aesthetic reasons, but because TypeScript's type system buys
nothing when `any` is allowed to leak: every escape becomes a corner the
compiler stops checking, and the type system silently degrades from a
verification tool into a documentation overlay. The rules below state what is
load-bearing about that bar; the canonical examples in
`references/canonical-examples.md` show the accepted shapes.

This skill assumes **TypeScript 6.0+**. It keeps the useful TS 5.x-era
language features (standard decorators, `using` declarations / `Disposable`,
`NoInfer`, inferred type predicates, and `isolatedDeclarations`) and adds the
TS 6.0 configuration and semantics changes that prepare projects for
TypeScript 7.0. Code targeting TypeScript 5.9 or older must state that
constraint and avoid the TS 6.0-only assumptions called out below.

This skill is rules, not a tutorial. It assumes familiarity with generics,
discriminated unions, mapped types, conditional types, and template literal
types — what it specifies is which of the available patterns projects using
this skill have chosen, and which they have rejected.

## Non-negotiables

- All configured type checkers pass clean. No errors, no warnings — whether
  invoked individually (`tsc --noEmit`, `eslint .`) or together via project
  scripts. The set of checkers may grow; the bar does not.
- `strict: true` is mandatory in `tsconfig.json`, even though TS 6.0 defaults
  it to true. So are `noUncheckedIndexedAccess`,
  `exactOptionalPropertyTypes`, `noImplicitOverride`,
  `noFallthroughCasesInSwitch`, `noPropertyAccessFromIndexSignature`, and
  `noUncheckedSideEffectImports`. The `strict` flag alone is not sufficient;
  each option catches a different class of real bugs.
- `isolatedDeclarations: true` is required for libraries that ship type
  declarations. It rejects type positions that require full type inference to
  resolve, ensuring the `.d.ts` emitter does not need to re-run the type
  checker. Omit it for applications that do not publish declarations.
- New `// @ts-expect-error` requires the specific error code and a
  justification on the same line — e.g. `// @ts-expect-error TS2345:
  upstream type stub missing field in v1.4`. Bare `// @ts-ignore` is
  rejected on review.
- `any` is forbidden. Use `unknown` where the type is genuinely unknown and
  narrow it via type guards or `Zod` parsing. The escape valve is a single
  type assertion at the narrowing site, never a parameter or return type.
- Public function signatures are fully annotated, including return types.
  Private one-liners may rely on inference; non-trivial bodies may not —
  inferred return types leak implementation detail into the API surface.
- `import type { ... }` for type-only imports. `verbatimModuleSyntax: true`
  enforces this; do not work around it with side-effect imports.
- ES modules with explicit `.js` extensions in relative import paths when
  using NodeNext resolution (`import { foo } from "./bar.js";`). Use
  `module: "nodenext"` plus `moduleResolution: "nodenext"` for direct Node.js targets and
  `moduleResolution: "bundler"` for bundled apps or Bun. Do not use
  `moduleResolution: "node"` / `"node10"` or `"classic"` in new code.

## TypeScript 6.0 Semantics

- **Version-specific claims must be source-checked.** Before changing guidance
  tied to a TypeScript version, query Context7 or the official TypeScript
  release notes / handbook. Do not rely on memory for compiler defaults,
  deprecations, or narrowing behavior.
- **Treat TS 6.0 as the baseline, not a temporary migration target.** New code
  should satisfy TS 6.0 without `ignoreDeprecations: "6.0"`. That setting is
  allowed only as a short-lived migration marker with an inline comment or
  linked issue naming the deprecated option and removal plan.
- **Compiler defaults are explicit in shared configs.** TS 6.0 defaults
  `strict` to true, `module` to `esnext`, and `target` to the current-year
  ECMAScript version. Still write these values explicitly in reusable
  `tsconfig` bases so downstream packages do not depend on moving defaults.
  Direct Node.js packages use `module: "nodenext"`; bundled apps normally keep
  `module: "esnext"` with `moduleResolution: "bundler"`.
- **Global ambient types are explicit.** TS 6.0 defaults `compilerOptions.types`
  to `[]`. Add only the globals a project needs, e.g. `["node"]`,
  `["vitest/globals"]`, or `["jest"]`. `types: ["*"]` restores the old
  node_modules-wide scan and is rejected unless it is a documented migration
  escape hatch.
- **Set `rootDir` deliberately for emitting projects.** TS 6.0 defaults
  `rootDir` to the directory containing `tsconfig.json`. Libraries and apps
  that emit to `dist` should set `rootDir` explicitly, usually `"./src"`, so
  output paths do not change when files move.
- **Do not use `baseUrl` as a lookup root.** TS 6.0 deprecates `baseUrl`.
  Path aliases include their full prefix directly:
  `"@app/*": ["./src/app/*"]`, not `"baseUrl": "./src"` plus
  `"@app/*": ["app/*"]`. A catch-all `"*": ["./src/*"]` is permitted only
  when intentionally preserving old lookup-root behavior during migration.
- **Deprecated compiler options are not project policy.** New configs must not
  use `target: "es5"`, `module: "amd" | "umd" | "system" | "systemjs" | "none"`,
  `moduleResolution: "classic" | "node" | "node10"`, `outFile`,
  `downlevelIteration`, `alwaysStrict`, `suppressImplicitAnyIndexErrors`, or
  `keyofStringsOnly`. Do not set `esModuleInterop` or
  `allowSyntheticDefaultImports` to false.
- **Import attributes use `with`, not `assert`.** JSON and other attribute
  imports use `import data from "./data.json" with { type: "json" }`.
  `import ... assert { ... }` and dynamic import `assert` options are rejected
  in new code.
- **Command-line file checks must not bypass project config.** In a directory
  with `tsconfig.json`, use `tsc --noEmit -p tsconfig.json` or the project
  script. Do not run `tsc src/file.ts` expecting project options to apply.
- **DOM iterable libs are folded into `dom`.** New browser configs should not
  add `dom.iterable` or `dom.asynciterable` out of habit; include only the
  libs the project actually needs.

- **Standard decorators (TS 5.0) — not `experimentalDecorators`.** TypeScript
  5.0 shipped decorators per the TC39 Stage 3 proposal. Do not enable
  `experimentalDecorators` in new code; the two systems are incompatible.
  Standard decorators receive typed context objects (`ClassMethodDecoratorContext`,
  `ClassFieldDecoratorContext`, `ClassDecoratorContext`, etc.) alongside the
  decorated value. Decorator functions return `void` or a replacement value
  compatible with the decorated declaration. Remove `emitDecoratorMetadata` alongside
  `experimentalDecorators` when migrating.
- **`using` declarations (TS 5.2) — prefer over manual `try/finally` cleanup.**
  `using resource = acquire()` calls `resource[Symbol.dispose]()` at end of
  scope, whether the scope exits normally or via exception. `await using` does
  the same for async cleanup via `Symbol.asyncDispose`. Implement `Disposable`
  or `AsyncDisposable` for any resource that has a teardown step. This replaces
  the `try { … } finally { resource.close(); }` pattern; do not write new
  `try/finally` teardown blocks when `using` applies.
- **Inferred type predicates — explicit `x is T` is now often unnecessary.**
  TypeScript infers `x is T` return types for functions whose body is a
  narrowing expression. Write the predicate without the annotation first; add
  an explicit `x is T` return annotation only when inference produces the wrong
  type or when the predicate is part of a public API that must be stable across
  refactors. Do not write explicit predicates for documentation — they drift.
- **`NoInfer<T>` utility (TS 5.4) — block unwanted inference sites.** Wrap a
  type parameter occurrence in `NoInfer<T>` to prevent that position from
  contributing to inference. Canonical use:
  `function fallback<T>(value: T | undefined, def: NoInfer<T>): T`. Without
  `NoInfer`, the `def` argument can widen the inferred `T` unexpectedly.
- **`infer T extends SomeType` constraints (TS 4.7+) — bound inferred types.**
  `infer T extends string` infers `T` and narrows it to `string` in the true
  branch, eliminating a secondary `T extends string ?` guard. Use it to avoid
  double conditional nesting in template-literal and mapped-type helpers.
- **`Awaited<T>` for async return types.** Use `Awaited<ReturnType<typeof fn>>`
  rather than manually unwrapping `Promise<T>` levels. `Awaited` handles nested
  and thenable types correctly. Annotate the function's own return type
  directly; use `Awaited` in generic utility types that operate over async
  functions.

## Project conventions

- **T-prefix on descriptive type parameters.** `TKey`, `TValue`, `TItem`,
  `TResult`, `TInput`, `TOutput`, `TContext` — not `K`, `V`, `T`, `R`. A bare
  `T` is acceptable only when the parameter is genuinely opaque (a passthrough
  generic with no role). *Why:* checker errors and IDE hovers are far more
  legible when the parameter is named for its role; `Registry<string, MyConfig>`
  shows up as `TKey=string, TValue=MyConfig`, not `K=string, V=MyConfig`. (This
  is the TypeScript convention; the `python:typings` skill uses suffix-T
  because that is the Python convention. The asymmetry is deliberate.)
- **`interface` for object shapes; `type` for unions, primitives, mapped, and
  conditional types.** Interfaces extend and merge declaration-wise; types do
  not. Use each for what it is good at; do not pick by personal preference.
- **`unknown` over `any`.** `unknown` forces the consumer to narrow before
  use. `any` opts out of the type system entirely. The cost of narrowing is
  exactly what TypeScript is paying you to enforce; opting out via `any`
  defeats the purpose.
- **Discriminated unions with `never` exhaustiveness check.** State machines,
  parser results, and async lifecycles use a literal-string discriminator and
  a `default: const _exhaustive: never = state` branch. *Why:* an added
  variant breaks the build at every consumer instead of falling through
  silently.
- **Branded types for primitive identifiers.** `type UserId = Brand<string,
  "UserId">;` is mandatory for IDs that the system distinguishes
  semantically. *Why:* prevents `getUser(orderId)` at compile time;
  `string` arguments to a typed `getUser(id: string)` are indistinguishable.
- **`Result<T, E>` for functional error paths; `throw` at API boundaries.**
  Pick deliberately per function. Mixing the two in one function (sometimes
  returning `Result.err`, sometimes throwing) is rejected on review — the
  caller cannot pattern-match what they cannot see.
- **Zod at runtime boundaries.** HTTP input, file parse, env vars, and IPC
  payloads pass through a Zod schema first. Types are derived from the schema
  via `z.infer<typeof Schema>`, never written by hand and kept in sync — that
  duplication drifts.
- **Errors inherit from the project's base error and carry structured
  context.** New error classes pass a `Record<string, unknown>` context object
  to the base constructor. Bare `Error` subclasses without context are
  reserved for genuinely contextless failures.
- **No `console.log` in library code.** `console.warn` / `console.error` only,
  and only via the ESLint `no-console` allowlist. Anything else uses the
  project's logger.
- **No backwards-compatibility shims.** The codebase has no external API
  guarantees yet. Refactor by replacement: rename callers, delete dead code,
  flip enum values in the same change.
- **`enum` is rejected — use `as const` objects with type derivation.**
  TypeScript `enum` carries runtime cost, breaks tree-shaking, mishandles
  reverse mappings on numeric enums, and complicates `verbatimModuleSyntax`.
  The canonical replacement is an `as const` object plus a derived value
  union: `const TaskStatus = { Pending: "pending", … } as const;` followed by
  `type TaskStatus = (typeof TaskStatus)[keyof typeof TaskStatus];`. This
  gives compile-time exhaustiveness, avoids enum-specific emit and reverse
  mappings, and keeps members easy to tree-shake.
- **`satisfies` over `as` for type-checked literals.** Use
  `const config = { … } satisfies AppConfig;` when validating a literal
  against a type without widening it. `as` casts are reserved for the
  narrowing site of branded types (`raw as UserId` after a parse). A bare
  `as Foo` cast on a wider value is rejected on review — it silences the
  type checker rather than satisfying it.
- **Assertion functions (`asserts ... is ...`) for narrowing-with-throw.**
  When a runtime invariant must hold *and* the type system should narrow on
  return, declare the function with `asserts`. Use it where the alternative
  is a type guard plus an explicit `throw` at every call site —
  `assertDefined`, `assertOk`, schema-parse helpers.
- **`readonly` by default on data type properties.** Interfaces and type
  aliases describing data mark every property `readonly` unless mutation is
  the explicit point. Arrays use `readonly T[]`, maps use `ReadonlyMap`, sets
  `ReadonlySet`. *Why:* the cost of marking is one keyword; the cost of an
  accidental mutation is a debugging session.
- **`<const T>` type parameters when capturing literal types.** Without
  `const`, TypeScript widens `["a", "b"]` to `string[]` at the call site.
  With `<const T extends readonly unknown[]>`, the literal types survive —
  enabling types-from-data patterns where an `as const` array drives a
  derived union.
- **Template literal types for structured strings.** Route paths
  (`${HTTPMethod} /${string}`), event names (`${Domain}.${Action}`), CSS
  variables (`--${string}`), and any string with internal grammar use
  template literal types. Plain `string` parameters at these boundaries are
  rejected on review.
- **Standard decorators for cross-cutting class concerns only.** Use decorators
  for logging, validation, dependency injection, and instrumentation that is
  genuinely orthogonal to the class body. Decorator factories must be explicitly
  typed with the decorated value parameter and matching standard context type
  (`ClassMethodDecoratorContext`, `ClassFieldDecoratorContext`,
  `ClassDecoratorContext`, etc.). Return `void` or a compatible replacement
  value; do not use legacy decorator aliases or `any`.
- **`using` for all resource lifetimes.** Any object with a cleanup step (file
  handles, database connections, timers, observers) must implement
  `[Symbol.dispose]()` and be acquired with `using`. Bare `try/finally` blocks
  for resource teardown must not appear in new code.

## Narrowing and Predicates

- **Let TypeScript infer type predicates.** In the TS 6.0 baseline, if a
  function body is a narrowing expression, omit the explicit `x is T`
  annotation and verify the inference with `tsc`. Add an explicit predicate
  annotation only when: (a) the inferred form differs from the intended
  narrowing, or (b) the function is exported and the predicate signature must
  be stable across refactors.
- **`x is T` vs `asserts x is T`.** Use a type predicate when the caller
  branches on the result (`if (isUser(x))`). Use an assertion function when
  the caller expects a throw on violation and the type should narrow on
  return (`assertUser(x); x.name`). They are not interchangeable — an
  assertion function cannot be used as a filter predicate.
- **Array filter predicates.** `arr.filter(isString)` produces `string[]`
  when TypeScript can infer the predicate. If a TS 5.4-or-older project is
  still in scope, document that compiler constraint and add explicit
  `(x): x is string` predicates where required.
- **`never` exhaustiveness in switches.** The final branch of a discriminated
  union switch assigns the residual value to `never`:
  `const _check: never = value;`. This surfaces missing cases at compile time,
  not at runtime, and is preferable to a lone `default: throw`.

## References

Long-form supporting material is split out so the rules above stay
scannable on first read:

- [`references/decision-trees.md`](references/decision-trees.md) — "When in
  doubt" lookup pairs (`interface` vs `type`, `null` vs `undefined`, `Result`
  vs `throw`, `as` vs `satisfies`, type guard vs assertion function,
  `using` vs `try/finally`, TS 6.0 config choices, explicit predicate vs
  inferred predicate).
- [`references/canonical-examples.md`](references/canonical-examples.md) —
  fully-typed code patterns and TS 6.0 config examples (Registry, Plugin
  protocol, branded types, discriminated union with exhaustiveness,
  `Result<T, E>`, Zod-validated config, error hierarchy, `as const` enum
  replacement, assertion function, `satisfies` operator, template literal
  types, const type parameter, `using` / Disposable, `infer T extends`,
  inferred type predicate) written to pass strict type-checking and type-aware
  linting cleanly.
- [TypeScript release notes](https://www.typescriptlang.org/docs/handbook/release-notes/overview.html)
  are the primary version reference. The handbook is the runtime reference.
  Release posts are historical context; prefer the official docs when they
  disagree.

## What this skill is NOT

- **Not a TypeScript tutorial.** Every primitive used in the examples —
  generics, conditional types, mapped types, template literal types,
  branded types, discriminated unions, `as const`, `satisfies`, assertion
  functions (`asserts ... is ...`), const type parameters (`<const T>`),
  `readonly` modifiers, utility types (`Pick` / `Omit` / `Awaited` /
  `ReturnType`) — is documented at typescriptlang.org. Consult the
  handbook for mechanics; this skill specifies which patterns projects using
  this skill have chosen.
- **Not the source of truth for tool configuration.** In a consuming
  TypeScript project, that belongs in `tsconfig.json`, `eslint.config.*`,
  `package.json`, and the project's task runner.
- **Not exhaustive.** New project-specific opinions earn a rule here when they
  recur. One-off judgment calls live in code review and PR descriptions.
- **Not a migration guide.** It does not prescribe a step-by-step path from
  `experimentalDecorators` to standard decorators, or from manual `try/finally`
  to `using`. Those decisions belong in a dedicated migration PR. This skill
  specifies the target state for new code.
