"""Unit + canary tests for Phase 1b CiParityAnalyzer.

The adapter wraps ``hefesto.validators.ci_parity.CIParityChecker`` — the
legacy tests in ``tests/validators/test_ci_parity.py`` continue to pin
its detection semantics. These tests pin the *adapter* contract only:
ParityIssue → AnalysisIssue mapping, severity demotion for tool-install
findings, and correct target file routing.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

import time
from enum import Enum
from pathlib import Path
from unittest.mock import MagicMock, patch

from hefesto.analyzers.operational_truth import CiParityAnalyzer
from hefesto.core.analysis_models import AnalysisIssueSeverity, AnalysisIssueType
from hefesto.core.analyzer_engine import AnalyzerEngine


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


PYPROJECT_MIN = """\
[project]
name = "demo-app"
version = "0.1.0"
dependencies = ["click>=8.0.0"]
"""


WORKFLOW_MATRIX = """\
name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - run: flake8 --max-line-length=100 --extend-ignore=E203,W503 hefesto/
"""


def _project_with_workflow(tmp_path: Path) -> Path:
    _write(tmp_path / "pyproject.toml", PYPROJECT_MIN)
    _write(tmp_path / ".github" / "workflows" / "tests.yml", WORKFLOW_MATRIX)
    return tmp_path


# ---------------------------------------------------------------- Mapping


def test_ci_parity_python_version_drift_targets_workflow(tmp_path: Path) -> None:
    _project_with_workflow(tmp_path)
    # Pin local Python to a value NOT in the CI matrix
    with patch(
        "hefesto.validators.ci_parity.CIParityChecker._get_python_version",
        return_value="3.9",
    ):
        # Keep check_tool_versions + check_flake8_config quiet
        with (
            patch(
                "hefesto.validators.ci_parity.CIParityChecker.check_tool_versions",
                return_value=[],
            ),
            patch(
                "hefesto.validators.ci_parity.CIParityChecker.check_flake8_config",
                return_value=[],
            ),
        ):
            issues = CiParityAnalyzer().analyze_project(tmp_path)

    assert len(issues) == 1
    issue = issues[0]
    assert issue.issue_type == AnalysisIssueType.CI_CONFIG_DRIFT
    assert issue.severity == AnalysisIssueSeverity.MEDIUM
    assert issue.rule_id == "OT-CI-001"
    assert issue.file_path.endswith("tests.yml")
    assert "Python" in issue.message
    assert issue.metadata["parity_category"] == "Python Version"


def test_ci_parity_tool_missing_is_demoted_to_low(tmp_path: Path) -> None:
    # A workflow must exist so the adapter actually runs check_tool_versions;
    # without one the BP-8 guard short-circuits the expensive subprocess path.
    _project_with_workflow(tmp_path)
    with (
        patch(
            "hefesto.validators.ci_parity.CIParityChecker._get_tool_version",
            return_value=None,
        ),
        patch(
            "hefesto.validators.ci_parity.CIParityChecker.check_python_version",
            return_value=[],
        ),
        patch(
            "hefesto.validators.ci_parity.CIParityChecker.check_flake8_config",
            return_value=[],
        ),
    ):
        issues = CiParityAnalyzer().analyze_project(tmp_path)

    assert issues
    assert all(i.severity == AnalysisIssueSeverity.LOW for i in issues)
    assert all(i.rule_id == "OT-CI-002" for i in issues)
    assert all(i.file_path.endswith("pyproject.toml") for i in issues)


def test_ci_parity_flake8_drift_targets_local_config(tmp_path: Path) -> None:
    _project_with_workflow(tmp_path)
    # Local .flake8 that disagrees with CI's max-line-length=100
    _write(tmp_path / ".flake8", "[flake8]\nmax-line-length = 79\n")
    with (
        patch(
            "hefesto.validators.ci_parity.CIParityChecker.check_python_version",
            return_value=[],
        ),
        patch(
            "hefesto.validators.ci_parity.CIParityChecker.check_tool_versions",
            return_value=[],
        ),
    ):
        issues = CiParityAnalyzer().analyze_project(tmp_path)

    assert len(issues) >= 1
    flake = [i for i in issues if i.rule_id == "OT-CI-003"]
    assert flake
    assert all(i.severity == AnalysisIssueSeverity.HIGH for i in flake)
    assert all(i.file_path.endswith(".flake8") for i in flake)


def test_ci_parity_clean_project_no_findings(tmp_path: Path) -> None:
    _write(tmp_path / "pyproject.toml", PYPROJECT_MIN)
    # No workflow, no flake8 config → checker returns []
    assert CiParityAnalyzer().analyze_project(tmp_path) == []


def test_ci_parity_skips_tool_subprocess_without_workflow(tmp_path: Path) -> None:
    """BP-8 regression pin: check_tool_versions must NOT be called when there
    is no CI workflow to parity against. The unconditional subprocess spawn
    added ~650ms of fixed startup cost per analyze invocation."""
    _write(tmp_path / "pyproject.toml", PYPROJECT_MIN)
    # No .github/workflows/*.yml on purpose.
    with patch("hefesto.validators.ci_parity.CIParityChecker.check_tool_versions") as mock_tools:
        mock_tools.side_effect = AssertionError("subprocess must not run")
        issues = CiParityAnalyzer().analyze_project(tmp_path)

    assert issues == []
    mock_tools.assert_not_called()


def test_ci_parity_runs_tool_subprocess_with_workflow(tmp_path: Path) -> None:
    """Symmetry pin: check_tool_versions IS invoked when a workflow exists."""
    _project_with_workflow(tmp_path)
    with (
        patch(
            "hefesto.validators.ci_parity.CIParityChecker.check_tool_versions",
            return_value=[],
        ) as mock_tools,
        patch(
            "hefesto.validators.ci_parity.CIParityChecker.check_python_version",
            return_value=[],
        ),
        patch(
            "hefesto.validators.ci_parity.CIParityChecker.check_flake8_config",
            return_value=[],
        ),
    ):
        CiParityAnalyzer().analyze_project(tmp_path)
    mock_tools.assert_called_once()


def test_ci_parity_analyze_no_ci_under_fifty_milliseconds(tmp_path: Path) -> None:
    """BP-8 benchmark: on a project with nothing CI-related, the adapter must
    complete in under 50ms. Threshold is generous to avoid flakes on slow CI
    runners; the real target is under 5ms once the subprocess guard is in
    place. A regression of the guard (e.g. reverting to check_all()) would
    push this well above 50ms on any real machine."""
    _write(tmp_path / "pyproject.toml", PYPROJECT_MIN)
    analyzer = CiParityAnalyzer()
    # Warm-up call (import + Path().resolve() caching).
    analyzer.analyze_project(tmp_path)

    start = time.perf_counter()
    issues = analyzer.analyze_project(tmp_path)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert issues == []
    assert elapsed_ms < 50, f"adapter took {elapsed_ms:.1f}ms (>50ms)"


def test_ci_parity_unknown_category_fails_open(tmp_path: Path) -> None:
    """H1 pin: a ParityIssue with an unknown category maps to OT-CI-000 / LOW.

    Protects against silent breakage if CIParityChecker grows a new category
    in the future (e.g. 'Pytest Version') without updating the adapter's
    _CATEGORY_TO_RULE table. The finding still surfaces at LOW severity
    rather than being dropped.
    """
    _write(tmp_path / "pyproject.toml", PYPROJECT_MIN)

    class _Sev(Enum):
        HIGH = "HIGH"

    fake_issue = MagicMock()
    fake_issue.category = "Pytest Version"
    fake_issue.severity = _Sev.HIGH
    fake_issue.local_value = "7.4"
    fake_issue.ci_value = "8.0"
    fake_issue.message = "Pytest version mismatch"
    fake_issue.fix_suggestion = "Pin pytest to 8.0"

    with (
        patch(
            "hefesto.validators.ci_parity.CIParityChecker.check_python_version",
            return_value=[fake_issue],
        ),
        patch(
            "hefesto.validators.ci_parity.CIParityChecker.check_flake8_config",
            return_value=[],
        ),
    ):
        issues = CiParityAnalyzer().analyze_project(tmp_path)

    assert len(issues) == 1
    issue = issues[0]
    assert issue.rule_id == "OT-CI-000"
    assert issue.severity == AnalysisIssueSeverity.LOW
    assert issue.issue_type == AnalysisIssueType.CI_CONFIG_DRIFT
    assert "Pytest Version" in issue.message


def test_ci_parity_analyzer_uses_engine_hook(tmp_path: Path) -> None:
    """Canary: findings surface through AnalyzerEngine.analyze_path like any
    other project analyzer — no separate command required."""
    _project_with_workflow(tmp_path)
    _write(tmp_path / ".flake8", "[flake8]\nmax-line-length = 79\n")

    engine = AnalyzerEngine(severity_threshold="LOW")
    engine.register_project_analyzer(CiParityAnalyzer())

    with (
        patch(
            "hefesto.validators.ci_parity.CIParityChecker.check_tool_versions",
            return_value=[],
        ),
        patch(
            "hefesto.validators.ci_parity.CIParityChecker._get_python_version",
            return_value="3.12",  # matches matrix → no python drift
        ),
    ):
        report = engine.analyze_path(str(tmp_path))

    ci_issues = [
        i for i in report.get_all_issues() if i.issue_type == AnalysisIssueType.CI_CONFIG_DRIFT
    ]
    assert ci_issues
    assert all(i.engine == "internal:operational_truth" for i in ci_issues)

    # files_analyzed must still reflect only real scanned files (the workflow
    # yaml IS scanned as a YAML file by the engine, but synthetic CI findings
    # anchored to .flake8 should not inflate the count beyond the real file).
    real = [fr for fr in report.file_results if not fr.metadata.get("synthetic")]
    assert report.summary.files_analyzed == len(real)
