#!/usr/bin/env bash
# Stop hook: prompt Claude to review documentation for drift after source changes.
#
# Checks git diff for uncommitted source-file changes. If found, blocks the
# stop and asks Claude to review docs for stale references. On the next stop
# attempt, stop_hook_active is true so the hook exits silently — no infinite
# loop.
set -euo pipefail

# --- Guard: prevent infinite loop ----------------------------------------
input=$(cat)
if echo "$input" | grep -q '"stop_hook_active": *true'; then
  exit 0
fi

# --- Check for uncommitted source-file changes ---------------------------
# -u shows individual untracked files (not just the directory name).
if ! git status --porcelain -u 2>/dev/null \
     | grep -qE '\.(py|ts|js|jsx|tsx|go|rs|java|rb|c|cpp|h|hpp|cs|kt|swift|sh|bash|zsh|lua)$'; then
  exit 0
fi

# --- Prompt Claude to review docs ----------------------------------------
cat <<'EOF'
{"decision":"block","reason":"Documentation drift check: source files were modified in this session. Please review documentation files (README.md, docs/, guides/, .claude/) for any references to the changed code that may now be stale — broken file paths, outdated line numbers, code snippets that no longer match, or diagrams needing updates. Read the relevant docs, fix any drift you find, then stop."}
EOF
