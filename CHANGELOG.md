# Changelog

All notable changes to the **omniagents** marketplace are recorded here. The
format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the
marketplace uses lockstep [Semantic Versioning](https://semver.org/) — every
plugin moves together under one version per release. See
[Versioning and releases](./README.md#versioning-and-releases) in the README for
the bump rules and the release workflow.

## [Unreleased]

## [1.1.0] - 2026-09-19

### Added

- **`omniagents-devops:kong`** — a research-first playbook for Kong Gateway and
  Konnect. Deliberately encodes **no Kong best practices**: Kong ships several
  gateway releases a year and the same question has different correct answers in
  OSS, Enterprise, and Konnect, so a frozen rulebook would rot silently. It
  encodes the research protocol instead — anchor version/edition/deployment
  mode/config tool before answering; check for (and offer to install) Kong's own
  bundled agent skills; pull current docs via context7 with a source-precedence
  order and an explicit distrust list; route by question genre across decK vs
  kongctl vs KIC/Operator vs the two Terraform providers vs custom-plugin
  authoring; verify the traps where model priors are reliably stale
  (Enterprise-only plugin gating, plugin execution order, `BasePlugin` removed in
  3.0, DB-less read-only Admin API); then cite version + edition + URL on every
  recommendation. Closes with a T1/T2/T3 enterprise table sharing the infra
  reference rows used across the other `omniagents-devops` skills.

- **`omniagents-design-patterns:system` → `growth.md`** — an eighth reference
  file (~509 lines), the load-indexed entry into the catalogue. The other seven
  files answer *which shape*; this one answers *which resource saturates next,
  and which shape relieves it*, split by write path and read path. Anchors-not-
  triggers table (how payload size, working set, and write mix move every
  threshold), USE-method saturation signals, a Little's Law sizing sketch, then
  Rungs 0–4 — each naming what breaks, the signal that proves it, the smallest
  move on each path, the contracts that move makes mandatory, its stop sign, and
  the entry elsewhere in the skill holding the sketch. Ends with anti-ladder
  failure modes and a capacity-review checklist.

### Changed

- **`omniagents-design-patterns:system`** — routes load-shaped questions ("what
  breaks next", a capacity review, a raw load number) to `growth.md` first, and
  widens the skill description to cover capacity planning. `data.md` gains a
  Storage Engine entry (B-tree vs LSM by the RUM trade) that the ladder's write
  amplification rung depends on; `communication.md` picks up the matching
  cross-reference.

## [1.0.0] - 2026-09-12

### Changed

- **BREAKING — `omniagents-iac` is now `omniagents-devops`** (directory
  `plugins/iac/` → `plugins/devops/`). The plugin holds three skills —
  `terraform` (provisioning), `docker` (packaging), and `github-actions`
  (pipelines) — and only the first is infrastructure-as-code in any standard
  sense. The label described one of three skills, so it was wrong; the skills
  themselves are unchanged in content by this release.

  **Migration** — the install name and the skill prefixes both change:

  ```bash
  # Claude
  claude plugin uninstall omniagents-iac@omniagents --prune
  claude plugin marketplace update omniagents
  claude plugin install omniagents-devops@omniagents

  # Codex
  codex plugin remove omniagents-iac@omniagents
  codex plugin add omniagents-devops@omniagents
  ```

  Skill invocation names change from `omniagents-iac:<skill>` to
  `omniagents-devops:<skill>` (`terraform`, `docker`, `github-actions`).
  Anything pinned to `v0.13.0` or earlier is unaffected and keeps the old
  names.

## [0.13.0] - 2026-09-12

### Added

- **`omniagents-iac:github-actions`** — a production rulebook for
  GitHub Actions workflows and custom actions, built on the same shape
  as the `docker` and `terraform` skills: thirteen default-posture
  non-negotiables (explicit `permissions`, SHA-pinned `uses` **with**
  an automated bumper, no untrusted context in `run:` bodies,
  `concurrency` and `timeout-minutes` everywhere, explicit `shell: bash`
  for `pipefail`, no fork code under `pull_request_target` /
  `workflow_run`, OIDC over static cloud keys, `persist-credentials:
  false`, no trigger filters on required checks, named secrets over
  `secrets: inherit`, no caches in release workflows, and
  actionlint + zizmor as the CI-for-the-CI gate), the shared T1/T2/T3
  tiering table mapped to pipelines, and two quick-paths (canonical PR
  CI, OIDC deploy behind an environment gate). Five references:
  `workflow-design.md` (triggers, the required-check filter trap, job
  graph, concurrency, matrix, shell discipline, contexts and
  environment files, caching, artifacts, runners, platform limits),
  `security.md` (permissions scopes, supply chain and CVE-2025-30066,
  script and `GITHUB_ENV` injection, fork-PR trust boundaries with the
  safe `workflow_run` handoff, cache poisoning and ArtiPACKED, secrets,
  OIDC `sub` claim design, environments, self-hosted runners, runtime
  hardening, compromise runbook), `reuse.md` (reusable-workflow vs
  composite vs JS/Docker decision table, `action.yml` reference,
  versioning and immutable publishing, testing an action),
  `gates-and-release.md` (actionlint/zizmor config with SARIF upload,
  Dependabot for actions, required checks and merge queue, environment
  protection rules, release workflow shape with trusted publishing and
  provenance, cost control), and `smells.md` (35 named smells with
  severity, symptom, fix, and a ten-question review checklist).

## [0.12.0] - 2026-08-30

### Added

- **Python production bar across skills** — the python, design-patterns,
  and reviewer plugins now enforce the applicable openai-python subset
  (NewType domain IDs, `Literal`/`StrEnum` closed sets, pydantic at every
  parse boundary, consolidated single-owner settings, no value
  fabrication). `omniagents-reviewer` gains a **Domain-Value Discipline**
  hunt plus Recall Sweep checks in `design-review`, and the design
  specialist preloads `omniagents-python:pydantic`, so audits now reach
  the content. `omniagents-design-patterns` ships the new
  **`codebase-design`** skill (Ousterhout interface depth: deep vs
  shallow modules, information hiding, deletion test, design-it-twice) —
  previously referenced by the marketplace manifest but never published —
  and the `software` anti-patterns catalogue gains two entries,
  `scattered-configuration` and `hand-rolled-boundary-coercion`, plus a
  table of contents and two review-checklist items.
- `omniagents-python:typings`: "Traps Reviewers Should Catch" section
  (isinstance-coercion families, fabricated fallbacks, costume aliases,
  two-owner defaults, docstring-defended smells); `NewType` rebalanced
  from alias-default to boundary-driven with an openai-python
  `FileId`-style domain-ID example; the `Final` rule routes
  configuration-valued constants to a pydantic Settings tree; trigger
  vocabulary extended; table of contents in canonical examples.
- `omniagents-python:pydantic`: `TypeAdapter`/boundary models positioned
  as the replacement for hand-rolled isinstance coercion at untrusted
  boundaries; two new Anti-Patterns; the Settings section documents the
  migration from scattered module constants to one settings tree
  (including the sanctioned library exception that exports a frozen
  config object for the consumer to nest).
- `omniagents-python:library-patterns`: domain-identifier
  non-negotiable (`NewType` ids, `Literal` request params) and
  `StrEnum` / PEP 604 consistency fixes in examples.
- Source dossier for all of the above with verification record:
  `docs/superpowers/specs/2026-08-30-python-production-bar.md`; the
  skill-quality audit research doc is now tracked.

### Fixed

- `omniagents-python:testing` trigger wording trimmed back under the
  per-skill listing budget (tail keywords were silently truncated).
- `plugins/reviewer/scripts/doctor.py` had a Python 2 `except` syntax
  error and could not run at all.
- design-patterns manifest (Claude + Codex), marketplace, and README now
  consistently describe the three-skill layout.

## [0.11.0] - 2026-08-02

### Added

- **OpenAI Codex marketplace support** — the repo now doubles as a Codex
  plugin marketplace (Codex CLI ≥ 0.146). `scripts/sync-codex.sh` (run via
  `make sync-codex`, and automatically inside `make release`) generates a
  `.codex-plugin/plugin.json` byte-copy for every skill-bearing plugin plus
  the catalog at `.agents/plugins/marketplace.json`, filtered to the
  plugins that ship `skills/`. Hooks, subagents, MCP wrappers, and the
  external `terraform-skill` remain Claude-only. Install with
  `codex plugin marketplace add gao-hongnan/omniagents`, then
  `codex plugin add <plugin>@omniagents`.

## [0.10.0] - 2026-07-26

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
