"""CSafeLoader must not crash, and a loader error must not drop findings.

On CPython 3.10-3.13 libyaml segfaults on a document nested about 50,000
levels (``'- ' * 50000``). Around 900 levels the pure-Python loader raises
and 4.20.1 reports YAML_SYNTAX_ERROR, while CSafeLoader still accepts the
document. A timestamp such as ``2001-13-01`` raises ValueError, which is
not a yaml.YAMLError; 4.20.1 caught it and still reported the file's other
findings.

This module is collected on every CI Python (3.10 through 3.14). The deep
case runs in a subprocess so a signal death fails the test instead of
killing the suite.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from hefesto.core.analyzer_engine import AnalyzerEngine

REPO = Path(__file__).resolve().parents[1]
DEEP = "- " * 50000 + "x\n"
NINE_HUNDRED = "- " * 900 + "x\n"
TIMESTAMP = """apiVersion: v1
kind: ConfigMap
metadata:
  name: cfg
  created: 2001-13-01
data:
  token: "abcdefghijklmnop"
  password: "super-secret-value"
"""


def _issues(path: Path):
    engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
    report = engine.analyze_path(str(path))
    issues = [issue for result in report.file_results for issue in result.issues]
    return engine, issues


def _sig(issues):
    return sorted(
        (issue.issue_type.value, issue.line, issue.column, issue.severity.value, issue.message)
        for issue in issues
    )


def test_pre_scan_flags_only_deep_runs():
    from hefesto.core.config_parse import C_LOADER_MAX_DEPTH, yaml_nesting_exceeds

    # 900 is the depth SafeLoader rejects and CSafeLoader accepts.
    assert C_LOADER_MAX_DEPTH < 900
    assert C_LOADER_MAX_DEPTH >= 32
    assert yaml_nesting_exceeds(DEEP)
    assert yaml_nesting_exceeds(NINE_HUNDRED)
    assert yaml_nesting_exceeds("[" * 900 + "x" + "]" * 900)
    assert yaml_nesting_exceeds("{" * (C_LOADER_MAX_DEPTH + 1))
    shallow = (
        "apiVersion: v1\nkind: Pod\nmetadata:\n  name: web\nspec:\n  containers:\n  - name: web\n"
    )
    assert not yaml_nesting_exceeds(shallow)
    assert not yaml_nesting_exceeds("- " * C_LOADER_MAX_DEPTH + "x\n")


def test_deep_nesting_does_not_kill_the_process(tmp_path):
    path = tmp_path / "deep.yaml"
    path.write_text(DEEP, encoding="utf-8")
    env = dict(os.environ, HEFESTO_TELEMETRY="0", HEFESTO_NO_UPSELL="1")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "hefesto.cli.main",
            "analyze",
            str(path),
            "--no-config",
            "--severity",
            "LOW",
            "--fail-on",
            "HIGH",
            "--output",
            "json",
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO),
        timeout=60,
    )
    # SIGSEGV is -11 from subprocess, or 139 when a shell encodes the signal.
    assert result.returncode > 0, result.returncode
    text = (result.stdout or "") + (result.stderr or "")
    assert "YAML_SYNTAX_ERROR" in text
    assert "could not be analyzed" not in text
    assert '"not_analyzed"' not in text


def test_nine_hundred_deep_matches_safeloader(tmp_path, monkeypatch):
    path = tmp_path / "nest.yaml"
    path.write_text(NINE_HUNDRED, encoding="utf-8")
    _, default_issues = _issues(path)
    monkeypatch.setattr("hefesto.core.config_parse.loader_class", lambda: yaml.SafeLoader)
    _, safe_issues = _issues(path)
    assert _sig(default_issues) == _sig(safe_issues)
    # SafeLoader rejects this depth (RecursionError). That is the 4.20.1 finding.
    with pytest.raises(RecursionError):
        list(yaml.load_all(NINE_HUNDRED, Loader=yaml.SafeLoader))
    assert any(issue.issue_type.value == "YAML_SYNTAX_ERROR" for issue in default_issues)
    assert all(issue.severity.value == "HIGH" for issue in default_issues)


def test_invalid_timestamp_keeps_the_other_findings(tmp_path, monkeypatch):
    path = tmp_path / "manifest.yaml"
    path.write_text(TIMESTAMP, encoding="utf-8")
    engine, issues = _issues(path)
    assert engine._not_analyzed == []
    assert _sig(issues) == [
        ("YAML_SECRET_EXPOSURE", 7, 0, "MEDIUM", "Possible hardcoded token"),
        ("YAML_SECRET_EXPOSURE", 8, 0, "HIGH", "Potential hardcoded password"),
        ("YAML_SYNTAX_ERROR", 1, 0, "HIGH", "YAML syntax error: month must be in 1..12"),
    ]
    monkeypatch.setenv("HEFESTO_TELEMETRY", "0")
    monkeypatch.setenv("HEFESTO_NO_UPSELL", "1")
    cli = __import__("hefesto.cli.main", fromlist=["cli"]).cli
    result = CliRunner().invoke(
        cli,
        ["analyze", str(path), "--fail-on", "critical", "--no-config", "--severity", "LOW"],
    )
    text = (result.output or "") + (result.stderr or "")
    assert result.exit_code == 0
    assert "could not be analyzed" not in text
    assert "month must be in 1..12" in text
    assert "token" in text
    assert "password" in text
