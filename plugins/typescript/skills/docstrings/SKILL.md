---
name: docstrings
description: >-
  Use when writing or reviewing TypeScript API documentation for exported
  modules, classes, functions, methods, types, interfaces, properties, TSDoc
  tags, TypeDoc output, compile-checkable examples, or JSDoc interop in
  legacy JavaScript.
---

# TSDoc Style Convention

The default style for projects using this skill is **TSDoc** — the
standardized doc-comment grammar maintained by Microsoft and consumed by
TypeDoc, the language service, and `eslint-plugin-tsdoc`. Public APIs
(anything `export`ed from a module, plus public class members) carry
structured doc comments. Type information lives in annotations; doc comments
describe **semantics** — what the function *means*, not what its parameter
types are.

## TSDoc style (default)

A doc comment opens with `/**`, has a one-line summary paragraph, a
blank-line-delimited remarks paragraph (optional), then `@`-tags in
order. **Omit any tag that doesn't apply** (don't keep empty
placeholders).

```typescript
/**
 * Return `[quotient, remainder]` from integer division.
 *
 * Wraps the built-in `Math.trunc` / `%` pair with an explicit
 * `RangeError` contract so callers can recover gracefully from a zero
 * denominator without monkey-patching the operator.
 *
 * @param numerator - The integer being divided.
 * @param denominator - The integer divisor; must be non-zero.
 * @returns A two-tuple of `[quotient, remainder]` from
 *   `Math.trunc(numerator / denominator)` and `numerator % denominator`.
 * @throws {@link RangeError} If `denominator` is `0`.
 *
 * @example
 * ```typescript
 * divmodSafe(7, 3);   // [2, 1]
 * divmodSafe(10, 5);  // [2, 0]
 * ```
 */
export function divmodSafe(
    numerator: number,
    denominator: number,
): readonly [number, number] {
    if (denominator === 0) {
        throw new RangeError("denominator must be non-zero");
    }
    return [Math.trunc(numerator / denominator), numerator % denominator];
}
```

### Required tags by API kind

- **Exported function or public method** — short summary line, blank
  line, optional remarks paragraph, then:
  - `@param` (required for each parameter, in declaration order)
  - `@returns` (required when the return type is not `void`)
  - `@throws` (required for each exception type the function can throw
    deliberately; reference the class with `{@link ErrorName}`)
  - `@example` (required when behavior is non-obvious — e.g. eviction
    semantics, mutation surprises). Examples MUST compile under the
    project's `tsconfig.json`.
- **Exported class** — short summary line, blank line, optional
  remarks paragraph. Per-member doc comments live on each member, NOT
  on the class. The class doc covers *purpose* and one canonical
  `@example`. Public properties get their own doc comments at the
  property declaration site (TSDoc has no `@property` analog to
  `Attributes`; the property's own comment is the source of truth).
- **Exported `type` / `interface`** — short summary line; per-property
  doc comments inline at each property declaration. Use `@remarks` for
  invariants the type itself can't express.
- **Module** — a top-of-file `/** ... */` block (or `@packageDocumentation`
  block) explaining *why* the module exists, not *what* it does. The
  "what" is discoverable from the names; the "why" is what code
  archaeology needs.

### Runnable examples

The `@example` tag uses fenced code blocks tagged `typescript` (or
`ts`). TSDoc supports multiple `@example` tags per item; each takes one
canonical scenario.

```typescript
/**
 * @example Hit and miss
 * ```typescript
 * const cache = new LRUCache<string, number>({ maxSize: 2 });
 * cache.set("a", 1);
 * cache.get("a");        // 1
 * cache.get("missing");  // undefined
 * ```
 */
```

These compile under `tsc --noEmit` when extracted by TypeDoc or
`eslint-plugin-tsdoc`. Keep them short (3-6 lines is plenty). Their
job is "show the canonical use case in 30 seconds of reading," not
"prove correctness" — Vitest / Jest tests handle that.

### Don't repeat type information

Type annotations are the source of truth for types. The doc-comment
prose describes semantics, invariants, and edge cases. **Wrong:**

```typescript
/**
 * Get a value.
 *
 * @param key - The key (a TKey).
 * @returns The value (a TValue) or undefined.
 */
get(key: TKey): TValue | undefined;
```

**Right:**

```typescript
/**
 * Look up a value, promoting it to most-recently-used on hit.
 *
 * @param key - Lookup key. A miss is silent; the cache state is
 *   unchanged.
 * @returns The stored value when `key` is present, otherwise
 *   `undefined`. On a hit, the entry is moved to the most-recently-used
 *   slot so subsequent eviction passes consider it last.
 */
get(key: TKey): TValue | undefined;
```

The "Right" version tells the reader what the method *does*, which
they can't get from `(key: TKey) => TValue | undefined` alone.

## JSDoc style (alternative — for legacy code only)

```typescript
/**
 * Return [quotient, remainder] from integer division.
 *
 * @param {number} numerator - The integer being divided.
 * @param {number} denominator - The integer divisor; must be non-zero.
 * @returns {[number, number]} [quotient, remainder] two-tuple.
 * @throws {RangeError} If denominator is 0.
 */
```

JSDoc duplicates the type annotations as `{type}` in tags, which TSDoc
explicitly forbids — TypeScript already knows the types, and the
duplication drifts. Use JSDoc only when interfacing with a `.js` file
that has no `.d.ts` and where the type annotations live in the comment.
Prefer TSDoc for all `.ts` / `.tsx` files unless the consuming project is
documenting legacy `.js` with JSDoc-owned types.

## Anti-patterns

- **Empty tag placeholders.** If a function has no `@throws`, *omit*
  the tag. `@throws None.` is worse than nothing.
- **Repeating annotations as prose.** `@param key {string} - the key`
  when the signature already says `key: string`. Wastes the reader's
  time and drifts when the signature changes.
- **Doc-comment-as-comment.** `/** Get a value. */` on a method named
  `get` is zero information. Either say something the name doesn't
  (semantics, side effects, edge cases) or omit the doc comment.
- **Missing `@packageDocumentation` on entry-point modules.** Even one
  sentence helps: *"LRU cache used by the request middleware to
  short-circuit duplicate signature lookups."*
- **`@example` blocks that don't compile.** A snippet with undefined
  imports or stale signatures rots silently. `eslint-plugin-tsdoc`
  validates TSDoc *syntax* but does not type-check the code inside an
  `@example` block — keep examples short, prefer signatures the reader
  can compile in their head, and lift any non-trivial scenario into a
  `*.test.ts` file that the test runner exercises.
- **Including `{type}` annotations in TSDoc.** TSDoc forbids JSDoc-style
  type tags — they conflict with the type system. The signature has
  the type; the doc comment has the meaning.
- **Doc comments on internal helpers.** A non-exported `function
  _normalize(...)` that lives one screen below its only caller doesn't
  need a TSDoc block. Save the structure for the public surface.

## Notes

- "Public" means **exported** from the module, **or** declared with the
  `public` modifier on a class. Non-exported helpers and `private` /
  `protected` members don't need this treatment, though a one-line
  `// comment` describing a non-obvious invariant is welcome.
- Mark exported-but-not-stable APIs with `@internal` so TypeDoc
  excludes them from generated documentation while still exposing them
  to in-tree consumers.
- Properties: the doc comment goes on the property declaration. For
  `get` / `set` accessor pairs, the doc comment goes on the getter; the
  setter inherits.
- Async functions follow the same shape as sync; the `async` keyword
  doesn't change documentation conventions. The `@returns` describes
  the resolved value, not the `Promise` wrapper — TSDoc is aware of
  `Promise<T>` and unwraps it for you.
- Mark deprecated APIs with `@deprecated <reason and migration path>`
  in the tag block, not buried in prose. The TypeScript language
  service surfaces this in IDE hovers and as a strikethrough at the
  call site.
- Reference other symbols with `{@link OtherSymbol}` rather than
  bare-text names — TypeDoc renders these as hyperlinks, and the
  language service validates the target exists.
- Generic type parameters are documented with `@typeParam <TName> -
  <description>` in the same tag block as `@param` / `@returns`. The
  T-prefix from the `typings` skill (`TKey`, `TValue`,
  `TItem`) usually makes the role obvious at a glance — document only
  when the parameter carries a non-obvious constraint or invariant.
