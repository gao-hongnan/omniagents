.DEFAULT_GOAL := help

MARKETPLACE := .claude-plugin/marketplace.json

# ==================================================================
# Quality
# ==================================================================

.PHONY: validate
validate:
	claude plugin validate .

# ==================================================================
# Release  (lockstep — every plugin moves together under one version)
# ==================================================================

.PHONY: release
release:
	@test -n "$(VERSION)" || { echo "Usage: make release VERSION=x.y.z"; exit 1; }
	@./scripts/release.sh $(VERSION)

.PHONY: stable
stable:
	@test -n "$(VERSION)" || { echo "Usage: make stable VERSION=x.y.z"; exit 1; }
	@git rev-parse -q --verify "refs/tags/v$(VERSION)" >/dev/null \
		|| { echo "error: tag v$(VERSION) not found; run 'make release VERSION=$(VERSION)' first"; exit 1; }
	git branch -f stable "v$(VERSION)"
	@echo "Moved 'stable' -> v$(VERSION). Publish it:  git push origin stable"

# ==================================================================
# Help
# ==================================================================

.PHONY: help
help:
	@echo "Quality:"
	@echo "  make validate                Validate the marketplace manifest"
	@echo ""
	@echo "Release (lockstep — all plugins share one version):"
	@echo "  make release VERSION=x.y.z   Bump all manifests, stamp CHANGELOG, validate, commit, tag vX.Y.Z"
	@echo "  make stable  VERSION=x.y.z   Move the 'stable' channel to tag vX.Y.Z (promote, or roll back)"
	@echo ""
	@echo "release/stable do not push. After 'make release', review then:"
	@echo "  git push origin main && git push origin vX.Y.Z"
	@echo "  make stable VERSION=x.y.z && git push origin stable"
