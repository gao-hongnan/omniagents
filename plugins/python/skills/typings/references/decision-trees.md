# Python Type-Safety Decision Trees

Reach-for guides for recurring "which form do I use here?" questions in
Python code that the consuming project type-checks under strict mypy, pyright,
pyrefly, ty, or equivalent.

This is a companion to `../SKILL.md`. The rules there are non-negotiable; this
file explains how to choose between valid forms.

## Contracts And Structure

### ABC vs Protocol

Default to `Protocol` when the contract is public, plugin-facing, or intended
for independent implementations.

Use `Protocol` when:

- Structural conformance is the point.
- Implementations should not need to inherit from a project base class.
- The contract only names required attributes or methods.

Use `ABC` when:

- Shared default behavior belongs on the base type.
- Nominal registration or inheritance is part of the design.
- Runtime subclass checks are required.

If an ABC only contributes `@abstractmethod` decorators, it is probably a
Protocol with extra steps.

### Inheritance vs Composition

Default to composition.

Use inheritance when:

- Implementing a `Protocol`.
- Modeling tightly related concrete types.
- The subclass genuinely is a specialization of the base class.

Use composition when:

- Sharing behavior is the main goal.
- The relationship is "has a" rather than "is a".
- A smaller collaborator object would make the dependency clearer.

## Data Shapes

### BaseModel vs TypedDict

Default to `pydantic.BaseModel` for structured values that benefit from
validation, defaults, serialization, or an explicit schema.

Use `BaseModel` when:

- Input may be untrusted.
- Boundary validation is needed.
- Defaults, parsing, serialization, or schema generation are useful.
- The value is passed around as a named domain object.

Use `TypedDict` only when:

- The value must remain dict-shaped.
- Shape matters more than behavior.
- The value is typed `**kwargs` via `Unpack`.
- The value is a JSON-like payload or mapping interop object with a known
  producer.

### TypedDict vs Dataclass vs Plain Class vs BaseModel

Default to the smallest shape that preserves the contract, with a bias toward
`BaseModel` for structured data.

Use `BaseModel` when:

- Validation, defaults, serialization, or an explicit schema matter.
- The value crosses a boundary.
- The value benefits from Pydantic's parsing and model behavior.

Use `TypedDict` when:

- The value must stay dict-shaped.
- The producer is known and validation is not the type's job.
- Consumers use mapping operations directly.

Use `@dataclass` only when:

- The value is a lightweight internal record.
- Pydantic behavior would add no value.
- Record syntax is the clearest expression.

Use a plain class when:

- Behavior is central.
- Invariants or construction rules matter.
- Methods are more important than record fields.

## Generics

### Generic Class vs Generic Function

Default to a generic function unless state needs to live across calls.

Use a generic class when:

- The object owns state, such as a registry or cache.
- Multiple methods share the same type parameters.
- The type relationship must be preserved across method calls.

Use a generic function when:

- The operation is stateless.
- Type parameters only describe one call.
- A class would only wrap a single function.

Examples:

```python
class Registry[KeyT, ValueT]:
    ...

def first[ItemT](items: Iterable[ItemT]) -> ItemT | None:
    ...
```

### Bounded vs Constrained TypeVars

Default to a bounded type parameter.

Use a bound when:

- Any subtype of the base type should work.
- The API should compose with user-defined subclasses.

Use constraints only when:

- The allowed set is intentionally closed.
- Each call site must resolve to one of the listed concrete types.
- Blocking other subtypes is part of the design.

Examples:

```python
def read_name[ItemT: HasName](item: ItemT) -> str:
    ...

def parse_number[NumberT: (int, float, Decimal)](value: str) -> NumberT:
    ...
```

### TypeVar Variance

Default to PEP 695 inference.

Use explicit `TypeVar(..., covariant=True)` or
`TypeVar(..., contravariant=True)` only when auto-inference cannot determine
variance.

Common cases:

- A read-only container is covariant in its element type.
- A sink is contravariant in the value it accepts.
- A Protocol method signature may force a specific variance for soundness.

Explicit variance is an exception to the suffix-T naming rule. Conventional
names such as `ValueT_co` and `InputT_contra` are acceptable in those rare
cases.

## Return Types

### Overload vs Union Return

Default to a union return when the result is genuinely one of several types.

Use overloads only when an input value narrows the output type.

Use overloads for:

- `as_bytes: Literal[True]` returns `bytes`.
- `as_bytes: Literal[False]` returns `str`.
- A mode literal chooses a precise result type.

Use a union return for:

- Results that are genuinely variable regardless of input.
- Runtime outcomes the caller must inspect.

## Names And Closed Sets

### Type Alias vs NewType vs Subclass

Default to a `type` alias for descriptive renames.

Use `type X = Y` when:

- `X` and `Y` are interchangeable.
- The name improves readability only.

Use `NewType("X", Y)` when:

- The checker must distinguish `X` from raw `Y`.
- Runtime representation should stay identical.
- The type is an ID-like value.

Use `class X(Y): ...` only when:

- Behavior is attached.
- Runtime subclass identity matters.

### Literal vs StrEnum

Default to `Literal[...]` for one-signature closed sets.

Use `Literal["a", "b"]` when:

- The closed set appears in one signature.
- No iteration over values is needed.
- The values are simple and local.

Promote to `StrEnum` when:

- The same set appears in a second place.
- Callers need to iterate over members.
- `.name` or non-trivial `.value` behavior is useful.

The promotion threshold is second usage, not a matter of taste.

## Narrowing

### TypeGuard vs TypeIs

Default to `TypeIs[T]` on Python 3.13+.

Use `TypeIs[T]` when:

- The predicate is an `isinstance`-style check.
- The `True` branch narrows to `T`.
- The `False` branch soundly narrows to not `T`.

Use `TypeGuard[T]` when:

- Only the `True` branch can be narrowed safely.
- The negative branch does not imply not `T`.
- The narrowed type is not a subtype of the input type.

`TypeIs` is more precise because it narrows both the positive and negative
branches. `TypeGuard` narrows only the positive branch.
