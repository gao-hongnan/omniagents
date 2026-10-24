#!/usr/bin/env bash
# check-frontmatter.sh — enforce SKILL.md frontmatter rules (name equals the
# directory, description 1-1024, description+when_to_use <= 1536 per skill and
# <= MAX_TOTAL_CHARS across the suite). Exit 1 with violations listed.
#
set -euo pipefail

command -v python3 >/dev/null 2>&1 || { echo "error: python3 is required but not on PATH"; exit 1; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 - <<'PYEOF'
import glob
import re
import sys

MAX_TOTAL_CHARS = 15000  # full-suite listing budget (~1% of context)

DELIM = re.compile(r"^---\s*$")
KEY = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):(.*)$")


def frontmatter(text):
    lines = text.split("\n")
    if not lines or not DELIM.match(lines[0]):
        return None
    for i in range(1, len(lines)):
        if DELIM.match(lines[i]):
            return lines[1:i]
    return None


def field(fm_lines, key):
    """Return the scalar value for `key`, unfolded like YAML folding would."""
    value_lines = []
    collecting = False
    for line in fm_lines:
        m = KEY.match(line)
        if m:
            if collecting:
                break
            collecting = m.group(1) == key
            if collecting:
                rest = m.group(2).strip()
                rest = re.sub(r"^[>|][+-]?\s*$", "", rest)
                if rest:
                    value_lines.append(rest)
            continue
        if collecting:
            if not line.strip():
                value_lines.append("")
            elif line.startswith((" ", "\t")):
                value_lines.append(line.strip())
            else:
                break
    while value_lines and not value_lines[-1]:
        value_lines.pop()
    return " ".join(part for part in value_lines if part)


skills = sorted(glob.glob("plugins/*/skills/*/SKILL.md"))
violations = []
total = 0
for path in skills:
    with open(path, encoding="utf-8") as fh:
        fm = frontmatter(fh.read())
    if fm is None:
        violations.append(f"{path}: no --- frontmatter block")
        continue
    name = field(fm, "name")
    description = field(fm, "description")
    when_to_use = field(fm, "when_to_use")
    dirname = path.split("/")[-2]

    if name != dirname:
        violations.append(f"{path}: name {name!r} != directory {dirname!r}")
    if not 1 <= len(description) <= 1024:
        violations.append(
            f"{path}: description is {len(description)} chars (limit 1–1024)"
        )
    eff = len(description) + len(when_to_use) + (1 if description and when_to_use else 0)
    if eff > 1536:
        violations.append(f"{path}: description+when_to_use is {eff} chars (limit 1536)")
    total += eff

print(f"skills checked: {len(skills)}")
print(f"total description+when_to_use: {total} chars (budget {MAX_TOTAL_CHARS})")
if total > MAX_TOTAL_CHARS:
    violations.append(
        f"full-suite listing total {total} exceeds budget {MAX_TOTAL_CHARS}"
    )

for v in violations:
    print(f"violation: {v}")
sys.exit(1 if violations else 0)
PYEOF
