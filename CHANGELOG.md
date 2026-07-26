# Changelog

All notable changes to the **omniagents** marketplace are recorded here. The
format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the
marketplace uses lockstep [Semantic Versioning](https://semver.org/) — every
plugin moves together under one version per release. See
[Versioning and releases](./README.md#versioning-and-releases) in the README for
the bump rules and the release workflow.

## [Unreleased]

### Added

- `omniagents-python`, `omniagents-typescript`: new `testing` skill in each
  plugin — a strict, enterprise-grade rulebook for `pytest` (Python 3.14+ /
  pytest 9) and `Vitest 4` (TS 6.0+) suites. Both enforce the same spine:
  tests are typed and linted like `src/`; warnings-as-errors and strict
  runner config; determinism by construction (faked network/clock/sleep/rng,
  no real timers); order-independent, parallel-safe suites; assert outcomes,
  not call traffic ("name the mutant each test kills"); and designed seams
  over global patching. Enterprise coverage includes suite architecture
  (unit/integration split, conftest/`projects` layering), the test-double
  vocabulary, boundary control (`MockTransport`/respx, MSW, autospec vs
  fakes), hermeticity and ambient state (`tmp_path`/`vi.stubEnv`,
  env/global/cache isolation, `vi.hoisted`), typed test-data builders
  (polyfactory for pydantic; `satisfies` builders for TS), property-based
  and model-based testing (hypothesis / fast-check), integration via
  testcontainers with transaction isolation, cross-team contract testing
  (Pact / schemathesis), coverage/mutation gates, and log/accessibility as
  tested contracts (`caplog` / `vitest-axe`). Each skill defers the
  red-green-refactor process to superpowers' `test-driven-development` and
  is the write-side complement to the `omniagents-reviewer` testing
  protocol. The Python skill additionally sorts every check into three gate
  tiers (G1 blocking / G2 gated job / G3 scheduled canary), so
  nondeterministic work gets a declared home off the merge path instead of
  contradicting the determinism spine: network hermeticity enforced by
  `--disable-socket` rather than convention, a remote-failure taxonomy in
  place of single-sad-path boundary tests, retry / circuit-breaker /
  idempotency assertions, type-level tests (`assert_type`,
  `pyright --verifytypes`) mirroring the TypeScript sibling, OpenTelemetry
  spans as tested contracts alongside logs, pytest 9's core `subtests` and
  native `[tool.pytest]` TOML configuration, memory and benchmark gates
  (pytest-memray; pytest-benchmark vs instruction counting) at G2, and the
  harness-tests-versus-LLM-evals boundary at G3. Chaos tooling and profiling
  workflows are explicitly scoped out and routed elsewhere.
- `omniagents-python`, `omniagents-typescript`: the `testing` skills ship
  hub-and-spoke — a lean routing `SKILL.md` per language plus `references/`
  split by level (`unit`, `integration`) and concern
  (`doubles-and-boundaries`, `determinism`, `property-based`,
  `gates-and-ci`; Python adds `fixtures-and-factories`, `resilience`,
  `evals`; TypeScript adds `components`). Every reference file cites its
  primary sources (Fowler, Google's SWE book, Khorikov, Meszaros, GOOS,
  Beck, Feathers, Dodds, Hillel Wayne, and official tool docs) with package
  versions verified 2026-07-26. The research dossier behind the split — 53
  source entries, 26 package verifications, and the eight corrections it
  forced (pytest 9.1 removals already shipped, Hypothesis's auto-loaded
  built-in `ci` profile, Vitest 4's `restoreMocks` narrowing and its
  mandatory `mockReset` pairing, Playwright 1.62 first-class component
  testing, among others) — is committed at
  `docs/superpowers/specs/2026-07-26-testing-skill-references-research.md`.
  Hub routing was verified by fourteen fresh-agent retrieval tests (14/14
  correct first-hop) and methodology coverage was audited file-by-file
  against the dossier canon.

## [0.9.0] - 2026-07-20

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
