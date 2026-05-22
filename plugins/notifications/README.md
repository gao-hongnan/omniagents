# Notifications Plugin

Fires a native macOS notification banner with a Glass sound chime whenever Claude Code needs your attention — permission prompts, tool approvals, or session completions.

## How it works

Two Claude Code hook events cover the "needs attention" surface:

| Hook | Subtype | When it fires |
|---|---|---|
| `Notification` | `permission_prompt` | Claude is blocked waiting for your approval |
| `Notification` | `idle_prompt` | Claude is idle, waiting for your next message |
| `Stop` | — | Claude finished the task and returned to the prompt |

Each fires a distinct `osascript` notification with a different message and sound so you know at a glance whether to approve something or just come read the result.

## Plugin structure

```
plugins/notifications/
├── .claude-plugin/
│   └── plugin.json             ← plugin manifest
├── hooks/
│   └── hooks.json              ← Notification + Stop hook declarations
├── scripts/
│   ├── notify-permission.sh    ← "needs your permission" (Glass)
│   ├── notify-idle.sh          ← "waiting for reply" (Ping)
│   └── notify-stop.sh          ← "finished" (Hero)
└── README.md
```

## Requirements

- macOS (uses `osascript` — built into macOS, no install needed)
- Notification permissions granted to Terminal / iTerm / your shell app in **System Settings → Notifications**

## Installation

**Validate the plugin:**

```bash
claude plugin validate ./plugins/notifications
```

**Install from this repo (local):**

```text
/plugin marketplace add ./
/plugin install notifications
```

**Or declare as a known marketplace in `.claude/settings.json` for team distribution:**

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

Then teammates run `/plugin install notifications@omniagents`.

## Customisation

| What to change | Where |
|---|---|
| Permission message / sound | `scripts/notify-permission.sh` — default sound: `Glass` |
| Idle message / sound | `scripts/notify-idle.sh` — default sound: `Ping` |
| Stop (finished) message / sound | `scripts/notify-stop.sh` — default sound: `Hero` |
| Available sounds | `/System/Library/Sounds/` (e.g. `Funk`, `Blow`, `Bottle`) |
| Linux | Replace each `osascript` line with `notify-send 'Claude Code' '<message>'` |
