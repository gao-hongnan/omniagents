---
description:
    Triage the diff, dispatch only the reviewer specialists it needs, verify
    and adjudicate their findings against the code, and persist every artifact
    under .reviews/<timestamp>/ (optionally post PR comments with --comment)
argument-hint:
    <TARGET -- file path, diff range, branch, PR ref, or empty for working
    tree> [--comment]
allowed-tools:
    Bash(git rev-parse:*), Bash(git branch:*), Bash(git log:*), Bash(git
    diff:*), Bash(git status:*), Bash(test:*), Bash(mkdir:*), Bash(date:*),
    Bash(python3:*), Bash(ln:*), Bash(grep:*), Bash(printf:*), Bash(basename:*),
    Bash(gh pr:*), Bash(gh api:*), Glob, Read, Write, Agent, AskUserQuestion
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

Triage the target, dispatch the applicable reviewer specialists (they persist
their own reports), merge through the `verifier`, adjudicate through the
`adjudicator`, and render the final report. JSON is canonical; Markdown is
rendered by `${CLAUDE_PLUGIN_ROOT}/skills/review-contract/schema.py` (stdlib
only).

1. Resolve `$ARGUMENTS` into a target and flags:
    - Strip and remember `--comment` if present (used in step 11; valid only
      for PR targets).
    - If empty, use the current working tree diff against `HEAD`.
    - If path-like, confirm the path exists with `Glob` or `Bash test -e`.
    - If a `<ref>..<ref>` or `HEAD~N..HEAD` range, confirm both refs with
      `git rev-parse`.
    - If a single branch name, confirm with `git rev-parse --verify`.
    - If a PR ref (`#N` or a PR URL), resolve it with `gh pr view` to a
      head/base range.
    - If the target cannot be validated, ask for one clarification and stop.

2. Gather lightweight dispatch context:
    - Target exactly as resolved.
    - Changed files from `git diff --name-only` where applicable.
    - **Change intent**: the commit subjects + bodies covering the target
      (`git log --format='%h %s%n%b'` over the range; for the working tree,
      the last few commits for context; for a PR, `gh pr view` title + body).
      Specialists judge subtle bugs as intent-vs-implementation mismatches,
      so always pass this along.
    - Repo context from the Context section.
    - Any user qualifiers attached to the command, such as "security only" or
      "ignore generated files".
    - **Repo review config**: `Read` `REVIEW.md` at the repo root if it
      exists (the org-opinion layer per the contract's Repo Configuration
      section — Path Guidance, Severity Overrides, Allowed Nits). If it is
      150 lines or fewer, carry its full contents; otherwise carry the path
      plus its section headings. Note whether `CLAUDE.md` or `AGENTS.md`
      also carry reviewer instructions.

3. **Triage** — pick the dimension set the diff actually needs. User
   qualifiers always override this table. Classify the changed files:

    | Diff profile | Dispatch |
    | --- | --- |
    | Docs only (`*.md`, `*.rst`, `docs/`) | Nothing — report "docs-only change; nothing to review" (suggest the doc-drift plugin) and stop |
    | Tests only | `testing`, `correctness` |
    | Dependency manifests touched (`pyproject.toml`, `package.json`, lockfiles, `requirements*`) | full set, and tell `security` to prioritize the dependency delta |
    | Config / infra / migrations touched (Dockerfiles, CI, `*.tf`, k8s, `migrations/`, settings) | ensure `operability` is in the set |
    | Anything else (runtime source) | full set: `correctness`, `security`, `performance`, `design`, `testing`, `operability` |

    **Quick mode**: if the diff is under ~20 changed lines in a single file,
    dispatch only the 2 most relevant dimensions for that file (for runtime
    source, `correctness` plus the best second). Cost should scale with the
    diff, not with the plugin.

4. Create the run directory and the changed-files list. Run once; reuse the
   printed path as `<DIR>` everywhere below:

    `D="$(git rev-parse --show-toplevel 2>/dev/null || pwd)/.reviews/$(date +%Y-%m-%dT%H-%M-%S)"; mkdir -p "$D"; git diff --name-only <target-range> > "$D/changed_files.txt" 2>/dev/null; echo "$D"`

    For the working-tree target only, also append untracked new files so
    they stay in review scope:
    `git ls-files --others --exclude-standard >> "$D/changed_files.txt"`

5. Dispatch every triaged specialist with the `Agent` tool in parallel,
   before reading any result. Number the dimensions in canonical order —
   correctness=01, security=02, performance=03, design=04, testing=05,
   operability=06. Each specialist prompt must be self-contained and include:
    - **Target**: exact target from step 1.
    - **Dimension**: specialist name.
    - **Report path**: `<DIR>/NN_<dimension>.json` — the specialist `Write`s
      its own `SpecialistReport` JSON there (per the
      `omniagents-reviewer:review-contract` schema, every finding carrying a
      confirmed `file` + `line`) and returns only a one-line summary.
    - **Repo context**: repo root, branch, latest commit, working tree
      summary.
    - **Changed files**: the list, and the path `<DIR>/changed_files.txt`.
    - **Change intent**: the commit messages from step 2, verbatim.
    - **Reviewer instructions**: the `REVIEW.md` contents from step 2
      verbatim (specialists apply it per the contract's Repo Configuration
      precedence — it never silences a BLOCKER), plus any reviewer guidance
      from `CLAUDE.md`/`AGENTS.md`.
    - **Constraints**: user qualifiers.

6. As each specialist returns, validate and render its file:
    - `python3 "${CLAUDE_PLUGIN_ROOT}/skills/review-contract/schema.py" specialist "<DIR>/NN_<dimension>.json" --changed-files "<DIR>/changed_files.txt"`
    - If the renderer prints a validation error, it names the offending field
      — fix that field in the JSON file and re-run. Do not invent missing
      data: if a specialist omitted a `line`, drop that finding rather than
      guessing. If a specialist failed to write its file at all, re-dispatch
      it once.

7. After every specialist report is validated, dispatch `verifier` with:
    - The target.
    - The contents of every `<DIR>/NN_<dimension>.json` verbatim.
    - Instruction to dedupe by `(file, line)`, cross-validate, filter
      unsupported or low-signal findings per the contract, and return a
      single `ReviewReport` JSON object (one fenced json block, no prose).
      Its `specialist_reports` should list the `NN_<dimension>.md` filenames
      produced in step 6.

    `Write` the verifier's JSON object **verbatim** to `<DIR>/merged.json`.

8. Dispatch `adjudicator` with:
    - The target and repo context.
    - The changed-files list and `<DIR>/changed_files.txt` path.
    - The contents of `<DIR>/merged.json` verbatim.
    - The `REVIEW.md` contents from step 2, if any — the adjudicator is the
      final enforcement point for repo-config drops and downgrades.
    - Instruction to re-verify every BLOCKER/IMPORTANT against the code,
      confirm/downgrade/drop per the contract's Adjudication section,
      recompute the verdict, and return the final `ReviewReport` JSON object
      (one fenced json block, no prose).

9. Persist and render the final report:
    - `Write` the adjudicator's JSON object **verbatim** to
      `<DIR>/review.json`.
    - `python3 "${CLAUDE_PLUGIN_ROOT}/skills/review-contract/schema.py" review "<DIR>/review.json" --changed-files "<DIR>/changed_files.txt"`
    - Fix-and-rerun on validation errors as in step 6.

10. Finalize the run (point `latest` at it and keep `.reviews/` out of git):

    `R="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"; ln -sfn "$(basename "<DIR>")" "$R/.reviews/latest"; grep -qxF '.reviews/' "$R/.gitignore" 2>/dev/null || printf '.reviews/\n' >> "$R/.gitignore"`

    Then `Read` `<DIR>/review.md` and relay it to the terminal verbatim. You
    may prepend one sentence saying the review completed (mention how many
    findings adjudication dropped, if any); do not rewrite or summarize the
    report. End with one line pointing to the saved artifacts, e.g.
    `Saved: .reviews/<timestamp>/ — review.md plus per-specialist JSON + Markdown.`

11. **Only if** `--comment` was passed **and** the target is a PR: post the
    surviving findings as inline PR comments:

    `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/post_pr_comments.py" "<DIR>/review.json" --pr <number> [--dry-run]`

    Run with `--dry-run` first, show the user what would be posted, and ask
    for confirmation with `AskUserQuestion` before the real run. Never post
    without the flag and that confirmation.

Target: $ARGUMENTS
