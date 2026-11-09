"""The zero-files warning names a missing parser and the fix (#160), and
scripts/verify_readme.py compiles under ``-W error`` (#157)."""

import subprocess
import sys
from pathlib import Path

from hefesto.cli.main import _run_analysis_loop
from hefesto.core.analysis_models import AnalysisReport, AnalysisSummary

REPO_ROOT = Path(__file__).resolve().parents[1]


class _Engine:
    def __init__(self, failures):
        self._failures = failures
        self._parser_failures = []
        self._not_analyzed = []

    def analyze_path(self, path, exclude):
        self._parser_failures.extend(self._failures)
        summary = AnalysisSummary(
            files_analyzed=0,
            total_issues=0,
            critical_issues=0,
            high_issues=0,
            medium_issues=0,
            low_issues=0,
            total_loc=0,
            duration_seconds=0.0,
        )
        return AnalysisReport(summary=summary, file_results=[])


def _fail(lang, category="parser_unavailable"):
    return {"path": f"a.{lang}", "language": lang, "category": category, "exception": "X"}


def test_missing_parser_hint_names_language_and_extra(capsys):
    _run_analysis_loop(_Engine([_fail("typescript"), _fail("javascript")]), ["a.ts"], [])
    err = capsys.readouterr().err
    assert "no files were analyzed in a.ts" in err
    assert "parser unavailable for javascript, typescript" in err
    assert 'pip install "hefesto-ai[multilang]"' in err


def test_parse_error_alone_does_not_suggest_multilang(capsys):
    _run_analysis_loop(_Engine([_fail("python", "parse_error")]), ["a.py"], [])
    err = capsys.readouterr().err
    assert "no files were analyzed" in err
    assert "multilang" not in err


def test_no_parser_failures_keeps_plain_warning(capsys):
    _run_analysis_loop(_Engine([]), ["site"], [])
    err = capsys.readouterr().err
    assert "no files were analyzed" in err
    assert "multilang" not in err


def test_verify_readme_compiles_with_warnings_as_errors():
    src = REPO_ROOT / "scripts" / "verify_readme.py"
    proc = subprocess.run(
        [sys.executable, "-W", "error", "-c", f"compile(open({str(src)!r}).read(), 'v', 'exec')"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
