#!/usr/bin/env bash
#
# sync-drawio.sh — vendor the drawio Claude Code plugin from upstream.
#
# Upstream ships the plugin as a *subdirectory* (plugins/claude-code) of the big
# jgraph/drawio-mcp repo, so a git submodule/subtree (which track whole repos)
# is the wrong tool. Instead we mirror just that subdirectory into
# plugins/drawio/ as real, committed files, pinned to a concrete upstream
# commit. Re-run this to update; review the diff, then `make validate` and
# `make release`.
#
# Usage:
#   scripts/sync-drawio.sh              # sync to the latest upstream main
#   scripts/sync-drawio.sh v1.1.0       # sync to a tag
#   scripts/sync-drawio.sh <full-sha>   # sync to a specific commit
#
set -euo pipefail

REPO="jgraph/drawio-mcp"
SUBDIR="plugins/claude-code"
REF="${1:-main}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/plugins/drawio"

say() { printf '\033[36m▸ %s\033[0m\n' "$*"; }
die() { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

command -v curl >/dev/null || die "curl is required"
command -v tar  >/dev/null || die "tar is required"

# Resolve whatever ref was given to a concrete 40-char commit sha, so the vendor
# stamp records exactly what we pulled (a branch name would drift).
say "resolving $REPO@$REF …"
SHA="$(curl -fsSL "https://api.github.com/repos/$REPO/commits/$REF" \
        | sed -n 's/.*"sha"[[:space:]]*:[[:space:]]*"\([0-9a-f]\{40\}\)".*/\1/p' \
        | head -1)"
[ -n "$SHA" ] || die "could not resolve ref '$REF' to a commit sha"
say "pinned commit: $SHA"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

say "downloading $SUBDIR from the source tarball …"
curl -fsSL "https://codeload.github.com/$REPO/tar.gz/$SHA" | tar -xz -C "$TMP"

SRC="$(find "$TMP" -maxdepth 3 -type d -path "*/$SUBDIR" | head -1)"
[ -n "$SRC" ] && [ -d "$SRC" ] || die "subdirectory '$SUBDIR' not found at $REF"
[ -f "$SRC/.claude-plugin/plugin.json" ] || die "$SRC is not a plugin (no .claude-plugin/plugin.json)"

# Full mirror: wipe and repopulate so upstream deletions/renames are reflected.
say "mirroring into $DEST …"
rm -rf "$DEST"
mkdir -p "$DEST"
cp -R "$SRC/." "$DEST/"

# Provenance stamp (regenerated every sync).
cat > "$DEST/UPSTREAM.md" <<EOF
# Vendored — do not edit by hand

This directory is a verbatim mirror of the \`$SUBDIR\` subdirectory of
[$REPO](https://github.com/$REPO), re-synced by \`scripts/sync-drawio.sh\`.
Local edits here are overwritten on the next sync — send fixes upstream instead.

| field | value |
|-------|-------|
| source | https://github.com/$REPO/tree/$SHA/$SUBDIR |
| pinned commit | \`$SHA\` |
| requested ref | \`$REF\` |

## Update

\`\`\`bash
scripts/sync-drawio.sh            # latest upstream main
scripts/sync-drawio.sh <ref>     # a tag or commit sha
make validate                    # confirm the marketplace still validates
\`\`\`

Review the resulting diff before committing, then \`make release\`.
EOF

say "done — $DEST now mirrors $REPO@${SHA:0:12}"
printf '  next: review the diff, then \033[1mmake validate\033[0m\n'
