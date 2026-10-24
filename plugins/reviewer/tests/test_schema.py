"""Valid/invalid artifacts per schema kind, plus renderer, floor, and CLI checks."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "skills" / "review-contract" / "schema.py"
)


def _load_schema() -> ModuleType:
    spec = importlib.util.spec_from_file_location("review_contract_schema", _SCHEMA_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


schema = _load_schema()


def finding_raw(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "severity": "BLOCKER",
        "file": "auth/login.py",
        "line": 42,
        "end_line": 55,
        "dimension": "security",
        "summary": "Token never expires",
        "why": "No expiry claim; a leaked token is valid forever",
        "blast_radius": "3 direct callers, 11 transitive importers",
        "fix": "Set exp = now + 1h at issue time",
        "confidence": 90,
    }
    base.update(overrides)
    return base


def specialist_raw(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "dimension": "security",
        "target": "feature/login",
        "date": "2026-10-24",
        "graph_available": False,
        "findings": [finding_raw()],
        "summary": "One blocker in the token path.",
    }
    base.update(overrides)
    return base


def review_raw(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "target": "feature/login",
        "date": "2026-10-24",
        "author": "verifier",
        "summary": "Request changes: one blocker.",
        "verdict": "REQUEST CHANGES",
        "actions": ["Rotate any tokens issued by this path"],
        "findings": [finding_raw(dimensions=["security", "correctness"])],
        "blast_radius": [
            {"symbol": "issue_token", "direct": 3, "transitive": 11, "flows": "auth -> api"}
        ],
        "cross_cutting": [
            {"file": "auth/__init__.py", "line": 5, "dimensions": ["security"], "note": "Re-exported"}
        ],
        "specialist_reports": ["review-security.md"],
    }
    base.update(overrides)
    return base


# -- Finding -----------------------------------------------------------------


def test_finding_valid_minimal_and_full() -> None:
    minimal_raw = finding_raw()
    minimal_raw.pop("end_line")
    minimal = schema.Finding.from_json(minimal_raw, 0)
    assert minimal.end_line is None
    assert minimal.dimensions == (schema.Dimension.SECURITY,)
    assert minimal.location == "auth/login.py:42"

    full = schema.Finding.from_json(finding_raw(), 1)
    assert full.severity is schema.Severity.BLOCKER
    assert full.line == 42 and full.end_line == 55
    assert full.dimensions == (schema.Dimension.SECURITY,)
    assert full.location == "auth/login.py:42-55"
    assert full.confidence == 90


@pytest.mark.parametrize(
    "overrides",
    [
        {"severity": "CATASTROPHIC"},          # not a Severity
        {"file": ""},                          # required string empty
        {"line": 0},                           # below 1
        {"line": "42"},                        # string, not int
        {"end_line": 10},                      # end before start
        {"confidence": 101},                   # out of range
        {"confidence": None},                  # missing
        {"summary": None},                     # required field absent
        {"dimension": "vibes"},                # not a Dimension
    ],
)
def test_finding_invalid(overrides: dict[str, object]) -> None:
    with pytest.raises(schema.ContractError):
        schema.Finding.from_json(finding_raw(**overrides), 0)


def test_finding_rejects_non_object() -> None:
    with pytest.raises(schema.ContractError):
        schema.Finding.from_json(["not", "an", "object"], 0)


# -- SpecialistReport ---------------------------------------------------------


def test_specialist_report_valid() -> None:
    report = schema.SpecialistReport.from_json(specialist_raw())
    assert report.dimension is schema.Dimension.SECURITY
    assert report.graph_available is False
    assert len(report.findings) == 1
    assert report.findings[0].file == "auth/login.py"


def test_specialist_report_invalid() -> None:
    with pytest.raises(schema.ContractError):
        schema.SpecialistReport.from_json(specialist_raw(dimension="typo-dimension"))
    with pytest.raises(schema.ContractError):
        schema.SpecialistReport.from_json(
            specialist_raw(findings=[finding_raw(line=0)])
        )


# -- ReviewReport -------------------------------------------------------------


def test_review_report_valid() -> None:
    report = schema.ReviewReport.from_json(review_raw())
    assert report.verdict is schema.Verdict.REQUEST_CHANGES
    assert report.actions == ("Rotate any tokens issued by this path",)
    assert len(report.blast_radius) == 1
    assert report.blast_radius[0].symbol == "issue_token"
    assert report.cross_cutting[0].dimensions == (schema.Dimension.SECURITY,)
    assert report.specialist_reports == ("review-security.md",)


def test_review_report_invalid() -> None:
    with pytest.raises(schema.ContractError):
        schema.ReviewReport.from_json(review_raw(verdict="SHIP IT"))
    with pytest.raises(schema.ContractError):
        schema.ReviewReport.from_json(review_raw(actions="not-a-list"))


# -- downstream checks --------------------------------------------------------


def test_render_review_keeps_file_line_citations() -> None:
    md = schema.render_review(schema.ReviewReport.from_json(review_raw()))
    assert "auth/login.py:42-55" in md
    assert "REQUEST CHANGES" in md


def test_scope_violations_flags_out_of_scope_files() -> None:
    finding = schema.Finding.from_json(finding_raw(), 0)
    assert schema.scope_violations((finding,), frozenset({"auth/login.py"})) == ()
    violations = schema.scope_violations((finding,), frozenset({"other/file.py"}))
    assert violations and "auth/login.py" in violations[0]


def test_enforce_confidence_drops_below_severity_floors() -> None:
    # Floors: IMPORTANT >= 70, SUGGESTION >= 80; BLOCKER never strips.
    report = schema.ReviewReport.from_json(
        review_raw(
            findings=[
                finding_raw(severity="IMPORTANT", confidence=60),
                finding_raw(severity="IMPORTANT", confidence=75),
                finding_raw(severity="BLOCKER", confidence=10),
            ]
        )
    )
    kept, warnings = schema.enforce_confidence(report)
    assert [f.confidence for f in kept.findings] == [75, 10]
    assert len(warnings) == 1 and "below the contract floor 70" in warnings[0]


# -- CLI ----------------------------------------------------------------------


def test_cli_review_renders_and_ci_exit_code(tmp_path: Path, capsys) -> None:
    payload = tmp_path / "review.json"
    payload.write_text(json.dumps(review_raw()), encoding="utf-8")
    rc = schema.main(["schema.py", "review", str(payload), "--ci"])
    out = capsys.readouterr()
    assert rc == 3  # REQUEST_CHANGES + --ci gates CI
    rendered = json.loads(out.out.splitlines()[0])["rendered"]
    assert Path(rendered).read_text(encoding="utf-8").count("auth/login.py") >= 1


def test_cli_invalid_json_is_exit_1(tmp_path: Path, capsys) -> None:
    payload = tmp_path / "review.json"
    payload.write_text(
        json.dumps(review_raw(findings=[finding_raw(line=0)])), encoding="utf-8"
    )
    assert schema.main(["schema.py", "review", str(payload)]) == 1
    assert "error" in capsys.readouterr().err


def test_cli_missing_file_is_exit_2(tmp_path: Path) -> None:
    assert schema.main(["schema.py", "review", str(tmp_path / "nope.json")]) == 2
