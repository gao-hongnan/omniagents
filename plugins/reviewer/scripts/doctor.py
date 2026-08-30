#!/usr/bin/env python3
"""Preload + wiring lint for the reviewer plugin.

Claude Code silently skips a subagent ``skills:`` frontmatter reference that
does not resolve to an installed skill -- the agent simply runs without that
checklist and nothing surfaces the gap. This script makes that failure mode
loud. It is the mechanical answer to "how do I know my skills frontmatter
actually loads?".

Checks
------
1. **Skill refs resolve in the repo.** Every ``plugin:skill`` ref in
   ``agents/*.md`` must map to ``<plugin-source>/skills/<skill>/SKILL.md``
   via the repo marketplace manifest. Dangling -> ERROR.
2. **Resolved skills are git-tracked.** A skill that exists locally but is
   untracked will not publish, so installs silently lose it. -> ERROR.
3. **Preload is not disabled.** ``disable-model-invocation: true`` in a skill
   prevents preloading into subagents. -> ERROR.
4. **Installed cache is current.** Tracked skill missing from the newest
   installed cache version of its plugin -> WARN (stale install: release +
   ``claude plugin update``).
5. **Dimension wiring.** Every ``Dimension`` enum member in ``schema.py``
   has a matching ``agents/<dim>.md`` and ``skills/<dim>-review/SKILL.md``,
   and appears in the command dispatch list. Drift -> ERROR.
6. **schema.py runs** under this interpreter. -> ERROR if not.
7. **code-review-graph availability.** Absent -> WARN (reviews degrade to
   "graph unavailable" blast radius; they do not fail).

Exit codes: 0 clean (warnings allowed), 1 any ERROR, 2 environment problem.

Usage:
    python3 scripts/doctor.py            # from anywhere; paths are derived
    python3 scripts/doctor.py --json     # machine-readable findings
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

PLUGIN_ROOT: Final = Path(__file__).resolve().parent.parent
CACHE_ROOT: Final = Path.home() / ".claude" / "plugins" / "cache"

_SKILL_REF: Final = re.compile(r"^\s+-\s+(\S+?:\S+)\s*$")
_ENUM_MEMBER: Final = re.compile(r'^\s+[A-Z_]+\s*=\s*"([a-z]+)"\s*$')


class Level(StrEnum):
    ERROR = "ERROR"
    WARN = "WARN"
    INFO = "INFO"


@dataclass(frozen=True, slots=True)
class Issue:
    level: Level
    check: str
    message: str


def _frontmatter(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return lines[1:idx]
    return []


def _skill_refs(agent_md: Path) -> tuple[str, ...]:
    """Extract `plugin:skill` entries from the agent's `skills:` block."""
    refs: list[str] = []
    in_skills = False
    for line in _frontmatter(agent_md):
        if re.match(r"^skills\s*:\s*$", line):
            in_skills = True
            continue
        if in_skills:
            m = _SKILL_REF.match(line)
            if m:
                refs.append(m.group(1))
                continue
            if line.strip() and not line.startswith((" ", "\t")):
                in_skills = False
    return tuple(refs)


def _repo_root() -> Path | None:
    for candidate in (PLUGIN_ROOT, *PLUGIN_ROOT.parents):
        if (candidate / ".claude-plugin" / "marketplace.json").is_file():
            return candidate
    return None


def _marketplace_sources(repo: Path) -> dict[str, Path]:
    """plugin name -> absolute source dir, from the marketplace manifest."""
    manifest = repo / ".claude-plugin" / "marketplace.json"
    raw: object = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    plugins = raw.get("plugins")
    if not isinstance(plugins, list):
        return {}
    out: dict[str, Path] = {}
    entries: list[object] = plugins
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        source = entry.get("source")
        if isinstance(name, str) and isinstance(source, str):
            out[name] = (repo / source).resolve()
    return out


def _git_tracked(repo: Path, path: Path) -> bool | None:
    """True/False if git answers; None when git is unavailable."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), "ls-files", "--error-unmatch", str(path)],
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.returncode == 0


def _newest_cache_version(plugin: str) -> Path | None:
    """Newest installed cache dir for `plugin` across all marketplaces."""

    def version_key(p: Path) -> tuple[int, ...]:
        parts = re.findall(r"\d+", p.name)
        return tuple(int(x) for x in parts) if parts else (0,)

    candidates: list[Path] = []
    if CACHE_ROOT.is_dir():
        for marketplace in CACHE_ROOT.iterdir():
            plugin_dir = marketplace / plugin
            if plugin_dir.is_dir():
                candidates.extend(v for v in plugin_dir.iterdir() if v.is_dir())
    if not candidates:
        return None
    return max(candidates, key=version_key)


def _preload_disabled(skill_md: Path) -> bool:
    for line in _frontmatter(skill_md):
        if re.match(r"^disable-model-invocation\s*:\s*true\s*$", line.strip()):
            return True
    return False


def _check_skill_refs(repo: Path, issues: list[Issue]) -> None:
    sources = _marketplace_sources(repo)
    for agent_md in sorted((PLUGIN_ROOT / "agents").glob("*.md")):
        for ref in _skill_refs(agent_md):
            plugin, _, skill = ref.partition(":")
            agent = agent_md.stem

            source = sources.get(plugin)
            if source is None:
                cached = _newest_cache_version(plugin)
                if cached is None:
                    issues.append(
                        Issue(
                            Level.ERROR,
                            "skill-refs",
                            f"{agent}: '{ref}' -- plugin '{plugin}' is in "
                            "neither the repo marketplace nor any installed "
                            "cache; this preload silently does nothing",
                        )
                    )
                continue

            skill_md = source / "skills" / skill / "SKILL.md"
            if not skill_md.is_file():
                issues.append(
                    Issue(
                        Level.ERROR,
                        "skill-refs",
                        f"{agent}: '{ref}' -- no {skill_md.relative_to(repo)} "
                        "in the repo; this preload silently does nothing",
                    )
                )
                continue

            tracked = _git_tracked(repo, skill_md)
            if tracked is False:
                issues.append(
                    Issue(
                        Level.ERROR,
                        "skill-refs",
                        f"{agent}: '{ref}' exists locally but is NOT "
                        "git-tracked -- it will not publish, so installed "
                        "copies of this agent run without it",
                    )
                )
                continue

            if _preload_disabled(skill_md):
                issues.append(
                    Issue(
                        Level.ERROR,
                        "skill-refs",
                        f"{agent}: '{ref}' has disable-model-invocation: true, which blocks preloading into subagents",
                    )
                )
                continue

            cached = _newest_cache_version(plugin)
            if cached is not None:
                cached_skill = cached / "skills" / skill / "SKILL.md"
                if not cached_skill.is_file():
                    issues.append(
                        Issue(
                            Level.WARN,
                            "skill-refs",
                            f"{agent}: '{ref}' is tracked in the repo but "
                            f"missing from the installed cache ({cached.name})"
                            " -- cut a release and run claude plugin update",
                        )
                    )


def _dimensions_from_schema(schema_py: Path) -> tuple[str, ...]:
    dims: list[str] = []
    in_enum = False
    for line in schema_py.read_text(encoding="utf-8").splitlines():
        if line.startswith("class Dimension"):
            in_enum = True
            continue
        if in_enum:
            if line.startswith("class "):
                break
            m = _ENUM_MEMBER.match(line)
            if m:
                dims.append(m.group(1))
    return tuple(dims)


def _check_dimension_wiring(issues: list[Issue]) -> None:
    schema_py = PLUGIN_ROOT / "skills" / "review-contract" / "schema.py"
    command_md = PLUGIN_ROOT / "commands" / "review.md"
    command_text = command_md.read_text(encoding="utf-8")
    for dim in _dimensions_from_schema(schema_py):
        if not (PLUGIN_ROOT / "agents" / f"{dim}.md").is_file():
            issues.append(
                Issue(
                    Level.ERROR,
                    "dimension-wiring",
                    f"Dimension '{dim}' in schema.py has no agents/{dim}.md",
                )
            )
        if not (PLUGIN_ROOT / "skills" / f"{dim}-review" / "SKILL.md").is_file():
            issues.append(
                Issue(
                    Level.ERROR,
                    "dimension-wiring",
                    f"Dimension '{dim}' in schema.py has no skills/{dim}-review/SKILL.md",
                )
            )
        if f"`{dim}`" not in command_text:
            issues.append(
                Issue(
                    Level.ERROR,
                    "dimension-wiring",
                    f"Dimension '{dim}' in schema.py is not in the commands/review.md dispatch list",
                )
            )


def _check_schema_runs(issues: list[Issue]) -> None:
    schema_py = PLUGIN_ROOT / "skills" / "review-contract" / "schema.py"
    try:
        proc = subprocess.run(
            [sys.executable, str(schema_py), "--schema"],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        issues.append(Issue(Level.ERROR, "schema-runs", f"schema.py failed to run: {exc}"))
        return
    if proc.returncode != 0:
        issues.append(
            Issue(
                Level.ERROR,
                "schema-runs",
                f"schema.py --schema exited {proc.returncode}: {proc.stderr.decode(errors='replace')[:200]}",
            )
        )


def _check_graph_available(issues: list[Issue]) -> None:
    if _newest_cache_version("code-review-graph") is None:
        issues.append(
            Issue(
                Level.WARN,
                "graph",
                "code-review-graph plugin not found in the installed cache; "
                "reviews will run with 'graph unavailable' blast radius",
            )
        )


def main(argv: list[str]) -> int:
    as_json = "--json" in argv[1:]

    repo = _repo_root()
    if repo is None:
        print("doctor: cannot locate repo marketplace manifest", file=sys.stderr)
        return 2

    issues: list[Issue] = []
    _check_skill_refs(repo, issues)
    _check_dimension_wiring(issues)
    _check_schema_runs(issues)
    _check_graph_available(issues)

    errors = sum(1 for i in issues if i.level is Level.ERROR)
    warns = sum(1 for i in issues if i.level is Level.WARN)

    if as_json:
        payload = {
            "errors": errors,
            "warnings": warns,
            "issues": [{"level": i.level.value, "check": i.check, "message": i.message} for i in issues],
        }
        print(json.dumps(payload, indent=2))
    else:
        for issue in issues:
            print(f"[{issue.level.value}] {issue.check}: {issue.message}")
        verdict = "FAIL" if errors else "OK"
        print(f"doctor: {verdict} -- {errors} error(s), {warns} warning(s)")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
