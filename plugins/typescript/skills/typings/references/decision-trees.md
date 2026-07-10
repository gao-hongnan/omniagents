# TypeScript Type-Safety Decision Trees

Reach-for guides for recurring "which form do I use here?" questions in
TypeScript code that the consuming project type-checks under `tsc --strict`
plus type-aware ESLint rules such as `strictTypeChecked`.

This is a companion to `../SKILL.md`. The rules there are non-negotiable; this
file explains how to choose between valid forms.

## Type Shapes

### Interface vs Type

Default to `interface` for object shapes.

Use `interface` when:

- The type describes an object shape.
- Extension with `extends` is expected.
- Declaration merging is useful or intentionally allowed.
- The shape is part of a public object contract.

Use `type` when:

- The type is a union.
- The type is a primitive alias.
- The type is a mapped, conditional, or template literal type.
- The type is a tuple.

These forms are not interchangeable for the cases above; use each for what it
does best.

### Inferred vs Explicit Return Types

Default to explicit return types on public surfaces.

Use explicit return types when:

- The function is exported.
- The function is part of an interface, class, or callback contract.
- The body is non-trivial.
- Consumers should not observe implementation-detail changes.

Use inferred return types when:

- The function is private.
- The body is a one-liner.
- The inferred type is obvious and not part of a public API.

Inference for non-trivial bodies can leak implementation detail into the
signature and break consumers when the implementation changes.

### As Const Object vs Enum

Default to an `as const` object.

The trigger is call sites, not declarations: a parameter typed `string` that
only ever receives a fixed set of bare literals is already a closed set —
type it before the literals multiply.

Use `as const` objects when:

- You need a closed value set.
- You want derived value unions.
- Tree-shaking and zero extra runtime machinery matter.
- `verbatimModuleSyntax` compatibility matters.

Do not use TypeScript `enum` in new code. Runtime cost, reverse mappings on
numeric enums, tree-shaking issues, and module semantics are language-design
problems with `enum`, not tradeoffs to rebalance per call site.

## Absence And Unknown Values

### Null vs Undefined

Default to `undefined` for absence.

Use `undefined` when:

- A value is not set.
- A field is optional.
- A field has never been assigned.
- The distinction between "absent" and "explicitly empty" does not matter.

Use `null` only when:

- "Explicitly empty" has semantics distinct from "not set".
- An external system returns `null`, such as a JSON column or database field.
- The wire format requires `null`.

When in doubt, use `undefined`.

### Unknown vs Any

Default to `unknown`.

Use `unknown` when:

- Input type is genuinely not known yet.
- A runtime check, type guard, or Zod schema will narrow the value.
- You are modeling untrusted input.

Use `any` only for documented interop escape hatches, and keep the leak at the
smallest possible narrowing site.

## Errors And Results

### Result vs Throw

Default deliberately per function; do not mix both in one error path.

Use `throw` when:

- The function is at an API or package boundary.
- Callers are expected to handle exceptions.
- The failure is exceptional rather than a normal branch in a pipeline.

Use `Result<T, E>` when:

- Callers want pattern-matched outcomes.
- The function is part of an internal pipeline.
- Parsing, validation, or domain branching is the normal control flow.

Throw across package boundaries; return `Result` within internal pipelines.

## Identifiers And Brands

### Branded Type vs Class Wrapper For IDs

Default to a branded primitive for identifiers.

Use a branded type when:

- The runtime representation should remain a string or number.
- Formatting, comparison, serialization, or URL building should keep working
  like the underlying primitive.
- The checker must prevent mixing semantically different IDs.

Use a class wrapper when:

- Behavior is attached to the identifier.
- Construction performs validation or normalization.
- Runtime identity or methods matter.

## Checking And Assertion

### Satisfies vs As

Default to `satisfies` for type-checked literals.

Use `satisfies` when:

- You want to validate a literal against a type.
- You want to preserve the narrower inferred literal type.
- You are checking configuration objects, route maps, or registry tables.

Use `as` only when:

- You are at a deliberate narrowing site.
- A wider runtime value has already been validated.
- Branding requires a cast after parsing.

A bare `as Foo` on a wider value silences the checker; it does not prove the
value satisfies `Foo`.

### Type Guard vs Assertion Function

Default to a type guard when the caller wants to branch.

Use a type guard (`x is T`) when:

- The caller needs an `if` / `else` branch.
- Both success and failure are normal outcomes.
- The function answers a predicate question.

Use an assertion function (`asserts x is T`) when:

- The caller expects the function to throw on failure.
- The function establishes an invariant for the rest of the scope.
- The alternative would be a guard plus repeated manual throws.

### Explicit Type Predicate vs Inferred Predicate

Default to inferred predicates on the TS 6.0 baseline.

Omit the explicit `x is T` annotation when:

- The function body is a narrowing expression.
- The predicate uses `typeof`, `instanceof`, or a discriminant check.
- The inferred predicate is the intended public behavior.

Add an explicit `x is T` annotation when:

- The function is exported and the predicate signature must remain stable
  across refactors.
- Inference produces a different type than intended.
- The compiler target is TS 5.4 or older.

Do not add explicit predicates for documentation only; they act like type
assertions and can drift from the body.

## Resources

### Using Declaration vs Manual Try/Finally

Default to `using` or `await using`.

Use `using` when:

- The acquired value implements `Disposable`.
- You control the resource type and can add `[Symbol.dispose]()`.
- Cleanup should happen at the end of scope on normal and exceptional exits.

Use `await using` when:

- The acquired value implements `AsyncDisposable`.
- Cleanup is asynchronous.

Use manual `try/finally` only when:

- You are integrating with a third-party API that cannot implement
  `[Symbol.dispose]()` or `[Symbol.asyncDispose]()`.
- The cleanup shape cannot be represented by `Disposable` / `AsyncDisposable`.

If you control the resource type, implementing `Symbol.dispose` is preferable
to scattering `try/finally` at every acquisition site.

## TS Config

### NodeNext vs Bundler Module Resolution

Choose based on who resolves imports at runtime.

Use `nodenext` when:

- Emitted code runs directly in Node.js.
- Node package exports and extension rules must apply.
- Relative ESM imports need explicit `.js` paths.

Use `bundler` when:

- Vite, Next.js, esbuild, Rollup, Webpack, Bun, or another bundler resolves
  imports.
- The project is an app or package compiled through a bundling step.

Do not use `node`, `node10`, or `classic` in new TS 6.0 configs.

### Paths With BaseUrl vs Explicit Path Targets

Default to explicit path targets.

Use explicit path targets:

```json
{
  "paths": {
    "@app/*": ["./src/app/*"]
  }
}
```

Avoid `baseUrl` as a lookup root:

```json
{
  "baseUrl": "./src",
  "paths": {
    "@app/*": ["app/*"]
  }
}
```

A catch-all `"*": ["./src/*"]` is a migration-only choice when preserving old
`baseUrl` behavior is deliberate.

### Explicit Types vs Implicit Globals

Default to explicit `types`.

List only ambient packages used by the project:

- `["node"]`
- `["vitest/globals"]`
- `["jest"]`

Use `["*"]` only as a temporary migration escape hatch.

### Explicit RootDir vs Inferred Emit Root

Default to explicit `rootDir` for emitting projects, usually `"./src"`.

Set `rootDir` when:

- The project emits JavaScript or declarations.
- Output layout must stay stable as files move.
- The package is a library or app that writes to `dist`.

Relying on old common-source-directory inference can change output layout under
TS 6.0 defaults.

### Import Attributes With vs Import Assertions Assert

Default to `with`.

Use import attributes:

```ts
import data from "./data.json" with { type: "json" };
```

Do not use deprecated import assertions:

```ts
import data from "./data.json" assert { type: "json" };
```
