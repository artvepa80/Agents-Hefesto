"""Tests for ``AnalyzerEngine.analyze_files`` — Phase 2 entry point.

``analyze_files`` is the scoped counterpart to ``analyze_path``: instead
of globbing a root directory, it analyses an explicit list of files
provided by the caller. This is the hook that Phase 2 PR review uses
to run the pipeline against the changed files returned by a git diff,
without picking up untouched siblings.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from hefesto.analyzers.operational_truth import ImportsVsDepsAnalyzer
from hefesto.core.analysis_models import AnalysisIssue, AnalysisIssueType
from hefesto.core.analyzer_engine import AnalyzerEngine


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class _FakeFileAnalyzer:
    """Minimal file analyzer that counts how many times it was invoked."""

    def __init__(self) -> None:
        self.calls: List[str] = []

    def analyze(self, tree, file_path: str, code: str) -> List[AnalysisIssue]:
        self.calls.append(file_path)
        return []


def test_analyze_files_empty_list_returns_empty_report(tmp_path: Path) -> None:
    engine = AnalyzerEngine(severity_threshold="LOW")
    report = engine.analyze_files([])
    assert report.summary.files_analyzed == 0
    assert report.file_results == []


def test_analyze_files_skips_nonexistent_paths(tmp_path: Path) -> None:
    """Phantom paths from a diff that no longer exist on disk must be
    silently skipped — they are not a parser error."""
    engine = AnalyzerEngine(severity_threshold="LOW")
    report = engine.analyze_files([str(tmp_path / "does_not_exist.py")])
    assert report.summary.files_analyzed == 0


def test_analyze_files_runs_file_analyzers_only_on_given_paths(tmp_path: Path) -> None:
    """File analyzers must see exactly the paths in the list — no glob
    discovery, no bleed from sibling files."""
    _write(tmp_path / "touched.py", "def f():\n    return 1\n")
    _write(tmp_path / "untouched.py", "def g():\n    return 2\n")

    engine = AnalyzerEngine(severity_threshold="LOW")
    fake = _FakeFileAnalyzer()
    engine.register_analyzer(fake)

    engine.analyze_files([str(tmp_path / "touched.py")])

    assert len(fake.calls) == 1
    assert fake.calls[0].endswith("touched.py")


def test_analyze_files_runs_project_analyzers_once(tmp_path: Path) -> None:
    """Project analyzers still run once per ``analyze_files`` invocation,
    keyed to ``project_root``. This is essential for PR review so that
    cross-file findings remain available before filtering."""
    _write(
        tmp_path / "pyproject.toml",
        '[project]\nname = "demo"\nversion = "0.1.0"\n' 'dependencies = ["pydantic>=2.0"]\n',
    )
    _write(tmp_path / "demo" / "__init__.py", "")
    _write(tmp_path / "demo" / "main.py", "import click\n")  # undeclared dep

    engine = AnalyzerEngine(severity_threshold="LOW")
    engine.register_project_analyzer(ImportsVsDepsAnalyzer())

    report = engine.analyze_files(
        [str(tmp_path / "demo" / "main.py")],
        project_root=str(tmp_path),
    )

    ot_issues = [
        i
        for i in report.get_all_issues()
        if i.issue_type == AnalysisIssueType.UNDECLARED_DEPENDENCY
    ]
    assert ot_issues, "project analyzer must fire against project_root"


def test_analyze_files_excludes_synthetic_from_files_analyzed(tmp_path: Path) -> None:
    """Same invariant as analyze_path — synthetic project-level results
    do not inflate the ``files_analyzed`` count."""
    _write(
        tmp_path / "pyproject.toml",
        '[project]\nname = "demo"\nversion = "0.1.0"\n' 'dependencies = ["pydantic>=2.0"]\n',
    )
    _write(tmp_path / "demo" / "__init__.py", "")
    _write(tmp_path / "demo" / "main.py", "import click\n")

    engine = AnalyzerEngine(severity_threshold="LOW")
    engine.register_project_analyzer(ImportsVsDepsAnalyzer())

    report = engine.analyze_files(
        [str(tmp_path / "demo" / "main.py")],
        project_root=str(tmp_path),
    )

    real = [fr for fr in report.file_results if not fr.metadata.get("synthetic")]
    assert report.summary.files_analyzed == len(real)


def test_analyze_files_mixed_languages(tmp_path: Path) -> None:
    """A mix of Python and DevOps files routes to the right analyzer
    branches without requiring a single file-extension filter.

    Both files must be counted as analyzed (strict ``== 2``) — a weaker
    ``>= 1`` assertion would silently pass even if the Dockerfile
    dispatch path regressed.
    """
    _write(tmp_path / "app.py", "def f():\n    return 1\n")
    _write(
        tmp_path / "Dockerfile",
        "FROM python:3.12-slim\nRUN echo hi\n",
    )

    engine = AnalyzerEngine(severity_threshold="LOW")
    report = engine.analyze_files([str(tmp_path / "app.py"), str(tmp_path / "Dockerfile")])
    assert report.summary.files_analyzed == 2


def test_analyze_files_without_project_root_warns(tmp_path: Path, caplog) -> None:
    """G1/G5: no silent fallback when project analyzers are registered
    but project_root is omitted. The engine must default to CWD and
    emit a warning so the caller realises project analyzers are being
    pointed at the wrong root."""
    import logging

    _write(tmp_path / "demo.py", "x = 1\n")

    engine = AnalyzerEngine(severity_threshold="LOW")
    engine.register_project_analyzer(ImportsVsDepsAnalyzer())

    with caplog.at_level(logging.WARNING, logger="hefesto.core.analyzer_engine"):
        engine.analyze_files([str(tmp_path / "demo.py")])

    assert any(
        "project_root" in rec.message and "CWD" in rec.message for rec in caplog.records
    ), caplog.text
