"""A run that analyzes no files must never look like a clean pass.

`hefesto analyze` used to print "No issues found!" and exit 0 when nothing was
analyzed (an empty directory, only unsupported files, or everything excluded),
even with `--fail-on`. A CI gate then passes without having checked anything.
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from hefesto.cli.main import _run_analysis_loop
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


class TestAllowNoFiles:
    """--allow-no-files: an intentionally empty run keeps exit 0; only the exit code changes."""

    def test_flag_keeps_exit_zero_under_fail_on(self, tmp_path):
        root = _no_supported_files(tmp_path)
        result = _run(str(root), "--fail-on", "HIGH", "--allow-no-files")
        assert result.returncode == 0
        assert "Gate failure" not in result.stdout
        assert "Gate skipped: no files were analyzed (--allow-no-files)" in result.stdout
        assert "Files analyzed: 0" in result.stdout
        # The warning is still printed: allowed, but never silent.
        assert "No files were analyzed" in result.stdout
        assert "no files were analyzed" in result.stderr
        assert str(root) in result.stderr

    def test_flag_with_quiet_still_warns(self, tmp_path):
        result = _run(
            str(_no_supported_files(tmp_path)), "--fail-on", "HIGH", "--quiet", "--allow-no-files"
        )
        assert result.returncode == 0
        assert "no files were analyzed" in result.stderr

    def test_flag_with_json_keeps_stdout_valid(self, tmp_path):
        result = _run(
            str(_only_excluded_files(tmp_path)),
            "--output",
            "json",
            "--fail-on",
            "LOW",
            "--allow-no-files",
        )
        assert result.returncode == 0
        assert json.loads(result.stdout)["summary"]["files_analyzed"] == 0
        assert "no files were analyzed" in result.stderr
        assert "Gate skipped" in result.stderr

    def test_flag_does_not_hide_findings(self, tmp_path):
        root = tmp_path / "bad"
        root.mkdir()
        (root / "x.py").write_text("password = 'hunter2hunter2'\neval(input())\n")
        without = _run(str(root), "--fail-on", "LOW")
        with_flag = _run(str(root), "--fail-on", "LOW", "--allow-no-files")
        assert without.returncode == 1
        assert with_flag.returncode == without.returncode

    def test_config_key_is_rejected(self, tmp_path):
        """--allow-no-files is a CLI flag only: .hefesto.yaml cannot set it.

        The key is rejected as unknown (exit 2), not silently ignored, so a
        config that tries to turn the gate off never passes by accident.
        """
        root = _no_supported_files(tmp_path)
        # Outside the target: a .hefesto.yaml inside it would itself be analyzed.
        config = tmp_path / "hefesto.yaml"
        config.write_text("fail_on: HIGH\nallow_no_files: true\n")
        env = dict(os.environ, HEFESTO_TELEMETRY="0")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "hefesto.cli.main",
                "analyze",
                str(root),
                "--config",
                str(config),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            env=env,
        )
        assert result.returncode == 2, result.stdout + result.stderr
        assert "allow_no_files" in result.stderr
        assert "Gate skipped" not in result.stdout

    def test_config_key_not_supported(self):
        from hefesto.config.project_config import SUPPORTED_KEYS, ConfigError, validate_config

        assert "allow_no_files" not in SUPPORTED_KEYS
        with pytest.raises(ConfigError):
            validate_config({"allow_no_files": True})


class _EmptyReport:
    file_results: list = []

    class summary:
        total_loc = 0
        duration_seconds = 0.0


class _FakeEngine:
    """Engine whose paths analyze nothing; each path skips some vendored files."""

    def __init__(self, skipped_per_path):
        self._skipped = list(skipped_per_path)
        self._count = 0

    def analyze_path(self, path, exclude_patterns):
        self._count += self._skipped.pop(0)
        return _EmptyReport()

    def _build_meta(self):
        if not self._count:
            return {}
        return {"vendored_skipped": {"count": self._count, "examples": []}}


class TestVendoredHint:
    """The zero-files warning names the vendored skip count and --include-vendored."""

    def test_hint_names_count_and_flag(self, capsys):
        _run_analysis_loop(_FakeEngine([3]), ["site"], [])
        err = capsys.readouterr().err
        assert "no files were analyzed in site" in err
        assert "3 files skipped as vendored (use --include-vendored)" in err

    def test_hint_singular(self, capsys):
        _run_analysis_loop(_FakeEngine([1]), ["site"], [])
        assert "1 file skipped as vendored (use --include-vendored)" in capsys.readouterr().err

    def test_no_hint_without_vendored_skips(self, capsys):
        _run_analysis_loop(_FakeEngine([0]), ["site"], [])
        err = capsys.readouterr().err
        assert "no files were analyzed in site" in err
        assert "vendored" not in err

    def test_hint_counts_only_the_empty_path(self, capsys):
        _run_analysis_loop(_FakeEngine([2, 5]), ["a", "b"], [])
        lines = [ln for ln in capsys.readouterr().err.splitlines() if ln.startswith("Warning")]
        assert "in a " in lines[0] and "2 files skipped as vendored" in lines[0]
        assert "in b " in lines[1] and "5 files skipped as vendored" in lines[1]

    def test_engine_without_meta(self, capsys):
        class _Bare:
            def analyze_path(self, path, exclude_patterns):
                return _EmptyReport()

        _run_analysis_loop(_Bare(), ["site"], [])
        err = capsys.readouterr().err
        assert "no files were analyzed in site" in err
        assert "vendored" not in err


def _has_vendored_skip():
    from hefesto.core import analyzer_engine

    return hasattr(analyzer_engine, "is_vendored_js")


@pytest.mark.skipif(
    not _has_vendored_skip(),
    reason="vendored JS skip (PR #91) not on this branch yet; runs once both PRs are merged",
)
class TestVendoredHintIntegration:
    def test_only_vendored_js_names_the_count(self, tmp_path):
        root = tmp_path / "site"
        (root / "vendor").mkdir(parents=True)
        (root / "vendor" / "jquery.js").write_text("var a = 1;\n")
        (root / "app.min.js").write_text("var b=2;\n")
        result = _run(str(root), "--fail-on", "HIGH")
        assert result.returncode == 1
        assert "2 files skipped as vendored (use --include-vendored)" in result.stderr
        assert str(root) in result.stderr

    @pytest.mark.skipif(
        importlib.util.find_spec("tree_sitter_language_pack") is None,
        reason="analyzing JavaScript needs the [multilang] extra (tree_sitter_language_pack)",
    )
    def test_include_vendored_analyzes_them(self, tmp_path):
        root = tmp_path / "site"
        (root / "vendor").mkdir(parents=True)
        (root / "vendor" / "jquery.js").write_text("var a = 1;\n")
        result = _run(str(root), "--fail-on", "HIGH", "--include-vendored")
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
