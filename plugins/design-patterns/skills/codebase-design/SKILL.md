---
name: codebase-design
description: >-
  Use when designing or improving a module's interface, judging whether a
  wrapper or layer earns its keep, deciding where a seam belongs, or making code
  testable through its interface. Supplies the interface-depth vocabulary — deep
  vs shallow modules, information hiding, the deletion test, seams, design it
  twice. The depth lens that complements the pattern catalogue: it answers "is
  this interface earning its complexity?", not "which pattern?".
---

# Codebase Design — Interface Depth

The `software` and `system` skills in this plugin are a *catalogue* — they
answer *which shape* to reach for. This skill answers a different question about
any shape you pick: **is the interface earning its complexity?** A module's
interface is the cost every caller pays; its hidden behaviour is the benefit. A
**deep** module returns a lot of behaviour for a small interface; a **shallow**
one exposes almost as much as it hides.

Reach for it when designing a new boundary, deciding whether a wrapper or layer
should exist, placing a seam, or making code testable through its interface
rather than its internals.

## Default posture

Surface these when a proposed boundary violates them; name the principle rather
than arguing from taste.

- **Depth beats count.** Maximize behaviour hidden per interface point.
  Splitting one deep module into many small ones usually *adds* interface
  without hiding more — that is classitis, not modularity.
- **Information hiding is the mechanism.** A module is deep because it hides a
  decision — a wire format, a retry budget, an index layout. The moment that
  decision leaks into the interface (callers must know it to use the module),
  depth collapses. Leakage is the failure mode, not line count.
- **A seam needs two implementations.** A port/`Protocol` is justified only when
  a second implementation exists — production plus a test fake that isolates a
  heavy dependency counts. One implementation behind an interface is indirection
  without variation (see [`../software/anti-patterns.md`](../software/anti-patterns.md),
  speculative generality).
- **Assert through the interface.** Tests that drive the module as a caller does
  and check observable outcomes survive refactors; tests that name internal
  collaborators bet the implementation never changes.

## Vocabulary

Precise terms; the other skills and the `design-review` hunt reference them.

- **Module** — any unit with an interface and a hidden implementation: function,
  class, package, or service.
- **Interface** — everything a caller must understand to use the module: the
  signature *and* the names, ordering rules, error modes, side effects, and
  invariants. Informal obligations count, not just the types.
- **Implementation** — the machinery behind the interface.
- **Depth** — behaviour hidden ÷ interface surface. Deep = much behaviour, small
  interface.
- **Shallow module** — interface nearly as wide as the behaviour it hides; the
  caller pays almost the full implementation cost through the interface.
- **Seam** — a boundary where one implementation can replace another without
  touching callers. Real only with ≥2 implementations.
- **Leverage** — caller-side benefit: how much one interface point does for the
  caller. **Locality** — maintainer-side benefit: a hidden decision changes in
  one place, not at N call sites.

## Deep vs shallow

**Shallow** — forwards one-to-one, hides nothing:

```python
class UserStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: int) -> User | None:
        return self._session.get(User, user_id)  # 1:1 forward
```

The caller still has to know the session's exception set, that `None` means
"missing", and the transaction boundary. The wrapper added a hop and hid none of
it.

**Deep** — one interface point hides a round-trip, a bounded retry, a timeout,
parsing, and error mapping into a domain type:

```python
class PricingClient:
    """Resolve a quote. Hides transport, retry budget, timeout, and parsing."""

    def quote(self, sku: str, *, region: str) -> Money:
        # round-trip + bounded retry + timeout + parse + map errors → Money
        ...
```

The whole interface is `quote(sku, *, region) -> Money`; everything else is
hidden from every call site.

## The deletion test

The fastest way to grade a boundary: mentally inline the module into its callers
and watch what complexity does.

- It **reappears across many callers** → the module concentrated real
  complexity. It earned its place (deep).
- It **relocates one hop, unchanged**, hiding nothing → shallow; question it.
- It **vanishes** and callers get simpler → it was a pass-through; delete it.

Depth is not line count: a 20-line module can pass, a 2-line wrapper can fail.

## Designing for testability

- **Substitute at owned seams.** For a dependency you own, define a narrow port
  (`Protocol`) with a production adapter and a test fake. Drive the port.
- **Inject true-external deps.** For a third-party API you do not own, inject the
  client so a double replaces it at the boundary — do not mock your own
  internals.
- **Assert observable outcomes** — returned value, persisted state, emitted
  event — never the internal call sequence.

## Reference index

| File | Read when… |
| --- | --- |
| [`references/deepening.md`](references/deepening.md) | Merging shallow, interdependent modules into one deeper module: deciding whether the dependency between them can be substituted in-process or must stay behind a seam, and re-testing at the new interface. |
| [`references/design-it-twice.md`](references/design-it-twice.md) | Choosing a module's interface: generating two or three genuinely different designs, each optimizing a different axis, then picking by depth, locality, and seam placement. |

## Decision flow

1. **Is this an interface decision?** A new boundary, a wrapper, a port, or a
   refactor that moves one. If it is algorithm or business logic, this skill
   does not apply.
2. **Measure depth.** Weigh everything a caller must know against everything
   hidden. When the surface approaches the implementation, it is shallow.
3. **Run the deletion test.** Concentrate, relocate, or vanish?
4. **Pick the reference.** Merging modules → [`references/deepening.md`](references/deepening.md).
   Choosing among interface shapes → [`references/design-it-twice.md`](references/design-it-twice.md).
5. **Confirm the seam is real (≥2 implementations) before adding a port.**

## What this skill does NOT cover

- **Which pattern to use** — GoF, DDD, functional, architectural layout,
  in-process concurrency. Load the `software` skill from this plugin (via the
  Skill tool); this skill only judges whether the chosen shape earns its
  interface.
- **Cross-service / distributed shape** — timeouts, retries, circuit breakers,
  CQRS, sharding. Load the `system` skill from this plugin.
- **Reviewing a diff** — the `reviewer:design-review` skill turns the deletion
  test into its *Shallow Wrapper* hunt; use it when reviewing rather than
  designing.

## Rejected framings

- **Deep ≠ "small files."** Splitting a deep module into many small ones adds
  interface without hiding more.
- **Deep ≠ "more layers."** A pass-through layer that re-exposes the layer below
  is shallow by construction — adjacent layers at the same abstraction.

## Provenance

The deep-module framing, information hiding, and "design it twice" are from John
Ousterhout, *A Philosophy of Software Design* (2nd ed.). This skill is an
omniagents house adaptation of those ideas — original prose and strict-typed
Python 3.13+ examples; no third-party text is reproduced.
