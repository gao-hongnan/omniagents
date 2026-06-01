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

# Design Review Checklist

Review for maintainability costs that will make the next change harder. Do not
report taste. A design finding needs concrete evidence and a clear future cost.

## Boundaries and Layers

- Business logic embedded in controllers, CLI handlers, or UI components
- Persistence or transport details leaking into domain code
- Cross-layer imports that make dependency direction ambiguous
- Public API changes without migration path or compatibility note
- Module responsibilities that no longer match their names

## Coupling and Cohesion

- One change requires edits across many unrelated modules
- Function or class knows too much about another module's internals
- Data structures passed around only to let callees pick through fields
- Shared mutable state used as an implicit communication channel
- Utility modules becoming catch-all dependency magnets

## Abstraction Quality

- Interface exists only to wrap one implementation with no real variation
- Abstraction exposes internals through escape hatches
- Boolean flags that select different behaviors inside one function
- Generic names (`Manager`, `Helper`, `Processor`) hiding real responsibility
- Inconsistent abstraction level within one function or class

## Duplication and Change Amplification

- Same business rule copied in multiple places
- Similar branches that will diverge on the next requirement
- Repeated validation, serialization, or mapping logic without one owner
- Shotgun surgery risk: adding one field requires many manual edits

## Pattern Fit

- Pattern added without the forces that justify it
- Pattern omitted where the codebase already uses one consistently
- Strategy/command/factory used where a plain function would be clearer
- Inheritance used where composition would reduce coupling
- Framework idioms bypassed in ways that surprise maintainers

## Severity

Grade with the shared severity rubric and elevation rule from the preloaded
`review-contract` skill. Dimension calibration:

- A change to a public boundary or shared abstraction is the BLOCKER case —
  check blast radius before finalizing.
- A design issue that materially raises maintenance cost or breaks a project
  pattern is IMPORTANT.
- Local clarity or naming with low blast radius is SUGGESTION.
