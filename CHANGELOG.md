# Changelog

All notable changes to the **omniagents** marketplace are recorded here. The
format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the
marketplace uses lockstep [Semantic Versioning](https://semver.org/) — every
plugin moves together under one version per release. See
[Versioning and releases](./README.md#versioning-and-releases) in the README for
the bump rules and the release workflow.

## [Unreleased]

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
