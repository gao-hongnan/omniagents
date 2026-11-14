#!/usr/bin/env bash
# check-links.sh — exit 1 on broken relative markdown links in README.md and
# plugins/**/*.md (code fences and inline code spans skipped).
#
set -euo pipefail

command -v python3 >/dev/null 2>&1 || { echo "error: python3 is required but not on PATH"; exit 1; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 - <<'PYEOF'
import os
import re
import sys
import urllib.parse

FILES = ["README.md"] + [
    os.path.join(root, f)
    for root, _, names in os.walk("plugins")
    for f in sorted(names)
    if f.endswith(".md")
]

INLINE_LINK = re.compile(r"\[[^\]\n]*\]\(([^)\s]+)\)")
REF_DEF = re.compile(r"^\s{0,3}\[[^\]\n]+\]:\s+(\S+)\s*$")
INLINE_CODE = re.compile(r"`[^`\n]*`")
FENCE = re.compile(r"^\s*(```|~~~)")

broken = []
for path in FILES:
    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()
    targets = []
    in_fence = False
    for line in lines:
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        bare = INLINE_CODE.sub("", line)
        targets += INLINE_LINK.findall(bare)
        m = REF_DEF.match(bare)
        if m:
            targets.append(m.group(1))

    for t in targets:
        if t.startswith(("http://", "https://", "mailto:", "#", "data:", "irc://")):
            continue
        rel = t.split("#")[0]
        if not rel:
            continue
        resolved = os.path.normpath(
            os.path.join(os.path.dirname(path), urllib.parse.unquote(rel))
        )
        if not os.path.exists(resolved):
            broken.append((path, t))

for path, t in broken:
    print(f"broken link: {path}: {t}")
print(f"checked {len(FILES)} markdown files, {len(broken)} broken relative links")
sys.exit(1 if broken else 0)
PYEOF
