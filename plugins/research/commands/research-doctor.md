---
description:
    Verify the research plugin's wiring — skill preloads resolve, the four agents
    are wired to the command, schema renders, MCP servers are declared — and
    optionally canary-test that preloading actually works (--deep)
argument-hint: "[--deep]"
allowed-tools: Bash(python3:*), Read, Agent
model: inherit
---

## Task

Run the research plugin's self-diagnostic and report the results.

1. Run the mechanical lint:

    `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py"`

    Relay its output verbatim. If it reports errors, explain each one in one
    sentence and name the fix (commit the skill, fix the ref, cut a release +
    `claude plugin update`, etc.). The most important failure mode it catches: a
    `skills:` frontmatter ref that does not resolve is **silently skipped** by
    Claude Code — the agent runs without that checklist and nothing warns you.

2. Run the deterministic contract guard (offline; no MCP needed):

    `bash "${CLAUDE_PLUGIN_ROOT}/evals/check_schema.sh"`

    This proves the Iron Law is enforced in code — `schema.py` rejects a claim
    with no quote, a malformed identifier, a hypothesis leaked into `claims[]`,
    and a grounded-mode report carrying hypotheses. Relay PASS/FAIL.

3. If `$ARGUMENTS` contains `--deep`, additionally run the preload canary:
   dispatch the `retriever` agent via the `Agent` tool with exactly this prompt:

    > Do not retrieve anything. This is a diagnostic. List every skill document
    > currently in your context: for each, quote its exact first `#` heading and
    > its `name:` frontmatter value. Then stop.

    Compare the quoted headings against the `skills:` list in
    `${CLAUDE_PLUGIN_ROOT}/agents/retriever.md` (Read it). A skill whose heading
    the agent **cannot quote was not preloaded** — report it as a preload
    failure even if doctor.py's static checks passed. The `retriever` is the
    canary because it carries the plugin's full skill set.

4. Summarize: one line per check (PASS/WARN/FAIL), then the single most
   important action if anything failed.

Target: $ARGUMENTS
