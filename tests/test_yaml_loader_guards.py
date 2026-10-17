"""CSafeLoader must not crash, and a loader error must not drop findings.

``CSafeLoader`` segfaults between 20,000 and 30,000 levels on CPython 3.13,
including flow documents whose ``[`` or ``{`` are not consecutive.
``SafeLoader`` rejects from depth 486-489 (the default recursion limit is
1000, about 2 frames per level) and 4.20.1 reports YAML_SYNTAX_ERROR.
``CSafeLoader`` still accepts those documents, so the gate exits 0.
A timestamp such as ``2001-13-01`` raises ValueError, which is not a
yaml.YAMLError; 4.20.1 caught it and still reported the file's other
findings.

This module is collected on every CI Python (3.10 through 3.14). The deep
cases run in a subprocess so a signal death fails the test instead of
killing the suite.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from hefesto.core.analyzer_engine import AnalyzerEngine
from hefesto.core.config_parse import load_yaml, parse_scope

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


def _analyze(path: Path, fail_on: str, **extra_env: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, HEFESTO_TELEMETRY="0", HEFESTO_NO_UPSELL="1")
    env.pop("HEFESTO_YAML_LOADER", None)
    env.update(extra_env)
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


def _nested(style: str, depth: int) -> str:
    """A document whose collection nesting is ``depth`` levels."""
    if style == "flow-seq":
        return "[ " * depth + "1" + "]" * depth + "\n"
    if style == "flow-map":
        return "{a: " * depth + "1" + "}" * depth + "\n"
    lines = ["  " * i + "a:" for i in range(depth)]
    lines.append("  " * depth + "1")
    return "\n".join(lines) + "\n"


def _alternating_block(depth: int) -> str:
    """``a:`` / ``-`` pairs. Two collections share one indent column."""
    lines = []
    for i in range(depth):
        indent = " " * (i // 2)
        lines.append(f"{indent}a:" if i % 2 == 0 else f"{indent}-")
    return "\n".join(lines) + "\n"


def _finding_sig(result: subprocess.CompletedProcess) -> list:
    data = json.loads(result.stdout)
    found = []
    for entry in data["files"]:
        for issue in entry["issues"]:
            found.append(
                (issue["type"], issue["line"], issue["column"], issue["severity"], issue["message"])
            )
    return sorted(found)


def _assert_same_as_safeloader(path: Path, content: str) -> None:
    """Findings and ``--fail-on high`` match SafeLoader on the same stack.

    The pure-Python loader is forced with ``HEFESTO_YAML_LOADER=safe``.
    A bare ``python -c`` SafeLoader is not the oracle: the CLI is already
    on the stack, and each nesting level uses about two frames.
    """
    path.write_text(content, encoding="utf-8")
    default = _analyze(path, "high")
    safe = _analyze(path, "high", HEFESTO_YAML_LOADER="safe")
    assert default.returncode == safe.returncode
    assert default.returncode in (0, 1)
    assert _finding_sig(default) == _finding_sig(safe)
    text = (default.stdout or "") + (default.stderr or "")
    assert "could not be analyzed" not in text


def _loader_outcome(content: str):
    """What the HIGH syntax finding is built from, or success.

    ``--fail-on high`` exits 1 when this is an error. The message is the
    same truncation ``YamlAnalyzer`` stores.
    """
    with parse_scope():
        loaded = load_yaml(content)
    if loaded.error is None:
        return ("ok", len(loaded.raw or []))
    return ("err", type(loaded.error).__name__, str(loaded.error)[:100])


def _sweep_depths(style: str) -> None:
    """Compare depths 480-505 to SafeLoader inside this process.

    The parent runs one subprocess per shape. A crash here fails that
    test. Print the depth before loading it so a signal still names the
    level; rerun that one depth only when diagnosing.
    """
    if style not in ("flow-seq", "flow-map", "block"):
        raise SystemExit("unknown style %s" % style)
    os.environ.pop("HEFESTO_YAML_LOADER", None)
    for depth in range(480, 506):
        print("depth %s %s" % (style, depth), flush=True)
        content = _nested(style, depth)
        os.environ.pop("HEFESTO_YAML_LOADER", None)
        default = _loader_outcome(content)
        os.environ["HEFESTO_YAML_LOADER"] = "safe"
        safe = _loader_outcome(content)
        if default != safe:
            raise SystemExit("mismatch %s %s\n%s\n%s" % (style, depth, default, safe))
    print("ok %s 480-505" % style, flush=True)


@pytest.mark.parametrize("style", ["flow-seq", "flow-map", "block"])
def test_depth_sweep_matches_safeloader(style):
    """One subprocess for the whole 480-505 sweep. Kept on PR CI, not nightly."""
    env = dict(os.environ, HEFESTO_TELEMETRY="0", HEFESTO_NO_UPSELL="1")
    env.pop("HEFESTO_YAML_LOADER", None)
    # pytest-cov traces every frame in the child. SafeLoader near the
    # recursion limit then dominates the sweep. The assertion is the
    # loader outcome, which does not need that trace.
    for key in list(env):
        if key.startswith("COV_CORE"):
            env.pop(key)
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--sweep", style],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO),
        timeout=60,
    )
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    assert "ok %s 480-505" % style in result.stdout


def test_alternating_block_at_990_matches_safeloader(tmp_path):
    content = _alternating_block(990)
    longest = max(len(line) for line in content.splitlines())
    # Brackets plus the longest line understates this shape by about half,
    # so a bound of that form stays under 500 and used to skip the scan.
    assert content.count("[") + content.count("{") + longest <= 500
    _assert_same_as_safeloader(tmp_path / "alt.yaml", content)


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


def _libyaml_invalid(label: str) -> str:
    """Invalid YAML libyaml accepts. 4.20.1 rejects it with SafeLoader."""
    bom = "\ufeff"
    # yaml-test-suite DMG6 and N4JP, both error cases.
    dmg6 = "key:\n  ok: 1\n wrong: 2\n"
    n4jp = 'map:\n  key1: "quoted1"\n key2: "bad indentation"\n'
    documents = {
        "bom-directive": bom + "%YAML 1.1#...\n---\n",
        "double-bom": bom + bom + "k1: v1\n k2: v2\n",
        "double-bom-DMG6": bom + bom + dmg6,
        "double-bom-N4JP": bom + bom + n4jp,
        "cat-bom": "a: 1\n---\n" + bom + "k1: v1\n k2: v2\n",
        "empty-key-brackets": "k: [?]]\n",
        "configmap-hosts": (
            "apiVersion: v1\n"
            "kind: ConfigMap\n"
            "metadata:\n"
            "  name: cfg\n"
            "data:\n"
            "  hosts: [? ]]\n"
        ),
        "empty-key-comma": "[ ?, , b, c ]",
        "empty-key-close": "[ a, b, ? ] ]",
    }
    return documents[label]


@pytest.mark.parametrize(
    "label",
    [
        "bom-directive",
        "double-bom",
        "double-bom-DMG6",
        "double-bom-N4JP",
        "cat-bom",
        "empty-key-brackets",
        "configmap-hosts",
        "empty-key-comma",
        "empty-key-close",
    ],
)
def test_bom_and_empty_flow_key_match_4_20_1(tmp_path, label):
    """``--fail-on high`` exits 1, the same as 4.20.1's SafeLoader."""
    path = tmp_path / "bad.yaml"
    path.write_text(_libyaml_invalid(label), encoding="utf-8")
    result = _analyze(path, "high")
    safe = _analyze(path, "high", HEFESTO_YAML_LOADER="safe")
    assert result.returncode == 1, (label, result.returncode, result.stdout, result.stderr)
    assert result.returncode == safe.returncode
    assert _finding_sig(result) == _finding_sig(safe)
    assert any(item[0] == "YAML_SYNTAX_ERROR" for item in _finding_sig(result))
    text = (result.stdout or "") + (result.stderr or "")
    assert "could not be analyzed" not in text


@pytest.mark.parametrize(
    "label",
    ["flow-question", "flow-question-brace", "flow-tag"],
)
def test_flow_question_and_tag_stay_unflagged(tmp_path, label):
    """Valid flow ``?`` / ``!`` that 4.20.1 flagged and this release does not."""
    documents = {
        "flow-question": "urls: [http://example.com/?a=1, b]\n",
        "flow-question-brace": "{foo: a?}\n",
        "flow-tag": "a: [!!str, c]\n",
    }
    path = tmp_path / "ok.yaml"
    path.write_text(documents[label], encoding="utf-8")
    result = _analyze(path, "high")
    assert result.returncode == 0, (label, result.returncode, result.stdout, result.stderr)
    assert "YAML_SYNTAX_ERROR" not in (result.stdout or "")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--sweep":
        _sweep_depths(sys.argv[2])
    else:
        raise SystemExit("usage: test_yaml_loader_guards.py --sweep STYLE")
