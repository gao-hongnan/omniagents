"""Offline --dry-run tests: payload with placeholders, no gh, no network."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "post_pr_comments.py"

_REVIEW_JSON = {
    "target": "feature/login",
    "date": "2026-10-24",
    "author": "verifier",
    "summary": "Request changes: one blocker.",
    "verdict": "REQUEST CHANGES",
    "actions": ["Rotate tokens"],
    "findings": [
        {
            "severity": "BLOCKER",
            "file": "auth/login.py",
            "line": 42,
            "end_line": 55,
            "dimensions": ["security"],
            "summary": "Token never expires",
            "why": "No expiry claim",
            "blast_radius": "3 direct callers",
            "fix": "Set exp",
            "confidence": 90,
        }
    ],
    "blast_radius": [],
    "cross_cutting": [],
    "specialist_reports": [],
}


def _run_dry(tmp_path: Path, review: object) -> subprocess.CompletedProcess[str]:
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("GH_")
    }
    env["PATH"] = "/usr/bin:/bin"  # no gh on PATH
    return subprocess.run(
        [sys.executable, str(_SCRIPT), "--pr", "7", str(review_path), "--dry-run"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
        timeout=60,
        check=False,
    )


def test_dry_run_prints_payload_with_placeholders(tmp_path: Path) -> None:
    proc = _run_dry(tmp_path, _REVIEW_JSON)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["pr"] == 7
    assert payload["repo"] == "<owner>/<repo>"
    assert payload["payload"]["commit_id"] == "<head-sha>"
    assert payload["payload"]["event"] == "COMMENT"
    (comment,) = payload["payload"]["comments"]
    assert comment["path"] == "auth/login.py"
    assert comment["line"] == 55
    assert comment["start_line"] == 42
    assert comment["side"] == comment["start_side"] == "RIGHT"
    assert "Token never expires" in comment["body"]


def test_dry_run_rejects_invalid_review_json(tmp_path: Path) -> None:
    invalid = dict(_REVIEW_JSON)
    invalid["findings"] = [dict(_REVIEW_JSON["findings"][0], line=0)]
    proc = _run_dry(tmp_path, invalid)
    assert proc.returncode == 1, proc.stdout
    assert "invalid review.json" in proc.stderr


def test_dry_run_requires_pr_flag(tmp_path: Path) -> None:
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(_REVIEW_JSON), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(_SCRIPT), str(review_path), "--dry-run"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 2
