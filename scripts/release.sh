#!/usr/bin/env bash
#
# release.sh — cut a lockstep release of the omniagents marketplace.
#
# Bumps every plugin.json + the marketplace manifest to ONE version, stamps the
# CHANGELOG, validates, commits, and tags vX.Y.Z. It does NOT push — review the
# commit, then:
#   git push origin main && git push origin vX.Y.Z
# Pushing the tag triggers the RELEASE workflow, which validates and publishes
# the GitHub Release from the matching CHANGELOG section.
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

command -v jq >/dev/null 2>&1 || { echo "error: jq is required but not on PATH"; exit 1; }

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

# Set a jq path to $VERSION, failing loudly if the path is absent so a manifest
# with an unexpected shape never silently goes unbumped. Atomic write-back.
bump() {  # $1=file  $2=jq path (e.g. .version)
	local f="$1" path="$2" tmp
	tmp="$(mktemp)"
	echo "Bumping $f -> $VERSION"
	jq --arg v "$VERSION" \
		"if ($path) == null then error(\"$f: missing $path\") else $path = \$v end" \
		"$f" > "$tmp" && mv "$tmp" "$f"
}

# 1. Bump versions. The marketplace carries its version at .metadata.version;
#    every plugin.json carries it at the top-level .version.
#    (The find above also matches .codex-plugin/plugin.json copies; bumping
#    them is harmless since the next step regenerates them anyway.)
bump "$MARKETPLACE" '.metadata.version'
for f in "${MANIFESTS[@]:1}"; do bump "$f" '.version'; done

# 1.5 Regenerate the Codex-side manifests from the bumped Claude manifests so
#     both marketplaces publish in lockstep (Codex also keys its plugin cache
#     on the version string). See scripts/sync-codex.sh.
./scripts/sync-codex.sh
CHANGED+=(".agents/plugins/marketplace.json")
while IFS= read -r f; do CHANGED+=("$f"); done \
	< <(find plugins -maxdepth 3 -path '*/.codex-plugin/plugin.json' | sort)

# 2. Stamp the CHANGELOG: insert a dated section after "## [Unreleased]" so its
#    accumulated entries become this release, leaving a fresh empty Unreleased.
if [ -f "$CHANGELOG" ] && grep -q '^## \[Unreleased\]$' "$CHANGELOG"; then
	DATE="$(date +%Y-%m-%d)"
	echo "Stamping $CHANGELOG -> [$VERSION] - $DATE"
	tmp="$(mktemp)"
	awk -v ver="$VERSION" -v date="$DATE" '
		{ print }
		/^## \[Unreleased\]$/ { print ""; print "## [" ver "] - " date }
	' "$CHANGELOG" > "$tmp" && mv "$tmp" "$CHANGELOG"
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
