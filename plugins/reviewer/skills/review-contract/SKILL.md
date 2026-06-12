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

Every specialist produces findings as **JSON**; the verifier aggregates them
into one JSON report. **JSON is canonical; Markdown is _rendered_ from it**
by `schema.py` (beside this file, stdlib-only; `python3 schema.py --schema`
prints the field-by-field shape — the machine-enforceable half of this
contract). Agents never hand-write the Markdown report. A finding that omits
`file` or `line` **fails validation and is never rendered** — every finding
a human reads carries a jump-to-able `file:line` citation.

## Dimensions

The reviewer specialist set is fixed: **correctness, security, performance,
design, testing, operability**. This is the single source of truth for the
dimension set: triage, the `dimension` field below, and the verifier's
one-report-per-dispatched-dimension expectation all enumerate it. Adding or
removing a
dimension means updating this section, the `Dimension` enum in `schema.py`,
the command's dispatch + triage lists, and the matching specialist agent
(`scripts/doctor.py` checks this wiring mechanically).

## Review Method

The difference between a reviewer people trust and one they mute is not how
many findings it produces — it is whether each finding survives scrutiny.
Hunts are search procedure, not quotas. Every specialist works in three
phases:

1. **Understand the change before judging it.** Read the commit messages and
   any PR description the dispatcher provided — they state intent, and a
   subtle bug is usually a mismatch between intent and implementation. Read
   changed files **in full, not just the hunks**: a line that looks wrong in
   isolation is often guarded twenty lines above the hunk. Identify the
   consumers of every changed symbol (Tool Selection below) before deciding
   what the change can break.

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

Each dimension skill expresses phases 2 and 3 as named **Hunts** — a `When`
trigger, a `Protocol`, an `Evidence bar`, and `Falsifiers`. Execute every
hunt whose trigger matches the diff, then run the skill's **Recall Sweep**
to catch what no trigger matched.

An empty `findings` array produced by this method is a **success** — it is
the report that the change is clean along your dimension. Never pad a report
to justify the dispatch.

### Tool Selection

Confirm availability once with `list_graph_stats_tool`; if the graph is
empty, fall back to Grep + Read and set `blast_radius` to
`"graph unavailable -- severity based on code analysis only"`. Then:

- Consumers of one known symbol → `query_graph_tool` with `callers_of` /
  `importers_of` (Grep when the graph lacks the symbol).
- Whole-change impact and the elevation rule's evidence →
  `get_impact_radius_tool`.
- Tests covering a symbol → `query_graph_tool` with `tests_for`.
- Surrounding code without re-reading whole files →
  `get_review_context_tool`.
- Unknown location → `semantic_search_nodes_tool`, then confirm with `Read`
  — the graph returns symbols, never citable line numbers.

## The Taste Test

A finding is depth when it is evidence; it is noise when it is preference.
Every candidate passes three gates before emission:

1. **Concrete trigger scenario.** Name the input, caller, configuration, or
   interleaving that makes the code go wrong — or the specific next change
   it makes more expensive. Cannot name one → do not flag.
2. **Falsifiable.** State what evidence would disprove it and confirm you
   looked — the dimension skill's Falsifiers are that checklist.
3. **Principle, not preference.** Name the violated contract, invariant,
   bound, or documented convention — not "I would have written it
   differently."

**Reconciliation rule:** technical facts overrule preference. If the
author's approach is defensibly equivalent to your alternative — same
behavior, same maintenance cost, different shape — it is their call, not a
finding. Prefer not reporting over guessing.

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
- **Anything that fails the Taste Test** — style preference without
  behavioral or maintenance consequence, docstring/comment nits, defensibly
  equivalent idioms — unless the repo's own configuration demands it (see
  Repo Configuration below).
- **Narration of the diff** — observations that describe what changed
  without identifying a problem.

## Repo Configuration (REVIEW.md)

A reviewed repo may carry a `REVIEW.md` at its root — the org-opinion layer.
The skills stay universal; repo taste lives in the repo. The dispatcher
passes its contents in the dispatch context. Three optional sections, plain
Markdown bullets:

- `## Path Guidance` — glob-scoped guidance, applied only to findings whose
  `file` matches (e.g. `services/billing/**` — money is integer cents; flag
  float arithmetic on it as IMPORTANT).
- `## Severity Overrides` — named repo invariants that raise a severity
  floor, or paths where it drops (e.g. `experimental/**`: cap non-BLOCKER
  findings at SUGGESTION).
- `## Allowed Nits` — patterns this repo accepts; matching candidates are
  not findings.

**Precedence:** repo config may adjust SUGGESTION and IMPORTANT handling in
either direction, but it can never silence, downgrade, or pre-filter a
BLOCKER, and it cannot override the Finding Schema, the Taste Test, or the
evidence requirements. The adjudicator is the final enforcement point for
repo-config drops.

## Finding Schema

Every finding is a JSON object with these fields (enforced by `schema.py`):

```json
{
  "severity": "BLOCKER | IMPORTANT | SUGGESTION",
  "file": "repo-relative/path.py",
  "line": 42,
  "end_line": 58,
  "dimension": "correctness | security | performance | design | testing | operability",
  "summary": "one-line description of the problem",
  "why": "rule violated + consequence if not fixed",
  "blast_radius": "N direct callers, M transitive importers",
  "fix": "concrete one-liner suggestion (do not implement)",
  "confidence": 92
}
```

The object renders as a Markdown bullet with a backtick-fenced
`file:line[-end_line]` citation (see Worked Examples for the rendered shape).

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

Partial-evidence example: you traced a `None` to its sink and verified two
of three call sites; the third is dynamic and unresolvable. That is 80-89
territory — emit at 82 and name the unverified call site in `why`. Five
call sites unread is not — that is below 70: keep falsifying or drop.

## Severity Rubric

### BLOCKER

Will break callers, lose data, allow unauthorized access, or corrupt
state. The PR is unmergeable with a BLOCKER finding.

**Examples:** SQL injection in a user-facing endpoint; race condition that
corrupts shared state; missing authentication on a state-changing handler.

### IMPORTANT

Materially harms maintainability, introduces a latent risk, or
violates a project convention the team enforces. Mergeable with a
tracked follow-up.

**Examples:** O(n^2) loop over a collection that will grow; bare `except`
swallowing exceptions silently; missing index on a filtered column in a new
query.

### SUGGESTION

Preferred style, minor improvement, or an observation that may not
warrant action. Non-blocking.

**Examples:** a name that misstates behavior; minor duplication (< 5
lines); a clearer idiom with a concrete maintenance payoff.

## Severity Elevation Rule

A finding graded IMPORTANT whose blast radius (via
`get_impact_radius_tool`) shows **50+ transitive importers** is
automatically elevated to BLOCKER. The specialist MUST check blast
radius before finalizing severity for every IMPORTANT finding.

## Worked Examples

Calibration anchors for grading and phrasing — never copy their wording into
a report.

**BLOCKER, confidence 95** (direct evidence; falsification attempted and
failed):

> **BLOCKER** `billing/invoice.py:27` — `render_invoice` reads
> `order.total_cents`, which this diff renamed to `amount_cents` everywhere
> else.
> **Why**: AttributeError on every invoice render; the rename updated the
> model and two other call sites but missed this one. Falsification: no
> try/except here, no test pins the old name.
> **Fix**: rename the access to `order.amount_cents`. **Confidence**: 95

**IMPORTANT, confidence 78** (one named assumption, stated in `why`):

> **IMPORTANT** `api/export.py:31` — new endpoint materializes the full
> result set with `list(rows)` before serializing.
> **Why**: rows scale with tenant data — no LIMIT upstream (checked the
> query at line 22). Assumes large tenants exist; could not verify from the
> repo.
> **Fix**: stream via the `iter_rows()` helper `report.py` already uses.
> **Confidence**: 78

A BLOCKER-grade issue on an untouched line keeps the prefix:
`[pre-existing] webhook signature never verified (hooks/receiver.py:18)`.

**A dropped candidate** (what falsification looks like): "`cfg.timeout` may
be `None` at use" — killed because `Config.__post_init__` (`config.py:41`)
raises on `None`, so the bad state is unreachable. Not emitted. That
silence is the method working.

## Specialist Report (JSON)

Each specialist **writes exactly one JSON object to the report path the
dispatcher provides** (`.reviews/<timestamp>/NN_<dimension>.json`) using its
`Write` tool, then returns a single summary line (dimension, counts by
severity, path written) — never the full JSON in the reply, never Markdown.
The `/review` command validates the file and renders `NN_<dimension>.md`
with `python3 schema.py specialist`.

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
`.reviews/<timestamp>/merged.json`. The adjudicator then re-tries it against
the code (next section) and returns the final object of the same shape,
which the command writes to `.reviews/<timestamp>/review.json` and renders
as `review.md` with `python3 schema.py review`.

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

## Adjudication

After the verifier merges, the **adjudicator** agent re-opens every BLOCKER
and IMPORTANT citation in the actual code and independently re-verifies it:

- **Confirm** — evidence holds; `why` gains `Adjudicated: confirmed — …`.
- **Downgrade** — real but overstated; severity drops one level and `why`
  gains `Adjudicated: downgraded — …`.
- **Drop** — the claim dies against the code (an upstream guard, an
  unreachable input, a misread line); the report `summary` records each drop
  with location and reason.

SUGGESTION findings pass through (citations spot-checked). The adjudicator
**never adds findings and never raises severity or confidence** — recall
belongs to the specialists; the adjudicator only buys precision. The verdict
is recomputed from the surviving findings. The output is a normal
`ReviewReport` (it may carry an extra `"adjudicated": true`, which the
renderer ignores).

## Rendered Output Layout

The `/review` command persists every run under a git-ignored folder:

```
.reviews/<timestamp>/
  changed_files.txt           # git diff --name-only output for scope checks
  01_correctness.json / .md   02_security.json / .md   03_performance.json / .md
  04_design.json / .md        05_testing.json / .md    06_operability.json / .md
  merged.json                 # verifier output (pre-adjudication)
  review.json                 # canonical final report (adjudicator output)
  review.md                   # headline human-readable report
.reviews/latest -> <timestamp>
```

Triage decides which `NN_*` files exist for a given run — a docs-only diff
may dispatch nothing; a test-only diff dispatches `testing` + `correctness`.
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
