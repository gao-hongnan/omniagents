---
name: typings
description: >-
  Use when writing or reviewing Python 3.14+ with strict type-safety enforced:
  generics with PEP 695 syntax, annotationlib / deferred annotations,
  Protocol vs ABC, ParamSpec decorators, TypeIs / TypeGuard narrowing,
  TypedDict / ReadOnly, Literal vs StrEnum, NewType vs aliases, or any time
  mypy / pyright / pyrefly / ty is configured, run, or failing.
when_to_use: >-
  Trigger for Python files, pyproject typing configuration, strict checker
  failures, type annotation design, runtime annotation introspection,
  PEP 695 generics, PEP 696 defaults, PEP 705 ReadOnly TypedDict keys,
  PEP 742 TypeIs predicates, PEP 649 / PEP 749 deferred annotations, decorator
  signatures, Protocol boundaries, NewType identifiers, enum/literal choices,
  or public API typing reviews.
disable-model-invocation: false
user-invocable: true
allowed-tools: []
model: inherit
paths:
  - "**/*.py"
  - "**/pyproject.toml"
shell: bash
---

# Python Type-Safety Rules

This project maintains a strict-by-default type-safety bar across every
configured type checker. The exact set is recorded in the consuming project's
tooling config (commonly mypy, pyright, pyrefly, ruff, ty, and a `typecheck`
target); what matters here is the rule, not the inventory. The cost of a
single `Any` leak compounds: types decay outward from the leak site,
mechanical refactors become exploratory, and bugs that should fail at the
boundary surface in unrelated modules.

This skill assumes **Python 3.14+**. It uses the modern syntax and semantics
from [PEP 695](https://peps.python.org/pep-0695/), [PEP 696](https://peps.python.org/pep-0696/),
[PEP 705](https://peps.python.org/pep-0705/), [PEP 742](https://peps.python.org/pep-0742/),
[PEP 649](https://peps.python.org/pep-0649/), and [PEP 749](https://peps.python.org/pep-0749/).
The canonical examples in `references/canonical-examples.md` show accepted
shapes; the decision table in `references/decision-trees.md` handles common
trade-offs.

This skill is rules, not a tutorial. It assumes familiarity with `TypeVar`,
`Protocol`, `ParamSpec`, `TypeGuard`, `TypeIs`, `TypedDict`, `Annotated`,
and `NewType`. It specifies which patterns projects using this skill have
chosen and which they have rejected.

## Non-negotiables

- All configured type checkers pass clean. No errors, no warnings, whether
  invoked individually (`uv run mypy`, `uv run pyright`, `uv run pyrefly`,
  `uv run ty check`) or together through the project typecheck target. The set of checkers may grow; the bar does not.
- New `# type: ignore` requires both an error code and an inline reason:
  `# type: ignore[arg-type]  # third-party stub missing field X`. Bare
  `# type: ignore` is rejected on review.
- `Any` is forbidden in internal code. It is permitted only at I/O boundaries
  such as CLI parsing, JSON ingest, and untyped third-party APIs, and only
  with a comment explaining the leak.
- Public function and method signatures are fully annotated, including return
  types. Private helpers may omit return annotations only when the body is a
  single expression.
- Never weaken a type to silence a checker. If a check fails, fix the type or
  fix the code; do not cast, `Any`, or `# type: ignore` your way out.
- Use `Self` from [PEP 673](https://peps.python.org/pep-0673/) for fluent,
  builder, and classmethod constructors that return the current class.
  When annotating `cls` explicitly in a classmethod, write
  `cls: type[Self]`, not `cls: type[BaseClass]`; the latter breaks subclass
  return inference.
  String-quoted forward references like `-> "QueryBuilder"` are forbidden in
  new code.

## Python 3.14 Annotation Semantics

- **Do not add `from __future__ import annotations` just for forward
  references.** Python 3.14 uses deferred annotation evaluation by default
  under [PEP 649](https://peps.python.org/pep-0649/) and
  [PEP 749](https://peps.python.org/pep-0749/). Plain forward references in
  annotations no longer need string quoting.
- **Keep the future import only for compatibility with older supported
  interpreters.** If a consuming project still supports Python 3.11-3.13,
  keep the import consistently until that compatibility target is dropped.
  In Python 3.14-only code, new modules should omit it.
- **Runtime annotation introspection uses `annotationlib`.** Code that reads
  annotations at runtime must use
  [`annotationlib.get_annotations()`](https://docs.python.org/3/library/annotationlib.html#annotationlib.get_annotations)
  or [`typing.get_type_hints()`](https://docs.python.org/3/library/typing.html#typing.get_type_hints)
  deliberately. Choose `annotationlib.Format.VALUE`, `FORWARDREF`, or
  `STRING` based on whether unresolved names should raise, become
  `ForwardRef` values, or remain source strings.
- **Do not parse `__annotations__` internals directly.** Python 3.14 changed
  the runtime model for annotations; direct reads are easy to get wrong when
  annotations are deferred or contain unresolved imports.
- **Use `TYPE_CHECKING` only to avoid runtime imports.** Undefined symbols in
  annotations are harmless until annotation introspection evaluates them, but
  static checkers still need imports guarded by `if TYPE_CHECKING:` when a
  type lives in an expensive or cyclic module.

## Project Conventions

- **Use [PEP 695](https://peps.python.org/pep-0695/) generic syntax.**
  `class Registry[KeyT, ValueT]:` and
  `def first[ItemT](items: Iterable[ItemT]) -> ItemT | None:` are mandatory.
  Module-level `TypeVar` / `ParamSpec` declarations followed by `Generic[T]`
  subclassing are rejected when ruff `UP046` / `UP047` are enabled. The legacy
  form is permitted only in `.pyi` stubs, vendored third-party code, and the
  rare Protocol variance cases called out in `references/decision-trees.md`.
- **Type parameter names use the `...T` suffix.** Prefer `KeyT`, `ValueT`,
  `ItemT`, `ReturnT`, `InputT`, and `OutputT` over bare `T`, `K`, `V`, or `R`.
  Single-letter names are reserved for `ParamSpec` (`**P`) and variadic type
  parameters (`*Ts`) when the conventional form is clearer.
- **Use [PEP 696](https://peps.python.org/pep-0696/) defaults sparingly.**
  Defaults for `TypeVar`, `ParamSpec`, and `TypeVarTuple` are appropriate
  when the default preserves the obvious common case. Do not use defaults to
  hide ambiguous APIs or to make partial specialization harder to see.
- **Protocol over ABC.** Extension points are structural, not nominal. Use an
  ABC only when sharing default method implementations is the actual reason to
  subclass.
- **`@runtime_checkable` only when `isinstance` is genuinely needed.** Protocol
  conformance is a static check by default; runtime-checkable Protocols are
  for plugin loaders and dynamic dispatch, not the default decoration.
- **Prefer `collections.abc` generics.** Import `Callable`, `Iterable`,
  `Iterator`, `Generator`, `AsyncGenerator`, `Mapping`, `Sequence`, and
  similar ABCs from `collections.abc`, not deprecated aliases in `typing`.
- **`Generator` / `AsyncGenerator` for context-manager return types.**
  `@contextmanager` functions return `Generator[YieldT]`; `@asynccontextmanager`
  functions return `AsyncGenerator[YieldT]`. Python 3.13+ defaults the send
  and return type parameters, so avoid noisy `Generator[YieldT, None, None]`
  unless a checker or public API requires it.
- **`ParamSpec` for decorators that wrap user callables.** Anything preserving
  the wrapped function's call signature uses `ParamSpec`:
  `def traced[**P, ReturnT](fn: Callable[P, ReturnT]) -> Callable[P, ReturnT]`.
  Plain `Callable[..., Any]` decorators are forbidden in typed package code.
- **`TypeIs` before `TypeGuard`.** Use
  [`TypeIs`](https://docs.python.org/3/library/typing.html#typing.TypeIs)
  from [PEP 742](https://peps.python.org/pep-0742/) for sound
  `isinstance`-style predicates because it narrows both true and false
  branches. Use `TypeGuard` only when the narrowed type is not a subtype of
  the input type or the negative branch cannot be narrowed safely.
- **Errors carry structured context.** New exceptions inherit from the
  project's base error type and pass `context: dict[str, object]` to the base.
  Bare-string `Exception` subclasses are reserved for genuinely contextless
  failures.
- **Pydantic at boundaries, dataclasses inside.** `pydantic.BaseModel` is for
  values crossing an I/O boundary. `@dataclass` is for in-process domain
  types. `TypedDict` is for structured dictionaries when validation is not the
  type's job.
- **Use [`ReadOnly`](https://docs.python.org/3/library/typing.html#typing.ReadOnly)
  for immutable `TypedDict` keys.** A `TypedDict` field that consumers must not
  mutate should be annotated with `ReadOnly[...]` from
  [PEP 705](https://peps.python.org/pep-0705/). Remember this is enforced by
  type checkers, not at runtime.
- **Numpy/Sphinx docstrings only when warranted.** Public API and non-obvious
  invariants get a docstring. Most internal code does not. When written, use
  Parameters, Returns, Raises, and Examples sections.
- **No backwards-compatibility shims.** The codebase has no external API
  guarantees yet. Refactor by replacement: rename callers, delete dead code,
  and flip enum values in the same PR.
- **`uv` is the only Python invoker.** Use `uv run mypy`, `uv run pytest`,
  `uv run python ...`. Never use bare `python` or `pip`.

## Aliases, NewTypes, and Closed Sets

- **Type aliases use the [PEP 695](https://peps.python.org/pep-0695/)
  `type` statement.** Use `type UserId = str`,
  `type Cache[KeyT, ValueT] = OrderedDict[KeyT, tuple[ValueT, float]]`, and
  recursive aliases such as `type JSONValue = str | int | float | bool | None
  | list[JSONValue] | dict[str, JSONValue]`. Module-level
  `X: TypeAlias = ...` is rejected in new code.
- **`NewType` for nominal id-like distinctions.** Use
  `UserId = NewType("UserId", str)` when the checker must distinguish
  `UserId` from a raw `str` despite identical runtime representation. Use
  `type UserId = str` only when it is a readability alias.
- **`StrEnum` / `IntEnum` for closed string and integer sets.** Module-level
  string constants describing one closed set collapse into a `StrEnum`
  subclass with `auto()`. Use `IntEnum` for numeric protocol codes and
  `Flag` / `IntFlag` when bitwise combination is the point.
- **`Literal[...]` for ad-hoc closed sets in one signature.** Promote to
  `StrEnum` the moment the same set appears in a second signature.
- **`LiteralString` from [PEP 675](https://peps.python.org/pep-0675/) for
  SQL, shell, and format-string parameters.** Functions that compose user
  input into queries or commands take `LiteralString`, not `str`, so the
  checker rejects untrusted strings at the call site.

## Overrides, Metadata, and Exhaustiveness

- **`@override` from [PEP 698](https://peps.python.org/pep-0698/) on every
  override.** Pyright flags missing decorators in strict mode. The decorator
  catches silent drift when a base method is renamed and the override
  accidentally becomes a new method.
- **`Annotated[T, ...]` for typed metadata.** Pydantic `Field`, Typer
  `Option` / `Argument`, and validation or serialization hints must travel
  alongside the type. Prefer `Annotated[int, Field(ge=0)]` over
  `x: int = Field(ge=0)`.
- **`Final` for module-level constants and class attrs not meant to be
  reassigned.** Use `MAX_RETRIES: Final = 3` and
  `Final[frozenset[str]]` for immutable container constants.
- **`assert_never` in unreachable exhaustive branches.** A new variant added
  to a discriminated union must break the build at every `case _:` or final
  `else`, not silently fall through at runtime.

## References

- [`references/decision-trees.md`](references/decision-trees.md) - lookup
  pairs for ABC vs Protocol, bounded vs constrained type variables, `Literal`
  vs `StrEnum`, `TypeGuard` vs `TypeIs`, and related choices.
- [`references/canonical-examples.md`](references/canonical-examples.md) -
  strict examples for Registry, Protocol, ParamSpec decorator, narrowing,
  error hierarchy, builder, overload, aliases, NewType, StrEnum,
  discriminated union, and Annotated + Pydantic.
- [Python 3.14 `typing` docs](https://docs.python.org/3/library/typing.html)
  and [Python 3.14 `annotationlib` docs](https://docs.python.org/3/library/annotationlib.html)
  are the runtime references. PEPs are historical design records; prefer the
  current docs when they disagree.

## What This Skill Is Not

- **Not a Python type-system tutorial.** Consult the Python docs for mechanics.
  This skill specifies project policy.
- **Not the source of truth for tool configuration.** In a consuming Python
  project, that belongs in `.ruff.toml` / `pyproject.toml`, `.mypy.ini`,
  `pyrightconfig.json`, and the task runner or `Makefile`.
- **Not exhaustive.** New project-specific opinions earn a rule here when they
  recur across PRs. One-off judgment calls live in code review, not in this
  skill.
