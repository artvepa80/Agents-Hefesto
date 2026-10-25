"""Analyzing user code must not leak Python warnings to stderr."""

from __future__ import annotations

import warnings
from pathlib import Path

from hefesto.analyzers.operational_truth import ImportsVsDepsAnalyzer
from hefesto.core.analysis_models import AnalysisReport, AnalysisSummary

PYPROJECT_MIN = """\
[project]
name = "demo"
version = "0.0.1"
dependencies = ["requests"]
"""


def test_imports_vs_deps_does_not_emit_syntaxwarning(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(PYPROJECT_MIN, encoding="utf-8")
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    # A non-raw string with an invalid escape sequence ("\d").
    (pkg / "bad_escape.py").write_text('"""Matches \\d digits."""\nimport os\n', encoding="utf-8")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        ImportsVsDepsAnalyzer().analyze_project(tmp_path)

    assert not [w for w in caught if issubclass(w.category, SyntaxWarning)]


def _summary() -> AnalysisSummary:
    return AnalysisSummary(
        files_analyzed=0,
        total_issues=0,
        critical_issues=0,
        high_issues=0,
        medium_issues=0,
        low_issues=0,
        total_loc=0,
        duration_seconds=0.0,
    )


def test_analysis_report_timestamp_has_no_utcnow_deprecation() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        report = AnalysisReport(summary=_summary(), file_results=[])

    assert not [w for w in caught if issubclass(w.category, DeprecationWarning)]
    # Serialized format is unchanged: naive UTC, no offset suffix.
    assert report.timestamp.tzinfo is None
    assert "+" not in report.to_dict()["timestamp"]
