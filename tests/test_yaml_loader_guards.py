"""CSafeLoader must not crash, and a loader error must not drop findings.

``CSafeLoader`` segfaults between 20,000 and 30,000 levels on CPython 3.13,
including flow documents whose ``[`` or ``{`` are not consecutive. Around
1,000 levels the pure-Python loader raises and 4.20.1 reports
YAML_SYNTAX_ERROR, while ``CSafeLoader`` still accepts the document and the
gate exits 0. A timestamp such as ``2001-13-01`` raises ValueError, which
is not a yaml.YAMLError; 4.20.1 caught it and still reported the file's
other findings.

This module is collected on every CI Python (3.10 through 3.14). The deep
cases run in a subprocess so a signal death fails the test instead of
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
FLOW_SEQ_30K = "[ " * 30000 + "]" * 30000 + "\n"
FLOW_MAP_30K = "{a: " * 30000 + "1" + "}" * 30000 + "\n"
PASSWORD_30K = 'password: "super-secret-value"\ncfg: ' + "{a: " * 30000 + "1" + "}" * 30000 + "\n"
THOUSAND = "{a: " * 1000 + "1" + "}" * 1000 + "\n"
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


def _analyze(path: Path, fail_on: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, HEFESTO_TELEMETRY="0", HEFESTO_NO_UPSELL="1")
    return subprocess.run(
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
            fail_on,
            "--output",
            "json",
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO),
        timeout=60,
    )


def _safe_syntax_message(content: str) -> str:
    """The HIGH finding 4.20.1 reported: SafeLoader's exception, truncated."""
    try:
        list(yaml.load_all(content, Loader=yaml.SafeLoader))
    except Exception as exc:
        return f"YAML syntax error: {str(exc)[:100]}"
    raise AssertionError("SafeLoader accepted a document 4.20.1 rejected")


def test_depth_above_500_is_too_deep_for_the_c_loader():
    from hefesto.core.config_parse import C_LOADER_MAX_DEPTH, yaml_nesting_exceeds

    # 500 is below the depth SafeLoader rejects on every supported Python.
    assert C_LOADER_MAX_DEPTH == 500
    assert yaml_nesting_exceeds("{a: " * 501 + "1" + "}" * 501 + "\n")
    assert yaml_nesting_exceeds("[ " * 501 + "]" * 501 + "\n")
    assert not yaml_nesting_exceeds("{a: " * 500 + "1" + "}" * 500 + "\n")
    assert not yaml_nesting_exceeds("[ " * 500 + "]" * 500 + "\n")
    shallow = (
        "apiVersion: v1\nkind: Pod\nmetadata:\n  name: web\nspec:\n  containers:\n  - name: web\n"
    )
    assert not yaml_nesting_exceeds(shallow)


def test_shallow_manifest_skips_the_event_scan(monkeypatch):
    from hefesto.core.config_parse import yaml_nesting_exceeds

    def boom(*_args, **_kwargs):
        raise AssertionError("yaml.parse was called for a shallow manifest")

    monkeypatch.setattr("hefesto.core.config_parse.yaml.parse", boom)
    shallow = "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: cfg\n"
    assert not yaml_nesting_exceeds(shallow)


def _thirty_k(label: str) -> str:
    if label == "flow-seq":
        return FLOW_SEQ_30K
    if label == "flow-map":
        return FLOW_MAP_30K
    return PASSWORD_30K


@pytest.mark.parametrize("label", ["flow-seq", "flow-map", "password"])
def test_thirty_thousand_deep_does_not_kill_the_process(tmp_path, label):
    # The document stays out of the test id. Pytest copies that id into the
    # environment, and a 30,000-level parameter exceeds the OS argument limit.
    content = _thirty_k(label)
    password = label == "password"
    path = tmp_path / f"{label}.yaml"
    path.write_text(content, encoding="utf-8")
    result = _analyze(path, "high")
    # SIGSEGV is -11 from subprocess, or 139 when a shell encodes the signal.
    # 4.20.1 exited 1 under --fail-on high.
    assert result.returncode == 1, result.returncode
    text = (result.stdout or "") + (result.stderr or "")
    assert "YAML_SYNTAX_ERROR" in text
    assert "could not be analyzed" not in text
    assert '"not_analyzed"' not in text
    if password:
        assert "YAML_SECRET_EXPOSURE" in text
        assert "password" in text


def test_thousand_deep_matches_4_20_1(tmp_path, monkeypatch):
    path = tmp_path / "nest.yaml"
    path.write_text(THOUSAND, encoding="utf-8")
    expected = _safe_syntax_message(THOUSAND)
    _, default_issues = _issues(path)
    monkeypatch.setattr("hefesto.core.config_parse.loader_class", lambda: yaml.SafeLoader)
    _, safe_issues = _issues(path)
    assert _sig(default_issues) == _sig(safe_issues)
    assert any(issue.issue_type.value == "YAML_SYNTAX_ERROR" for issue in default_issues)
    assert all(issue.severity.value == "HIGH" for issue in default_issues)
    result = _analyze(path, "high")
    text = (result.stdout or "") + (result.stderr or "")
    assert result.returncode == 1, result.returncode
    assert expected in text
    assert "could not be analyzed" not in text


def test_invalid_timestamp_keeps_the_other_findings(tmp_path, monkeypatch):
    path = tmp_path / "manifest.yaml"
    path.write_text(TIMESTAMP, encoding="utf-8")
    engine, issues = _issues(path)
    assert engine._not_analyzed == []
    # 4.20.1 stored str(ValueError)[:100]. CPython 3.14 appends ", not 13".
    sig = _sig(issues)
    assert sig[:2] == [
        ("YAML_SECRET_EXPOSURE", 7, 0, "MEDIUM", "Possible hardcoded token"),
        ("YAML_SECRET_EXPOSURE", 8, 0, "HIGH", "Potential hardcoded password"),
    ]
    assert len(sig) == 3
    assert sig[2][:4] == ("YAML_SYNTAX_ERROR", 1, 0, "HIGH")
    assert sig[2][4].startswith("YAML syntax error: month must be in 1..12")
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
