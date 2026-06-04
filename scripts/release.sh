#!/usr/bin/env bash
#
# release.sh — cut a lockstep release of the omniagents marketplace.
#
# Bumps every plugin.json + the marketplace manifest to ONE version, stamps the
# CHANGELOG, validates, commits, and tags vX.Y.Z. It does NOT push — review the
# commit, then:
#   git push origin main && git push origin vX.Y.Z
#   make stable VERSION=X.Y.Z   # promote to the stable channel once vetted
#
# Lockstep versioning is deliberate: Claude Code keys its plugin cache on the
# version string and skips any update where it is unchanged, so the version MUST
# advance on every published change or users silently never receive it.
#
# Usage:  make release VERSION=x.y.z      (or:  ./scripts/release.sh x.y.z)
#
set -euo pipefail

if [ "$#" -lt 1 ] || [ -z "${1:-}" ]; then
	echo "Usage: make release VERSION=x.y.z"
	echo "       (or: ./scripts/release.sh x.y.z)"
	exit 1
fi

VERSION="$1"
TAG="v$VERSION"

if ! echo "$VERSION" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.-]+)?$'; then
	echo "error: '$VERSION' is not a valid semver (expected x.y.z or x.y.z-pre)"
	exit 1
fi

# Repo root = parent of this script's directory.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! git rev-parse --git-dir >/dev/null 2>&1; then
	echo "error: not inside a git repository"; exit 1
fi
if ! git diff --quiet || ! git diff --cached --quiet; then
	echo "error: working tree is dirty; commit or stash changes before releasing"
	git status --short; exit 1
fi
if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
	echo "error: tag $TAG already exists"; exit 1
fi

MARKETPLACE=".claude-plugin/marketplace.json"
CHANGELOG="CHANGELOG.md"
[ -f "$MARKETPLACE" ] || { echo "error: $MARKETPLACE not found in $ROOT"; exit 1; }

# Portable in-place sed (GNU accepts --version; BSD/macOS does not).
if sed --version >/dev/null 2>&1; then SED_INPLACE=(sed -i); else SED_INPLACE=(sed -i ''); fi

# Manifests to bump: the marketplace + every plugin.json.
MANIFESTS=("$MARKETPLACE")
while IFS= read -r f; do MANIFESTS+=("$f"); done \
	< <(find plugins -maxdepth 3 -name plugin.json | sort)

CHANGED=("${MANIFESTS[@]}")
[ -f "$CHANGELOG" ] && CHANGED+=("$CHANGELOG")

rollback() {
	echo "Rolling back release..."
	git checkout HEAD -- "${CHANGED[@]}" 2>/dev/null || true
	git tag -d "$TAG" 2>/dev/null || true
}
trap rollback ERR

# 1. Bump the FIRST "version": "..." in each manifest. The 1,/.../ range stops at
#    the first match, so nested version-like keys are never touched.
for f in "${MANIFESTS[@]}"; do
	echo "Bumping $f -> $VERSION"
	"${SED_INPLACE[@]}" '1,/"version":/ s/"version": *"[^"]*"/"version": "'"$VERSION"'"/' "$f"
done

# 2. Stamp the CHANGELOG: rename "## [Unreleased]" to a new dated section so its
#    accumulated entries become this release, leaving a fresh empty Unreleased.
if [ -f "$CHANGELOG" ] && grep -q '^## \[Unreleased\]' "$CHANGELOG"; then
	DATE="$(date +%Y-%m-%d)"
	echo "Stamping $CHANGELOG -> [$VERSION] - $DATE"
	"${SED_INPLACE[@]}" "s/^## \[Unreleased\]\$/## [Unreleased]\\
\\
## [$VERSION] - $DATE/" "$CHANGELOG"
fi

# 3. Validate before committing (fail the release if the manifest is invalid).
if command -v claude >/dev/null 2>&1; then
	echo "Validating marketplace..."
	claude plugin validate . >/dev/null
else
	echo "warning: 'claude' not on PATH; skipping validation"
fi

# 4. Commit + annotated tag. Push is intentionally left to you.
git add "${CHANGED[@]}"
git commit -m "release: $TAG"
git tag -a "$TAG" -m "Release $TAG"

trap - ERR

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
echo ""
echo "Tagged $TAG on $(git rev-parse --short HEAD)."
echo "Next:"
echo "  git push origin $BRANCH && git push origin $TAG"
echo "  make stable VERSION=$VERSION   # promote to the 'stable' channel once vetted"
