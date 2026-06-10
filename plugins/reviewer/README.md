# omniagents-reviewer

Multi-specialist code-review plugin built for **precision first**: every
serious finding survives three independent gates before a human reads it.

`/omniagents-reviewer:review` **triages** the diff and dispatches only the
specialists it needs — `correctness`, `security`, `performance`, `design`,
`testing`, `operability` — in parallel. Each specialist works intent-first
(commit messages + full-file reads), hunts for what the diff *should have
changed but did not*, and must attempt to falsify each candidate finding
before emitting it. A `verifier` merges and filters mechanically; an
`adjudicator` then **re-opens every BLOCKER/IMPORTANT citation in the actual
code** and confirms, downgrades, or drops it. Only what survives is rendered.

Findings are produced as **JSON** (every finding carries a required `file` +
`line`) and persisted under a git-ignored `.reviews/<timestamp>/` folder —
per-specialist, merged, and final — plus rendered Markdown. The headline
`review.md` is relayed to the terminal. With `--comment` on a PR target, the
adjudicated findings post as inline PR comments (dry-run + confirmation
first; never by default).

## Pipeline

```
/review <target> [--comment]
  └─ triage (docs-only? test-only? deps? config? small diff?)
       └─ specialists (parallel, self-persist NN_<dim>.json)
            └─ verifier   (mechanical merge/dedupe/filter → merged.json)
                 └─ adjudicator (re-reads code, confirm/downgrade/drop → review.json)
                      └─ schema.py (validate + scope-check + render → review.md)
                           └─ post_pr_comments.py (only with --comment, after confirmation)
```

Cost scales with the diff: a docs-only change dispatches nothing; a tiny
single-file diff dispatches two specialists, not six.

## Verification: `/omniagents-reviewer:doctor`

Claude Code **silently skips** a `skills:` frontmatter ref that does not
resolve — the specialist just runs without that checklist. `doctor` makes
that loud:

- `scripts/doctor.py` lints every agent's skill refs against the repo
  marketplace **and** the installed cache, flags untracked skill files
  (they will not publish), `disable-model-invocation: true` (blocks
  preloading), dimension-wiring drift, and a broken `schema.py`.
- `--deep` additionally dispatches the design specialist (longest skill
  list) and asks it to quote the first heading of every skill document in
  its context — a heading it cannot quote was not preloaded, whatever the
  static checks say.

Run it after every release or plugin update.

## Requirements

Sibling plugins (declared in `plugin.json` `dependencies`); install from the
same marketplace:

- **`code-review-graph`** — knowledge-graph MCP tools for blast-radius
  analysis. The specialist `tools:` grants are fully qualified
  (`mcp__plugin_code-review-graph_code-review-graph__*`), which assumes the
  graph is installed **as a plugin named `code-review-graph`**.
- **`omniagents-python`**, **`omniagents-typescript`**,
  **`omniagents-design-patterns`** — force-preloaded into the specialists
  via each agent's `skills:` frontmatter.

**Graceful degradation.** If `code-review-graph` is absent — or wired
through a project `.mcp.json` as `mcp__code-review-graph__*` (no `plugin_`
prefix) — reviews still run but blast-radius falls back to
`graph unavailable — severity based on code analysis only`. A missing
skill-plugin dependency means that checklist is not preloaded (and `doctor`
will say so).

## Layout

```
agents/     correctness, security, performance, design, testing, operability,
            verifier (mechanical merge), adjudicator (evidentiary re-check)
skills/     one checklist per dimension + review-contract (the shared contract);
            review-contract/schema.py validates, scope-checks, and renders
commands/   review.md (orchestrator), doctor.md (self-diagnostic)
scripts/    doctor.py (preload/wiring lint), post_pr_comments.py (PR delivery)
evals/      seeded-bug fixtures measuring recall AND precision per release
```

## Output

Every run writes a timestamped, git-ignored folder at the repo root. JSON is
canonical; Markdown is rendered by `review-contract/schema.py` (stdlib only):

```
.reviews/<timestamp>/
  changed_files.txt           # diff scope, enforced by schema.py --changed-files
  01_correctness.json / .md   02_security.json / .md   03_performance.json / .md
  04_design.json / .md        05_testing.json / .md    06_operability.json / .md
  merged.json                 # verifier output (pre-adjudication)
  review.json                 # final adjudicated report
  review.md                   # headline report, also relayed to the terminal
.reviews/latest -> <timestamp>
```

`schema.py` enforcement (beyond field validation): with
`--changed-files`, any finding outside the diff must carry a
`[pre-existing]` prefix or validation fails; `review` rendering strips
non-BLOCKER findings below the contract confidence floors; `--ci` exits 3
on REQUEST CHANGES for pipeline gating.

```
python3 skills/review-contract/schema.py specialist <r.json> [--changed-files f]
python3 skills/review-contract/schema.py review     <r.json> [--changed-files f] [--ci]
python3 skills/review-contract/schema.py --schema
```

## How the skills are consumed (read before editing)

Each specialist agent lists its checklist skill plus `review-contract` in its
`skills:` frontmatter. Skills referenced that way are **force-preloaded**: the
full `SKILL.md` body is injected into the subagent at startup, not lazily
discovered by description match.

Consequences for anyone editing these skills:

- **`disable-model-invocation: false` is load-bearing — do not set it `true`.**
  Per the Claude Code skills docs, `true` "also prevents the skill from being
  preloaded into subagents," which would silently break every specialist
  (`doctor.py` checks this). The `user-invocable: false` pairing is correct:
  these are reference checklists, not `/`-menu commands.
- **Splitting a checklist into linked reference files saves no tokens here** —
  preload injects the whole body regardless. Only split for navigability.
- **Description / `when_to_use` discoverability barely matters** in this
  architecture. Optimize those fields for leanness, not discovery.

## Single source of truth

`skills/review-contract/SKILL.md` owns the shared contract: the finding
**schema** (`file` and `line` are separate required fields), the **review
method** (intent-first analysis → omission hunting → falsification before
reporting), the **What Not to Report** noise rules, the **adjudication**
rules, confidence and severity rubrics, the severity-elevation rule, report
shapes, verdict rules, dedup/filter rules, and the canonical **dimension
set** (`## Dimensions`). Its sibling `schema.py` is the machine-enforceable
half. When adding or removing a review dimension, update `review-contract`'s
`## Dimensions` section, the `Dimension` enum in `schema.py`, the command's
dispatch + triage lists, and the matching agent — then run
`python3 scripts/doctor.py`, which checks exactly this wiring.

## Evals

`evals/` holds seeded-bug fixtures (each plants subtle bugs **and** noise
baits) plus a `setup_fixture.sh` that materializes them into throwaway git
repos. Recall = seeded bugs found; precision = baits left alone. See
`evals/README.md`. Run them before cutting a release that touches agents,
skills, or the contract.
