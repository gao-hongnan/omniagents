# omniagents

A Claude Code plugin suite — coding conventions, design patterns, and MCP server
integrations packaged as installable skills. The skill-bearing plugins are also
published to OpenAI Codex from the same repo — see
[OpenAI Codex support](#openai-codex-support).

---

## Marketplace and plugins: how they relate

A **plugin** is a self-contained unit of capability — skills, agents, hooks, MCP
servers, or LSP servers — optionally described by a `.claude-plugin/plugin.json`
manifest. A **marketplace** is the catalog that distributes plugins:
["A plugin marketplace is a catalog that lets you distribute plugins to others."](https://code.claude.com/docs/en/plugin-marketplaces)
One marketplace lists many plugins, and each plugin entry only needs a `name`
and a `source` telling Claude Code where to fetch it from.

This repository _is_ a marketplace. The catalog lives at
`.claude-plugin/marketplace.json`; each of the sixteen plugins under `plugins/*`
carries its own `.claude-plugin/plugin.json` (one further entry,
`terraform-skill`, is sourced externally from GitHub rather than a local
directory):

| Layer       | File                                        | Role                                |
| ----------- | ------------------------------------------- | ----------------------------------- |
| Marketplace | `.claude-plugin/marketplace.json`           | Catalog — lists plugins and sources |
| Plugin      | `plugins/<name>/.claude-plugin/plugin.json` | Capability — skills, agents, hooks  |

The **marketplace source** and the **plugin source** are distinct concepts. The
marketplace source is where the catalog itself lives (set when you run
`/plugin marketplace add`). Each **plugin source** is where an individual plugin
is fetched (the `source` field inside `marketplace.json`). They are pinned
independently: marketplace sources support a branch/tag `ref`; plugin sources
support both `ref` and an exact commit `sha`.

For a visual overview of why this model pays off across an organization, open
[`marketplace-benefits.html`](./marketplace-benefits.html) in a browser.

---

## Creating a marketplace and a plugin

The two artifacts are authored in the order capability → catalog. The steps
below condense the official Claude Code guides; see [References](#references)
for the authoritative pages.

1. **Create a plugin.** Make a directory containing a `skills/` folder (and
   optionally `agents/`, `hooks/`, `.mcp.json`, `.lsp.json`), plus a
   `.claude-plugin/plugin.json` manifest with at least a `name`. Test it without
   installing via `claude --plugin-dir ./my-plugin`. See
   [Create plugins](https://code.claude.com/docs/en/plugins).
2. **Write the marketplace catalog.** Create `.claude-plugin/marketplace.json`
   at the repo root with `name`, `owner`, and a `plugins` array. Each entry
   needs a `name` and a `source` — a relative path, or a `github`, `url`,
   `git-subdir`, or `npm` source. See
   [Create and distribute a plugin marketplace](https://code.claude.com/docs/en/plugin-marketplaces).
3. **Validate.** Run `claude plugin validate .` against the marketplace, and
   `claude plugin validate ./plugins/<name>` against each plugin.
4. **Host it.** Push to GitHub (recommended), GitLab, or any git host — public
   or private. Private marketplaces work with your existing git credentials, and
   a `GITHUB_TOKEN` / `GITLAB_TOKEN` enables background auto-updates.
5. **Share and govern.** Users add it with `/plugin marketplace add owner/repo`,
   then install with `/plugin install name@marketplace`. For org-wide control,
   require it via `extraKnownMarketplaces` and restrict the allowed sources with
   `strictKnownMarketplaces` in managed settings. See
   [Plugin settings](https://code.claude.com/docs/en/settings).

---

## Plugin catalogue

| Plugin                       | Type             | Skills / Tools                                                                                                                                                                                         | Requires                                                                                        |
| ---------------------------- | ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------- |
| `omniagents-python`          | Skills           | `omniagents-python:typings`, `omniagents-python:docstrings`, `omniagents-python:performance`, `omniagents-python:pydantic`, `omniagents-python:library-patterns`, `omniagents-python:testing`          | —                                                                                               |
| `omniagents-typescript`      | Skills           | `omniagents-typescript:typings`, `omniagents-typescript:docstrings`, `omniagents-typescript:library-patterns`, `omniagents-typescript:testing`                                                         | —                                                                                               |
| `omniagents-design-patterns` | Skills           | `omniagents-design-patterns:software`, `omniagents-design-patterns:system`, `omniagents-design-patterns:codebase-design`                                                                               | —                                                                                               |
| `omniagents-writing`         | Skills           | `omniagents-writing:measured-persuasion`, `omniagents-writing:markdown-conventions`, `omniagents-writing:blueprint` (format-clean HTML/SVG diagrams via coordinate discipline)                         | Python 3 optional (for the `check_diagram.py` linter)                                           |
| `omniagents-reviewer`        | Skills + Command | `/omniagents-reviewer:review` — triaged parallel specialists (correctness, security, performance, design, testing, operability) + verifier + adjudicator                                               | `code-review-graph`, `omniagents-python`, `omniagents-typescript`, `omniagents-design-patterns` |
| `code-review-graph`          | MCP (stdio)      | Tree-sitter knowledge graph tools                                                                                                                                                                      | `uv` on PATH                                                                                    |
| `codegraph`                  | MCP (stdio)      | Code knowledge-graph tools (symbol search, callers/callees, impact analysis)                                                                                                                           | Node.js + npm on PATH (for `npx`)                                                               |
| `context7`                   | MCP (HTTP)       | Library documentation lookup                                                                                                                                                                           | `CONTEXT7_API_KEY`                                                                              |
| `google-workspace`           | MCP (stdio)      | Gmail, Drive, Calendar, Docs, Contacts, Tasks, Chat                                                                                                                                                    | `uv` on PATH + Google OAuth creds                                                               |
| `playwright`                 | MCP (stdio)      | Browser automation + accessibility-tree page snapshots                                                                                                                                                 | Node.js 18+ on PATH                                                                             |
| `notifications`              | Hooks            | macOS banner + sound when Claude needs attention                                                                                                                                                       | macOS                                                                                           |
| `doc-drift`                  | Hooks            | Prompts Claude to review docs for drift after code changes (broken refs, stale line numbers, snippets, diagrams)                                                                                       | `git` + `bash`                                                                                  |
| `omniagents-pedagogy`        | Skills           | `omniagents-pedagogy:coding-teacher` — `/coding-teacher [topic]` starts an incremental Socratic teaching session                                                                                       | —                                                                                               |
| `omniagents-unknowns`        | Skills           | `omniagents-unknowns:blindspot-pass` — `/blindspot-pass [task/area]` surveys unfamiliar territory and reports your unknown unknowns, ending in a sharper prompt                                        | —                                                                                               |
| `omniagents-iac`             | Skills           | `omniagents-iac:docker` — production Dockerfile/compose rulebook; `omniagents-iac:terraform` — module hygiene + T1/T2/T3 tiering, routes deep failure-mode and state-surgery work to `terraform-skill` | `terraform-skill`                                                                               |
| `terraform-skill` (external) | Skill            | `terraform-skill:terraform-skill` — deep Terraform/OpenTofu skill by Anton Babenko: failure-mode diagnosis, state surgery, migrations (Apache-2.0)                                                     | —                                                                                               |
| `drawio` (vendored)          | Skill            | `drawio:drawio` — native `.drawio` diagrams from Mermaid or draw.io XML, ELK auto-layout, PNG/SVG/PDF/`url` export                                                                                     | draw.io Desktop (optional — Mermaid conversion + PNG/SVG/PDF export only)                       |

---

## Under evaluation — not yet packaged

Candidates that have been researched but are deliberately **absent** from
`.claude-plugin/marketplace.json`, and therefore have no install command. They
are recorded here so the evaluation — and the reason for the verdict — is
versioned rather than lost in a chat log.

### `graphiti` — temporal knowledge-graph agent memory

[getzep/graphiti](https://github.com/getzep/graphiti) (Apache-2.0, by Zep) is a
temporal context-graph engine. You feed it _episodes_ — chat turns, documents,
JSON payloads — and an LLM extracts entities and relationships into a graph that
updates incrementally, without batch recomputation.

Its distinguishing property is **bi-temporal fact invalidation**: when new
information contradicts an existing fact, the old edge is not deleted but
stamped with `invalid_at`, so both _what is true now_ and _what did we believe
in March_ remain answerable. Every node and edge retains provenance back to the
episode that produced it. Retrieval is hybrid — semantic embeddings, BM25, and
graph traversal, with RRF, MMR, and graph-distance rerankers. Entity and edge
types can be prescribed as Pydantic models rather than left to the LLM.

#### Why it is not packaged

Every MCP plugin in the catalogue above is zero-infra: `npx -y`, `uvx`, or a
hosted HTTP endpoint. Graphiti would be the first to require a **running graph
database** (Neo4j or FalkorDB) alongside an LLM API key, and a `.mcp.json`
cannot start a container.

There is no shortcut around that. `graphiti-core` is published to PyPI (0.29.3,
Python 3.10–3.13), but the MCP server ships only inside the upstream repository
under `mcp_server/` — there is no `graphiti-mcp` package to `uvx`. Packaging it
would mean shipping a manual setup step whose failure mode is silent: the tools
appear in `claude mcp list`, and every call errors.

A second consideration is running cost. Each episode triggers several LLM calls
— entity extraction, deduplication against existing nodes, edge extraction,
temporal invalidation — so ingestion is measured in seconds and cents per
episode. It is a write-heavy system to be fed deliberately, not a drop-in vector
store.

#### Trialling it without touching this repo

```bash
git clone https://github.com/getzep/graphiti ~/src/graphiti
cd ~/src/graphiti/mcp_server
cp .env.example .env      # set OPENAI_API_KEY; FalkorDB is the compose default
docker compose up -d
claude mcp add --scope user graphiti --transport sse http://localhost:8000/sse
```

Confirm the transport and path against what the server logs on boot — some
builds serve `/mcp` rather than `/sse`.

#### Decision criterion

`codegraph` and `code-review-graph` already answer _what calls what_ from
deterministic tree-sitter parses. Graphiti's non-overlapping claim is memory of
**decisions and their history** — why a design was chosen, and when that
reasoning changed. Adopt it only if a period of real use produces queries that
neither structural graph nor a hand-curated notes file can answer.

#### Shape if adopted

Three files, following the `codegraph` pattern — `plugins/graphiti/.mcp.json`,
`plugins/graphiti/.claude-plugin/plugin.json`, and a `README.md` carrying the
database setup — plus a catalogue row and a `marketplace.json` entry stating the
dependency the way `google-workspace` does:

```json
{
    "mcpServers": {
        "graphiti": {
            "type": "sse",
            "url": "http://localhost:8000/sse"
        }
    }
}
```

---

## Prerequisites

- Claude Code CLI — `claude --version`
- For `code-review-graph` and `google-workspace`: `uv` installed —
  `uvx --version`
- For `codegraph`: Node.js and npm on PATH (to run `npx`) — `npx --version`
- For `context7`: a Context7 API key from <https://context7.com/dashboard>
- For `google-workspace`: Google OAuth credentials — see
  `plugins/google-workspace/README.md`
- For `playwright`: Node.js 18+ on PATH — `node --version` (first run downloads
  a browser)
- For `notifications`: macOS (uses built-in `osascript`)
- For `doc-drift`: `git` and `bash` (standard on macOS/Linux)

---

## Installation

### Add the marketplace

```bash
claude plugin marketplace add gao-hongnan/omniagents
```

Or from inside Claude Code:

```text
/plugin marketplace add gao-hongnan/omniagents
```

### Install plugins

Install individually:

```bash
claude plugin install omniagents-python@omniagents
claude plugin install omniagents-typescript@omniagents
claude plugin install omniagents-design-patterns@omniagents
claude plugin install omniagents-writing@omniagents
claude plugin install omniagents-reviewer@omniagents
claude plugin install code-review-graph@omniagents
claude plugin install codegraph@omniagents
claude plugin install context7@omniagents
claude plugin install google-workspace@omniagents
claude plugin install playwright@omniagents
claude plugin install notifications@omniagents
claude plugin install doc-drift@omniagents
claude plugin install omniagents-pedagogy@omniagents
claude plugin install omniagents-unknowns@omniagents
claude plugin install omniagents-iac@omniagents
claude plugin install terraform-skill@omniagents
```

### Scope options

| Flag              | Effect                                          |
| ----------------- | ----------------------------------------------- |
| _(none)_          | User scope — available across all projects      |
| `--scope project` | Project scope — committed to `.claude/`, shared |
| `--scope local`   | Local scope — gitignored, machine-local only    |

Example — install `omniagents-python` for the whole team:

```bash
claude plugin install omniagents-python@omniagents --scope project
```

---

## OpenAI Codex support

This repository doubles as an **OpenAI Codex plugin marketplace** (Codex CLI ≥
0.146). Codex's plugin system mirrors Claude Code's — a
`.codex-plugin/plugin.json` per plugin and a catalog at
`.agents/plugins/marketplace.json` — and both formats are compatible supersets
of the Claude ones (identical core fields; extra keys and Claude-style string
`source` entries are accepted). The Codex artifacts are therefore **generated,
never hand-edited**: `make sync-codex` byte-copies each
`.claude-plugin/plugin.json` to `.codex-plugin/plugin.json` and filters the
catalog, and `make release` re-runs the sync so both marketplaces publish in
lockstep (Codex, like Claude Code, keys its plugin cache on the version string).

Why `.agents/` and not `.codex-plugin/` for the catalog: the location is
Codex's, not ours. Codex resolves a marketplace root by probing, in order,
`.agents/plugins/marketplace.json`, `.agents/plugins/api_marketplace.json`,
`.claude-plugin/marketplace.json`, and `.cursor-plugin/marketplace.json` — the
`MARKETPLACE_MANIFEST_RELATIVE_PATHS` constant in
[`codex-rs/core-plugins/src/marketplace.rs`](https://github.com/openai/codex/blob/main/codex-rs/core-plugins/src/marketplace.rs);
`.codex-plugin/marketplace.json` is not probed at all. `.agents/` is OpenAI's
vendor-neutral namespace (the
[Agent Skills spec](https://agentskills.io/specification) standardizes only the
SKILL.md format, leaving discovery paths to each product). Note the third entry:
Codex would fall back to reading our Claude catalog directly via its compat
shim. We generate the `.agents/` catalog anyway because it is probed **first** —
so Codex users get the curated skill-bearing subset below rather than all Claude
entries (hook plugins, MCP wrappers, external sources) — and because it is the
documented primary path OpenAI's own
[openai/plugins](https://github.com/openai/plugins) catalog uses, rather than a
compatibility fallback.

A plugin is published to Codex **iff it ships a `skills/` directory** — SKILL.md
is the cross-agent standard, and Codex loads these skills unchanged: frontmatter
beyond `name`/`description` is tolerated, and skills are namespaced
`<plugin>:<skill>` exactly as in Claude Code (so `omniagents-python:typings` and
`omniagents-typescript:typings` coexist). Invoke one explicitly with `$<skill>`
in the Codex CLI, or let Codex select it implicitly from the `description`.
Claude `commands/` need no port — Codex auto-migrates them into invokable skills
at install time.

What stays Claude-only, and why:

| Excluded                                                                                 | Reason                                                    |
| ---------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| `notifications`, `doc-drift`                                                             | Claude Code hook events; Codex has a different hook model |
| `omniagents-tech-lead`                                                                   | Claude subagents/commands only — no skills to publish     |
| `context7`, `codegraph`, `code-review-graph`, `google-workspace`, `notion`, `playwright` | MCP wrappers — add these servers natively via `codex mcp` |
| `terraform-skill` (external)                                                             | GitHub-sourced Claude entry; install upstream directly    |

Note that `omniagents-reviewer` is published for its seven review skills, but
its multi-agent `/review` pipeline (subagents + verifier + adjudicator) runs
only in Claude Code.

### Install (Codex)

```bash
codex plugin marketplace add gao-hongnan/omniagents
codex plugin add omniagents-python@omniagents
codex plugin add omniagents-typescript@omniagents
codex plugin add omniagents-design-patterns@omniagents
codex plugin add omniagents-writing@omniagents
codex plugin add omniagents-reviewer@omniagents
codex plugin add omniagents-pedagogy@omniagents
codex plugin add omniagents-unknowns@omniagents
codex plugin add omniagents-iac@omniagents
codex plugin add drawio@omniagents
```

From a local clone, substitute the path:
`codex plugin marketplace add ./omniagents`.

Inside the Codex TUI, `/plugins` opens the marketplace browser instead — switch
sources with the tabs, install from there, and press Space on an installed
plugin to toggle it.

### Update (Codex)

```bash
codex plugin marketplace upgrade      # refresh the git marketplace snapshot
codex plugin add omniagents-python@omniagents   # re-add is idempotent; picks up the new version
```

### Verify (Codex)

```bash
codex plugin list        # installed plugins show STATUS installed
codex debug prompt-input | grep -oE 'omniagents-[a-z-]+:[a-z-]+' | sort -u
```

The second command renders the model-visible prompt without calling the model;
every installed skill should appear in it, namespaced `<plugin>:<skill>`.

---

## Updating installed plugins

If a plugin is already installed, running `claude plugin install ...` again is
expected to report that it is already installed. Install is not the update path.

Marketplace update only refreshes the catalogue; it does not install plugins
that are not already installed.

Refresh the marketplace, then update the installed plugin:

```bash
claude plugin marketplace update omniagents
claude plugin update omniagents-python@omniagents
claude plugin update omniagents-typescript@omniagents
claude plugin update omniagents-design-patterns@omniagents
claude plugin update omniagents-writing@omniagents
claude plugin update omniagents-reviewer@omniagents
claude plugin update code-review-graph@omniagents
claude plugin update codegraph@omniagents
claude plugin update context7@omniagents
claude plugin update google-workspace@omniagents
claude plugin update playwright@omniagents
claude plugin update notifications@omniagents
claude plugin update doc-drift@omniagents
claude plugin update omniagents-pedagogy@omniagents
claude plugin update omniagents-unknowns@omniagents
claude plugin update omniagents-iac@omniagents
claude plugin update terraform-skill@omniagents
```

Inside Claude Code, the equivalent commands are:

```text
/plugin marketplace update omniagents
/plugin update omniagents-python@omniagents
/plugin update omniagents-typescript@omniagents
/reload-plugins
```

Claude Code uses the plugin version as the cache key. Because these plugins set
`version` in each `.claude-plugin/plugin.json`, maintainers must bump that
version whenever published skill contents change. Pushing new commits without a
version bump will make updates look current to already-installed users. For
fast-moving internal plugins, omit `version` from both `plugin.json` and the
marketplace entry so Claude Code uses the git commit SHA as the version.

---

## Versioning and releases

This marketplace uses **lockstep [Semantic Versioning](https://semver.org/)**:
every plugin shares one version, bumped together on each release. One number to
cite and one tag to roll back to — at the cost that editing one plugin bumps
them all (unchanged plugins simply do a no-op refresh). Because Claude Code keys
its plugin cache on the version string and **delivers a release only when that
string changes**, the version must advance on every published change. The
`make release` target enforces this by bumping all manifests at once.

### Bump rule

| Bump  | When                                                               |
| ----- | ------------------------------------------------------------------ |
| patch | Wording, typos, formatting — Claude's behavior is unchanged        |
| minor | A new skill/agent, or new guidance that changes output             |
| major | A broken contract: renamed/removed a skill, command, or convention |

### Channels — how users choose a version

A "channel" is simply this repo added at a different git ref. Users select a
version at `marketplace add` time (`/plugin install` has no version flag), and
re-adding the marketplace at a different ref **replaces** the prior registration
(same `name`):

| Channel           | Add command                                             | Tracks                   |
| ----------------- | ------------------------------------------------------- | ------------------------ |
| Latest            | `/plugin marketplace add gao-hongnan/omniagents`        | `main`                   |
| Pinned / rollback | `/plugin marketplace add gao-hongnan/omniagents@v0.1.0` | an immutable version tag |

After switching or rolling back, run `/plugin marketplace update omniagents` and
`/reload-plugins`.

### Cutting a release (maintainers)

Accumulate notes under `## [Unreleased]` in `CHANGELOG.md` as you work, then:

```bash
make release VERSION=0.2.0   # bumps every manifest, stamps CHANGELOG, validates, commits, tags v0.2.0
git push origin main && git push origin v0.2.0
```

Pushing the tag triggers the `RELEASE` workflow, which validates the marketplace
and publishes a GitHub Release from the matching `CHANGELOG.md` section.

First-time bootstrap (one-off, before the first `make release`):

```bash
git tag -a v0.1.0 -m "omniagents v0.1.0 — baseline" && git push origin v0.1.0
```

### Rolling back

On a published marketplace, **revert — never `reset` + force-push** (a
force-push breaks commit-SHA pins and anyone who already pulled):

```bash
git revert --no-edit <bad-sha>
make release VERSION=0.2.1    # the revert reaches users only once the version changes
git push origin main && git push origin v0.2.1
```

Users on a pinned tag are unaffected until they re-add the marketplace at a
newer ref; users on `main` receive the revert on their next
`/plugin marketplace update omniagents`.

---

## Uninstall

The default scope is `user`. A bare uninstall command removes from user scope
without needing a flag. Add `--prune` to also drop any orphaned auto-installed
dependencies left behind:

```bash
claude plugin uninstall omniagents-python@omniagents --prune
claude plugin uninstall omniagents-typescript@omniagents --prune
claude plugin uninstall omniagents-design-patterns@omniagents --prune
claude plugin uninstall omniagents-writing@omniagents --prune
claude plugin uninstall omniagents-reviewer@omniagents --prune
claude plugin uninstall code-review-graph@omniagents --prune
claude plugin uninstall codegraph@omniagents --prune
claude plugin uninstall context7@omniagents --prune
claude plugin uninstall google-workspace@omniagents --prune
claude plugin uninstall playwright@omniagents --prune
claude plugin uninstall notifications@omniagents --prune
claude plugin uninstall doc-drift@omniagents --prune
claude plugin uninstall omniagents-pedagogy@omniagents --prune
claude plugin uninstall omniagents-unknowns@omniagents --prune
claude plugin uninstall omniagents-iac@omniagents --prune
claude plugin uninstall terraform-skill@omniagents --prune
```

If the plugin was installed with a non-default scope, pass the matching
`--scope` flag:

```bash
claude plugin uninstall omniagents-python@omniagents --scope project --prune
claude plugin uninstall omniagents-python@omniagents --scope local --prune
```

Use `--keep-data` to preserve the plugin's data directory if you plan to
reinstall:

```bash
claude plugin uninstall omniagents-python@omniagents --prune --keep-data
```

---

## MCP server setup

### code-review-graph

The plugin starts the server automatically via `uvx code-review-graph serve`. No
extra configuration is needed beyond having `uv` on your PATH.

Verify:

```bash
claude mcp get code-review-graph
```

Expected output:

```text
Scope: Project config (shared via .mcp.json)
Type: stdio
Command: uvx
Args: code-review-graph serve
```

If the server is found but fails to connect, run the launch command directly to
diagnose:

```bash
uvx code-review-graph serve
```

Common causes are `uvx` not on PATH or a first-run package download failure.

### codegraph

The plugin launches [`codegraph`](https://github.com/colbymchenry/codegraph) via
`npx -y @colbymchenry/codegraph serve --mcp`. No global install or configuration
is needed; `npx` resolves and runs the latest published version on each launch.
The server indexes the working project with tree-sitter into a local, persistent
graph and keeps it in sync via a background file watcher.

Verify:

```bash
claude mcp get codegraph
```

Expected output:

```text
Scope: Project config (shared via .mcp.json)
Type: stdio
Command: npx
Args: -y @colbymchenry/codegraph serve --mcp
```

If the server is found but fails to connect, run the launch command directly to
diagnose:

```bash
npx -y @colbymchenry/codegraph serve --mcp
```

Common causes are `npx`/Node.js not on PATH or a first-run package download
failure. See `plugins/codegraph/README.md` for CLI usage beyond MCP and
telemetry controls.

### context7

Set the API key in your shell before launching Claude Code:

```bash
export CONTEXT7_API_KEY="ctx7sk-your-key-here"
claude
```

To make it persistent on zsh/macOS:

```bash
echo 'export CONTEXT7_API_KEY="ctx7sk-your-key-here"' >> ~/.zshrc
source ~/.zshrc
```

Verify:

```bash
claude mcp get context7
```

Expected output:

```text
Scope: Project config (shared via .mcp.json)
Type: http
URL: https://mcp.context7.com/mcp
```

Context7 works without an API key at reduced rate limits, but the plugin is
configured to send one when present.

### google-workspace

The plugin starts the MCP server via `uvx workspace-mcp`. Three environment
variables must be exported before launching Claude Code:

```bash
export GOOGLE_OAUTH_CLIENT_ID="<your-client-id>.apps.googleusercontent.com"
export GOOGLE_OAUTH_CLIENT_SECRET="<your-client-secret>"
export USER_GOOGLE_EMAIL="your.email@gmail.com"
```

Full credential setup (Google Cloud project, OAuth consent screen, client ID) is
documented in `plugins/google-workspace/README.md`.

On first run the server opens a browser for the OAuth consent flow. The token is
cached locally; subsequent starts do not prompt again.

Verify:

```bash
claude mcp get google_workspace
```

Expected output:

```text
Scope: Project config (shared via .mcp.json)
Type: stdio
Command: uvx
Args: workspace-mcp
```

### playwright

No configuration or API key is required. The plugin launches Microsoft's
Playwright MCP via `npx @playwright/mcp@latest`, which gives agents browser
automation driven by the accessibility tree — navigate, click, type, and capture
structured page snapshots.

Requirements: Node.js 18+ on PATH. The first run downloads the browser
Playwright drives (Chromium by default), so allow network access and some disk.

Verify:

```bash
claude mcp get playwright
```

Expected output:

```text
Scope: Project config (shared via .mcp.json)
Type: stdio
Command: npx
Args: @playwright/mcp@latest
```

Common flags such as `--headless`, `--browser <name>`, and `--isolated` can be
appended to the `args` array; see `plugins/playwright/README.md`.

### notifications

No configuration is required beyond installing the plugin on macOS. The hook
fires automatically via `osascript` whenever Claude Code needs your attention.

Grant notification permission to your terminal app the first time it fires:
**System Settings → Notifications → [Terminal / iTerm2]**.

Validate the plugin structure:

```bash
claude plugin validate ./plugins/notifications
```

### doc-drift

No configuration is required. A single **Stop** hook checks `git diff` for
uncommitted source-file changes; if found, it prompts Claude to review
documentation for stale references and fix any drift.

Requirements: `git` and `bash` (standard on macOS/Linux).

Validate the plugin structure:

```bash
claude plugin validate ./plugins/doc-drift
```

---

## Verification

List all active MCP servers:

```bash
claude mcp list
```

All MCP plugins should appear. Inside Claude Code, smoke-test context7 with:

```text
use context7 mcp to search pydantic
```

---

## Development install

To install from a local clone instead of GitHub:

```bash
git clone https://github.com/gao-hongnan/omniagents
claude plugin marketplace add ./omniagents
claude plugin install omniagents-python@omniagents --scope local
```

---

## References

Claude Code official documentation cited above:

1. [Create plugins](https://code.claude.com/docs/en/plugins)
2. [Create and distribute a plugin marketplace](https://code.claude.com/docs/en/plugin-marketplaces)
3. [Plugins reference](https://code.claude.com/docs/en/plugins-reference)
4. [Discover and install plugins](https://code.claude.com/docs/en/discover-plugins)
5. [Plugin settings — managed settings & `strictKnownMarketplaces`](https://code.claude.com/docs/en/settings)

OpenAI Codex documentation and sources for the
[Codex support](#openai-codex-support) section:

1. [Build skills](https://developers.openai.com/codex/skills) — SKILL.md format
   and the `.agents/skills` discovery locations
2. [Use plugins](https://developers.openai.com/codex/plugins) — `/plugins`
   browser, install and management flows
3. [openai/plugins](https://github.com/openai/plugins) — OpenAI's official
   plugin marketplace; reference layout for `.codex-plugin/plugin.json` and
   `.agents/plugins/marketplace.json`
4. [openai/codex — `marketplace.rs`](https://github.com/openai/codex/blob/main/codex-rs/core-plugins/src/marketplace.rs)
   — `MARKETPLACE_MANIFEST_RELATIVE_PATHS`, the catalog locations Codex probes
5. [Agent Skills specification](https://agentskills.io/specification) — the
   cross-agent SKILL.md format (directory discovery is per-product)

---

## Credits

- **`drawio`** is vendored from
  [jgraph/drawio-mcp](https://github.com/jgraph/drawio-mcp/tree/main/plugins/claude-code)
  (Apache-2.0, by draw.io) — only the `plugins/claude-code` subdirectory. It is
  pinned to an upstream commit and re-synced with `scripts/sync-drawio.sh`; the
  pinned ref and full provenance live in `plugins/drawio/UPSTREAM.md`. We vendor
  the files (rather than a git submodule) so the marketplace sees normal paths
  and we can review upstream diffs before adopting them.
- **`terraform-skill`** is not vendored — it is registered as an external
  `github` source pointing at
  [antonbabenko/terraform-skill](https://github.com/antonbabenko/terraform-skill)
  (Apache-2.0, by Anton Babenko), pinned to `ref: v1.17.1` in
  `.claude-plugin/marketplace.json` and declared as a plugin dependency of
  `omniagents-iac`. `omniagents-iac:terraform` is a house-layer rulebook that
  routes deep failure-mode and state-surgery work to it instead of restating it.

## License

MIT. See individual `plugin.json` files for per-plugin authorship.
