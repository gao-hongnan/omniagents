# Changelog

All notable changes to the **omniagents** marketplace are recorded here. The
format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the
marketplace uses lockstep [Semantic Versioning](https://semver.org/) — every
plugin moves together under one version per release. See
[Versioning and releases](./README.md#versioning-and-releases) in the README for
the bump rules and the release workflow.

## [Unreleased]

### Added

- `omniagents-iac`: new plugin — infrastructure-as-code conventions, two
  skills. `terraform` is a house-layer rulebook (module design, state and
  environments, security and gates, modern features 1.3→1.15, and a
  T1/T2/T3 tiering framework: name your tier before naming controls) that
  routes deep failure-mode and state-surgery work to Anton Babenko's
  `terraform-skill` instead of restating it — wired into this marketplace
  as an external entry (`ref: v1.17.1`) and a declared plugin dependency.
  `docker` is a full production catalogue: Dockerfile layering, cache and
  bind mounts, base-image discipline (Alpine-for-Python ban), the
  canonical uv two-phase build, compose file-layering / profiles /
  single-host production, CIS-derived runtime hardening, supply chain
  (SBOM, provenance, cosign, Trivy as the house scanner), and CI
  build-push / multi-arch / tag-strategy conventions.

## [0.8.0] - 2026-07-10

### Changed

- `omniagents-python`, `omniagents-typescript`: the `typings` skills now catch
  closed sets hiding at call sites — a `str` / `string` parameter fed only
  bare literals (`record("result_probe")`, `publish(state="failed")`) must be
  typed as the closed set it is (`Literal[...]` / `StrEnum` in Python, a
  literal or `as const`-derived union in TypeScript), enum members and
  derived-union members are never stringified or widened back to plain
  strings at call sites, and inline numeric literals with semantic weight are
  promoted to named constants (`Final` in Python, module-level `const` in
  TypeScript). Previously every closed-set rule triggered only from declared
  constants, so magic strings feeding string-typed parameters slipped through
  reviews.

## [0.7.0] - 2026-07-08

## [0.6.0] - 2026-07-04

### Added

- `codegraph`: new MCP plugin — tree-sitter knowledge-graph tools (symbol
  search, callers/callees, impact analysis) auto-syncing on file changes
  (requires Node.js + npm on PATH).
- `omniagents-unknowns`: new plugin with the `blindspot-pass` skill —
  `/blindspot-pass` (or model-invoked) surveys unfamiliar territory, surfaces
  the user's unknown unknowns via the four-quadrant framework, and converts them
  into a sharper prompt.

### Removed

- `omniagents-research`: the medical-research plugin was removed entirely —
  `/medical-research`, `/research-doctor`, and the citation-verifier /
  evidence-adjudicator / hypothesis-critic / retriever agents are gone. This
  release also drops the marketplace entry that had been left pointing at the
  deleted `./plugins/research` directory (which broke `make validate`).

## [0.5.0] - 2026-06-19

## [0.4.0] - 2026-06-12

### Added

- `RELEASE` GitHub Actions workflow: on every `v*` tag it validates the
  marketplace and publishes a GitHub Release from the matching `CHANGELOG.md`
  section.
- `omniagents-reviewer`: eval fixtures covering IDOR on a sibling endpoint, loop
  query amplification (N+1), duplicate-validator drift, a no-regression bugfix,
  and a one-shot column rename.

### Changed

- `omniagents-reviewer`: rewrote every specialist review skill around an
  explicit **Hunt Protocol**, tightened the specialist agent prompts, the
  review/doctor commands, and the review contract, and refreshed the eval
  harness and plugin description.
- Release tooling now bumps manifest versions with `jq` (targeting `.version` /
  `.metadata.version`) instead of a `sed` range, and stamps the `CHANGELOG` with
  `awk`.

### Removed

- The `stable` release channel: the `make stable` target and the CI
  stable-promotion job are gone. Releases are cut as immutable version tags off
  `main`.

## [0.3.0] - 2026-06-10

## [0.2.0] - 2026-06-10

## [0.1.0] - 2026-06-04

### Added

- Initial marketplace with 10 plugins: `omniagents-python`,
  `omniagents-typescript`, `omniagents-design-patterns`, `omniagents-writing`,
  `omniagents-reviewer`, `code-review-graph`, `context7`, `google-workspace`,
  `notifications`, `doc-drift`.
- Per-entry `category` and `keywords` for discovery in the `/plugin` UI.
- `make release` / `make stable` workflow with lockstep versioning and a
  `stable` release channel.
