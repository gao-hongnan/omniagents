# Evals for the writing plugin

Scenarios for the writing plugin's skills. Only `technical-writing` has evals so
far.

## Layout

```text
technical-writing/
  evals.json      # behavior scenarios, in the skill-creator eval format
  triggers.json   # 10 queries that should load the skill and 10 near misses that shouldn't
```

Each assertion in `evals.json` carries a `kind`:

- `shape`: the output contract, such as the review template or a title form.
- `rule`: one rule from the skill, checkable by reading or by `lint_prose.py`.
- `judgment`: a catch that no pattern finds, such as three names for one thing.
  These separate the skill from a linter.
- `fact`: nothing invented. Commands, counts, and names match the prompt.
- `scope`: the change stays the size that the user asked for.

## Scenarios

- **review-planted-defects:** a doc section full of planted defects. Three of
  them only judgment catches. The review must use the template and must not
  rewrite.
- **howto-from-notes:** raw notes become a how-to guide. The warning must come
  before the step that it guards, and every command must stay verbatim.
- **pr-description:** an agent-style draft with a pasted log, a file list, and
  emoji becomes a one-minute briefing.
- **commit-message-repo-convention:** the repo's "area: " convention beats the
  skill's default capitalization.
- **split-mixed-mode-page:** a getting-started page that mixes three modes gets
  a split plan and an outline, not polished prose.
- **typo-only-scope:** the calibration case. Fix one typo, and leave every other
  flaw alone.

## Run them

Drive the behavior scenarios with the `skill-creator` skill's eval loop. It runs
each prompt with the skill and without it, then opens a review page. Grade
`rule` assertions with the checker where you can:

```bash
python3 plugins/writing/skills/technical-writing/scripts/lint_prose.py <output.md>
```

Run `triggers.json` through skill-creator's trigger evaluation to measure how
often the description loads the skill. Four near misses belong to neighbor
skills: `measured-persuasion`, `markdown-conventions`, the `docstrings` skills,
and `blueprint`. The other six share words with documentation but ask for no
doc. They ask for a UI label, tests, a translation check, a cover letter, a
summary, and ADR tooling setup.

The checker has its own tests:

```bash
python3 plugins/writing/skills/technical-writing/scripts/lint_prose.py --self-test
```
