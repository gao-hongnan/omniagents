# Unknowns Evals

Scenarios for `depth-pass`, measuring the two numbers a depth pass lives or dies
by: **depth** (did the rewrite go deeper — a named practitioner, raw material,
step-bound methods, a check that can fail?) and **scope** (did it stay the same
size — same deliverable, no work done, nothing invented?). Every scenario
probes both, because a pass that deepens by adding everything has learned
nothing: bigger is the failure the skill exists to prevent.

`blindspot-pass` has no evals yet.

## Layout

Cases are in the **`claude plugin eval` format** (one directory per case:
`prompt.md` + `graders/*.md`). Run the suite with:

```bash
claude plugin eval plugins/unknowns \
  --model claude-sonnet-4-5 --judge-model claude-sonnet-4-5 \
  --trust-plugin --no-publish
```

```
<case>/
  prompt.md          # the raw request (pasted verbatim as the baseline to beat)
  graders/
    shape.md         # regex floor: the response carries a 'Deeper prompt' block
    depth-rubric.md  # llm judge: named practitioner, raw material, methods, check
    scope-rubric.md  # llm judge: same deliverable, no work done, nothing invented
```

Assertions carry a `kind`: `shape` (the output contract), `depth`, `scope`, or
`calibration` (small tasks get one line and the missing piece, not the full
pass).

## Scenarios

- **flaky-test** (code) — a 1-in-20 CI flake. Depth is a repeated-run check
  instead of one green run, and no masking with retries or sleeps.
- **churn-post** (analysis) — triggers without the slash command. Depth is
  event-level data, a voluntary/involuntary split, and a reconciliation.
  Scope trap: a retention plan or a new dashboard.
- **cli-readme** (writing) — the classic scope trap: badges, a contributing
  guide, a roadmap. Depth is examples produced by running the tool and a
  clean-environment quickstart check.
- **trivial-rename** (calibration) — must not manufacture depth.
- **wedding-toast** (subjective) — no true outside oracle exists; the pass must
  say so, name an honest proxy, and invent nothing about the sister.
- **creatine-evidence** (research) — primary trials over coverage, and a
  deliverable that stays "a few paragraphs".

## Running

Drive it with the `skill-creator` skill's eval loop, which spawns with-skill
and baseline runs in parallel and renders a review UI. The honest baseline is
not "no skill" but **the task plus Felix Rieseberg's prompt pasted verbatim**
(quoted in the skill's Credits) — that is what a user would do without the
skill, so it is the bar the skill has to clear.
