---
name: software
description: >-
  Use when designing or reviewing Python code shape inside one service:
  module/class boundaries, GoF patterns, DDD, functional Result/Option/ADT
  shapes, in-process concurrency, package architecture, code smells,
  anti-patterns, refactors, "what pattern?", "where should X live?", or
  "how should I model this?". For cross-service or distributed concerns, use
  the system skill instead.
---

# Software Patterns — Inside One Service

Strict-typed Python 3.13+ patterns for shapes that live inside one
codebase: GoF, functional & ADTs, DDD, architectural layouts (hexagonal,
onion, clean, modular monolith, microservices boundary), in-process
concurrency, code-level anti-patterns. For cross-service concerns
(reliability across process boundaries, communication channels,
distributed coordination, data architecture, scaling, cloud topology),
load the `system` skill from this plugin instead.

## Default posture

Surface these non-negotiables when proposed code violates them. Point at
the exact reference rather than re-arguing from first principles.

- **Strict typing always.** Python 3.13+, `Protocol` over `ABC`, PEP 695
  generics (`class Foo[T]:`), PEP 604 unions (`X | Y`), `list[int]` not
  `List[int]`, `Self` for fluent returns, `Final` for constants, `@override`
  where applicable, and no `Any` leakage. Use the annotation-evaluation policy
  in the conventions section below; omit `from __future__ import annotations`
  only when runtime introspection genuinely requires evaluated annotations.
  Code blocks in this catalogue are written to target `mypy --strict` and
  `pyright --strict`.
- **Fail fast, fail explicitly, recover deliberately.** No silent
  fallbacks. No unbounded retries. No exception swallowing. No
  library-default timeouts. Every remote call has a timeout; every retry
  has a budget; every degraded mode is observable.
- **Smallest shape that satisfies the constraint.** Don't reach for
  Repository, Unit of Work, CQRS, Event Sourcing, Microservices, Saga,
  or a Visitor when a plain function over the ORM would do. Each
  pattern carries an *overkill threshold* — if you cannot name today's
  concrete pain, don't introduce it.
- **Encode invariants in types, not in services.** Anemic dataclasses +
  `*Service` mutators are an anti-pattern. Behaviour lives on the
  entity; orchestration lives in the service.
- **Make illegal states unrepresentable.** Wlaschin's framing — sum
  types, `NewType`, smart constructors, `frozen=True`, `Final`. The
  type checker does the work.
- **Pydantic at boundaries, dataclasses inside.** Pydantic is a
  first-class option for patterns whose values cross a trust boundary
  (Adapter, Command, Memento snapshots, Observer events on a bus,
  Specification predicates, configuration). In-process domain types
  stay `@dataclass(frozen=True, slots=True)`. Each pattern entry picks
  ONE primary example and adds a *When to switch* sub-note when the
  other shape is also viable. Pydantic snippets use
  `Annotated[T, Field(...)]` form, never bare `Field()` as a default; see
  the conventions section below.
- **Visualize structure or flow when it aids comprehension.** Each
  pattern entry includes at most one Mermaid diagram: `classDiagram`
  for structural collaboration, `sequenceDiagram` for call-flow
  behavioural patterns, `stateDiagram-v2` for state machines. Skip the
  diagram when the code is trivially self-explanatory.

## Pydantic & typing conventions assumed

Every Python block in this catalogue binds itself to these rules. They are
inlined here so the software-patterns skill remains correct even when no other
skill is loaded.

- **Strict-typed Python 3.13+.** Blocks target `mypy --strict` and
  `pyright --strict`: PEP 695 generics (`class Foo[T]:`), PEP 604 unions
  (`X | Y`), `list[int]` not `List[int]`, `Self` for fluent returns, `Final`
  for constants, and `@override` on subclass methods.
- **Protocol over ABC.** Use `Protocol` for structural extension contracts
  unless explicit registration, shared default behavior, or runtime subclass
  checks require an ABC.
- **No `Any` leaks.** Bare `Any` is forbidden outside I/O boundaries. Boundary
  adapters may carry one `cast` only with an inline reason comment naming the
  vendor docs reference.
- **Typed ignores only.** `# type: ignore` requires an error code and an inline
  reason: `# type: ignore[arg-type]  # third-party stub missing field X`. Bare
  `# type: ignore` is forbidden.
- **Suffix-`T` type parameters.** Prefer `KeyT`, `ValueT`, `ItemT`,
  `ReturnT`, `InputT`, and `OutputT`; never bare `T`, `K`, or `V`. Use PEP
  695 syntax such as `class Registry[KeyT, ValueT]:`, not
  `Generic[KeyT, ValueT]`.
- **Pydantic at boundaries, dataclasses inside.** Use Pydantic when a value
  crosses a trust boundary: deserialization, untrusted input,
  payload-on-the-wire, or configuration. Use
  `@dataclass(frozen=True, slots=True)` for in-process domain types.
- **Pydantic v2 always.** Use `Annotated[T, Field(...)]`; bare `Field()` as a
  default is forbidden. Boundary models add
  `model_config = ConfigDict(frozen=True, extra="forbid")` to reject unknown
  fields and prevent post-construction mutation.

The `python:typings` skill in the sister python plugin holds the full
canonical examples and rationale behind each rule. If both plugins are
installed, you can load it via the Skill tool when you need the deep reference,
but this catalogue does not require it to be loaded to be correct.

## Reference index

| File | Read when… |
| --- | --- |
| [`gof/index.md`](gof/index.md) | Choosing a class-level shape from the Gang of Four catalogue. Category navigation for all 23 patterns, with individual pages under `gof/creational/`, `gof/structural/`, and `gof/behavioral/`. Includes Pythonic rewrites for GoF patterns that often collapse into module state, top-level functions, Protocols, injected callables, or generators. |
| [`functional.md`](functional.md) | Reaching for Result/Either, Option/Maybe, ADTs (sum + product types), immutability, composition / pipelines, currying, railway-oriented programming, lenses, totality, smart constructors, the Functor/Applicative/Monad shapes-and-laws. Mix of Python with Rust (`Result<T, E>` + `?`-operator) and F#/Haskell intuition where it expresses the pattern more naturally. |
| [`ddd.md`](ddd.md) | Modelling a non-trivial domain. Tactical (Entity, Value Object, Aggregate Root with invariants, Repository, Domain Service, Domain Events, Specification, Factory, Module) and strategic (Bounded Context, Context Map, Anti-Corruption Layer, Shared Kernel, Customer/Supplier, Conformist, Open Host Service, Published Language, Big Ball of Mud as the *absence* of strategic design). |
| [`architectural.md`](architectural.md) | Deciding *where things live in the codebase*: layered / N-tier, hexagonal / ports & adapters (Cockburn), onion (Palermo), clean (Martin), modular monolith, microservices (Newman's "is the pain ≥ the cost"), in-process event-driven, plugin architecture, MVC / MVP / MVVM. Each entry has an `import-linter` / `grimp` boundary test. |
| [`concurrency.md`](concurrency.md) | Async / threads / processes inside one service: actor model (Erlang/Akka with Python equivalents), producer-consumer with bounded queues, pipeline / dataflow, in-process pub/sub, reader-writer locks, futures / promises, async/await + event loop, structured concurrency (`asyncio.TaskGroup`, Trio nurseries, Smith's "go statement considered harmful"), channels (Go-style with Python equivalents), fork-join. |
| [`anti-patterns.md`](anti-patterns.md) | Code review / refactor target: God Object, Anemic Domain, Feature Envy, Shotgun Surgery, Primitive Obsession, Stringly-Typed APIs / Booleans, Boolean Flag Parameters, Hidden Temporal Coupling, Happy-Path-Only Error Handling, Exception Swallowing, Over-Mocking, Premature Abstraction, Speculative Generality, Big Ball of Mud, Circular Imports, Leaky Abstractions, ISP / LSP violations, Dead Code Tolerance, Magic Numbers / Strings, Comments-as-Apology, Type Erosion (`Any` creep, `cast` everywhere), Mutable Default Arguments. Each entry pairs the *bad* code with a *fixed* version and the static-analysis rule that catches it. |

Read **only** the reference relevant to the current decision — every
file has a Table of Contents at the top; jump to the specific anchor.

## Decision flow

1. **Is this a structural decision?** New module / class boundary /
   dependency / failure-mode / data-shape, or a refactor of one. If no,
   skip this skill — these references are about *shape*, not algorithms
   or business logic.
2. **Pick the axis.**
   - Object collaboration → `gof/index.md`
   - Return shape, error shape, totality → `functional.md`
   - Domain modelling, bounded contexts → `ddd.md`
   - Package layout, dependency rule → `architectural.md`
   - Async / threads / processes inside one service → `concurrency.md`
   - Refactor target / code smell → `anti-patterns.md`
3. **Read the relevant reference.** Start at `gof/index.md` when
   choosing among patterns; jump directly to an individual pattern page
   when the pattern is already known. Each GoF pattern page follows a
   fixed shape: `Intent`, `Use When`,
   `Prefer A Simpler Python Shape When`, `Structure`,
   `Strict-Typed Python Sketch`, `Type-Safety Notes`,
   `Common Misuse`, `Real-World Examples`, `References` (with a
   stable Refactoring Guru URL where the pattern appears in their
   catalogue). Skim *Intent* and *Prefer A Simpler Python Shape When*
   before reading the full sketch.
4. **Apply the strict-typed sketch directly.** The references already
   account for `Protocol`, `Self`, `override`, `Final`, PEP 604/695.
   Don't re-derive ABC-heavy Java-style translations. Don't sprinkle
   `Any` to make types "easier" — the sketch already shows the
   type-clean form.
5. **Check the *When NOT to use* / overkill threshold before
   adopting.** Most patterns are wrong by default; they earn their
   place only against a specific named pain.

## Citing a specific section

Prefer citing the individual pattern page directly — for example
`gof/behavioral/strategy.md`,
`gof/behavioral/chain-of-responsibility.md`,
`anti-patterns.md#exception-swallowing`, or
`architectural.md#hexagonal-ports-and-adapters`. For intra-page sections,
anchor on the heading exactly as written; anchors are kebab-case slugs of
the heading text.

## What this skill does NOT cover

- **Cross-service / cross-process / distributed concerns** —
  reliability across process boundaries (timeout, retry, circuit
  breaker, bulkhead), communication channels (REST/gRPC/pub-sub),
  distributed coordination (saga, leader election, consensus), data
  architecture across services (CQRS, event sourcing, sharding,
  replication), scaling (cache, load balancing, autoscaling), cloud
  topology (sidecar, strangler fig, cell-based), distributed
  anti-patterns. Load the `system` skill from this plugin for those.
- **Vendor / library choices** (httpx vs requests, FastAPI vs
  Starlette, SQLAlchemy vs raw SQL) — the references show *shapes*,
  not vendor recommendations.
- **Test strategy** beyond *Over-Mocking in Tests* (in
  `anti-patterns.md`).

If a question lands outside this scope, say so rather than bending one
of the references to fit. If a question lands *inside* the scope but
the answer isn't in the references, that's a signal the catalogue
should be extended — flag it and propose the addition rather than
improvising silently.
