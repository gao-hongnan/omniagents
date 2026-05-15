---
name: typings
description: >-
  Use when writing or reviewing TypeScript with `tsc --strict` and ESLint
  `strictTypeChecked` — designing generics with T-prefix names (TKey,
  TValue), branded types for identifiers, discriminated unions with `never`
  exhaustiveness, Result types, Zod at runtime boundaries with `z.infer`,
  `as const` objects over `enum`, `satisfies` over `as`, assertion
  functions, const type parameters, template literal types, `unknown` vs
  `any`, type-only imports, or `// @ts-expect-error` review.
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

This skill is rules, not a tutorial. It assumes familiarity with generics,
discriminated unions, mapped types, conditional types, and template literal
types — what it specifies is which of the available patterns projects using
this skill have chosen, and which they have rejected.

## Non-negotiables

- All configured type checkers pass clean. No errors, no warnings — whether
  invoked individually (`tsc --noEmit`, `eslint .`) or together via project
  scripts. The set of checkers may grow; the bar does not.
- `strict: true` is mandatory in `tsconfig.json`. So are `noUncheckedIndexedAccess`,
  `exactOptionalPropertyTypes`, `noImplicitOverride`, and
  `noFallthroughCasesInSwitch`. The `strict` flag alone is not sufficient — it
  does not enable the four above, and each catches a class of real bugs.
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
- ES modules with explicit `.js` extensions in import paths
  (`import { foo } from "./bar.js";`). NodeNext resolution is the norm.

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
  gives compile-time exhaustiveness, zero runtime cost, and tree-shakeable
  members.
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

## References

Long-form supporting material is split out so the rules above stay
scannable on first read:

- `references/decision-trees.md` — "When in doubt" lookup pairs (`interface`
  vs `type`, `null` vs `undefined`, `Result` vs `throw`, `as` vs
  `satisfies`, type guard vs assertion function, etc.).
- `references/canonical-examples.md` — 12 fully-typed code patterns
  (Registry, Plugin protocol, branded types, discriminated union with
  exhaustiveness, `Result<T, E>`, Zod-validated config, error hierarchy,
  `as const` enum replacement, assertion function, `satisfies` operator,
  template literal types, const type parameter) written to pass strict
  type-checking and type-aware linting cleanly.

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
