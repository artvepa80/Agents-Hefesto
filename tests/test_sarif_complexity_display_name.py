"""SARIF display name for HIGH_COMPLEXITY is neutral; the rule id is unchanged."""

from __future__ import annotations

from hefesto.core.analysis_models import AnalysisIssue, AnalysisIssueSeverity, AnalysisIssueType
from hefesto.reports.sarif_reporter import _rule


def _issue(kind: AnalysisIssueType, severity: AnalysisIssueSeverity) -> AnalysisIssue:
    return AnalysisIssue(
        file_path="c.py",
        line=1,
        column=0,
        issue_type=kind,
        severity=severity,
        message="Cyclomatic complexity too high (7, threshold 6 for MEDIUM)",
    )


def test_high_complexity_keeps_id_with_neutral_name() -> None:
    rule = _rule(
        "HIGH_COMPLEXITY", [_issue(AnalysisIssueType.HIGH_COMPLEXITY, AnalysisIssueSeverity.MEDIUM)]
    )
    assert rule["id"] == "HIGH_COMPLEXITY"
    assert rule["name"] == "Complexity"
    assert rule["shortDescription"]["text"] == "Complexity"
    assert rule["fullDescription"]["text"] == "Complexity (HIGH_COMPLEXITY), reported by HefestoAI."
    for text in (
        rule["name"],
        rule["shortDescription"]["text"],
        rule["help"]["markdown"].split("(")[0],
    ):
        assert "High" not in text


def test_other_rules_keep_derived_names() -> None:
    rule = _rule(
        "VERY_HIGH_COMPLEXITY",
        [_issue(AnalysisIssueType.VERY_HIGH_COMPLEXITY, AnalysisIssueSeverity.CRITICAL)],
    )
    assert rule["name"] == "VeryHighComplexity"
    assert rule["shortDescription"]["text"] == "Very high complexity"
