"""Tests for the opt-in ``hefesto analyze --format-check`` flag (Black drift).

Covers:
1. Flag off (default): no FORMAT_DRIFT findings, exit codes unchanged.
2. Flag on: one LOW FORMAT_DRIFT finding per misformatted file, with diff.
3. --fail-on / --exclude-types semantics apply to FORMAT_DRIFT.
4. Black missing: one-line warning on stderr, no crash, exit 0.
5. Black config from pyproject.toml is respected (line-length, excludes).

Copyright (c) 2026 Narapa LLC, Miami, Florida
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from hefesto.analyzers import format_drift
from hefesto.analyzers.format_drift import (
    BLACK_MISSING_WARNING,
    FormatDriftChecker,
    _first_changed_line,
    is_black_available,
    run_format_check,
)
from hefesto.cli.main import cli
from hefesto.core.analysis_models import FileAnalysisResult

MISFORMATTED = 'def f( a,b ):\n    return {"x":a,  "y":b}\n'
WELL_FORMATTED = 'def g(a, b):\n    return {"x": a, "y": b}\n'


def _project(tmp_path: Path) -> Path:
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "bad.py").write_text(MISFORMATTED)
    (proj / "good.py").write_text(WELL_FORMATTED)
    return proj


def _run(args, timeout=120):
    env = dict(os.environ, HEFESTO_TELEMETRY="0")
    return subprocess.run(
        [sys.executable, "-m", "hefesto.cli.main", "analyze", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def _format_issues(stdout: str):
    data = json.loads(stdout)
    return [i for f in data["files"] for i in f["issues"] if i["type"] == "FORMAT_DRIFT"]


# ---------------------------------------------------------------------------
# 1. Flag off — default behavior unchanged
# ---------------------------------------------------------------------------


def test_flag_off_reports_no_format_findings(tmp_path):
    proj = _project(tmp_path)
    result = _run([str(proj), "--output", "json", "--severity", "LOW"])
    assert result.returncode == 0, result.stderr
    assert _format_issues(result.stdout) == []
    assert "format-check" not in result.stderr


def test_flag_off_fail_on_low_does_not_trip_on_formatting(tmp_path):
    proj = _project(tmp_path)
    result = _run([str(proj), "--fail-on", "LOW", "--quiet"])
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------------------
# 2. Flag on — findings
# ---------------------------------------------------------------------------


def test_flag_on_reports_one_low_finding_per_misformatted_file(tmp_path):
    pytest.importorskip("black")
    proj = _project(tmp_path)
    # Default --severity MEDIUM: opt-in format findings are still shown.
    result = _run([str(proj), "--format-check", "--output", "json"])
    assert result.returncode == 0, result.stderr

    issues = _format_issues(result.stdout)
    assert len(issues) == 1
    issue = issues[0]
    assert issue["file"].endswith("bad.py")
    assert issue["severity"] == "LOW"
    assert issue["engine"] == "internal:format_drift"
    assert issue["line"] == 1
    assert "Black would reformat" in issue["message"]
    assert "+def f(a, b):" in issue["code_snippet"]
    assert issue["metadata"]["formatter"] == "black"
    assert issue["metadata"]["lines_added"] == 2
    assert issue["metadata"]["lines_removed"] == 2

    data = json.loads(result.stdout)
    assert data["summary"]["low"] >= 1


def test_flag_on_text_output_shows_summary_line(tmp_path):
    pytest.importorskip("black")
    proj = _project(tmp_path)
    result = _run([str(proj), "--format-check"])
    assert result.returncode == 0, result.stderr
    assert "FORMAT_DRIFT" in result.stdout
    assert "2 file(s) checked, 1 would be reformatted" in result.stdout


def test_flag_on_does_not_modify_files(tmp_path):
    pytest.importorskip("black")
    proj = _project(tmp_path)
    _run([str(proj), "--format-check", "--quiet"])
    assert (proj / "bad.py").read_text() == MISFORMATTED


# ---------------------------------------------------------------------------
# 3. Gate semantics
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "extra, expected",
    [
        (["--fail-on", "LOW"], 1),
        (["--fail-on", "MEDIUM"], 0),
        (["--fail-on", "LOW", "--exclude-types", "FORMAT_DRIFT"], 0),
        ([], 0),
    ],
)
def test_flag_on_respects_fail_on_and_exclude_types(tmp_path, extra, expected):
    pytest.importorskip("black")
    proj = _project(tmp_path)
    result = _run([str(proj), "--format-check", "--quiet", *extra])
    assert result.returncode == expected, result.stdout + result.stderr


# ---------------------------------------------------------------------------
# 4. Black missing
# ---------------------------------------------------------------------------


def test_black_missing_warns_and_continues(tmp_path, monkeypatch):
    proj = _project(tmp_path)
    monkeypatch.setenv("HEFESTO_TELEMETRY", "0")
    # A None entry in sys.modules makes find_spec() return None and import fail.
    monkeypatch.setitem(sys.modules, "black", None)
    assert is_black_available() is False

    result = CliRunner().invoke(cli, ["analyze", str(proj), "--format-check", "--fail-on", "LOW"])
    assert result.exit_code == 0, result.output
    assert BLACK_MISSING_WARNING in result.output
    assert BLACK_MISSING_WARNING.count("\n") == 0
    assert 'pip install "hefesto-ai[format]"' in BLACK_MISSING_WARNING
    assert "FORMAT_DRIFT" not in result.output


def test_black_missing_flag_off_prints_nothing(tmp_path, monkeypatch):
    proj = _project(tmp_path)
    monkeypatch.setenv("HEFESTO_TELEMETRY", "0")
    monkeypatch.setitem(sys.modules, "black", None)
    result = CliRunner().invoke(cli, ["analyze", str(proj)])
    assert result.exit_code == 0, result.output
    assert "format-check" not in result.output


def test_checker_error_is_reported_not_raised(tmp_path, monkeypatch):
    proj = _project(tmp_path)
    monkeypatch.setenv("HEFESTO_TELEMETRY", "0")
    monkeypatch.setattr(format_drift, "is_black_available", lambda: True)

    def boom(*_args, **_kwargs):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(format_drift, "run_format_check", boom)
    result = CliRunner().invoke(cli, ["analyze", str(proj), "--format-check"])
    assert result.exit_code == 0, result.output
    assert "--format-check failed and was skipped: kaboom" in result.output


# ---------------------------------------------------------------------------
# 5. Checker unit tests (Black config, edge cases)
# ---------------------------------------------------------------------------


def _result(path: Path) -> FileAnalysisResult:
    return FileAnalysisResult(
        file_path=str(path), issues=[], lines_of_code=1, analysis_duration_ms=0.0, language="python"
    )


LONG_LINE = "x = [" + ", ".join(f'"item{i:02d}"' for i in range(11)) + "]\n"  # 114 chars


def test_respects_pyproject_line_length(tmp_path):
    pytest.importorskip("black")
    assert 100 < len(LONG_LINE.rstrip()) < 120
    # Separate projects: black caches parsed pyproject.toml files per path.
    results = {}
    for line_length in (120, 88):
        proj = tmp_path / f"ll{line_length}"
        proj.mkdir()
        (proj / "pyproject.toml").write_text(f"[tool.black]\nline-length = {line_length}\n")
        target = proj / "mod.py"
        target.write_text(LONG_LINE)
        results[line_length] = run_format_check([_result(target)])

    issues_120, stats_120 = results[120]
    assert issues_120 == []
    assert stats_120.checked == 1

    issues_88, stats_88 = results[88]
    assert len(issues_88) == 1
    assert stats_88.drifted == 1


def test_respects_extend_exclude(tmp_path):
    pytest.importorskip("black")
    (tmp_path / "pyproject.toml").write_text("[tool.black]\nextend-exclude = '^/legacy/'\n")
    (tmp_path / "legacy").mkdir()
    legacy = tmp_path / "legacy" / "old.py"
    legacy.write_text(MISFORMATTED)
    fresh = tmp_path / "new.py"
    fresh.write_text(MISFORMATTED)

    issues, stats = run_format_check([_result(legacy), _result(fresh)])
    assert [i.file_path for i in issues] == [str(fresh)]
    assert stats.skipped == 1


def test_required_version_mismatch_warns(tmp_path):
    pytest.importorskip("black")
    (tmp_path / "pyproject.toml").write_text('[tool.black]\nrequired-version = "1.0.0"\n')
    target = tmp_path / "ok.py"
    target.write_text(WELL_FORMATTED)

    _, stats = run_format_check([_result(target)])
    assert any("required-version 1.0.0" in w for w in stats.warnings)


def test_invalid_syntax_counts_as_error_not_crash(tmp_path):
    pytest.importorskip("black")
    target = tmp_path / "broken.py"
    target.write_text("def broken(:\n    pass\n")
    issues, stats = run_format_check([_result(target)])
    assert issues == []
    assert stats.errors == 1


def test_uses_source_cache_and_skips_non_python(tmp_path):
    pytest.importorskip("black")
    target = tmp_path / "cached.py"
    target.write_text(WELL_FORMATTED)  # on disk: fine
    yaml_result = FileAnalysisResult(
        file_path=str(tmp_path / "x.yaml"),
        issues=[],
        lines_of_code=1,
        analysis_duration_ms=0.0,
        language="yaml",
    )
    py_result = _result(target)
    issues, stats = run_format_check(
        [py_result, yaml_result], source_cache={str(target): MISFORMATTED}
    )
    assert len(issues) == 1
    assert py_result.issues == issues
    assert yaml_result.issues == []
    assert stats.checked == 1


def test_diff_snippet_is_truncated(tmp_path, monkeypatch):
    pytest.importorskip("black")
    monkeypatch.setattr(format_drift, "MAX_DIFF_LINES", 5)
    target = tmp_path / "many.py"
    target.write_text("".join(f"v{i}=  {i}\n" for i in range(30)))
    issue = FormatDriftChecker().check_file(str(target))
    assert issue is not None
    assert issue.metadata["diff_truncated"] is True
    assert "more diff lines" in issue.code_snippet


def test_first_changed_line_skips_context():
    diff = [
        "--- a\n",
        "+++ b\n",
        "@@ -10,7 +10,7 @@\n",
        " ctx\n",
        " ctx\n",
        " ctx\n",
        "-old\n",
        "+new\n",
    ]
    assert _first_changed_line(diff) == 13
    assert _first_changed_line([]) == 1
