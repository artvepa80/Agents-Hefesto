"""Regression test: action fixtures must not be skipped by secret detection."""

from pathlib import Path

from hefesto.analyzers.security import SecurityAnalyzer
from hefesto.core.analysis_models import AnalysisIssueSeverity, AnalysisIssueType

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "action"


def test_critical_secret_detected_in_action_fixture():
    """Fixture with AKIA key must produce at least 1 CRITICAL HARDCODED_SECRET."""
    fixture = FIXTURES_DIR / "critical_secret.py"
    assert fixture.exists(), f"Fixture missing: {fixture}"

    code = fixture.read_text()
    analyzer = SecurityAnalyzer()
    # Call internal method directly — no AST/ML needed for secret patterns.
    issues = analyzer._check_hardcoded_secrets(None, str(fixture), code)

    secret_issues = [
        i
        for i in issues
        if i.issue_type == AnalysisIssueType.HARDCODED_SECRET
        and i.severity == AnalysisIssueSeverity.CRITICAL
    ]
    assert len(secret_issues) >= 1, (
        f"Expected >=1 CRITICAL HARDCODED_SECRET in {fixture.name}, "
        f"got {len(secret_issues)}. All issues: {issues}"
    )


def test_clean_fixture_has_no_secrets():
    """Clean fixture must produce 0 HARDCODED_SECRET issues."""
    fixture = FIXTURES_DIR / "clean.py"
    assert fixture.exists(), f"Fixture missing: {fixture}"

    code = fixture.read_text()
    analyzer = SecurityAnalyzer()
    issues = analyzer._check_hardcoded_secrets(None, str(fixture), code)

    secret_issues = [i for i in issues if i.issue_type == AnalysisIssueType.HARDCODED_SECRET]
    assert len(secret_issues) == 0, (
        f"Expected 0 HARDCODED_SECRET in {fixture.name}, "
        f"got {len(secret_issues)}: {secret_issues}"
    )
