#!/usr/bin/env bash
#
# sync-codex.sh — derive the OpenAI Codex marketplace from the Claude manifests.
#
# Codex (CLI >= 0.146) ships a plugin system that mirrors Claude Code's: a
# `.codex-plugin/plugin.json` per plugin and a catalog at
# `.agents/plugins/marketplace.json`. Both formats are compatible supersets of
# ours (verified empirically: identical core fields, extra keys tolerated,
# Claude-style string `source` entries accepted), so the Codex artifacts are
# GENERATED — never edited by hand:
#
#   plugins/<dir>/.codex-plugin/plugin.json  = byte-copy of .claude-plugin/plugin.json
#   .agents/plugins/marketplace.json         = Claude catalog filtered to
#                                              plugins that ship skills
#
# A plugin is published to Codex iff it has a skills/ directory: SKILL.md is
# the cross-agent standard, while hooks, subagents, and MCP wiring remain
# Claude-only. External (github-sourced) catalog entries drop out with the same
# rule. release.sh runs this after version bumps so both marketplaces publish
# in lockstep.
#
# Usage:  make sync-codex      (or:  ./scripts/sync-codex.sh)
#
set -euo pipefail

command -v jq >/dev/null 2>&1 || { echo "error: jq is required but not on PATH"; exit 1; }

# Repo root = parent of this script's directory.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

CLAUDE_MARKETPLACE=".claude-plugin/marketplace.json"
CODEX_MARKETPLACE=".agents/plugins/marketplace.json"
[ -f "$CLAUDE_MARKETPLACE" ] || { echo "error: $CLAUDE_MARKETPLACE not found in $ROOT"; exit 1; }

# 1. Per-plugin manifests: copy for skill-bearing plugins, prune the rest so a
#    plugin that loses its skills/ also leaves the Codex marketplace.
INCLUDED=()
for dir in plugins/*/; do
	dir="${dir%/}"
	manifest="$dir/.claude-plugin/plugin.json"
	[ -f "$manifest" ] || continue
	if [ -d "$dir/skills" ]; then
		mkdir -p "$dir/.codex-plugin"
		cp "$manifest" "$dir/.codex-plugin/plugin.json"
		INCLUDED+=("./$dir")
		echo "synced  $dir/.codex-plugin/plugin.json"
	elif [ -f "$dir/.codex-plugin/plugin.json" ]; then
		rm "$dir/.codex-plugin/plugin.json"
		rmdir "$dir/.codex-plugin" 2>/dev/null || true
		echo "pruned  $dir/.codex-plugin/plugin.json (no skills/)"
	fi
done

[ "${#INCLUDED[@]}" -gt 0 ] || { echo "error: no skill-bearing plugins found; refusing to write an empty catalog"; exit 1; }

# 2. Catalog: keep only entries whose local `source` string names an included
#    plugin (object-form sources — external github entries — never match).
mkdir -p "$(dirname "$CODEX_MARKETPLACE")"
KEEP="$(printf '%s\n' "${INCLUDED[@]}" | jq -R . | jq -s .)"
tmp="$(mktemp)"
jq --argjson keep "$KEEP" \
	'.plugins |= map(select((.source | type == "string") and (.source as $s | $keep | index($s) != null)))' \
	"$CLAUDE_MARKETPLACE" > "$tmp" && mv "$tmp" "$CODEX_MARKETPLACE"
echo "wrote   $CODEX_MARKETPLACE ($(jq '.plugins | length' "$CODEX_MARKETPLACE") plugins)"
