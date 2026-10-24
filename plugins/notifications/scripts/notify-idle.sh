#!/usr/bin/env bash
set -euo pipefail

command -v osascript >/dev/null 2>&1 || exit 0

osascript -e 'display notification "Claude is waiting for your reply" with title "Claude Code" sound name "Ping"'
