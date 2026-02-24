"""Tests for Resource Safety Pack v1 (EPIC 4 — Reliability Drift Gates)."""

from pathlib import Path

from hefesto.core.analysis_models import AnalysisIssueSeverity, AnalysisIssueType
from hefesto.security.packs.resource_safety_v1 import ResourceSafetyAnalyzer

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "reliability_drift"


def _run(fixture_name: str):
    """Helper: run analyzer on a fixture file and return issues."""
    fixture = FIXTURES_DIR / fixture_name
    assert fixture.exists(), f"Fixture missing: {fixture}"
    code = fixture.read_text()
    analyzer = ResourceSafetyAnalyzer()
    return analyzer.analyze(None, str(fixture), code)


# ── R1: Unbounded Global ─────────────────────────────────────────────


def test_r1_unbounded_global_detected():
    issues = _run("r1_unbounded_global.py")
    r1 = [i for i in issues if i.issue_type == AnalysisIssueType.RELIABILITY_UNBOUNDED_GLOBAL]
    assert len(r1) >= 1
    assert all(i.severity == AnalysisIssueSeverity.MEDIUM for i in r1)
    assert all(i.rule_id == "R1" for i in r1)
    assert all(i.engine == "internal:resource_safety_v1" for i in r1)


# ── R2: Unbounded Cache ──────────────────────────────────────────────


def test_r2_unbounded_cache_detected():
    issues = _run("r2_unbounded_cache.py")
    r2 = [i for i in issues if i.issue_type == AnalysisIssueType.RELIABILITY_UNBOUNDED_CACHE]
    assert len(r2) == 1
    assert r2[0].severity == AnalysisIssueSeverity.MEDIUM
    assert r2[0].rule_id == "R2"
    assert "maxsize" in r2[0].suggestion.lower()


# ── R3: Session Lifecycle ─────────────────────────────────────────────


def test_r3_session_lifecycle_detected():
    issues = _run("r3_unclosed_session.py")
    r3 = [i for i in issues if i.issue_type == AnalysisIssueType.RELIABILITY_SESSION_LIFECYCLE]
    assert len(r3) == 1
    assert r3[0].severity == AnalysisIssueSeverity.MEDIUM
    assert r3[0].rule_id == "R3"
    assert "close" in r3[0].suggestion.lower() or "with" in r3[0].suggestion.lower()


# ── R4: Logging Handler Duplication ───────────────────────────────────


def test_r4_handler_duplication_detected():
    issues = _run("r4_handler_duplication.py")
    r4 = [i for i in issues if i.issue_type == AnalysisIssueType.RELIABILITY_LOGGING_HANDLER_DUP]
    assert len(r4) == 1
    assert r4[0].severity == AnalysisIssueSeverity.MEDIUM
    assert r4[0].rule_id == "R4"
    assert r4[0].function_name == "setup_logging"


# ── R5: Thread in Request ─────────────────────────────────────────────


def test_r5_thread_in_request_detected():
    issues = _run("r5_thread_in_request.py")
    r5 = [i for i in issues if i.issue_type == AnalysisIssueType.RELIABILITY_THREAD_IN_REQUEST]
    assert len(r5) == 1
    assert r5[0].severity == AnalysisIssueSeverity.MEDIUM
    assert r5[0].rule_id == "R5"
    assert r5[0].function_name == "handle_request"


# ── Clean fixture (negative test) ─────────────────────────────────────


def test_clean_no_issues():
    issues = _run("clean_no_issues.py")
    reliability_issues = [i for i in issues if i.issue_type.value.startswith("RELIABILITY_")]
    assert (
        len(reliability_issues) == 0
    ), f"Clean fixture should produce 0 reliability issues, got {len(reliability_issues)}"


# ── Non-Python file skipped ───────────────────────────────────────────


def test_non_python_file_skipped():
    analyzer = ResourceSafetyAnalyzer()
    issues = analyzer.analyze(None, "config.yaml", "key: value")
    assert issues == []


# ── Enterprise fields present ─────────────────────────────────────────


def test_enterprise_fields():
    issues = _run("r1_unbounded_global.py")
    assert len(issues) >= 1
    issue = issues[0]
    assert issue.engine == "internal:resource_safety_v1"
    assert issue.confidence == 0.85
    assert issue.rule_id in ("R1", "R2", "R3", "R4", "R5")
