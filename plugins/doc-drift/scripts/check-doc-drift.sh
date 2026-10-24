#!/usr/bin/env bash
# Stop hook: prompt Claude to review documentation for drift after source
# changes. Blocks at most once per distinct change set.
set -euo pipefail

# --- Guard 1: prevent infinite loop within one stop sequence -------------
input=$(cat)
if echo "$input" | grep -q '"stop_hook_active": *true'; then
	exit 0
fi

# --- Check for uncommitted source-file changes ---------------------------
# -u shows individual untracked files (not just the directory name).
if ! git status --porcelain -u 2>/dev/null \
     | grep -qE '\.(py|ts|js|jsx|tsx|go|rs|java|rb|c|cpp|h|hpp|cs|kt|swift|sh|bash|zsh|lua)$'; then
	STATE_DIR="${CLAUDE_PLUGIN_DATA:-${XDG_STATE_HOME:-$HOME/.local/state}/omniagents-doc-drift}"
	rm -f "$STATE_DIR/last-changeset.sha" 2>/dev/null || true
	exit 0
fi

# --- Guard 2: block at most once per distinct change set -----------------
CHANGESET_HASH="$(
	{
		git diff
		git status --porcelain -u
	} | shasum -a 256 | cut -d' ' -f1
)"
STATE_DIR="${CLAUDE_PLUGIN_DATA:-${XDG_STATE_HOME:-$HOME/.local/state}/omniagents-doc-drift}"
STATE_FILE="$STATE_DIR/last-changeset.sha"

if [ -f "$STATE_FILE" ] && [ "$(cat "$STATE_FILE")" = "$CHANGESET_HASH" ]; then
	exit 0
fi

mkdir -p "$STATE_DIR"
printf '%s\n' "$CHANGESET_HASH" > "$STATE_FILE"

# --- Prompt Claude to review docs ----------------------------------------
cat <<'EOF'
{"decision":"block","reason":"Documentation drift check: source files were modified in this session. Please review documentation files (README.md, docs/, guides/, .claude/) for any references to the changed code that may now be stale — broken file paths, outdated line numbers, code snippets that no longer match, or diagrams needing updates. Read the relevant docs, fix any drift you find, then stop."}
EOF
