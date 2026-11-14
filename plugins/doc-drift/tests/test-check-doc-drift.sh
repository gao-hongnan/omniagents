#!/usr/bin/env bash
# test-check-doc-drift.sh — clean pass / first dirty block / repeated-stop
# silence for the doc-drift Stop hook, against a scratch git repo.
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
HOOK="$REPO_ROOT/plugins/doc-drift/scripts/check-doc-drift.sh"

SCRATCH="$(mktemp -d)"
trap 'rm -rf "$SCRATCH"' EXIT
GIT_DIR="$SCRATCH/repo"
DATA_DIR="$SCRATCH/plugin-data"
mkdir -p "$GIT_DIR" "$DATA_DIR"
git -C "$GIT_DIR" init -q
git -C "$GIT_DIR" config user.email test@example.com
git -C "$GIT_DIR" config user.name test
commit() { git -C "$GIT_DIR" add -A >/dev/null && git -C "$GIT_DIR" commit -qm "$1"; }

STOP_JSON='{"session_id":"test","stop_hook_active":false}'
run_hook() {
	(cd "$GIT_DIR" && printf '%s' "$STOP_JSON" \
		| CLAUDE_PROJECT_DIR="$GIT_DIR" CLAUDE_PLUGIN_DATA="$DATA_DIR" bash "$HOOK")
}

fail() { echo "FAIL: $*"; exit 1; }

# --- Case 1: clean tree passes ------------------------------------------
OUT="$(run_hook)" || fail "case 1: hook exited non-zero on a clean tree"
[ -z "$OUT" ] || fail "case 1: clean tree produced output: $OUT"
echo "case 1 OK: clean tree passes silently"

# --- Case 2: first dirty stop blocks ------------------------------------
echo "print('hi')" > "$GIT_DIR/app.py"
commit baseline 2>/dev/null || true
echo "print('bye')" >> "$GIT_DIR/app.py"
OUT="$(run_hook)" || fail "case 2: hook exited non-zero on first dirty stop"
echo "$OUT" | grep -q '"decision":"block"' || fail "case 2: no block decision: $OUT"
[ -f "$DATA_DIR/last-changeset.sha" ] || fail "case 2: changeset hash not stored"
echo "case 2 OK: first dirty stop blocks and stores the changeset hash"

# --- Case 3: repeated stop on unchanged tree passes; new change blocks ---
OUT="$(run_hook)" || fail "case 3: hook exited non-zero on repeated stop"
[ -z "$OUT" ] || fail "case 3: repeated stop re-blocked: $OUT"
echo "case 3a OK: repeated stop on unchanged tree stays silent"

echo "x = 1" > "$GIT_DIR/new_module.py"
OUT="$(run_hook)" || fail "case 3b: hook exited non-zero after new change"
echo "$OUT" | grep -q '"decision":"block"' || fail "case 3b: new changeset did not block: $OUT"
echo "case 3b OK: a changed tree blocks again (new hash)"

# --- Case 4 (bonus): committing clears state ----------------------------
commit "second"
OUT="$(run_hook)" || fail "case 4: hook exited non-zero on clean tree after commit"
[ -z "$OUT" ] || fail "case 4: clean tree after commit produced output: $OUT"
[ ! -f "$DATA_DIR/last-changeset.sha" ] || fail "case 4: state file not cleared on clean tree"
echo "case 4 OK: clean tree clears stored state"

echo "ALL PASS"
