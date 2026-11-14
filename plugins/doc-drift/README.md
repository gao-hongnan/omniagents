# Doc-Drift Plugin

Detects documentation drift after code changes and prompts Claude to review and
fix stale references. Runs automatically on session stop — no manual invocation
needed.

## How it works

A single **Stop** hook fires when Claude finishes responding:

1. Checks `git status` for uncommitted source-file changes
2. If source files changed → blocks the stop **at most once per distinct
   change set** and asks Claude to review docs
3. Claude reads documentation, finds drift, fixes it, then stops again
4. The hook fires again but `stop_hook_active` is `true` → exits silently
5. On later turns, a hash of `git diff` plus the untracked list (stored in
   `${CLAUDE_PLUGIN_DATA}`) skips re-blocking while the tree is unchanged —
   a new change or a fresh changeset blocks again

**Why not scripts with regex?** Claude is far better at detecting drift than
pattern matching. It understands semantic changes, diagrams, function
signatures, and context — not just line-number counts.

## Drift types Claude checks for

| Type                         | Example                                                   |
| ---------------------------- | --------------------------------------------------------- |
| Broken file-path references  | Doc links to a renamed / moved / deleted file             |
| Stale line-number references | "see line 120" but the file shrank to 85 lines            |
| Outdated code snippets       | Inline ` ``` ` blocks that no longer match the source     |
| Diagram drift                | Mermaid / PlantUML diagrams out of sync with architecture |
| Semantic content drift       | Descriptions that no longer match behaviour               |

## Plugin structure

```
plugins/doc-drift/
├── .claude-plugin/
│   └── plugin.json          ← plugin manifest
├── hooks/
│   └── hooks.json           ← Stop hook declaration
├── scripts/
│   └── check-doc-drift.sh   ← git diff check + changeset hash + prompt
├── tests/
│   └── test-check-doc-drift.sh ← clean/dirty/repeated-stop cases (run in CI)
└── README.md
```

## Requirements

- `git` (for `git diff`)
- `bash`

## Installation

**Validate the plugin:**

```bash
claude plugin validate ./plugins/doc-drift
```

**Install from marketplace:**

```bash
claude plugin install doc-drift@omniagents
```

**Install scopes:**

| Flag              | Effect                                                    |
| ----------------- | --------------------------------------------------------- |
| _(none)_          | User scope — available across all your projects           |
| `--scope project` | Project scope — committed to `.claude/`, shared with team |
| `--scope local`   | Local scope — gitignored, this machine only               |

**Team distribution** — add to `.claude/settings.json`:

```json
{
    "extraKnownMarketplaces": {
        "omniagents": {
            "source": {
                "source": "github",
                "repo": "gao-hongnan/omniagents"
            }
        }
    }
}
```

Then teammates run `claude plugin install doc-drift@omniagents`.
