"""Line-level suppression: ``# hefesto: ignore[TYPE] reason`` (Python only)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from hefesto.cli.main import cli
from hefesto.core.suppressions import (
    new_suppressions_in_diff,
    parse_suppressions,
)

PICKLE_LINE = "import pickle"
EVAL_BODY = "def load(data):\n    return eval(data)\n"


def _analyze(tmp_path: Path, source: str, *args: str, name: str = "mod.py"):
    target = tmp_path / name
    target.write_text(source, encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["analyze", str(target), "--output", "json", *args],
        env={"HEFESTO_TELEMETRY": "0"},
    )
    out = result.stdout if hasattr(result, "stdout") else result.output
    start = out.index("{")
    return result, json.loads(out[start:])


def _issues(data):
    return [i for f in data["files"] for i in f["issues"]]


def _suppressed(data):
    return [i for f in data["files"] for i in f.get("suppressed_issues", [])]


# ---------------------------------------------------------------- parsing


def test_parse_valid_directive():
    (s,) = parse_suppressions("x = 1  # hefesto: ignore[PICKLE_USAGE] trusted cache\n")
    assert s.line == 1
    assert s.types == ("PICKLE_USAGE",)
    assert s.reason == "trusted cache"
    assert s.problem is None


def test_parse_multiple_types():
    (s,) = parse_suppressions("x = 1  # hefesto: ignore[EVAL_USAGE, PICKLE_USAGE] why\n")
    assert s.types == ("EVAL_USAGE", "PICKLE_USAGE")


def test_parse_missing_reason_is_malformed():
    (s,) = parse_suppressions("x = 1  # hefesto: ignore[PICKLE_USAGE]\n")
    assert s.problem and "reason" in s.problem


def test_parse_missing_type_is_malformed():
    (s,) = parse_suppressions("x = 1  # hefesto: ignore because\n")
    assert s.problem and "TYPE" in s.problem


def test_parse_ignores_strings():
    assert parse_suppressions('x = "# hefesto: ignore[PICKLE_USAGE] no"\n') == []


# ---------------------------------------------------------------- analyze


def test_high_finding_is_suppressed_with_reason(tmp_path):
    src = f"{PICKLE_LINE}  # hefesto: ignore[PICKLE_USAGE] reads our own signed cache\n"
    result, data = _analyze(tmp_path, src)
    assert not [i for i in _issues(data) if i["type"] == "PICKLE_USAGE"]
    (sup,) = [i for i in _suppressed(data) if i["type"] == "PICKLE_USAGE"]
    assert sup["suppressed"] is True
    assert sup["suppression_reason"] == "reads our own signed cache"
    assert data["summary"]["suppressed"] == 1


def test_critical_is_never_suppressed(tmp_path):
    src = "def load(data):\n    return eval(data)  # hefesto: ignore[EVAL_USAGE] trusted\n"
    result, data = _analyze(tmp_path, src)
    assert [i for i in _issues(data) if i["type"] == "EVAL_USAGE"]
    assert _suppressed(data) == []
    warnings = data["meta"]["suppression_warnings"]
    assert any("CRITICAL" in w["message"] for w in warnings)


def test_missing_reason_suppresses_nothing(tmp_path):
    src = f"{PICKLE_LINE}  # hefesto: ignore[PICKLE_USAGE]\n"
    result, data = _analyze(tmp_path, src)
    assert [i for i in _issues(data) if i["type"] == "PICKLE_USAGE"]
    assert _suppressed(data) == []
    assert data["meta"]["suppression_warnings"]


def test_type_mismatch_suppresses_nothing(tmp_path):
    src = f"{PICKLE_LINE}  # hefesto: ignore[EVAL_USAGE] wrong type\n"
    result, data = _analyze(tmp_path, src)
    assert [i for i in _issues(data) if i["type"] == "PICKLE_USAGE"]
    assert _suppressed(data) == []
    assert any("no EVAL_USAGE" in w["message"] for w in data["meta"]["suppression_warnings"])


def test_fail_on_ignores_suppressed(tmp_path):
    src = f"{PICKLE_LINE}  # hefesto: ignore[PICKLE_USAGE] trusted cache\n"
    result, _ = _analyze(tmp_path, src, "--fail-on", "HIGH")
    assert result.exit_code == 0
    result, _ = _analyze(tmp_path, PICKLE_LINE + "\n", "--fail-on", "HIGH")
    assert result.exit_code == 1


def test_fail_on_still_fails_on_critical_with_directive(tmp_path):
    src = "def load(data):\n    return eval(data)  # hefesto: ignore[EVAL_USAGE] trusted\n"
    result, _ = _analyze(tmp_path, src, "--fail-on", "CRITICAL")
    assert result.exit_code == 1


def test_text_output_reports_count(tmp_path):
    target = tmp_path / "mod.py"
    target.write_text(f"{PICKLE_LINE}  # hefesto: ignore[PICKLE_USAGE] trusted\n")
    result = CliRunner().invoke(cli, ["analyze", str(target)], env={"HEFESTO_TELEMETRY": "0"})
    assert "Suppressed: 1" in result.output


def test_non_python_files_are_not_suppressed(tmp_path):
    target = tmp_path / "run.sh"
    target.write_text("eval $1  # hefesto: ignore[COMMAND_INJECTION] x\n")
    result = CliRunner().invoke(
        cli, ["analyze", str(target), "--output", "json"], env={"HEFESTO_TELEMETRY": "0"}
    )
    out = result.output
    data = json.loads(out[out.index("{") :])
    assert _suppressed(data) == []


def test_sarif_has_in_source_suppression(tmp_path):
    target = tmp_path / "mod.py"
    target.write_text(f"{PICKLE_LINE}  # hefesto: ignore[PICKLE_USAGE] trusted cache\n")
    sarif = tmp_path / "out.sarif"
    CliRunner().invoke(
        cli,
        ["analyze", str(target), "--sarif-file", str(sarif)],
        env={"HEFESTO_TELEMETRY": "0"},
    )
    log = json.loads(sarif.read_text())
    results = [r for r in log["runs"][0]["results"] if r["ruleId"].startswith("PICKLE")]
    assert results
    (sup,) = results[0]["suppressions"]
    assert sup == {"kind": "inSource", "justification": "trusted cache"}


# ---------------------------------------------------------------- new suppressions

DIFF = """diff --git a/pkg/a.py b/pkg/a.py
--- a/pkg/a.py
+++ b/pkg/a.py
@@ -1,2 +1,3 @@
 import os
+import pickle  # hefesto: ignore[PICKLE_USAGE] signed cache
 x = 1  # hefesto: ignore[EVAL_USAGE] old one
diff --git a/run.sh b/run.sh
--- a/run.sh
+++ b/run.sh
@@ -1 +1,2 @@
 echo
+eval $1  # hefesto: ignore[COMMAND_INJECTION] x
"""


def test_new_suppressions_in_diff_lists_only_added_python_lines():
    (new,) = new_suppressions_in_diff(DIFF)
    assert new.file == "pkg/a.py"
    assert new.line == 2
    assert new.types == ("PICKLE_USAGE",)
    assert new.reason == "signed cache"


def test_new_suppressions_skip_text_inside_strings(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "a.py").write_text(
        "import os\nimport pickle  # hefesto: ignore[PICKLE_USAGE] signed cache\n"
        "x = 1  # hefesto: ignore[EVAL_USAGE] old one\n"
    )
    assert len(new_suppressions_in_diff(DIFF, tmp_path)) == 1
    (pkg / "a.py").write_text('import os\nS = """# hefesto: ignore[PICKLE_USAGE] signed cache"""\n')
    assert new_suppressions_in_diff(DIFF, tmp_path) == []


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.py").write_text("x = 1\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "base")
    base = _git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / "a.py").write_text(
        "x = 1\nimport pickle  # hefesto: ignore[PICKLE_USAGE] signed cache\n"
    )
    _git(tmp_path, "commit", "-qam", "head")
    return tmp_path, base


def test_pr_review_lists_new_suppressions(repo):
    path, base = repo
    result = CliRunner().invoke(
        cli,
        ["pr-review", "--project-root", str(path), "--base", base, "--head", "HEAD"],
        env={"HEFESTO_TELEMETRY": "0"},
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output[result.output.index("{") :])
    (new,) = data["new_suppressions"]
    assert new["file"] == "a.py" and new["reason"] == "signed cache"
    assert not [f for f in data["findings"] if f.get("type") == "PICKLE_USAGE"]


def test_pr_review_fail_on_new_suppressions(repo):
    path, base = repo
    args = ["pr-review", "--project-root", str(path), "--base", base, "--head", "HEAD"]
    result = CliRunner().invoke(
        cli, [*args, "--fail-on-new-suppressions"], env={"HEFESTO_TELEMETRY": "0"}
    )
    assert result.exit_code == 1


def test_dogfood_script_lists_and_can_fail(repo):
    path, base = repo
    script = Path(__file__).resolve().parents[1] / "scripts" / "dogfood_changed.py"
    run = [sys.executable, str(script), "--repo", str(path), "--base", base, "--head", "HEAD"]
    env = {"HEFESTO_TELEMETRY": "0", "PATH": "/usr/bin:/bin"}
    ok = subprocess.run(run, capture_output=True, text=True, env=env)
    assert "New line suppressions (1)" in ok.stdout
    assert "a.py:2 [PICKLE_USAGE] signed cache" in ok.stdout
    failed = subprocess.run(
        [*run, "--fail-on-new-suppressions"], capture_output=True, text=True, env=env
    )
    assert failed.returncode == 1
