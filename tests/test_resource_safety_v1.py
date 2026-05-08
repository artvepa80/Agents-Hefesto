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


def test_r3_self_attribute_with_close_method_no_finding():
    """Lazy-getter cache pattern: self._conn = connect() + class-level close().

    Mirrors swarm/storage/sqlite_store.py (PRO repo) FP-1 from EPIC 4 Phase D
    warn soak (2026-05-08). The class manages connection lifecycle via an
    explicit close() method that calls self._conn.close(); R3 must recognize
    this pattern and NOT emit a finding.
    """
    issues = _run("r3_self_attr_managed.py")
    r3 = [i for i in issues if i.issue_type == AnalysisIssueType.RELIABILITY_SESSION_LIFECYCLE]
    assert r3 == [], (
        "Lazy-getter cache + class-level close() should not trigger R3, "
        f"got {len(r3)} finding(s): {[(i.line, i.message) for i in r3]}"
    )


def test_r3_message_never_contains_assigned_to_none():
    """R3 messages must never contain the literal "'None'" as the assigned
    variable. Prior bug: ast.Attribute targets (e.g., self._conn) fell through
    to var_name=None and produced messages like
    "'connect()' assigned to 'None' without ...".

    This regression guard scans every R3 emission across every reliability
    fixture in the repo, including fixtures that intentionally use
    self-attribute targets.
    """
    fixtures = sorted(FIXTURES_DIR.glob("*.py"))
    assert fixtures, "no reliability fixtures discovered"

    for fixture in fixtures:
        issues = _run(fixture.name)
        for i in issues:
            if i.issue_type != AnalysisIssueType.RELIABILITY_SESSION_LIFECYCLE:
                continue
            assert "'None'" not in i.message, (
                f"R3 emitted message with 'None' literal in {fixture.name}: " f"{i.message!r}"
            )


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
