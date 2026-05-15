# Python Type-Safety — Decision Trees

Reach-for guides for the recurring "which form do I use here?" questions
inside Python code that the consuming project type-checks under strict mypy,
pyright, pyrefly, or equivalent. Companion to `../SKILL.md`; the rules there
are non-negotiable, the choices below are decision pairs.

## When in doubt

- **ABC vs Protocol** → Protocol unless you genuinely need to share a default
  implementation. If the only thing the ABC contributes is `@abstractmethod`
  decorators, it is a Protocol with extra steps.
- **Generic class vs generic function** → function unless you need state across
  calls. `Registry[KeyT, ValueT]` is a class because it owns a dict;
  `first[ItemT](items: Iterable[ItemT]) -> ItemT | None` is a function
  because it does not.
- **Overload vs union return** → overload only when the input narrows the
  output type (e.g., `as_bytes: Literal[True]` → `bytes`, otherwise `str`). If
  the return is genuinely a union regardless of input, return a union.
- **Inheritance vs composition** → composition by default. Inheritance is for
  Protocol implementations and for tightly related concrete types — not for
  code reuse.
- **`pydantic.BaseModel` vs `TypedDict`** → BaseModel when validation matters
  (untrusted input). TypedDict when shape matters but validation does not
  (internal payloads with a known producer).
- **Bounded vs constrained TypeVars** → bounded (`[ItemT: SomeBase]`) when
  "any subtype of `SomeBase` works"; constrained (`[NumberT: (int, float,
Decimal)]`) when only a closed set of specific types makes sense. Bounded
  composes; constrained pins the call site to one of the listed types and
  blocks every other subtype, even valid ones — reach for it only when that
  pinning is the point.
- **TypeVar variance** → let PEP 695 infer it. The explicit
  `TypeVar(..., covariant=True)` / `contravariant=True` form (and conventional
  `KeyT_co`, `ValueT_contra` naming) is an exception to the suffix-T rule and
  is needed only when auto-inference cannot determine variance — typically
  when a Protocol's method signature forces a specific variance for soundness
  (e.g., a read-only container is covariant in its element type; a sink is
  contravariant). Reach for it consciously, not as a habit.
- **`type` alias vs `NewType` vs subclass** → `type X = Y` for a descriptive
  rename (`X` and `Y` interchangeable). `NewType("X", Y)` for a nominal
  distinction the checker enforces (`X` not assignable from `Y`, but identical
  at runtime). `class X(Y): ...` only when behaviour is attached — every
  other ID-like need is `NewType` or `type` alias.
- **`Literal[...]` vs `StrEnum`** → `Literal["a", "b"]` when the set lives
  in one signature. `StrEnum` once the same set is referenced from two or
  more places, or when iteration over members or a non-trivial `.value` /
  `.name` is needed. The promotion threshold is "second usage", not a
  matter of taste.
- **`TypeGuard` vs `TypeIs`** (3.13+) → `TypeIs[T]` (PEP 742) is strictly
  more precise: it narrows `T` in the `True` branch _and_ its negation in
  the `False` branch. `TypeGuard[T]` only narrows the `True` branch. Prefer
  `TypeIs` whenever the predicate is a genuine isinstance-style check; fall
  back to `TypeGuard` only when the predicate's negative does not soundly
  imply `not T`.
- **`TypedDict` vs `dataclass` vs `pydantic.BaseModel`** → `TypedDict` for
  dict-shaped values where the producer is trusted (typed `**kwargs` via
  `Unpack`, parsed JSON with a known schema). `@dataclass` for in-process
  domain types. `BaseModel` when validation must run at the boundary.
