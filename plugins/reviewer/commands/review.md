---
description:
    Dispatch reviewer specialists in parallel, persist per-specialist +
    aggregated reports as JSON + Markdown under .reviews/<timestamp>/, then
    synthesize through the verifier
argument-hint:
    <TARGET -- file path, diff range, branch, PR ref, or empty for working tree>
allowed-tools:
    Bash(git rev-parse:*), Bash(git branch:*), Bash(git log:*), Bash(git
    diff:*), Bash(git status:*), Bash(test:*), Bash(mkdir:*), Bash(date:*),
    Bash(python3:*), Bash(ln:*), Bash(grep:*), Bash(printf:*), Bash(basename:*),
    Glob, Read, Write, Agent, AskUserQuestion
model: inherit
---

## Context

- Repo root: !`git rev-parse --show-toplevel 2>/dev/null || pwd`
- Current branch:
  !`git branch --show-current 2>/dev/null || echo '(not a git repo)'`
- Latest commit:
  !`git log -1 --format='%h %s' 2>/dev/null || echo '(no commits)'`
- Working tree summary:
  !`git status --short 2>/dev/null || echo '(no git status)'`

## Task

Dispatch the reviewer specialist team, persist each report as JSON + rendered
Markdown under `.reviews/<timestamp>/`, then aggregate through the `verifier`.
JSON is canonical; the Markdown is rendered from it by
`${CLAUDE_PLUGIN_ROOT}/skills/review-contract/schema.py` (stdlib only).

1. Resolve `$ARGUMENTS` into a target:
    - If empty, use the current working tree diff against `HEAD`.
    - If path-like, confirm the path exists with `Glob` or `Bash test -e`.
    - If a `<ref>..<ref>` or `HEAD~N..HEAD` range, confirm both refs with
      `git rev-parse`.
    - If a single branch name, confirm with `git rev-parse --verify`.
    - If the target cannot be validated, ask for one clarification and stop.

2. Gather lightweight dispatch context:
    - Target exactly as resolved.
    - Changed files from `git diff --name-only` where applicable.
    - Repo context from the Context section.
    - Any user qualifiers attached to the command, such as "security only" or
      "ignore generated files".
    - Whether `REVIEW.md`, `CLAUDE.md`, or `AGENTS.md` exists at repo root.

3. Create the run directory. Run this once and reuse the printed path as `<DIR>`
   for every step below:

    `D="$(git rev-parse --show-toplevel 2>/dev/null || pwd)/.reviews/$(date +%Y-%m-%dT%H-%M-%S)"; mkdir -p "$D"; echo "$D"`

4. Dispatch all applicable specialists with the `Agent` tool before reading any
   individual result (the canonical dimension set is defined in
   `omniagents-reviewer:review-contract`):
    - `correctness`
    - `security`
    - `performance`
    - `design`
    - `testing`

    If the user explicitly narrows dimensions, dispatch only those named
    dimensions plus `verifier`.

5. Each specialist prompt must be self-contained and include:
    - **Target**: exact target from step 1.
    - **Dimension**: specialist name.
    - **Repo context**: repo root, branch, latest commit, working tree summary.
    - **Changed files**: file list when available.
    - **Reviewer instructions**: contents or existence of `REVIEW.md`,
      `CLAUDE.md`, or `AGENTS.md` if available.
    - **Constraints**: user qualifiers.
    - **Expected output**: a single `SpecialistReport` JSON object — one fenced
      json block, no prose before or after — per the
      `omniagents-reviewer:review-contract` schema. Every finding carries `file`
      and a confirmed `line`.

6. As each specialist returns, persist and render it. Number the dimensions in
   canonical order — correctness=01, security=02, performance=03, design=04,
   testing=05:
    - `Write` the returned JSON object **verbatim** to
      `<DIR>/NN_<dimension>.json`.
    - Render it:
      `python3 "${CLAUDE_PLUGIN_ROOT}/skills/review-contract/schema.py" specialist "<DIR>/NN_<dimension>.json"`
    - If the renderer prints a validation error, it names the offending field —
      fix that field in the JSON and re-run. Do not invent missing data: if a
      specialist omitted a `line`, drop that finding rather than guessing.

7. After every specialist report is persisted, dispatch `verifier` with:
    - The target.
    - The contents of every `<DIR>/NN_<dimension>.json` verbatim.
    - Instruction to dedupe by `(file, line)`, cross-validate, filter
      unsupported or low-signal findings, compute the verdict, and return a
      single `ReviewReport` JSON object (one fenced json block, no prose). Its
      `specialist_reports` should list the `NN_<dimension>.md` filenames that
      were produced.

8. Persist and render the aggregate:
    - `Write` the verifier's JSON object **verbatim** to `<DIR>/review.json`.
    - Render it:
      `python3 "${CLAUDE_PLUGIN_ROOT}/skills/review-contract/schema.py" review "<DIR>/review.json"`

9. Finalize the run (point `latest` at it and keep `.reviews/` out of git):

    `R="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"; ln -sfn "$(basename "<DIR>")" "$R/.reviews/latest"; grep -qxF '.reviews/' "$R/.gitignore" 2>/dev/null || printf '.reviews/\n' >> "$R/.gitignore"`

10. `Read` `<DIR>/review.md` and relay it to the terminal verbatim. You may
    prepend one sentence saying the review completed; do not rewrite or
    summarize the report. End with one line pointing to the saved artifacts,
    e.g.
    `Saved: .reviews/<timestamp>/ — review.md plus per-specialist JSON + Markdown.`

Target: $ARGUMENTS
