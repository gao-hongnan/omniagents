#!/usr/bin/env bash
#
# Materialize an eval fixture into a throwaway git repo with the patch
# applied as the uncommitted working-tree diff — exactly the default
# target shape of /omniagents-reviewer:review.
#
# Usage:  ./setup_fixture.sh fixtures/<name> [dest-dir]
# Prints the destination path; run the review command from inside it.
set -euo pipefail

FIXTURE="$(cd "$1" && pwd)"
DEST="${2:-$(mktemp -d /tmp/reviewer-eval-XXXXXX)}"

cp -R "$FIXTURE/repo/." "$DEST/"
git -C "$DEST" init -q
git -C "$DEST" add -A
git -C "$DEST" -c user.email=eval@example.com -c user.name=eval \
	commit -qm "base: pre-change state"
git -C "$DEST" apply "$FIXTURE/patch.diff"

echo "$DEST"
