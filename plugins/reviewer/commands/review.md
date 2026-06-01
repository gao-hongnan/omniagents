---
description:
    Dispatch reviewer specialists in parallel, then synthesize findings through
    the verifier
argument-hint:
    <TARGET -- file path, diff range, branch, PR ref, or empty for working tree>
allowed-tools:
    Bash(git rev-parse:*), Bash(git branch:*), Bash(git log:*), Bash(git
    diff:*), Bash(git status:*), Bash(test:*), Glob, Read, Agent,
    AskUserQuestion
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

Dispatch the reviewer specialist team, then pass their reports to the `verifier`
agent for the final report.

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

3. Dispatch all applicable specialists with the `Agent` tool before reading any
   individual result (the canonical dimension set is defined in
   `omniagents-reviewer:review-contract`):
    - `correctness`
    - `security`
    - `performance`
    - `design`
    - `testing`

    If the user explicitly narrows dimensions, dispatch only those named
    dimensions plus `verifier`.

4. Each specialist prompt must be self-contained and include:
    - **Target**: exact target from step 1.
    - **Dimension**: specialist name.
    - **Repo context**: repo root, branch, latest commit, working tree summary.
    - **Changed files**: file list when available.
    - **Reviewer instructions**: contents or existence of `REVIEW.md`,
      `CLAUDE.md`, or `AGENTS.md` if available.
    - **Constraints**: user qualifiers.
    - **Expected output**: the per-specialist template from
      `omniagents-reviewer:review-contract`.

5. After every specialist report returns, dispatch `verifier` with:
    - The target.
    - The specialist reports verbatim.
    - Instruction to aggregate, deduplicate, normalize confidence, filter
      unsupported or low-signal findings, and produce the final report.

6. Relay the verifier report verbatim. You may prepend one sentence saying the
   specialist review completed; do not rewrite or summarize the report.

Target: $ARGUMENTS
