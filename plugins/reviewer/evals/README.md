# Reviewer Evals

Seeded-bug fixtures that measure the two numbers a reviewer lives or dies by:
**recall** (does it catch the planted subtle bugs?) and **precision** (does it
stay silent on the planted noise baits?). Every fixture plants both, because a
reviewer that catches everything by flagging everything has learned nothing.

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

One per dimension (correctness has two — it is the highest-traffic specialist).
Each seeded bug requires its skill's hunt protocol to find; each bait dies to a
falsifier from the same skill.

- **stale-callsite-rename** (correctness) — a field rename that misses one call
  site. The omission class: invisible in the hunks, fatal at runtime. Baits: a
  pre-existing exception swallow in an untouched file, an unused import in a
  touched file (linter territory).
- **missing-await-toctou** (correctness) — a new orchestrator with an un-awaited
  coroutine and an exists()-then-open race. Baits: a bounded 3-element loop
  (speculative-perf bait), a missing docstring (taste bait).
- **idor-sibling-endpoint** (security) — a DELETE handler authenticated but
  missing the ownership check its GET sibling enforces. Baits: parameterized
  queries (safe construct), a fake test token (test secret).
- **loop-query-amplification** (performance) — one SELECT per team member in a
  loop while a bulk variant exists in the same module. Baits: a sort over a
  4-element constant, an lru_cache with maxsize set.
- **duplicate-validator-drift** (design) — a new module reimplements the email
  rule `validators.py` already owns, divergently. Baits: a single-use Pydantic
  model matching the repo's form idiom, missing docstrings.
- **bugfix-no-regression** (testing) — a CHANGELOG-declared bug fix with no
  regression test pinning it. Baits: parametrized indirect coverage that must
  not be called weak, a trivial formatter that needs no test.
- **one-shot-column-rename** (operability) — a column rename migration in the
  same deploy as the code that reads the new name, with no down(). Baits: a
  no-inline-timeout call through a shared client constructed with one, a log
  line whose request_id a middleware filter injects.

## Running

One fixture by hand:

```bash
DEST=$(./setup_fixture.sh fixtures/stale-callsite-rename)
cd "$DEST" && claude   # then: /omniagents-reviewer:review
# grade .reviews/latest/review.json against fixtures/<name>/expected.json
```

Full old-vs-new comparison: drive it with the `skill-creator` skill's eval loop
(it spawns with-skill and baseline runs in parallel and renders a review UI).
Point the baseline at a snapshot of the previous plugin version from
`~/.claude/plugins/cache/omniagents/omniagents-reviewer/<old-version>/`.

Fixtures are throwaway local repos with no PR, so always run
`/omniagents-reviewer:review` with no target (working-tree diff) and never
`--comment` here. For real-PR usage — including `--comment` to post the
adjudicated findings as inline PR comments — see `../README.md#usage`.

## Grading

For each fixture, against `.reviews/latest/review.json`:

- **artifact-valid** —
  `python3 ../skills/review-contract/schema.py review review.json` exits 0.
- **recall** — every entry in `expected.json:seeded_bugs` has a finding citing
  its `file` whose text matches `evidence_substring`.
- **precision** — no entry in `expected.json:noise_traps` is contradicted: trap
  files are absent from findings (or carry the `[pre-existing]` prefix where the
  trap allows it).

A run that misses a seeded bug is a recall regression; a run that bites a bait
is a precision regression. Track both per release — improving one by sacrificing
the other is the failure mode this directory exists to catch.

## Adding a fixture

1. Build `repo/` at the pre-change state; keep it under ~80 lines total.
2. Make the change, capture `git diff > patch.diff`, revert.
3. Plant at least one **omission-class** bug (something the diff should have
   changed but did not) — they separate strong reviewers from pattern-matchers —
   and at least two noise baits from the contract's What Not to Report list.
4. Record both in `expected.json` with `evidence_substring`s.
