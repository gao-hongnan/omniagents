---
name: review-contract
description: >-
  Use when producing or consuming structured code review findings.
  Defines the shared output contract, severity rubric, finding schema,
  per-specialist report shape, and final aggregated report shape
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

Every specialist agent in the reviewer plugin produces findings as **JSON**, and
the verifier aggregates them into a single JSON report. **JSON is the canonical
artifact; the human-readable Markdown is _rendered_ from it** by `schema.py`
(beside this file). Agents never hand-write the Markdown report.

The machine-enforceable half of this contract is
`${CLAUDE_PLUGIN_ROOT}/skills/review-contract/schema.py` (stdlib only — runs with
any `python3`). Run `python3 schema.py --schema` to print the field-by-field
shape. The `/review` command validates and renders with it. A finding that omits
`file` or `line` **fails validation and is never rendered** — that is how this
contract guarantees every finding a human reads carries a jump-to-able
`file:line` citation.

## Dimensions

The reviewer specialist set is fixed: **correctness, security, performance,
design, testing**. This is the single source of truth for the dimension set —
the `/review` command dispatches one specialist per dimension, the `dimension`
field below enumerates the same values, and the verifier expects one report per
dispatched dimension. Adding or removing a dimension means updating this section,
the `DIMENSIONS` tuple in `schema.py`, the command's dispatch list, and the
matching specialist agent.

## Review Method

The difference between a reviewer people trust and one they mute is not how
many findings it produces — it is whether each finding survives scrutiny.
Checklists are recall aids for phase 2, not quotas. Every specialist works in
three phases:

1. **Understand the change before judging it.** Read the commit messages and
   any PR description the dispatcher provided — they state intent, and a
   subtle bug is usually a mismatch between intent and implementation. Read
   changed files **in full, not just the hunks**: a line that looks wrong in
   isolation is often guarded twenty lines above the hunk. Identify the
   consumers of every changed symbol (graph `callers_of` / `importers_of`,
   or Grep) before deciding what the change can break.

2. **Hunt for what the diff should have changed but did not.** The bugs that
   embarrass reviewers are omissions, invisible in the hunks themselves: a
   renamed field with one stale call site, a new enum case missing from one
   `match`, a sibling implementation left inconsistent, a changed default
   not propagated to config/docs/migrations, a bug fix applied to one copy
   of a duplicated block. Enumerate the places that mirror, consume, or
   duplicate the changed code and check each one.

3. **Falsify before you report.** For every candidate finding, actively try
   to prove yourself wrong before emitting it: look for an upstream guard, a
   type-system guarantee, a framework behavior, an invariant that makes the
   "bad" input unreachable, or an existing test that pins the behavior. Most
   false positives die here. Report only what survives, and when the
   falsification attempt was non-obvious, record what you checked in the
   finding's `why` ("no None-guard upstream: checked both call sites in
   api/routes.py").

An empty `findings` array produced by this method is a **success** — it is
the report that the change is clean along your dimension. Never pad a report
to justify the dispatch.

## What Not to Report

Every low-value finding costs trust that the high-value findings need. Do
not report:

- **Pre-existing issues on lines the diff does not touch** — unless
  BLOCKER-grade (data loss, exploit, corruption), and then prefix the
  summary with `[pre-existing]` so the author knows it is not their
  regression.
- **Anything a formatter, linter, or type checker will catch** — unused
  imports, line length, formatting, missing annotations that `mypy`/`tsc`
  already flags. CI does this cheaper.
- **Speculative concerns** — "could be a problem if…" without a concrete,
  reachable trigger in this codebase. Name the input, caller, or
  configuration that triggers it, or drop it.
- **Taste** — style preferences with no behavioral or maintenance
  consequence, docstring/comment nits, alternative idioms of equal merit —
  unless the repo's own conventions (`REVIEW.md`, `CLAUDE.md`) demand them.
- **Narration of the diff** — observations that describe what changed
  without identifying a problem.

## Finding Schema

Every finding is a JSON object with these fields (enforced by `schema.py`):

```json
{
  "severity": "BLOCKER | IMPORTANT | SUGGESTION",
  "file": "repo-relative/path.py",
  "line": 42,
  "end_line": 58,
  "dimension": "correctness | security | performance | design | testing",
  "summary": "one-line description of the problem",
  "why": "rule violated + consequence if not fixed",
  "blast_radius": "N direct callers, M transitive importers",
  "fix": "concrete one-liner suggestion (do not implement)",
  "confidence": 92
}
```

The object above renders to this Markdown line (note the always-present
backtick-fenced citation):

```markdown
- **BLOCKER** `auth/login.py:42-58` — one-line description of the problem
  - **Dimension**: correctness
  - **Why**: rule violated + consequence if not fixed
  - **Blast radius**: N direct callers, M transitive importers
  - **Fix**: concrete one-liner suggestion (do not implement)
  - **Confidence**: 92
```

### Required Fields

`severity`, `file`, `line`, `dimension`, `summary`, `why`, `blast_radius`,
`fix`, and `confidence` are all **required**. There is no finding without a
confirmed `file` and `line`.

- **`file`** — path relative to the repo root, e.g. `auth/login.py`. Not a bare
  filename, not an absolute path.
- **`line`** — integer ≥ 1, the start line of the problem. **Confirm it by
  reading the file (the `Read` tool returns `cat -n` line numbers) or by locating
  the line in the `git diff` hunk. The code-review-graph returns symbols, not
  line numbers — never cite a line you have not confirmed against the file or the
  diff.**
- **`end_line`** — optional integer ≥ `line`; set it when the issue spans a range
  (renders as `file:line-end_line`). Omit or `null` for single-line issues.
- **`dimension`** — the producing specialist's dimension. (The verifier emits
  `"dimensions": ["correctness", "security"]` instead when it merges a finding
  flagged by more than one specialist.)
- **`blast_radius`** — `"N direct callers, M transitive importers"`. If no graph
  is built, use `"graph unavailable -- severity based on code analysis only"`.
- **`confidence`** — integer 0–100 (see rubric).

### Confidence Rubric

Confidence is **the probability that a maintainer who investigates will agree
this is a real, reachable problem worth fixing** — not your certainty about
what the code does. Grade it after the falsification pass (see Review
Method), and grade against these anchors:

- `90-100`: Direct evidence, clear consequence, falsification attempted and
  failed — you traced the trigger.
- `80-89`: Strong evidence with one small assumption about runtime or caller
  behavior that you could not fully verify.
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

## Specialist Report (JSON)

Each specialist returns **exactly one JSON object and nothing else** — no
Markdown, no prose wrapper, a single fenced `json` code block. The `/review`
command writes it to `.reviews/<timestamp>/NN_<dimension>.json` and renders
`NN_<dimension>.md` with `python3 schema.py specialist`.

```json
{
  "dimension": "correctness",
  "target": "<the review target>",
  "date": "YYYY-MM-DD",
  "graph_available": true,
  "findings": [],
  "summary": "2-3 sentence specialist-scoped verdict: what was reviewed, key risk areas, and whether the change is safe from this dimension's perspective."
}
```

`findings` holds Finding objects (schema above); use `[]` when there are none.
Set `graph_available` to `false` if the code-review-graph was empty.

## Aggregated Review Report (JSON)

The verifier returns **exactly one JSON object and nothing else** — a single
fenced `json` code block. The `/review` command writes it to
`.reviews/<timestamp>/review.json` and renders `review.md` with
`python3 schema.py review`.

```json
{
  "target": "<the review target>",
  "date": "YYYY-MM-DD",
  "author": "<git user name>",
  "summary": "3-5 sentences: scope, languages, specialists invoked, finding counts by severity, overall risk.",
  "verdict": "APPROVE | APPROVE WITH FOLLOWUPS | REQUEST CHANGES",
  "blast_radius": [
    {"symbol": "login()", "direct": 12, "transitive": 63, "flows": "auth-request"}
  ],
  "findings": [],
  "cross_cutting": [
    {"file": "auth/login.py", "line": 42, "dimensions": ["correctness", "security"], "note": "why the co-location compounds risk"}
  ],
  "actions": ["top 3-5 actions in priority order"],
  "specialist_reports": ["01_correctness.md", "02_security.md", "03_performance.md", "04_design.md", "05_testing.md"]
}
```

In `findings`, a finding flagged by multiple specialists carries
`"dimensions": ["correctness", "security"]` instead of a single `dimension`.
Every finding's `file` and `line` are preserved **verbatim** from the specialist
report — the verifier never collapses a citation.

## Rendered Output Layout

The `/review` command persists every run under a git-ignored folder:

```
.reviews/<timestamp>/
  01_correctness.json / .md   02_security.json / .md   03_performance.json / .md
  04_design.json / .md        05_testing.json / .md
  review.json                 # canonical aggregated report (verifier output)
  review.md                   # headline human-readable report
.reviews/latest -> <timestamp>
```

`review.md` is the headline artifact; the per-dimension files preserve each
specialist's full findings.

## Verdict Rules

- Any BLOCKER finding present: **REQUEST CHANGES**
- Only IMPORTANT findings (no BLOCKERs): **APPROVE WITH FOLLOWUPS**
- Only SUGGESTION findings (or no findings): **APPROVE**

## Deduplication Rules (Verifier)

When multiple specialists flag the same `(file, line)`:

1. **Same root cause**: merge into one finding, keep the highest severity, list
   every dimension in the finding's `dimensions` array.
2. **Different root causes**: keep as separate findings, note the co-location in
   `cross_cutting`.
3. **Conflicting severity**: use the higher severity and note the disagreement in
   the merged finding's `why`.

## Filtering Rules (Verifier)

Drop findings that:

- Lack a concrete `file` + `line` (schema validation also enforces this — the
  "no finding without evidence" rule)
- Are tagged SUGGESTION with `confidence < 80`
- Are tagged IMPORTANT with `confidence < 70`
- Are duplicates of a higher-severity finding at the same location
- Violate **What Not to Report**: pre-existing issues below BLOCKER (or
  missing the `[pre-existing]` prefix), linter/type-checker territory,
  speculative `why` with no concrete trigger, taste, or diff narration

The final bar for every surviving non-BLOCKER finding: **would a staff
engineer raise this in a real PR review, or would it read as noise?** When
in doubt at SUGGESTION level, drop it — a short report of real issues
outperforms a long report of maybes.
