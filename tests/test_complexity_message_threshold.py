"""The complexity message names the threshold it crossed (#159), and the
PR-review dedup key and SARIF fingerprint do not change because of it."""

from __future__ import annotations

import pytest

from hefesto.analyzers.complexity import ComplexityAnalyzer
from hefesto.core.analysis_models import AnalysisIssue, AnalysisIssueSeverity, AnalysisIssueType
from hefesto.core.language_detector import Language
from hefesto.core.parsers.parser_factory import ParserFactory
from hefesto.pr_review.dedup import compute_dedup_key
from hefesto.reports.sarif_reporter import SARIFReporter


def _func_with_ifs(n: int) -> str:
    body = "".join(f"    if a == {i}:\n        return {i}\n" for i in range(n))
    return f"def f(a):\n{body}    return -1\n"


@pytest.mark.parametrize(
    "ifs, expected",
    [
        (5, "Cyclomatic complexity too high (6, threshold 6 for MEDIUM)"),
        (13, "Cyclomatic complexity too high (14, threshold 11 for HIGH)"),
        (21, "Cyclomatic complexity too high (22, threshold 21 for CRITICAL)"),
    ],
)
def test_message_includes_threshold(ifs: int, expected: str) -> None:
    code = _func_with_ifs(ifs)
    tree = ParserFactory.get_parser(Language.PYTHON).parse(code, "c.py")
    issues = ComplexityAnalyzer().analyze(tree, "c.py", code)
    assert [i.message for i in issues] == [expected]


def _issue(message: str, path: str = "/abs/project/c.py") -> AnalysisIssue:
    return AnalysisIssue(
        file_path=path,
        line=1,
        column=0,
        issue_type=AnalysisIssueType.HIGH_COMPLEXITY,
        severity=AnalysisIssueSeverity.HIGH,
        message=message,
    )


OLD = "Cyclomatic complexity too high (14)"
NEW = "Cyclomatic complexity too high (14, threshold 11 for HIGH)"


def test_dedup_key_unchanged_by_threshold_clause() -> None:
    old = compute_dedup_key(_issue(OLD), relative_path="c.py")
    assert compute_dedup_key(_issue(NEW), relative_path="c.py") == old


def test_dedup_key_still_changes_for_other_threshold_text() -> None:
    a = compute_dedup_key(
        _issue("Function 'f' has deep nesting (level 5, threshold=4)"), relative_path="c.py"
    )
    b = compute_dedup_key(_issue("Function 'f' has deep nesting (level 5)"), relative_path="c.py")
    assert a != b


def test_sarif_fallback_fingerprint_unchanged_by_threshold_clause(tmp_path) -> None:
    reporter = SARIFReporter(root=str(tmp_path))
    missing = str(tmp_path / "gone.py")  # no line text: the message is the context
    old = reporter._fingerprint(_issue(OLD, missing), "HIGH_COMPLEXITY", "gone.py", {})
    new = reporter._fingerprint(_issue(NEW, missing), "HIGH_COMPLEXITY", "gone.py", {})
    assert new == old
