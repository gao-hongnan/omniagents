# Plugin Gap Analysis — omniagents (2026-10-24)

A gap analysis of the omniagents marketplace at `v1.3.0` (`27a703d`). It compares the
repo against three references:

1. **The official Claude Code docs**: plugin manifest reference, create/host marketplace,
   and plugin evals.
2. **High-standard peer marketplaces**:
   [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official)
   (9 CI workflows: plugin validation, frontmatter, licenses, MCP URL checks, policy scan),
   [obra/superpowers](https://github.com/obra/superpowers) (`tests/` for hooks,
   skill size, shell lint, version bump, and Codex sync), and
   [wshobson/agents](https://github.com/wshobson/agents) (PR validation, eval reports,
   `CONTRIBUTING.md`).
3. **This repo's own rulebooks**: the `github-actions`, `testing`, and `typings` skills, and
   the [2026-07-31 skill quality audit](./2026-07-31-skill-quality-audit.md).

## How to read this

- **Complexity** is the effort to close the gap: **Low** (under an hour, mechanical),
  **Medium** (half a day to two days, a design decision or a new script), and **High**
  (several days, new infrastructure or content work across many skills).
- **Success criteria** are the must-have exit criteria. They are kept to the minimum needed
  to close the gap. Anything beyond that is in
  [Additional improvements](#additional-improvements-good-to-have).

## What is already strong (no action)

- `claude plugin validate . --strict` passes for the marketplace and all 18 plugin dirs.
- Lockstep SemVer, a scripted release (`make release`) with rollback-on-error, a
  CHANGELOG-driven GitHub Release, and a documented revert-not-force-push policy.
- Codex dual-publishing is generated, not hand-edited (`scripts/sync-codex.sh`).
- The reviewer plugin has seeded-bug fixtures that score both recall and precision, plus a
  `/doctor` self-diagnostic. Few peer plugins have this.
- Vendoring is done with provenance: `drawio/UPSTREAM.md` and the sync script.
- Hook commands quote `"${CLAUDE_PLUGIN_ROOT}"` as the docs recommend. The `doc-drift` hook
  guards `stop_hook_active`.
- Bundled Python passes `ruff` (E9/F/B).

## Summary

| ID | Gap | Complexity | Value |
| --- | --- | --- | --- |
| L1 | Orphaned plugin dirs (`tech-lead`, `notion`) and a stale audit record | Low | High |
| L2 | Docs correctness: a broken link, a wrong count, and the wrong pin syntax | Low | Medium |
| L3 | No root `LICENSE`, and no Apache-2.0 license text for vendored `drawio` | Low | High |
| L4 | `notifications` hooks fail outside macOS | Low | Medium |
| L5 | Release workflow breaks the repo's own GitHub Actions rules | Low | Medium |
| L6 | MCP servers run floating `latest` versions | Low | High |
| M1 | No CI on pull requests or `main`: validation runs only at tag time | Medium | Very high |
| M2 | Secrets passed as shell env vars instead of `userConfig` (`sensitive`) | Medium | High |
| M3 | Skill listing exceeds the default description budget (22.6k vs ~15k chars) | Medium | High |
| M4 | `doc-drift` re-blocks on every turn while the tree is dirty | Medium | Medium |
| M5 | Bundled Python tooling has no tests | Medium | Medium |
| M6 | Two SKILL.md bodies exceed the 500-line guidance | Medium | Medium |
| H1 | Evals are manual, use a format CI can't run, and cover 2 of 13 plugins | High | Very high |

---

## Low complexity

### L1 — Orphaned plugin directories and a stale audit record

**Evidence**

- `plugins/tech-lead/` contains only `.claude-plugin/plugin.json`. It has no agents,
  skills, or commands. Its description promises "Tech-lead subagent…".
- `plugins/notion/` is a working MCP wrapper, and the root `.mcp.json` uses it. It is
  missing from `.claude-plugin/marketplace.json`, from the README catalogue, and from the
  install, update, and uninstall lists. The README's Codex table does mention it.
- `scripts/release.sh` bumps every tracked `plugin.json`, so both orphans get a version
  bump on every release even though they are never published.
- The 2026-07-31 audit (§3) says `plugins/workflow`, `plugins/sre`, and `plugins/data`
  were imported and that `omniagents-tech-lead` was registered. Neither change exists
  anywhere in git history. Neither orphan was ever in the marketplace, so no `renames`
  entry is needed.

**Rationale.** Dead manifests and records of work that never landed mislead contributors
and users. Someone reading the README or the audit will look for capabilities that don't
exist.

**Value.** The catalogue becomes trustworthy: what's in `plugins/` is what ships. It also
removes a recurring source of drift.

**Success criteria**

- [ ] `notion` is either listed in `marketplace.json` with a README catalogue row,
      prerequisites, and install/update/uninstall lines, or deleted.
- [ ] `tech-lead` either ships its agent, or its directory is deleted along with its README
      mention.
- [ ] The 2026-07-31 audit gets a one-line note saying the §3 imports were never committed.
- [ ] Every `plugins/*/` directory appears in `marketplace.json`, or is deliberately listed
      as unpublished in the README.

### L2 — Docs correctness

**Evidence**

- `README.md:38` links to `./marketplace-benefits.html`, which isn't in the repo.
- `README.md:20` says "sixteen plugins under `plugins/*`". There are 18 directories and 16
  local catalogue entries.
- `README.md:416` pins with `gao-hongnan/omniagents@v0.1.0`. The official docs
  ([Host a marketplace](https://code.claude.com/docs/en/plugins/host-marketplace)) give
  the ref syntax as `owner/repo#<ref>`.
- `plugins/drawio/README.md` links to `../../shared/…` and `../../mcp-tool-server/…`, which
  only resolve in the upstream repo.

**Rationale.** The README is the install surface. The pin syntax is the documented
rollback path, so an error there breaks rollback exactly when it's needed.

**Value.** Users can install, pin, and roll back the way the docs describe.

**Success criteria**

- [ ] A markdown link check over `README.md` and `plugins/**/*.md` reports 0 broken
      relative links. Vendored files are either fixed in `sync-drawio.sh` or excluded
      explicitly.
- [ ] The pinned-channel command has been run once with the documented syntax and works.
- [ ] Plugin counts in the README match `marketplace.json`.

### L3 — Licensing

**Evidence**

- The repo has no `LICENSE` file. The README says "MIT", and 15 manifests declare
  `"license": "MIT"`.
- `plugins/drawio` is Apache-2.0 (vendored) and doesn't include the license text.
  Apache-2.0 §4(a) requires giving recipients a copy.
- Peers ship root `LICENSE` files, and `claude-plugins-official` runs a
  `validate-licenses.yml` gate.

**Rationale.** Without a license file the code isn't legally reusable, whatever the README
says. The vendored code also currently breaks its upstream license terms.

**Value.** Legal clarity for users and organizations. Organizations often require it before
adding a marketplace with `extraKnownMarketplaces`.

**Success criteria**

- [ ] The repo has a root `LICENSE` (MIT) with the copyright holder.
- [ ] `plugins/drawio/LICENSE` (Apache-2.0, copied from upstream) exists, and
      `sync-drawio.sh` copies it on every re-sync.

### L4 — `notifications` hooks fail outside macOS

**Evidence.** The three scripts call `osascript` under `set -euo pipefail` with no platform
guard. On Linux or Windows, every Notification and Stop event fails the hook. The docs
recommend `defaultEnabled`, and peers like superpowers test their hooks across platforms.

**Rationale.** A hook that errors on every turn is worse than having no hook. Teams with
mixed operating systems that install the plugin at project scope will hit it.

**Value.** The plugin becomes safe to install at project scope.

**Success criteria**

- [ ] Each script exits 0 silently when `osascript` isn't on `PATH`.
- [ ] The README states "no-op on non-macOS".

### L5 — Release workflow breaks the repo's own GitHub Actions rules

**Evidence.** In `.github/workflows/release.yml`:

- `actions/checkout@v6` and `softprops/action-gh-release@v3` are pinned by tag, not by SHA.
- There is no top-level `permissions:`, so the `validate` job runs with default token
  scope.
- `npm install -g @anthropic-ai/claude-code` installs an unpinned version.
- `--strict` isn't used.

The `omniagents-devops:github-actions` skill names each of these as a smell. The official
docs recommend `--strict` for CI.

**Rationale.** The only workflow in a repo that teaches workflow hardening breaks its own
rules. That's a credibility gap and a real supply-chain exposure on a job with
`contents: write`.

**Value.** Release-path supply-chain hardening, and the repo practices what it teaches.

**Success criteria**

- [ ] All `uses:` are pinned to full commit SHAs with a version comment.
- [ ] Top-level `permissions: contents: read`, with `contents: write` only on the release
      job.
- [ ] The Claude Code CLI version is pinned, and validation runs with `--strict`.

### L6 — MCP servers run floating versions

**Evidence.** These launch commands resolve to whatever is newest at session start:

- `npx @playwright/mcp@latest`
- `npx -y @colbymchenry/codegraph`
- `uvx --upgrade code-review-graph`
- `uvx workspace-mcp`
- `npx -y @notionhq/notion-mcp-server`

The README promises "one tag to roll back to", but rolling back the tag doesn't roll back
the MCP code users execute.

**Rationale.** Unpinned `npx`/`uvx` on every session start is a supply-chain risk. A
compromised or broken upstream release reaches every user immediately. It also makes
regressions impossible to bisect by release tag.

**Value.** Releases become reproducible, and upstream changes become deliberate,
reviewable version bumps.

**Success criteria**

- [ ] Every stdio MCP launch command names an exact version (`pkg@x.y.z` /
      `pkg==x.y.z`), with no `--upgrade` and no `@latest`.
- [ ] The README states the bump policy, for example "MCP versions are bumped in a normal
      release PR".

---

## Medium complexity

### M1 — No CI on pull requests or `main`

**Evidence.** The only workflow triggers on `v*` tags. Validation, Codex sync, and link
integrity are never checked before merge, so a broken manifest is found only at release
time. `.markdownlint.json` and `.prettierrc` exist but nothing runs them. Peers gate every
PR: `claude-plugins-official` has `validate-plugins.yml` and `validate-frontmatter.yml`,
and `wshobson/agents` has `validate.yml`.

**Rationale.** This is the biggest structural gap. Several gaps above (L1, L2, and Codex
drift) can only happen because nothing checks the tree between releases. One workflow
prevents a whole class of regressions.

**Value.** Very high. Problems are caught at PR time instead of release time, and the
checks run without anyone remembering to run them.

**Success criteria.** A `validate.yml` runs on `pull_request` and on `push` to `main`, and
fails on any of these:

- [ ] `claude plugin validate . --strict`, plus each `plugins/*/` with `--strict`.
- [ ] Codex drift: `./scripts/sync-codex.sh && git diff --exit-code`.
- [ ] Broken relative markdown links (the check from L2).
- [ ] Skill frontmatter rules: `name` equals the directory name, `description` is 1–1,024
      characters, and `description` plus `when_to_use` is at most 1,536 characters.
- [ ] The workflow follows L5's hardening rules.

### M2 — Secrets passed as shell env vars instead of `userConfig`

**Evidence**

- `context7` reads `${CONTEXT7_API_KEY}`, and `google-workspace` reads
  `${GOOGLE_OAUTH_CLIENT_SECRET}` (and more) from the shell.
- The README tells users to
  `echo 'export CONTEXT7_API_KEY=…' >> ~/.zshrc`.
- The plugin reference provides `userConfig` with `sensitive: true`. Claude Code then
  prompts when the plugin is enabled, stores the value in the OS keychain, and substitutes
  `${user_config.KEY}` into MCP `env` and `headers`.

**Rationale.** A plaintext secret in a dotfile is exposed to every process the user runs
and is easy to commit by accident. The official mechanism removes that and makes setup a
prompt instead of a doc page.

**Value.** Better security, and much easier first-run setup for the three credentialed
plugins.

**Success criteria**

- [ ] `context7` and `google-workspace` (and `notion`, if kept by L1) declare their
      credentials in `userConfig`. Secrets are `sensitive: true`. The `.mcp.json` files
      reference `${user_config.*}`.
- [ ] `claude plugin validate --strict` passes, and a fresh install prompts for the values.
- [ ] The README's `export … >> ~/.zshrc` instructions are removed.

### M3 — Skill listing exceeds the default description budget

**Evidence.** Measured on 2026-10-24:

- `description` plus `when_to_use` across all 32 skills totals **22,600 characters**. The
  default listing budget is about **15,000 characters** (roughly 1% of context; see the
  audit's §1).
- When the listing overflows, Claude Code silently drops descriptions, least-invoked first.
- The largest entries are `python/testing` (1,493), `writing/blueprint` (1,103),
  `typescript/testing` (1,018), and `typescript/typings` (985).
- The audit logged this as backlog P1, and it's still open.

**Rationale.** A skill whose description gets dropped never auto-triggers. Users who
install the full suite lose skills invisibly. This is the "installed and completely inert"
failure the audit warns about.

**Value.** Every installed skill stays discoverable. This directly affects how often skills
activate, which is the product.

**Success criteria**

- [ ] The full-suite total of `description` plus `when_to_use` is at most 15,000
      characters, enforced by the M1 frontmatter check.
- [ ] Each trimmed skill keeps its primary trigger in the first sentence (truncation cuts
      from the end).

### M4 — `doc-drift` re-blocks on every turn while the tree is dirty

**Evidence.** `check-doc-drift.sh` blocks Stop whenever `git status` shows any modified
source file. `stop_hook_active` only prevents a loop within one stop sequence. On the next
user turn the tree is still dirty, so the hook blocks again. In a long session that means a
forced documentation review after every turn until the user commits. The hook also counts
changes the user made outside the session.

**Rationale.** A hook that fires on every turn costs tokens and trains users to uninstall
it. The intent is "after code changes", not "while uncommitted changes exist".

**Value.** The hook stays useful in long sessions instead of becoming noise.

**Success criteria**

- [ ] The hook blocks at most once per distinct change set. For example, it stores a hash
      of `git diff` plus the untracked list in `${CLAUDE_PLUGIN_DATA}` and skips when the
      hash is unchanged.
- [ ] A shell test covers three cases: a clean tree passes, a first dirty stop blocks, and
      a repeated stop on an unchanged tree passes. The test runs in M1's CI.

### M5 — Bundled Python tooling has no tests

**Evidence.** These scripts have no tests and no type-check run:

- `review-contract/schema.py`: 753 lines. It's the contract validator the reviewer
  pipeline and evals depend on.
- `post_pr_comments.py`: 260 lines. It writes to GitHub.
- `doctor.py`: 349 lines.
- `check_diagram.py`: 248 lines.

The repo ships strict-typing and testing rulebooks (`omniagents-python:typings`,
`:testing`), and superpowers keeps a `tests/` tree for its tooling.

**Rationale.** `schema.py` is the gate everything else trusts. A regression there silently
corrupts every review and every eval grade. `post_pr_comments.py` has external side
effects.

**Value.** The reviewer's precision pipeline gets a trustworthy foundation, and the repo
applies its own Python standards to itself.

**Success criteria**

- [ ] `pytest` covers `schema.py`: at least one valid and one invalid artifact per schema
      kind. It also covers `post_pr_comments.py`'s dry-run path with no network calls.
- [ ] The tests run in M1's CI.

### M6 — Two SKILL.md bodies exceed the 500-line guidance

**Evidence.** `python/library-patterns` has 642 lines and `typescript/library-patterns` has
604. The platform best-practices guidance says to keep bodies under 500 lines and move the
rest to `references/`. After compaction, only the first ~5k tokens of each skill
re-attach. The audit logged this as P2, and it's still open.

**Rationale.** Long monoliths get truncated after compaction, which is exactly when a
session is longest. The `testing` skills already prove the hub-plus-references split.

**Value.** Guidance survives compaction, and only the relevant reference loads.

**Success criteria**

- [ ] Both SKILL.md files are under 500 lines, with the rest moved to one-level-deep
      `references/` files that the hub links to.
- [ ] No rule is lost. A diff review confirms every removed section exists in a reference.

---

## High complexity

### H1 — Evals are manual, can't run in CI, and cover 2 of 13 plugins

**Evidence**

- Only `reviewer` (7 fixtures) and `unknowns` (6 scenarios, `depth-pass` only) have evals.
  The other 30 skills have none, including the most-used `python` and `typescript` skills.
- Both suites use skill-creator's `evals/evals.json` format and are run by hand. The
  official `claude plugin eval` doesn't read that format. It expects `evals/<case>/` with
  `prompt.md` and `graders/`, and it gates CI through exit codes, `--max-cost-usd`, and
  pinned `--model`/`--judge-model`. It also uses `evals/` as its default directory, which
  collides with the current layout.
- The audit logged eval adoption as P4, and it's still open.

**Rationale.** Activation and outcome quality are what these plugins exist for, yet nothing
measures them between releases. A model update or a description trim (M3) could cut
activation in half without anyone noticing. Without the official runner there is also no
no-plugin baseline to show what a plugin adds.

**Value.** Very high. This is the only way to know that releases improve behavior, and it
protects the M3 and M6 edits from regressions.

**Success criteria**

- [ ] The reviewer and `depth-pass` suites are ported to `claude plugin eval` format.
      Existing fixtures are reused, and the recall and precision assertions become
      `file_exists`, `regex`, or `llm` graders.
- [ ] Three high-traffic skills (`python:typings`, `python:testing`,
      `devops:github-actions`) each get at least one should-trigger case, one
      should-not-trigger case, and a `skill-fired` grader.
- [ ] A `workflow_dispatch` (manual) CI job runs the suites with pinned models,
      `--trust-plugin`, and `--max-cost-usd`, and archives `results.json`.
- [ ] The release checklist records the pass rate and the with-vs-without delta in the
      CHANGELOG for each release.

---

## Additional improvements (good to have)

None of these is needed to close a gap above. Each is worth doing once the must-haves land.

| Item | Why | Complexity |
| --- | --- | --- |
| Migrate `reviewer/commands/*.md` to `skills/` | The plugin reference says "Prefer `skills/` for new plugins". One mechanism, and the same behavior in Codex | Low |
| Drop explicit-default frontmatter (`disable-model-invocation: false`, `user-invocable: true`, `model: inherit`, `shell: bash`) | Audit P5. Less noise, and helps the M3 budget slightly | Low |
| Add `$schema` and `displayName` to manifests | Editor autocomplete and nicer `/plugin` labels | Low |
| `CONTRIBUTING.md` and `SECURITY.md` | Peers ship them. They tell contributors about the release, eval, and Codex-sync workflow | Low |
| TOCs on reference files longer than 100 lines | Audit P3. Lets Claude navigate long references | Low |
| Optional Linux `notify-send` support in `notifications` | Turns L4's no-op into real cross-platform support | Low |
| Renovate or Dependabot for SHA-pinned actions and pinned MCP versions | Keeps the L5 and L6 pins fresh without manual work | Low |
| `relevance` blocks on marketplace entries | Claude Code can suggest, for example, `omniagents-devops` in repos with `*.tf` or `Dockerfile` | Medium |
| Pre-commit config (markdownlint, prettier, shellcheck, ruff) | Faster local feedback than CI. Reuses the existing `.markdownlint.json` and `.prettierrc` | Low |
| Version range on the `terraform-skill` dependency | `dependencies` supports semver ranges, which makes the external pin explicit at the plugin level | Low |
| Evals for the remaining skills, and `blindspot-pass` | Extends H1 beyond the first set | High |
| Root `.mcp.json` generated from `plugins/*/.mcp.json` | Removes duplicated config that can drift; the root copy is a dev convenience | Low |
| Hide or remove the empty `[Unreleased]` CHANGELOG section in the release body | Cosmetic | Low |

## Suggested order

1. **L1–L6.** One afternoon. Each change is mechanical and stands alone.
2. **M1.** The gate that keeps L1–L6 fixed. Its frontmatter check also enforces M3.
3. **M2, M4, M5.** Independent of each other, so they can run in parallel.
4. **M3 and M6, after H1's trigger cases exist.** Trimming descriptions without an
   activation eval is guesswork.
5. **H1.**

## Sources

- Claude Code docs:
  [Plugin manifest reference](https://code.claude.com/docs/en/plugins-reference) ·
  [Create a marketplace](https://code.claude.com/docs/en/plugin-marketplaces) ·
  [Host and maintain a marketplace](https://code.claude.com/docs/en/plugins/host-marketplace) ·
  [Test plugins with evals](https://code.claude.com/docs/en/plugin-evals) ·
  [Skills](https://code.claude.com/docs/en/skills)
- Skill authoring:
  [Platform best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) ·
  [Agent Skills spec](https://agentskills.io/specification)
- Peers: [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) ·
  [obra/superpowers](https://github.com/obra/superpowers) ·
  [wshobson/agents](https://github.com/wshobson/agents) ·
  [anthropics/skills](https://github.com/anthropics/skills)
- Internal: [2026-07-31 skill quality audit](./2026-07-31-skill-quality-audit.md)
