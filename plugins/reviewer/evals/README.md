# Reviewer Evals

Seeded-bug fixtures that measure the two numbers a reviewer lives or dies
by: **recall** (does it catch the planted subtle bugs?) and **precision**
(does it stay silent on the planted noise baits?). Every fixture plants
both, because a reviewer that catches everything by flagging everything has
learned nothing.

## Layout

```
evals.json                  # skill-creator-compatible eval set
setup_fixture.sh            # fixture -> throwaway git repo with patch applied
fixtures/<name>/
  repo/                     # pre-change state (committed as base)
  patch.diff                # the change under review (working-tree diff)
  expected.json             # seeded_bugs (recall) + noise_traps (precision)
```

## Fixtures

- **stale-callsite-rename** — a field rename that misses one call site.
  The omission class: invisible in the hunks, fatal at runtime. Baits: a
  pre-existing exception swallow in an untouched file, an unused import in
  a touched file (linter territory).
- **missing-await-toctou** — a new orchestrator with an un-awaited
  coroutine and an exists()-then-open race. Baits: a bounded 3-element
  loop (speculative-perf bait), a missing docstring (taste bait).

## Running

One fixture by hand:

```bash
DEST=$(./setup_fixture.sh fixtures/stale-callsite-rename)
cd "$DEST" && claude   # then: /omniagents-reviewer:review
# grade .reviews/latest/review.json against fixtures/<name>/expected.json
```

Full old-vs-new comparison: drive it with the `skill-creator` skill's eval
loop (it spawns with-skill and baseline runs in parallel and renders a
review UI). Point the baseline at a snapshot of the previous plugin version
from `~/.claude/plugins/cache/omniagents/omniagents-reviewer/<old-version>/`.

## Grading

For each fixture, against `.reviews/latest/review.json`:

- **artifact-valid** — `python3 ../skills/review-contract/schema.py review
  review.json` exits 0.
- **recall** — every entry in `expected.json:seeded_bugs` has a finding
  citing its `file` whose text matches `evidence_substring`.
- **precision** — no entry in `expected.json:noise_traps` is contradicted:
  trap files are absent from findings (or carry the `[pre-existing]`
  prefix where the trap allows it).

A run that misses a seeded bug is a recall regression; a run that bites a
bait is a precision regression. Track both per release — improving one by
sacrificing the other is the failure mode this directory exists to catch.

## Adding a fixture

1. Build `repo/` at the pre-change state; keep it under ~80 lines total.
2. Make the change, capture `git diff > patch.diff`, revert.
3. Plant at least one **omission-class** bug (something the diff should
   have changed but did not) — they separate strong reviewers from
   pattern-matchers — and at least two noise baits from the contract's
   What Not to Report list.
4. Record both in `expected.json` with `evidence_substring`s.
