#!/usr/bin/env bash
set -euo pipefail

command -v osascript >/dev/null 2>&1 || exit 0

osascript -e 'display notification "Claude needs your permission" with title "Claude Code" sound name "Glass"'
