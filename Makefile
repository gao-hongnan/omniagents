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
	@echo ""
	@echo "release does not push. After 'make release', review then:"
	@echo "  git push origin main && git push origin vX.Y.Z"
