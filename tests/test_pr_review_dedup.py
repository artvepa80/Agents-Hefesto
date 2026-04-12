"""Tests for ``hefesto/pr_review/dedup.py`` — stable dedup keys.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)
from hefesto.pr_review import compute_dedup_key


def _issue(
    *,
    line: int = 10,
    issue_type: AnalysisIssueType = AnalysisIssueType.SQL_INJECTION_RISK,
    message: str = "Potential SQL injection via string concatenation",
    file_path: str = "/abs/tmp/project/hefesto/foo.py",
) -> AnalysisIssue:
    return AnalysisIssue(
        file_path=file_path,
        line=line,
        column=0,
        issue_type=issue_type,
        severity=AnalysisIssueSeverity.HIGH,
        message=message,
    )


def test_same_inputs_produce_same_key() -> None:
    i1 = _issue()
    i2 = _issue()
    assert compute_dedup_key(i1, relative_path="hefesto/foo.py") == compute_dedup_key(
        i2, relative_path="hefesto/foo.py"
    )


def test_key_changes_with_issue_type() -> None:
    i = _issue()
    k1 = compute_dedup_key(i, relative_path="hefesto/foo.py")
    i2 = _issue(issue_type=AnalysisIssueType.COMMAND_INJECTION)
    k2 = compute_dedup_key(i2, relative_path="hefesto/foo.py")
    assert k1 != k2


def test_key_changes_with_line_number() -> None:
    i1 = _issue(line=10)
    i2 = _issue(line=11)
    k1 = compute_dedup_key(i1, relative_path="hefesto/foo.py")
    k2 = compute_dedup_key(i2, relative_path="hefesto/foo.py")
    assert k1 != k2


def test_key_changes_with_relative_path() -> None:
    i = _issue()
    k1 = compute_dedup_key(i, relative_path="hefesto/foo.py")
    k2 = compute_dedup_key(i, relative_path="hefesto/bar.py")
    assert k1 != k2


def test_key_stable_across_absolute_file_path_checkout_locations() -> None:
    """The absolute ``file_path`` on the issue must NOT participate in
    the key — only the caller-provided relative path does. This ensures
    a CI run at ``/runner/_work/repo/`` matches a local run at
    ``/Users/dev/repo/``."""
    i1 = _issue(file_path="/runner/_work/repo/hefesto/foo.py")
    i2 = _issue(file_path="/Users/dev/projects/repo/hefesto/foo.py")
    k1 = compute_dedup_key(i1, relative_path="hefesto/foo.py")
    k2 = compute_dedup_key(i2, relative_path="hefesto/foo.py")
    assert k1 == k2


def test_key_stable_across_metric_drift_in_message() -> None:
    """Messages that embed numbers (complexity values, line counts)
    should not destabilize the key when the metric shifts slightly."""
    k1 = compute_dedup_key(
        _issue(message="Cyclomatic complexity too high (14)"),
        relative_path="hefesto/foo.py",
    )
    k2 = compute_dedup_key(
        _issue(message="Cyclomatic complexity too high (15)"),
        relative_path="hefesto/foo.py",
    )
    assert k1 == k2


def test_key_stable_across_absolute_paths_in_message() -> None:
    k1 = compute_dedup_key(
        _issue(message="Import not declared: /runner/_work/repo/pyproject.toml"),
        relative_path="hefesto/foo.py",
    )
    k2 = compute_dedup_key(
        _issue(message="Import not declared: /Users/dev/project/pyproject.toml"),
        relative_path="hefesto/foo.py",
    )
    assert k1 == k2


def test_key_format_is_sha256_prefixed() -> None:
    key = compute_dedup_key(_issue(), relative_path="hefesto/foo.py")
    assert key.startswith("sha256:")
    assert len(key) == len("sha256:") + 64  # 64 hex chars
    hex_part = key.split(":", 1)[1]
    int(hex_part, 16)  # must parse as hex
