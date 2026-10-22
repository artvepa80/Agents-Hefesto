"""Text output shows the rule id of a finding that has one.

JSON and SARIF already carry ``rule_id``; the text formatter dropped it, so a
hook block printed "Hardcoded secret in key 'api_key'" without ``J001``.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)
from hefesto.reports.text_reporter import TextReporter

REPO_ROOT = Path(__file__).resolve().parents[1]


def _issue(rule_id=None):
    return AnalysisIssue(
        file_path="c.json",
        line=1,
        column=2,
        issue_type=AnalysisIssueType.HARDCODED_SECRET,
        severity=AnalysisIssueSeverity.CRITICAL,
        message="Hardcoded secret in key 'api_key'",
        rule_id=rule_id,
    )


def _issue_line(text):
    return [line for line in text.splitlines() if "├─ Issue:" in line]


def test_issue_line_shows_rule_id_in_brackets():
    text = TextReporter()._format_issue(_issue("J001"))
    assert _issue_line(text) == ["  ├─ Issue: [J001] Hardcoded secret in key 'api_key'"]


def test_issue_line_without_rule_id_is_unchanged():
    text = TextReporter()._format_issue(_issue(None))
    assert _issue_line(text) == ["  ├─ Issue: Hardcoded secret in key 'api_key'"]
    assert "[]" not in text
    assert "Rule" not in text


def test_empty_rule_id_prints_no_brackets():
    text = TextReporter()._format_issue(_issue(""))
    assert _issue_line(text) == ["  ├─ Issue: Hardcoded secret in key 'api_key'"]


def test_cli_text_output_shows_json_rule_id(tmp_path):
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"api_key": "sk_live_" + "a1B2c3D4e5F6g7H8i9J0k1L2"}))
    env = dict(os.environ, HEFESTO_TELEMETRY="0", HEFESTO_NO_UPSELL="1", HOME=str(tmp_path))
    proc = subprocess.run(
        [sys.executable, "-m", "hefesto.cli.main", "analyze", str(cfg), "--no-config"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
    )
    assert "├─ Issue: [J001] " in proc.stdout, proc.stdout + proc.stderr
