"""OSS-side contract test for the PR review finding schema.

The PR review finding dict produced by
``hefesto/pr_review/orchestrator.py::_filter_and_serialize`` is the
contract boundary between OSS and Pro. Pro's ``enrich_findings()``
consumes these dicts and protects every key in ``_DETERMINISTIC_KEYS``.

This test pins the **exact** set of keys produced by OSS so that:
- Adding a key is a deliberate, test-visible decision (not accidental).
- Removing or renaming a key breaks this test before it reaches Pro.
- Pro's ``_finding()`` fixture can be verified against this canonical set.

The contract is unilateral: OSS and Pro are separate repos without
shared CI. Each side pins the expected shape independently. Drift is
caught when either side's test fails after a change.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)
from hefesto.pr_review.dedup import compute_dedup_key

# ---------------------------------------------------------------- contract

# The canonical set of keys in a PR review finding dict. This MUST match
# the dict literal in ``_filter_and_serialize()`` (orchestrator.py).
# When this set changes, update Pro's ``_finding()`` fixture in
# ``tests/test_pr_review_enrichment.py`` and Pro's ``_DETERMINISTIC_KEYS``
# in ``hefesto_pro/pr_review_enrichment.py``.
PR_REVIEW_FINDING_KEYS = frozenset(
    {
        "file",
        "line",
        "column",
        "type",
        "severity",
        "message",
        "suggestion",
        "code_snippet",
        "dedup_key",
        "in_hunk",
        "anchor_line",
        "engine",
        "rule_id",
    }
)


# ---------------------------------------------------------------- helpers


def _make_finding_dict() -> dict:
    """Build a finding dict the same way ``_filter_and_serialize`` does."""
    issue = AnalysisIssue(
        file_path="/repo/hefesto/app.py",
        line=42,
        column=0,
        issue_type=AnalysisIssueType.SQL_INJECTION_RISK,
        severity=AnalysisIssueSeverity.HIGH,
        message="Potential SQL injection via string concatenation",
        suggestion="Use parameterized queries with placeholders",
        engine="internal:security",
        rule_id=None,
    )
    rel_path = "hefesto/app.py"
    return {
        "file": rel_path,
        "line": issue.line,
        "column": issue.column,
        "type": issue.issue_type.value,
        "severity": issue.severity.value,
        "message": issue.message,
        "suggestion": issue.suggestion,
        "code_snippet": issue.code_snippet,
        "dedup_key": compute_dedup_key(issue, relative_path=rel_path),
        "in_hunk": True,
        "anchor_line": issue.line,
        "engine": issue.engine,
        "rule_id": issue.rule_id,
    }


# ---------------------------------------------------------------- tests


class TestPrReviewSchemaContract:
    """Pin the PR review finding dict schema."""

    def test_finding_keys_match_contract(self):
        """The dict built by ``_filter_and_serialize`` must produce
        exactly the keys declared in ``PR_REVIEW_FINDING_KEYS``."""
        finding = _make_finding_dict()
        assert set(finding.keys()) == PR_REVIEW_FINDING_KEYS

    def test_no_extra_keys(self):
        """Guard against silent key additions."""
        finding = _make_finding_dict()
        extra = set(finding.keys()) - PR_REVIEW_FINDING_KEYS
        assert extra == set(), f"Undeclared keys in finding dict: {extra}"

    def test_no_missing_keys(self):
        """Guard against silent key removals."""
        finding = _make_finding_dict()
        missing = PR_REVIEW_FINDING_KEYS - set(finding.keys())
        assert missing == set(), f"Missing keys from finding dict: {missing}"

    def test_value_types_are_stable(self):
        """Pin the types of each field to prevent silent type changes."""
        finding = _make_finding_dict()
        assert isinstance(finding["file"], str)
        assert isinstance(finding["line"], int)
        assert isinstance(finding["column"], int)
        assert isinstance(finding["type"], str)
        assert isinstance(finding["severity"], str)
        assert isinstance(finding["message"], str)
        assert finding["suggestion"] is None or isinstance(finding["suggestion"], str)
        assert finding["code_snippet"] is None or isinstance(finding["code_snippet"], str)
        assert isinstance(finding["dedup_key"], str)
        assert finding["dedup_key"].startswith("sha256:")
        assert isinstance(finding["in_hunk"], bool)
        # anchor_line is Optional[int]: None exactly when in_hunk is False
        assert finding["anchor_line"] is None or isinstance(finding["anchor_line"], int)
        assert isinstance(finding["engine"], str)
        # rule_id is Optional[str]
        assert finding["rule_id"] is None or isinstance(finding["rule_id"], str)


def test_real_serializer_emits_contract_keys(tmp_path):
    """``_make_finding_dict`` mirrors the serializer by hand; this test runs
    the real ``_filter_and_serialize`` so an added or dropped key fails here
    even when the mirror is not updated."""
    from hefesto.core.analysis_models import AnalysisReport, AnalysisSummary, FileAnalysisResult
    from hefesto.pr_review.orchestrator import _filter_and_serialize

    issue = AnalysisIssue(
        file_path=str(tmp_path / "app.py"),
        line=3,
        column=0,
        issue_type=AnalysisIssueType.HIGH_COMPLEXITY,
        severity=AnalysisIssueSeverity.HIGH,
        message="Cyclomatic complexity too high (11)",
        end_line=9,
    )
    report = AnalysisReport(
        summary=AnalysisSummary(
            files_analyzed=1,
            total_issues=1,
            critical_issues=0,
            high_issues=1,
            medium_issues=0,
            low_issues=0,
            total_loc=10,
            duration_seconds=0.0,
        ),
        file_results=[FileAnalysisResult(str(tmp_path / "app.py"), [issue], 10, 0.0)],
    )
    out = _filter_and_serialize(report, tmp_path, {"app.py": {5}}, strict=False)
    assert len(out) == 1
    assert set(out[0].keys()) == PR_REVIEW_FINDING_KEYS
    assert out[0]["line"] == 3
    assert out[0]["anchor_line"] == 5
