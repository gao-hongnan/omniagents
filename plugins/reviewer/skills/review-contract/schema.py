#!/usr/bin/env python3
"""Schema, validation, and JSON->Markdown renderer for the reviewer plugin.

This is the machine-enforceable half of the `review-contract` skill: JSON is the
canonical artifact every specialist and the verifier produce, and the
human-readable Markdown report is *rendered* from that JSON by this script. The
prose half (severity rubric, confidence rubric, authoring guidance) lives beside
this file in ``SKILL.md``.

Stdlib only -- no pydantic, no jinja2 -- so it runs under any Python 3.11+
interpreter in any repo under review (the plugin ships no virtualenv).

Parse, don't validate: raw JSON is parsed *once* at the boundary into frozen,
fully-typed domain objects (``Finding``, ``SpecialistReport``, ``ReviewReport``)
by ``from_json`` smart constructors that raise ``ContractError`` on the first bad
field. Everything downstream -- counting, severity bucketing, Markdown rendering
-- operates on those typed objects, so a renderer never re-reads or re-coerces an
untyped dict. The single untyped value in the program is the ``object`` that
``json.loads`` returns; it is narrowed immediately and never propagates.

Why JSON-first: ``file`` and ``line`` are separate, required, typed fields on
every finding. A finding that omits either fails validation and is never
rendered, so the Markdown a human reads always carries a jump-to-able
``file:line`` citation. The verifier cannot summarize a citation away because it
re-emits structured data, not re-typed prose.

Shapes
------
Finding (leaf):
    severity      "BLOCKER" | "IMPORTANT" | "SUGGESTION"        (required)
    file          repo-relative path, e.g. "auth/login.py"     (required)
    line          start line, int >= 1                          (required)
    end_line      end line for multi-line issues, int | null    (optional)
    dimension     one of the five dimensions (specialist output) (one of
    dimensions    list of dimensions (verifier-merged output)     these two)
    summary       one-line description                           (required)
    why           rule violated + consequence                    (required)
    blast_radius  "N direct callers, M transitive importers" or
                  "graph unavailable -- severity from code analysis only"
                                                                 (required)
    fix           concrete one-liner suggestion                  (required)
    confidence    int 0..100                                     (required)

SpecialistReport (one per dimension):
    dimension, target, date, graph_available (bool),
    findings: [Finding], summary

ReviewReport (aggregated, verifier output):
    target, date, author, summary, verdict, actions: [str],
    findings: [Finding]                  (merged/deduped; may carry `dimensions`),
    blast_radius: [{symbol, direct, transitive, flows}],
    cross_cutting: [{file, line?, dimensions, note}],
    specialist_reports: [str]            (relative paths to per-dim .md files)

CLI
---
    python3 schema.py specialist <json> [out.md]   # validate -> render .md
    python3 schema.py review     <json> [out.md]   # validate -> render .md
    python3 schema.py --schema                      # print the annotated shape

Invalid input exits non-zero naming the offending field/index and writes no .md,
so a caller can surface the error instead of persisting a broken report.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final, Self, TypeGuard, TypeVar

# -- closed sets ------------------------------------------------------------


class Severity(StrEnum):
    BLOCKER = "BLOCKER"
    IMPORTANT = "IMPORTANT"
    SUGGESTION = "SUGGESTION"


class Dimension(StrEnum):
    CORRECTNESS = "correctness"
    SECURITY = "security"
    PERFORMANCE = "performance"
    DESIGN = "design"
    TESTING = "testing"


class Verdict(StrEnum):
    APPROVE = "APPROVE"
    APPROVE_WITH_FOLLOWUPS = "APPROVE WITH FOLLOWUPS"
    REQUEST_CHANGES = "REQUEST CHANGES"


class ContractError(ValueError):
    """Raised when a JSON payload violates the review contract."""


# -- domain model -----------------------------------------------------------
#
# Each type is frozen and only constructible (in practice) through `from_json`,
# which is the boundary parser: once an instance exists, every field is the
# right type and present, so renderers below need no defensive `.get()`.


@dataclass(frozen=True, slots=True)
class Finding:
    """One reviewable issue. Always valid once built via `from_json`."""

    severity: Severity
    file: str
    line: int
    end_line: int | None
    dimensions: tuple[Dimension, ...]
    summary: str
    why: str
    blast_radius: str
    fix: str
    confidence: int

    @classmethod
    def from_json(cls: type[Self], raw: object, idx: int) -> Self:
        """Parse one finding. Raises ContractError naming ``finding[idx]``."""
        ctx = f"finding[{idx}]"
        data = _require_object(raw, ctx)

        severity = _parse_enum(Severity, data.get("severity"), "severity", ctx)

        # The traceability contract: file + line are required and typed.
        file = _req_str(data, "file", ctx)
        line = _coerce_int(data.get("line"))
        if line is None:
            raise ContractError(
                f"{ctx}: missing line (int >= 1 required for traceability)"
            )
        if line < 1:
            raise ContractError(f"{ctx}: line must be >= 1, got {line}")

        end_line: int | None = None
        if data.get("end_line") is not None:
            end_line = _coerce_int(data.get("end_line"))
            if end_line is None:
                raise ContractError(f"{ctx}: end_line must be an integer or null")
            if end_line < line:
                raise ContractError(
                    f"{ctx}: end_line ({end_line}) must be >= line ({line})"
                )

        dimensions = _parse_dimensions(data, ctx)

        summary = _req_str(data, "summary", ctx)
        why = _req_str(data, "why", ctx)
        blast_radius = _req_str(data, "blast_radius", ctx)
        fix = _req_str(data, "fix", ctx)

        confidence = _coerce_int(data.get("confidence"))
        if confidence is None:
            raise ContractError(f"{ctx}: missing confidence (int 0..100)")
        if not 0 <= confidence <= 100:
            raise ContractError(f"{ctx}: confidence must be 0..100, got {confidence}")

        return cls(
            severity=severity,
            file=file,
            line=line,
            end_line=end_line,
            dimensions=dimensions,
            summary=summary,
            why=why,
            blast_radius=blast_radius,
            fix=fix,
            confidence=confidence,
        )

    @property
    def location(self) -> str:
        if self.end_line is not None and self.end_line != self.line:
            return f"{self.file}:{self.line}-{self.end_line}"
        return f"{self.file}:{self.line}"


@dataclass(frozen=True, slots=True)
class BlastRadiusRow:
    """One row of the change-impact table. Verifier-supplied, unvalidated."""

    symbol: str
    direct: str
    transitive: str
    flows: str

    @classmethod
    def from_json(cls: type[Self], raw: object) -> Self:
        data = _object_map_or_empty(raw)
        return cls(
            symbol=_opt_str(data, "symbol"),
            direct=_opt_str(data, "direct"),
            transitive=_opt_str(data, "transitive"),
            flows=_opt_str(data, "flows"),
        )


@dataclass(frozen=True, slots=True)
class CrossCuttingRow:
    """One cross-dimension observation. Verifier-supplied, unvalidated.

    ``dimensions`` is free-form here (not checked against ``Dimension``) because
    the original contract never constrained cross-cutting dimensions.
    """

    file: str
    line: int | None
    dimensions: tuple[str, ...]
    note: str

    @classmethod
    def from_json(cls: type[Self], raw: object) -> Self:
        data = _object_map_or_empty(raw)
        dims_raw = data.get("dimensions")
        if isinstance(dims_raw, list):
            dims_items: list[object] = dims_raw
            dimensions = tuple(str(d) for d in dims_items)
        else:
            dimensions = ()
        line_raw = data.get("line")
        line = _coerce_int(line_raw) if line_raw is not None else None
        return cls(
            file=_opt_str(data, "file"),
            line=line,
            dimensions=dimensions,
            note=_opt_str(data, "note"),
        )


@dataclass(frozen=True, slots=True)
class SpecialistReport:
    """One specialist's findings for a single dimension."""

    dimension: Dimension
    target: str
    date: str
    graph_available: bool
    findings: tuple[Finding, ...]
    summary: str

    @classmethod
    def from_json(cls: type[Self], raw: object) -> Self:
        ctx = "specialist report"
        data = _require_object(raw, ctx)
        dimension = _parse_enum(Dimension, data.get("dimension"), "dimension", ctx)
        target = _req_str(data, "target", ctx)
        summary = _req_str(data, "summary", ctx)
        findings = _parse_findings(data.get("findings"), ctx)
        return cls(
            dimension=dimension,
            target=target,
            date=_opt_str(data, "date"),
            graph_available=bool(data.get("graph_available", True)),
            findings=findings,
            summary=summary,
        )


@dataclass(frozen=True, slots=True)
class ReviewReport:
    """The aggregated, deduped report the verifier emits."""

    target: str
    date: str
    author: str
    summary: str
    verdict: Verdict
    actions: tuple[str, ...]
    findings: tuple[Finding, ...]
    blast_radius: tuple[BlastRadiusRow, ...]
    cross_cutting: tuple[CrossCuttingRow, ...]
    specialist_reports: tuple[str, ...]

    @classmethod
    def from_json(cls: type[Self], raw: object) -> Self:
        ctx = "review report"
        data = _require_object(raw, ctx)
        target = _req_str(data, "target", ctx)
        summary = _req_str(data, "summary", ctx)
        verdict = _parse_enum(Verdict, data.get("verdict"), "verdict", ctx)
        findings = _parse_findings(data.get("findings"), ctx)
        actions_raw = data.get("actions", [])
        if not isinstance(actions_raw, list):
            raise ContractError("review report: actions must be a list")
        action_items: list[object] = actions_raw
        return cls(
            target=target,
            date=_opt_str(data, "date"),
            author=_opt_str(data, "author"),
            summary=summary,
            verdict=verdict,
            actions=tuple(str(a) for a in action_items),
            findings=findings,
            blast_radius=_parse_blast_radius(data.get("blast_radius")),
            cross_cutting=_parse_cross_cutting(data.get("cross_cutting")),
            specialist_reports=_parse_str_list(data.get("specialist_reports")),
        )


# -- parsing (the only place untyped JSON is touched) -----------------------


def _is_int(value: object) -> TypeGuard[int]:
    # bool is a subclass of int; a line or confidence of `True` is a bug, not a
    # number. TypeGuard, not TypeIs: the negative branch must NOT narrow `int`
    # away, since a bool returns False here yet is still an int.
    return isinstance(value, int) and not isinstance(value, bool)


def _coerce_int(value: object) -> int | None:
    if _is_int(value):
        return value
    # JSON has no int/float distinction for whole numbers like 95.0.
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _require_object(raw: object, ctx: str) -> dict[str, object]:
    # The one JSON-ingest boundary: `raw` is what json.loads returned. JSON
    # object keys are always strings; values stay `object` so every field read
    # below is forced to narrow before use.
    if isinstance(raw, dict):
        data: dict[str, object] = raw
        return data
    raise ContractError(f"{ctx}: must be a JSON object")


def _object_map_or_empty(raw: object) -> dict[str, object]:
    # Lenient variant for the unvalidated verifier sub-rows: a non-object
    # degrades to empty instead of raising, matching the original tolerance.
    if isinstance(raw, dict):
        data: dict[str, object] = raw
        return data
    return {}


def _req_str(data: Mapping[str, object], key: str, ctx: str) -> str:
    value = data.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ContractError(f"{ctx}: missing {key}")
    if not isinstance(value, str):
        raise ContractError(f"{ctx}: {key} must be a string")
    return value


def _opt_str(data: Mapping[str, object], key: str) -> str:
    # Optional / free-form field. Reproduces the f-string str() the original
    # renderer applied: absent -> "", explicit null -> "None".
    return str(data.get(key, ""))


_EnumT = TypeVar("_EnumT", bound=StrEnum)


def _parse_enum(enum_cls: type[_EnumT], value: object, field: str, ctx: str) -> _EnumT:
    # One parser for every closed set. The enum is the single source of truth:
    # its members define what is valid, and their `.value`s repr as the bare
    # strings the error shows ('BLOCKER', ...), so the message needs no pinned
    # tuple. Adding a Severity/Dimension/Verdict case requires no new parser.
    if isinstance(value, str):
        try:
            return enum_cls(value)
        except ValueError:
            pass
    valid = tuple(member.value for member in enum_cls)
    raise ContractError(f"{ctx}: {field} must be one of {valid}, got {value!r}")


def _parse_dimensions(data: Mapping[str, object], ctx: str) -> tuple[Dimension, ...]:
    # A finding carries either dimensions[] (verifier-merged) or a single
    # dimension (specialist output); the list wins when non-empty. Candidates
    # are stringified before the membership check so a non-string member is
    # reported as e.g. got '42', matching the original behavior.
    dims_raw = data.get("dimensions")
    if isinstance(dims_raw, list) and dims_raw:
        dims_items: list[object] = dims_raw
        candidates = [str(d) for d in dims_items]
    else:
        single = data.get("dimension")
        candidates = [str(single)] if single else []
    if not candidates:
        raise ContractError(f"{ctx}: missing dimension (or dimensions[])")
    return tuple(_parse_enum(Dimension, c, "dimension", ctx) for c in candidates)


def _parse_findings(value: object, ctx: str) -> tuple[Finding, ...]:
    if not isinstance(value, list):
        raise ContractError(f"{ctx}: findings must be a list")
    items: list[object] = value
    return tuple(Finding.from_json(item, idx) for idx, item in enumerate(items))


def _parse_blast_radius(value: object) -> tuple[BlastRadiusRow, ...]:
    if not isinstance(value, list):
        return ()
    items: list[object] = value
    return tuple(BlastRadiusRow.from_json(item) for item in items)


def _parse_cross_cutting(value: object) -> tuple[CrossCuttingRow, ...]:
    if not isinstance(value, list):
        return ()
    items: list[object] = value
    return tuple(CrossCuttingRow.from_json(item) for item in items)


def _parse_str_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    items: list[object] = value
    return tuple(str(item) for item in items)


# -- rendering --------------------------------------------------------------


def _render_finding(f: Finding) -> str:
    dim_str = ", ".join(d.value for d in f.dimensions)
    return "\n".join(
        [
            f"- **{f.severity.value}** `{f.location}` — {f.summary}",
            f"  - **Dimension**: {dim_str}",
            f"  - **Why**: {f.why}",
            f"  - **Blast radius**: {f.blast_radius}",
            f"  - **Fix**: {f.fix}",
            f"  - **Confidence**: {f.confidence}",
        ]
    )


def _render_findings_by_severity(findings: tuple[Finding, ...]) -> str:
    buckets: dict[Severity, list[Finding]] = {sev: [] for sev in Severity}
    for f in findings:
        buckets[f.severity].append(f)
    blocks: list[str] = []
    for sev in Severity:
        rows = buckets[sev]
        body = "\n\n".join(_render_finding(f) for f in rows) if rows else "_None_"
        blocks.append(f"### {sev.value}\n\n{body}")
    return "\n\n".join(blocks)


def _counts(findings: tuple[Finding, ...]) -> dict[Severity, int]:
    counts = {sev: 0 for sev in Severity}
    for f in findings:
        counts[f.severity] += 1
    return counts


def render_specialist(report: SpecialistReport) -> str:
    front = [
        "---",
        f"dimension: {report.dimension.value}",
        f"target: {report.target}",
        f"date: {report.date}",
        f"graph_available: {str(report.graph_available).lower()}",
        "---",
    ]
    return "\n".join(
        [
            *front,
            "",
            f"# {report.dimension.value.capitalize()} Review — {report.target}",
            "",
            "## Findings",
            "",
            _render_findings_by_severity(report.findings),
            "",
            "## Summary",
            "",
            report.summary,
            "",
        ]
    )


def _render_blast_radius(rows: tuple[BlastRadiusRow, ...]) -> str:
    if not rows:
        return "_Blast radius: graph unavailable or no changed symbols resolved._"
    out = [
        "| Changed Symbol | Direct Callers | Transitive Importers | Flows |",
        "|----------------|----------------|----------------------|-------|",
    ]
    for r in rows:
        out.append(f"| {r.symbol} | {r.direct} | {r.transitive} | {r.flows} |")
    return "\n".join(out)


def _render_cross_cutting(rows: tuple[CrossCuttingRow, ...]) -> str:
    if not rows:
        return "_None._"
    out: list[str] = []
    for r in rows:
        dims = ", ".join(r.dimensions)
        loc = r.file
        if r.line is not None:
            loc = f"{loc}:{r.line}"
        prefix = f"`{loc}` " if loc else ""
        out.append(f"- {prefix}({dims}): {r.note}")
    return "\n".join(out)


def _render_actions(actions: tuple[str, ...]) -> str:
    if not actions:
        return "_None._"
    return "\n".join(f"{i}. {a}" for i, a in enumerate(actions, start=1))


def render_review(report: ReviewReport) -> str:
    counts = _counts(report.findings)
    front = [
        "---",
        f"target: {report.target}",
        f"date: {report.date}",
        f"author: {report.author}",
        f"verdict: {report.verdict.value}",
        f"blocker: {counts[Severity.BLOCKER]}",
        f"important: {counts[Severity.IMPORTANT]}",
        f"suggestion: {counts[Severity.SUGGESTION]}",
        "---",
    ]
    sidecar_block = ""
    if report.specialist_reports:
        links = "\n".join(f"- [`{p}`]({p})" for p in report.specialist_reports)
        sidecar_block = f"\n## Per-Specialist Reports\n\n{links}\n"
    return "\n".join(
        [
            *front,
            "",
            f"# Code Review — {report.target}",
            "",
            "## Summary",
            "",
            report.summary,
            "",
            "## Blast Radius",
            "",
            _render_blast_radius(report.blast_radius),
            "",
            "## Findings by Severity",
            "",
            _render_findings_by_severity(report.findings),
            "",
            "## Cross-Cutting Observations",
            "",
            _render_cross_cutting(report.cross_cutting),
            "",
            "## Verdict",
            "",
            f"**{report.verdict.value}**",
            "",
            _render_actions(report.actions),
            sidecar_block,
        ]
    )


# -- CLI --------------------------------------------------------------------

SCHEMA_DOC: Final = __doc__


def _out_path(json_path: Path, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    return json_path.with_suffix(".md")


def _render_cli(kind: str, json_path: str, out: str | None) -> int:
    path = Path(json_path)
    try:
        # The one untyped boundary: json.loads is typed `-> Any`. Pinning it to
        # `object` forces every downstream read to narrow; no Any escapes here.
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(json.dumps({"error": f"file not found: {json_path}"}), file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(
            json.dumps({"error": f"invalid JSON in {json_path}: {exc}"}),
            file=sys.stderr,
        )
        return 2

    try:
        if kind == "specialist":
            md = render_specialist(SpecialistReport.from_json(raw))
        else:
            md = render_review(ReviewReport.from_json(raw))
    except ContractError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1

    out_path = _out_path(path, out)
    out_path.write_text(md, encoding="utf-8")
    print(json.dumps({"rendered": str(out_path)}))
    return 0


def main(argv: list[str]) -> int:
    args = argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(SCHEMA_DOC)
        return 0 if args else 2
    if args[0] == "--schema":
        print(SCHEMA_DOC)
        return 0
    if args[0] in ("specialist", "review"):
        if len(args) < 2:
            print(
                json.dumps({"error": f"usage: schema.py {args[0]} <json> [out.md]"}),
                file=sys.stderr,
            )
            return 2
        out = args[2] if len(args) > 2 else None
        return _render_cli(args[0], args[1], out)
    unknown = f"unknown command {args[0]!r}; expected specialist|review|--schema"
    print(json.dumps({"error": unknown}), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
