#!/usr/bin/env python3
"""Preload + wiring lint for the research plugin.

Claude Code silently skips a subagent ``skills:`` frontmatter reference that
does not resolve to an installed skill -- the agent simply runs without that
checklist and nothing surfaces the gap. This script makes that failure mode
loud, and checks the rest of the plugin's wiring is consistent.

Checks
------
1. **Skill refs resolve in the repo.** Every ``plugin:skill`` ref in
   ``agents/*.md`` must map to ``<plugin-source>/skills/<skill>/SKILL.md`` via
   the repo marketplace manifest. Dangling -> ERROR.
2. **Resolved skills are git-tracked.** A skill that exists locally but is
   untracked will not publish, so installs silently lose it. -> ERROR.
3. **Preload is not disabled.** ``disable-model-invocation: true`` in a skill
   prevents preloading into subagents. -> ERROR.
4. **Installed cache is current.** Tracked skill missing from the newest
   installed cache version of its plugin -> WARN (release + ``plugin update``).
5. **Agent wiring.** Every expected agent (``retriever``, ``citation-verifier``,
   ``evidence-adjudicator``, ``hypothesis-critic``) has an ``agents/<name>.md``
   and is named in the ``commands/medical-research.md`` dispatch list. Drift ->
   ERROR.
6. **Contract skills exist** (``medical-research``, ``research-contract``) and
   ``schema.py`` runs under this interpreter, exposing the ``Tier`` enum. -> ERROR.
7. **MCP servers declared.** ``.mcp.json`` declares ``pubmed`` and ``biomcp``;
   absent -> WARN (retrieval degrades to public-API fallback via WebFetch).

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

# The fixed agent set and the command that must dispatch each.
_EXPECTED_AGENTS: Final = (
    "retriever",
    "citation-verifier",
    "evidence-adjudicator",
    "hypothesis-critic",
)
_EXPECTED_SKILLS: Final = ("medical-research", "research-contract")
_EXPECTED_MCP_SERVERS: Final = ("pubmed", "biomcp")


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
                if _newest_cache_version(plugin) is None:
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

            if _git_tracked(repo, skill_md) is False:
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
                        f"{agent}: '{ref}' has disable-model-invocation: true,"
                        " which blocks preloading into subagents",
                    )
                )
                continue

            cached = _newest_cache_version(plugin)
            if cached is not None and not (
                cached / "skills" / skill / "SKILL.md"
            ).is_file():
                issues.append(
                    Issue(
                        Level.WARN,
                        "skill-refs",
                        f"{agent}: '{ref}' is tracked in the repo but missing "
                        f"from the installed cache ({cached.name}) -- cut a "
                        "release and run claude plugin update",
                    )
                )


def _check_agent_wiring(issues: list[Issue]) -> None:
    command_md = PLUGIN_ROOT / "commands" / "medical-research.md"
    command_text = command_md.read_text(encoding="utf-8") if command_md.is_file() else ""
    if not command_text:
        issues.append(
            Issue(Level.ERROR, "wiring", "commands/medical-research.md is missing")
        )
    for agent in _EXPECTED_AGENTS:
        if not (PLUGIN_ROOT / "agents" / f"{agent}.md").is_file():
            issues.append(
                Issue(Level.ERROR, "wiring", f"expected agents/{agent}.md is missing")
            )
        elif f"`{agent}`" not in command_text and agent not in command_text:
            issues.append(
                Issue(
                    Level.ERROR,
                    "wiring",
                    f"agent '{agent}' is not dispatched by commands/"
                    "medical-research.md",
                )
            )
    for skill in _EXPECTED_SKILLS:
        if not (PLUGIN_ROOT / "skills" / skill / "SKILL.md").is_file():
            issues.append(
                Issue(
                    Level.ERROR, "wiring", f"expected skills/{skill}/SKILL.md is missing"
                )
            )


def _check_schema_runs(issues: list[Issue]) -> None:
    schema_py = PLUGIN_ROOT / "skills" / "research-contract" / "schema.py"
    if not schema_py.is_file():
        issues.append(Issue(Level.ERROR, "schema", "research-contract/schema.py missing"))
        return
    if "class Tier" not in schema_py.read_text(encoding="utf-8"):
        issues.append(Issue(Level.ERROR, "schema", "schema.py has no Tier enum"))
    try:
        proc = subprocess.run(
            [sys.executable, str(schema_py), "--schema"],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        issues.append(Issue(Level.ERROR, "schema", f"schema.py failed to run: {exc}"))
        return
    if proc.returncode != 0:
        issues.append(
            Issue(
                Level.ERROR,
                "schema",
                f"schema.py --schema exited {proc.returncode}: "
                f"{proc.stderr.decode(errors='replace')[:200]}",
            )
        )


def _check_mcp_servers(issues: list[Issue]) -> None:
    mcp_json = PLUGIN_ROOT / ".mcp.json"
    if not mcp_json.is_file():
        issues.append(
            Issue(
                Level.WARN,
                "mcp",
                ".mcp.json is missing; retrieval falls back to public APIs",
            )
        )
        return
    raw: object = json.loads(mcp_json.read_text(encoding="utf-8"))
    servers: object = raw.get("mcpServers") if isinstance(raw, dict) else None
    declared = set(servers) if isinstance(servers, dict) else set()
    for server in _EXPECTED_MCP_SERVERS:
        if server not in declared:
            issues.append(
                Issue(
                    Level.WARN,
                    "mcp",
                    f"MCP server '{server}' not declared in .mcp.json; that "
                    "retrieval path is unavailable",
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
    _check_agent_wiring(issues)
    _check_schema_runs(issues)
    _check_mcp_servers(issues)

    errors = sum(1 for i in issues if i.level is Level.ERROR)
    warns = sum(1 for i in issues if i.level is Level.WARN)

    if as_json:
        payload = {
            "errors": errors,
            "warnings": warns,
            "issues": [
                {"level": i.level.value, "check": i.check, "message": i.message}
                for i in issues
            ],
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
