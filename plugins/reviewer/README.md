# omniagents-reviewer

Multi-specialist code-review plugin. The `/omniagents-reviewer:review` command
dispatches five specialist subagents in parallel — `correctness`, `security`,
`performance`, `design`, `testing` — then a `verifier` subagent deduplicates and
aggregates their findings into one report.

## Requirements

This plugin depends on four sibling plugins (declared in `plugin.json`
`dependencies`); install them from the same marketplace before running
`/omniagents-reviewer:review`:

- **`code-review-graph`** — supplies the knowledge-graph MCP tools the
  specialists use for blast-radius analysis. The specialist `tools:` grants are
  fully qualified (`mcp__plugin_code-review-graph_code-review-graph__*`), which
  assumes the graph is installed **as a plugin named `code-review-graph`**.
- **`omniagents-python`**, **`omniagents-typescript`**,
  **`omniagents-design-patterns`** — force-preloaded into the specialists via
  each agent's `skills:` frontmatter (language type-safety, library patterns,
  and design-pattern checklists).

**Graceful degradation.** If `code-review-graph` is absent — or it is wired
through a project `.mcp.json` as `mcp__code-review-graph__*` (no `plugin_`
prefix), so the grants no longer match — reviews still run but lose blast-radius
calibration: findings fall back to
`Blast radius: graph unavailable — severity based on code analysis only` (per
`review-contract`). It degrades, it does not hard-fail. A missing skill-plugin
dependency just means that checklist is not preloaded into the relevant
specialist.

## Layout

```
agents/     correctness, security, performance, design, testing, verifier
skills/     one checklist per dimension + review-contract (the shared contract)
commands/   review.md (the orchestrator entrypoint)
```

## How the skills are consumed (read before editing)

Each specialist agent lists its checklist skill plus `review-contract` in its
`skills:` frontmatter. Skills referenced that way are **force-preloaded**: the
full `SKILL.md` body is injected into the subagent at startup, not lazily
discovered by description match. The agent bodies say so ("already loaded into
your context at startup").

Consequences for anyone editing these skills:

- **`disable-model-invocation: false` is load-bearing — do not set it `true`.**
  Per the Claude Code skills docs, `true` "also prevents the skill from being
  preloaded into subagents," which would silently break every specialist. The
  `user-invocable: false` pairing is correct: these are reference checklists,
  not `/`-menu commands.
- **Splitting a checklist into linked reference files saves no tokens here** —
  preload injects the whole body regardless. Only split for navigability, and
  keep references one level deep.
- **Description / `when_to_use` discoverability barely matters** in this
  architecture (the subagent path force-loads the skill; the main session never
  triggers these). Optimize those fields for leanness, not discovery. The
  combined `description` + `when_to_use` text is capped at 1,536 characters.

## Single source of truth

`skills/review-contract/SKILL.md` owns the shared contract: the finding format,
confidence and severity rubrics, the severity-elevation rule, the report
templates, the verdict rules, the dedup/filter rules, and the canonical
**dimension set** (`## Dimensions`). Specialist skills and agents should _defer_
to it rather than restating these — restated copies drift. When adding or
removing a review dimension, update `review-contract`'s `## Dimensions` section,
its `Dimension` field, the command's dispatch list, and the matching agent.

## Roadmap

- **Observability dimension** (planned fast-follow): a 6th `operability`
  specialist for logging, metrics, tracing, error-reporting, and trace-ID
  adequacy — wired in via the four coordination points above. Error handling
  itself is already covered by the `correctness` specialist.
