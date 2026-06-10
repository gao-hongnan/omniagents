---
description:
    Verify the reviewer plugin's wiring — skill preloads resolve, dimensions
    are wired, schema renders — and optionally canary-test that preloading
    actually works (--deep)
argument-hint: "[--deep]"
allowed-tools: Bash(python3:*), Read, Agent
model: inherit
---

## Task

Run the reviewer plugin's self-diagnostic and report the results.

1. Run the mechanical lint:

    `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py"`

    Relay its output verbatim. If it reports errors, explain each one in one
    sentence and name the fix (commit the skill, fix the ref, cut a release +
    `claude plugin update`, etc.). The most important failure mode it catches:
    a `skills:` frontmatter ref that does not resolve is **silently skipped**
    by Claude Code — the specialist runs without that checklist and nothing
    warns you.

2. If `$ARGUMENTS` contains `--deep`, additionally run the preload canary:
   dispatch the `design` specialist via the `Agent` tool with exactly this
   prompt:

    > Do not review anything. This is a diagnostic. List every skill document
    > currently in your context: for each, quote its exact first `#` heading
    > and its `name:` frontmatter value. Then stop.

    Compare the quoted headings against the `skills:` list in
    `${CLAUDE_PLUGIN_ROOT}/agents/design.md` (Read it). A skill whose heading
    the agent **cannot quote was not preloaded** — report it as a preload
    failure even if doctor.py's static checks passed. The design agent is the
    canary because it has the longest skill list.

3. Summarize: one line per check (PASS/WARN/FAIL), then the single most
   important action if anything failed.

Target: $ARGUMENTS
