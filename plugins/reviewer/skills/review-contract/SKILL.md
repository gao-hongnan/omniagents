---
name: review-contract
description: >-
  Use when producing or consuming structured code review findings.
  Defines the shared output contract, severity rubric, finding format,
  per-specialist report template, and final aggregated report structure
  that all reviewer specialist agents must follow and the verifier
  agent enforces.
when_to_use: >-
  Trigger for any reviewer specialist agent (correctness, security,
  performance, design, testing) producing findings, or the verifier agent aggregating
  and deduplicating findings into a final review report. Also use
  when reviewing or validating structured review reports.
disable-model-invocation: false
user-invocable: false
---

# Review Contract

Every specialist agent in the reviewer plugin produces findings in
this exact format. The verifier agent enforces this contract when
aggregating.

## Dimensions

The reviewer specialist set is fixed: **correctness, security, performance,
design, testing**. This is the single source of truth for the dimension set —
the `/review` command dispatches one specialist per dimension, the
`Dimension` field below enumerates the same values, and the verifier expects
one report per dispatched dimension. Adding or removing a dimension means
updating this section, the `Dimension` field, the command's dispatch list,
and the matching specialist agent.

## Individual Finding Format

```markdown
- **[BLOCKER|IMPORTANT|SUGGESTION]** `path/to/file.py:42` -- summary
  - **Dimension**: correctness|security|performance|design|testing
  - **Why**: rule violated + consequence if not fixed
  - **Blast radius**: N direct callers, M transitive importers
  - **Fix**: concrete one-liner suggestion (do not implement)
  - **Confidence**: 0-100
```

### Required Fields

Every finding MUST include all six fields. Omitting any field is a
contract violation. Confidence MUST be an integer from 0 to 100.
If blast radius data is unavailable (no graph built), write
`Blast radius: graph unavailable -- severity based on code analysis only`.

### Confidence Rubric

- `90-100`: Direct evidence, clear consequence, likely actionable.
- `80-89`: Strong evidence with a small assumption about runtime or caller
  behavior.
- `70-79`: Plausible and worth surfacing for IMPORTANT or BLOCKER findings,
  but missing one piece of context.
- `<70`: Do not emit as a finding unless it is a BLOCKER candidate that the
  verifier must see.

## Severity Rubric

### BLOCKER

Will break callers, lose data, allow unauthorized access, or corrupt
state. The PR is unmergeable with a BLOCKER finding.

**Examples:**

- SQL injection in a user-facing endpoint
- Unchecked `None` dereference on a hot path with 100+ callers
- Race condition that corrupts shared state
- Missing authentication on a state-changing handler

### IMPORTANT

Materially harms maintainability, introduces a latent risk, or
violates a project convention the team enforces. Mergeable with a
tracked follow-up.

**Examples:**

- O(n^2) loop over a collection that will grow
- Bare `except` swallowing exceptions silently
- Hardcoded timeout without configuration
- Missing index on a filtered column in a new query

### SUGGESTION

Preferred style, minor improvement, or an observation that may not
warrant action. Non-blocking.

**Examples:**

- Variable name could be more descriptive
- Docstring missing on a public function
- Could use a context manager instead of try/finally
- Minor code duplication (< 5 lines)

## Severity Elevation Rule

A finding graded IMPORTANT whose blast radius (via
`get_impact_radius_tool`) shows **50+ transitive importers** is
automatically elevated to BLOCKER. The specialist MUST check blast
radius before finalizing severity for every IMPORTANT finding.

## Per-Specialist Report Template

Each specialist produces exactly this structure:

```markdown
# <Dimension> Review — <target>

## Findings

### BLOCKER

<findings or _None_>

### IMPORTANT

<findings or _None_>

### SUGGESTION

<findings or _None_>

## Summary

<2-3 sentence specialist-scoped verdict. State what was reviewed,
key risk areas, and whether the change is safe from this dimension's
perspective.>
```

## Final Aggregated Report Template

The verifier agent produces this structure after receiving all
specialist reports:

```markdown
# Code Review — <target>

## Summary

<3-5 sentences. State scope, languages, specialists invoked,
finding counts by severity, and the overall risk assessment.>

## Blast Radius

| Changed Symbol | Direct Callers | Transitive Importers | Flows |
|----------------|----------------|----------------------|-------|
| ...            | ...            | ...                  | ...   |

## Findings by Severity

### BLOCKER

<merged/deduped findings across all dimensions, tagged>

### IMPORTANT

<merged/deduped findings across all dimensions>

### SUGGESTION

<merged/deduped findings across all dimensions>

## Cross-Cutting Observations

<Findings where multiple specialists flagged the same location or
pattern. Cite both dimensions and explain the compound risk.>

## Verdict

<APPROVE | APPROVE WITH FOLLOWUPS | REQUEST CHANGES>

<Numbered list of top 3-5 actions in priority order.>
```

## Verdict Rules

- Any BLOCKER finding present: **REQUEST CHANGES**
- Only IMPORTANT findings (no BLOCKERs): **APPROVE WITH FOLLOWUPS**
- Only SUGGESTION findings (or no findings): **APPROVE**

## Deduplication Rules (Verifier)

When multiple specialists flag the same `file:line`:

1. **Same root cause**: merge into one finding, keep the highest
   severity, cite all dimensions in the finding
2. **Different root causes**: keep as separate findings, note the
   co-location in Cross-Cutting Observations
3. **Conflicting severity**: use the higher severity and note the
   disagreement

## Filtering Rules (Verifier)

Drop findings that:

- Lack a concrete `file:line` citation (the "no finding without
  evidence" rule)
- Are tagged SUGGESTION with `Confidence < 80`
- Are tagged IMPORTANT with `Confidence < 70`
- Are duplicates of a higher-severity finding at the same location
