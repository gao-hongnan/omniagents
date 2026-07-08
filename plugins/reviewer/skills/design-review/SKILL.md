---
name: design-review
description: >-
  Use when reviewing code for maintainability issues such as coupling,
  cohesion, abstraction leaks, boundary drift, code smells, naming problems,
  duplicated logic, premature generalization, or design-pattern misuse.
when_to_use: >-
  Trigger for design code review: high coupling, low cohesion, leaky
  abstraction, unclear boundary, misplaced responsibility, feature envy,
  shotgun surgery, long function, duplicated logic, primitive obsession,
  boolean flag parameter, god object, premature abstraction, inconsistent
  local pattern, misleading name, SOLID violation, layer violation.
disable-model-invocation: false
user-invocable: false
---

# Design Review — Hunt Protocols

Find maintainability costs that make the **next change** harder, riskier, or
easier to get wrong. Design findings are predictions, so they carry the
heaviest evidence burden: every one names the concrete future edit that gets
more expensive. If you cannot name that edit, it is taste — drop it.

## Hunts

Execute every hunt whose `When` matches; skip the rest. Exemplars are
calibration anchors, never templates — do not copy their wording into
reports.

### Hunt: Next-Change Simulation

- **When**: a new abstraction, module, or data shape — or one logical
  change that required edits across several files.
- **Protocol**:
    1. Pick the most plausible next requirement in this area (new field,
       new variant, new consumer) — plausible means signaled by the domain
       or git history, not invented.
    2. Walk that edit: enumerate the files and sites it must touch.
    3. Three or more scattered, compiler-unassisted edits — or one that is
       easy to miss — is change amplification. One or two cohesive edits is
       normal.
- **Evidence bar**: the named next change plus the enumerated edit sites.
- **Falsifiers**: the scattered sites are generated from one source; the
  type checker forces all of them (a missed one fails the build); the next
  change is pure speculation with no domain signal.
- **Exemplar**: IMPORTANT 82 — "adding one notification channel touches
  four files (enum, factory, config parser, dispatcher) with no compiler
  help; git history shows channels added quarterly." / **Noise twin**: a
  model change plus its migration — two files, inherent to the framework.

### Hunt: Convention Drift

- **When**: new code lands inside an existing package.
- **Protocol**:
    1. Glob and read 2–3 sibling modules of the same kind (handler beside
       handlers, repository beside repositories).
    2. Compare structure: naming, error idiom, construction/DI pattern,
       layering, return shapes.
    3. Silent divergence is the finding — cite the sibling that
       establishes the pattern.
- **Evidence bar**: a named sibling establishing the local pattern, plus
  the divergence.
- **Falsifiers**: the diff is an intentional migration to a new pattern
  (commit message or ADR says so); the siblings disagree among themselves
  (no convention exists); the divergence is invisible to consumers and
  defensibly equivalent — reconciliation rule.
- **Exemplar**: IMPORTANT 80 — "every other repository class returns
  domain objects; the new one returns raw rows, pushing mapping into both
  its callers." / **Noise twin**: f-strings where siblings use `.format`
  — behaviorally identical; the author's call.

### Hunt: Boundary Leak

- **When**: the diff adds import edges between modules or layers.
- **Protocol**:
    1. List the new edges — `query_graph_tool` `imports_of` on changed
       modules, or read the import blocks.
    2. Classify each edge's direction against the codebase's layering:
       does domain now import infra, UI import persistence?
    3. Flag transport/persistence types (ORM rows, request objects, wire
       DTOs) crossing into domain logic, and any new cycle.
- **Evidence bar**: the import edge, the direction it violates, and the
  cost (e.g. domain logic now untestable without a DB).
- **Falsifiers**: the codebase is deliberately flat (no layering to
  violate); the importer is the composition root, whose job is to know
  everything.
- **Exemplar**: IMPORTANT 83 — "the pricing-rules module now imports the
  framework request object to read one header — pricing becomes untestable
  without an HTTP context; pass the value in instead." / **Noise twin**:
  `main.py` importing both domain and infra to wire them together.

### Hunt: Duplicate Logic

- **When**: a new function implements validation, mapping, formatting, or
  a business rule.
- **Protocol**:
    1. Search for an existing owner of the same rule —
       `semantic_search_nodes_tool` and Grep by the **domain noun**
       (the rule's subject), not the new function's name.
    2. If found, compare: is it the same rule, and will both copies have
       to change together on the next requirement?
    3. The finding is the divergence risk; cite both sites.
- **Evidence bar**: both implementations cited, plus the shared rule
  named.
- **Falsifiers**: the resemblance is coincidental — different invariants
  that evolve separately; the copy is a deliberate seam (vendored,
  boundary isolation) and documented as such.
- **Exemplar**: IMPORTANT 81 — "invoice renderer reimplements money
  formatting; `shared/format.py` already owns the rounding rule — the
  next rounding change forks behavior." / **Noise twin**: a username
  validator and a slug validator that merely look alike — different
  invariants.

### Hunt: God-Growth

- **When**: the diff edits an already-large module, class, or function.
- **Protocol**:
    1. Size the host — `find_large_functions_tool` on changed files; note
       responsibility count, not just lines.
    2. Ask whether the diff **adds an unrelated responsibility** (a new
       reason to change) or extends the existing one.
    3. Only the trajectory is in scope: flag what the diff worsens, not
       the pre-existing size (What Not to Report).
- **Evidence bar**: the new responsibility named, plus why it has a
  different reason to change than its host.
- **Falsifiers**: the addition is cohesive with the module's single
  responsibility; the "god object" complaint is about untouched code.
- **Exemplar**: IMPORTANT 78 — "`UserService` (900 lines) gains email
  template rendering — a presentation concern; template edits now risk
  user logic." / **Noise twin**: a fifth validation rule added to a module
  whose whole job is validation.

### Hunt: Speculative Abstraction

- **When**: a new interface, ABC, factory, strategy, or plugin layer.
- **Protocol**:
    1. Count implementations (`inheritors_of`) and call sites
       (`callers_of`).
    2. One implementation, one consumer, and no concrete second use in
       sight = indirection without variation.
    3. Price the indirection: how many files does a reader traverse to
       find the behavior?
- **Evidence bar**: the implementation/caller counts plus the traversal
  cost.
- **Falsifiers**: a test fake with real value counts as a second
  implementation (isolating a heavy dependency is legitimate variation);
  the interface is the codebase's established extension idiom; the
  boundary wraps a dependency that genuinely gets swapped.
- **Exemplar**: SUGGESTION 82 — "factory + abstract base with exactly one
  implementation and one caller; the behavior now lives three files from
  its use — inline until a second implementation exists." / **Noise
  twin**: an ABC with one production implementation and an in-memory fake
  exercised across the test suite.

### Hunt: Shallow Wrapper (Deletion Test)

- **When**: the diff adds a module, class, or function that mostly forwards to
  one collaborator, or whose interface is nearly as wide as the implementation
  it hides.
- **Protocol**:
    1. List its callees and callers — `query_graph_tool` `callees_of` and
       `callers_of` on the new symbol. A single callee it forwards to is the
       first signal.
    2. Apply the deletion test: inline the unit into its callers. Does
       complexity concentrate back across them (real work was hidden), merely
       relocate one hop unchanged, or vanish (callers get simpler)?
    3. Compare interface surface to behaviour hidden: what must a caller still
       know — parameters, ordering, error modes, return sentinels — that the
       wrapper failed to encapsulate? A pass-through that re-exposes the
       collaborator's contract is the finding.
- **Evidence bar**: the forwarded callee plus what the caller must still know
  despite the wrapper.
- **Falsifiers**: it is a real seam (≥2 implementations — a test fake isolating
  a heavy dependency counts); it adapts a true-external boundary; it hides a
  genuinely complex sequence (retry, parse, error-mapping) behind the one call.
- **Exemplar**: SUGGESTION 80 — "`UserRepo.get()` forwards 1:1 to
  `session.get()` and re-exposes its exception set; deleting it removes a hop
  and hides nothing." / **Noise twin**: a repository that hides query
  construction, row mapping, and caching behind `get_active_users()` — one call,
  real work hidden.

### Hunt: Public Contract Drift

- **When**: the diff changes the shape of an exported API — signature,
  return type, exception set, wire format.
- **Protocol**:
    1. Count consumers — `importers_of` / `get_impact_radius_tool`.
    2. Check the migration affordance: deprecation path, compat shim,
       version note, changelog entry.
    3. Verify "internal" claims: a symbol is only internal if the graph
       shows no external importers.
- **Evidence bar**: the breaking shape change, the consumer count, and
  the missing migration affordance.
- **Falsifiers**: every consumer is updated in this same diff (atomic
  change); the graph confirms zero external importers; a semver-major
  release where breaking is the documented point.
- **Exemplar**: IMPORTANT 84 — "`parse_config` now raises instead of
  returning None; 23 importers, 4 updated here — the other 19 inherit a
  new crash path silently. (50+ importers would elevate to BLOCKER.)" /
  **Noise twin**: a breaking rename whose diff updates every caller, with
  the graph confirming none remain.

## Severity Anchors

Grade with the contract's Severity Rubric and elevation rule. In this
dimension:

- **BLOCKER**: a public boundary or shared abstraction change that breaks
  consumers now, or an IMPORTANT finding whose blast radius crosses the
  elevation threshold.
- **IMPORTANT**: materially raises maintenance cost or breaks a project
  pattern the team enforces — with the next-edit cost named.
- **SUGGESTION**: local clarity or naming with low blast radius and a
  concrete payoff.

## Recall Sweep

After the hunts, sweep the diff once against these. Flag only what passes
the contract's Taste Test:

- Boolean flag parameters selecting between behaviors in one function.
- Generic names (`Manager`, `Helper`, `Processor`, `Util`) hiding the real
  responsibility; names that misstate behavior.
- Mixed abstraction levels inside one function; escape hatches exposing an
  abstraction's internals.
- Inheritance where composition would decouple; framework idioms bypassed
  in ways that surprise maintainers.
- Feature envy: data structures passed around only to be field-picked by
  callees.
- Shared mutable state as an implicit communication channel; catch-all
  utility modules accreting dependencies.
