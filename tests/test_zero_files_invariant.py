"""A run that analyzes no files must never look like a clean pass.

`hefesto analyze` used to print "No issues found!" and exit 0 when nothing was
analyzed (an empty directory, only unsupported files, or everything excluded),
even with `--fail-on`. A CI gate then passes without having checked anything.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from hefesto.core.analysis_models import AnalysisReport, AnalysisSummary
from hefesto.reports.text_reporter import TextReporter

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(*args):
    env = dict(os.environ, HEFESTO_TELEMETRY="0")
    return subprocess.run(
        [sys.executable, "-m", "hefesto.cli.main", "analyze", *args, "--no-config"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
    )


def _no_supported_files(tmp_path):
    root = tmp_path / "assets"
    root.mkdir()
    (root / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    return root


def _only_excluded_files(tmp_path):
    root = tmp_path / "project"
    (root / "build").mkdir(parents=True)
    (root / "build" / "app.py").write_text("import os\n")
    return root


def _clean_project(tmp_path):
    root = tmp_path / "clean"
    root.mkdir()
    (root / "ok.py").write_text('def hello():\n    return "world"\n')
    return root


class TestZeroFilesText:
    def test_no_success_message_and_warning_on_stderr(self, tmp_path):
        root = _no_supported_files(tmp_path)
        result = _run(str(root))
        assert result.returncode == 0  # no --fail-on: findings never set the exit code
        assert "Files analyzed: 0" in result.stdout
        assert "No issues found" not in result.stdout
        assert "✅" not in result.stdout
        assert "No files were analyzed" in result.stdout
        assert "no files were analyzed" in result.stderr
        assert str(root) in result.stderr

    def test_fail_on_exits_non_zero(self, tmp_path):
        result = _run(str(_no_supported_files(tmp_path)), "--fail-on", "HIGH")
        assert result.returncode == 1
        assert "Gate failure: no files were analyzed" in result.stdout
        assert "Gate passed" not in result.stdout

    def test_fail_on_exits_non_zero_when_everything_is_excluded(self, tmp_path):
        result = _run(str(_only_excluded_files(tmp_path)), "--fail-on", "CRITICAL")
        assert result.returncode == 1
        assert "Files analyzed: 0" in result.stdout

    def test_quiet_still_warns_and_fails(self, tmp_path):
        result = _run(str(_no_supported_files(tmp_path)), "--fail-on", "HIGH", "--quiet")
        assert result.returncode == 1
        assert "no files were analyzed" in result.stderr

    def test_user_exclude_removing_every_file(self, tmp_path):
        root = _clean_project(tmp_path)
        result = _run(str(root), "--exclude", "ok.py", "--fail-on", "LOW")
        assert result.returncode == 1


class TestZeroFilesJson:
    def test_json_stdout_stays_valid_and_gate_fails(self, tmp_path):
        result = _run(str(_no_supported_files(tmp_path)), "--output", "json", "--fail-on", "HIGH")
        assert result.returncode == 1
        data = json.loads(result.stdout)
        assert data["summary"]["files_analyzed"] == 0
        assert "no files were analyzed" in result.stderr


class TestPartialAndRegression:
    def test_one_empty_path_among_others_only_warns(self, tmp_path):
        empty = _no_supported_files(tmp_path)
        clean = _clean_project(tmp_path)
        result = _run(str(empty), str(clean), "--fail-on", "HIGH")
        assert result.returncode == 0
        assert "Gate passed" in result.stdout
        assert str(empty) in result.stderr
        assert str(clean) not in result.stderr

    def test_clean_project_still_reports_success(self, tmp_path):
        result = _run(str(_clean_project(tmp_path)), "--fail-on", "HIGH")
        assert result.returncode == 0
        assert "No issues found" in result.stdout
        assert "no files were analyzed" not in result.stderr


def _summary(files):
    return AnalysisSummary(
        files_analyzed=files,
        total_issues=0,
        critical_issues=0,
        high_issues=0,
        medium_issues=0,
        low_issues=0,
        total_loc=0,
        duration_seconds=0.0,
    )


class TestTextReporterFooter:
    def test_footer_for_zero_files(self):
        footer = TextReporter()._format_footer(AnalysisReport(summary=_summary(0), file_results=[]))
        assert "No files were analyzed" in footer
        assert "No issues found" not in footer and "✅" not in footer

    def test_footer_for_clean_files(self):
        footer = TextReporter()._format_footer(AnalysisReport(summary=_summary(3), file_results=[]))
        assert "✅ No issues found!" in footer
