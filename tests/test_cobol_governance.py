"""
Unit tests for COBOL Governance Analyzer (Phase 1-Lite Sprint 2).

Tests 7 governance rules against synthetic COBOL fixtures:
- FREE tier: GOTO_EXCESSIVE, HARDCODED_CREDENTIALS, ACCEPT
- PRO tier: REDEFINES_SENSITIVE, OCCURS_DEPENDING_ON, PERFORM_THRU_CHAIN, COPYBOOK_BLAST_RADIUS

Copyright 2025 Narapa LLC, Miami, Florida
"""

from pathlib import Path

from hefesto.analyzers.devops.cobol_governance_analyzer import CobolGovernanceAnalyzer
from hefesto.core.analysis_models import AnalysisIssueSeverity, AnalysisIssueType

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "cobol"


class TestCobolGovernancePositive:
    """Positive tests: fixtures SHOULD trigger rules."""

    def setup_method(self):
        self.analyzer = CobolGovernanceAnalyzer()

    def test_goto_excessive_spaghetti_logic(self):
        """SPAGHETTI-LOGIC.cbl has 23 GO TOs → should trigger GOTO_EXCESSIVE (HIGH)."""
        fixture = FIXTURES_DIR / "SPAGHETTI-LOGIC.cbl"
        code = fixture.read_text()
        issues = self.analyzer.analyze(str(fixture), code)

        goto_issues = [i for i in issues if i.issue_type == AnalysisIssueType.COBOL_GOTO_EXCESSIVE]
        assert len(goto_issues) == 1, f"Expected 1 GOTO_EXCESSIVE, got {len(goto_issues)}"
        assert goto_issues[0].severity == AnalysisIssueSeverity.HIGH
        assert goto_issues[0].rule_id == "COBOL001"
        assert "23" in goto_issues[0].message  # Should mention count

    def test_hardcoded_credentials_batch_db2(self):
        """BATCH-DB2.cbl hardcoded password → HARDCODED_CREDENTIALS (CRITICAL)."""
        fixture = FIXTURES_DIR / "BATCH-DB2.cbl"
        code = fixture.read_text()
        issues = self.analyzer.analyze(str(fixture), code)

        cred_issues = [
            i for i in issues if i.issue_type == AnalysisIssueType.COBOL_HARDCODED_CREDENTIALS
        ]
        # Should detect at least password field (WS-DB-PASSWORD)
        assert len(cred_issues) >= 1, f"Expected ≥1 HARDCODED_CREDENTIALS, got {len(cred_issues)}"
        assert all(i.severity == AnalysisIssueSeverity.CRITICAL for i in cred_issues)
        assert all(i.rule_id == "COBOL002" for i in cred_issues)
        # Verify it mentions field name but NOT literal value
        assert any("PASSWORD" in i.message.upper() for i in cred_issues)
        assert not any(
            "PROD2026" in i.message for i in cred_issues
        ), "Should not leak literal value"

    def test_accept_unvalidated_legacy_report(self):
        """LEGACY-REPORT.cbl ACCEPT statements → ACCEPT (MEDIUM)."""
        fixture = FIXTURES_DIR / "LEGACY-REPORT.cbl"
        code = fixture.read_text()
        issues = self.analyzer.analyze(str(fixture), code)

        accept_issues = [
            i for i in issues if i.issue_type == AnalysisIssueType.COBOL_ACCEPT_UNVALIDATED
        ]
        assert len(accept_issues) >= 1, f"Expected ≥1 ACCEPT, got {len(accept_issues)}"
        assert all(i.severity == AnalysisIssueSeverity.MEDIUM for i in accept_issues)
        assert all(i.rule_id == "COBOL003" for i in accept_issues)

    def test_redefines_sensitive_balance_calc(self):
        """BALANCE-CALC.cbl REDEFINES → REDEFINES_SENSITIVE (HIGH)."""
        fixture = FIXTURES_DIR / "BALANCE-CALC.cbl"
        code = fixture.read_text()
        issues = self.analyzer.analyze(str(fixture), code)

        redefines_issues = [
            i for i in issues if i.issue_type == AnalysisIssueType.COBOL_REDEFINES_SENSITIVE
        ]
        assert (
            len(redefines_issues) >= 1
        ), f"Expected ≥1 REDEFINES_SENSITIVE, got {len(redefines_issues)}"
        assert all(i.severity == AnalysisIssueSeverity.HIGH for i in redefines_issues)
        assert all(i.rule_id == "COBOL004" for i in redefines_issues)

    def test_occurs_depending_dynamic_table(self):
        """DYNAMIC-TABLE.cbl OCCURS DEPENDING ON → OCCURS_DEPENDING_ON (MEDIUM)."""
        fixture = FIXTURES_DIR / "DYNAMIC-TABLE.cbl"
        code = fixture.read_text()
        issues = self.analyzer.analyze(str(fixture), code)

        occurs_issues = [
            i for i in issues if i.issue_type == AnalysisIssueType.COBOL_OCCURS_DEPENDING_ON
        ]
        assert len(occurs_issues) >= 1, f"Expected ≥1 OCCURS_DEPENDING_ON, got {len(occurs_issues)}"
        assert all(i.severity == AnalysisIssueSeverity.MEDIUM for i in occurs_issues)
        assert all(i.rule_id == "COBOL005" for i in occurs_issues)

    def test_perform_thru_chain_batch_loop(self):
        """BATCH-LOOP.cbl PERFORM THRU 7 paragraphs → PERFORM_THRU_CHAIN (HIGH)."""
        fixture = FIXTURES_DIR / "BATCH-LOOP.cbl"
        code = fixture.read_text()
        issues = self.analyzer.analyze(str(fixture), code)

        perform_issues = [
            i for i in issues if i.issue_type == AnalysisIssueType.COBOL_PERFORM_THRU_CHAIN
        ]
        assert (
            len(perform_issues) >= 1
        ), f"Expected ≥1 PERFORM_THRU_CHAIN, got {len(perform_issues)}"
        assert all(i.severity == AnalysisIssueSeverity.HIGH for i in perform_issues)
        assert all(i.rule_id == "COBOL006" for i in perform_issues)

    def test_copybook_blast_radius_acct_open(self):
        """ACCT-OPEN.cbl CUST-RECORD copybook → COPYBOOK_BLAST_RADIUS."""
        fixture = FIXTURES_DIR / "ACCT-OPEN.cbl"
        code = fixture.read_text()
        issues = self.analyzer.analyze(str(fixture), code)

        copybook_issues = [
            i for i in issues if i.issue_type == AnalysisIssueType.COBOL_COPYBOOK_BLAST_RADIUS
        ]
        assert (
            len(copybook_issues) >= 1
        ), f"Expected ≥1 COPYBOOK_BLAST_RADIUS, got {len(copybook_issues)}"
        assert all(i.rule_id == "COBOL007" for i in copybook_issues)
        # CUST-RECORD is specific name → HIGH severity
        assert any(i.severity == AnalysisIssueSeverity.HIGH for i in copybook_issues)


class TestCobolGovernanceNegative:
    """Negative tests: fixtures should NOT trigger rules."""

    def setup_method(self):
        self.analyzer = CobolGovernanceAnalyzer()

    def test_clean_prog_no_goto_excessive(self):
        """CLEAN-PROG.cbl has 0 GO TOs → should NOT trigger GOTO_EXCESSIVE."""
        fixture = FIXTURES_DIR / "CLEAN-PROG.cbl"
        code = fixture.read_text()
        issues = self.analyzer.analyze(str(fixture), code)

        goto_issues = [i for i in issues if i.issue_type == AnalysisIssueType.COBOL_GOTO_EXCESSIVE]
        assert len(goto_issues) == 0, "CLEAN-PROG should not trigger GOTO_EXCESSIVE"

    def test_clean_prog_no_hardcoded_credentials(self):
        """CLEAN-PROG.cbl no credentials → NOT HARDCODED_CREDENTIALS."""
        fixture = FIXTURES_DIR / "CLEAN-PROG.cbl"
        code = fixture.read_text()
        issues = self.analyzer.analyze(str(fixture), code)

        cred_issues = [
            i for i in issues if i.issue_type == AnalysisIssueType.COBOL_HARDCODED_CREDENTIALS
        ]
        assert len(cred_issues) == 0, "CLEAN-PROG should not trigger HARDCODED_CREDENTIALS"

    def test_clean_prog_no_accept(self):
        """CLEAN-PROG.cbl has no ACCEPT → should NOT trigger ACCEPT."""
        fixture = FIXTURES_DIR / "CLEAN-PROG.cbl"
        code = fixture.read_text()
        issues = self.analyzer.analyze(str(fixture), code)

        accept_issues = [
            i for i in issues if i.issue_type == AnalysisIssueType.COBOL_ACCEPT_UNVALIDATED
        ]
        assert len(accept_issues) == 0, "CLEAN-PROG should not trigger ACCEPT"

    def test_empty_proc_no_findings(self):
        """EMPTY-PROC.cbl is minimal baseline → should have 0 findings."""
        fixture = FIXTURES_DIR / "EMPTY-PROC.cbl"
        code = fixture.read_text()
        issues = self.analyzer.analyze(str(fixture), code)

        assert len(issues) == 0, f"EMPTY-PROC should have 0 findings, got {len(issues)}"

    def test_spaghetti_no_hardcoded_credentials(self):
        """SPAGHETTI-LOGIC.cbl GO TOs but no passwords → NOT HARDCODED_CREDENTIALS."""
        fixture = FIXTURES_DIR / "SPAGHETTI-LOGIC.cbl"
        code = fixture.read_text()
        issues = self.analyzer.analyze(str(fixture), code)

        cred_issues = [
            i for i in issues if i.issue_type == AnalysisIssueType.COBOL_HARDCODED_CREDENTIALS
        ]
        assert len(cred_issues) == 0, "SPAGHETTI-LOGIC should not trigger HARDCODED_CREDENTIALS"

    def test_cust_record_copybook_no_findings(self):
        """CUST-RECORD.cpy is data definition only → should have 0 findings."""
        fixture = FIXTURES_DIR / "CUST-RECORD.cpy"
        code = fixture.read_text()
        issues = self.analyzer.analyze(str(fixture), code)

        # Copybooks may have data structures but no procedure code
        # Should not trigger procedural rules
        assert len(issues) == 0, f"CUST-RECORD.cpy should have 0 findings, got {len(issues)}"

    def test_acct_open_no_goto_excessive(self):
        """ACCT-OPEN.cbl uses PERFORM, not GO TO → should NOT trigger GOTO_EXCESSIVE."""
        fixture = FIXTURES_DIR / "ACCT-OPEN.cbl"
        code = fixture.read_text()
        issues = self.analyzer.analyze(str(fixture), code)

        goto_issues = [i for i in issues if i.issue_type == AnalysisIssueType.COBOL_GOTO_EXCESSIVE]
        assert len(goto_issues) == 0, "ACCT-OPEN should not trigger GOTO_EXCESSIVE"


class TestCobolGovernanceMixed:
    """Test fixtures with multiple findings."""

    def setup_method(self):
        self.analyzer = CobolGovernanceAnalyzer()

    def test_legacy_report_mixed_findings(self):
        """LEGACY-REPORT.cbl multiple findings (CREDENTIALS + GOTO + ACCEPT)."""
        fixture = FIXTURES_DIR / "LEGACY-REPORT.cbl"
        code = fixture.read_text()
        issues = self.analyzer.analyze(str(fixture), code)

        # Should have at least 3 findings from different rules
        issue_types = {i.issue_type for i in issues}

        # Verify we have findings from multiple rules
        assert len(issues) >= 3, f"Expected ≥3 findings in LEGACY-REPORT, got {len(issues)}"

        # Should include at least these types
        expected_types = {
            AnalysisIssueType.COBOL_HARDCODED_CREDENTIALS,
            AnalysisIssueType.COBOL_GOTO_EXCESSIVE,
            AnalysisIssueType.COBOL_ACCEPT_UNVALIDATED,
        }
        found_types = issue_types & expected_types
        assert len(found_types) >= 2, f"Expected at least 2 of {expected_types}, got {found_types}"


class TestCobolGovernanceEdgeCases:
    """Edge case tests."""

    def setup_method(self):
        self.analyzer = CobolGovernanceAnalyzer()

    def test_empty_file_no_crash(self):
        """Empty file should not crash, should return 0 findings."""
        issues = self.analyzer.analyze("empty.cbl", "")
        assert len(issues) == 0

    def test_comment_only_file_no_crash(self):
        """File with only comments should not crash, should return 0 findings."""
        code = """      *****************************************************************
      * This is a comment-only file
      *****************************************************************
"""
        issues = self.analyzer.analyze("comments.cbl", code)
        assert len(issues) == 0

    def test_identification_division_only_no_crash(self):
        """File with only IDENTIFICATION DIVISION should not crash."""
        code = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. MINIMAL.
"""
        issues = self.analyzer.analyze("minimal.cbl", code)
        assert len(issues) == 0

    def test_mixed_case_keywords_detected(self):
        """Mixed case keywords (go to, Go To, GO TO) should all be detected."""
        code = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. MIXED-CASE.
       PROCEDURE DIVISION.
       PARA-1.
           go to PARA-2.
       PARA-2.
           Go To PARA-3.
       PARA-3.
           GO TO PARA-4.
       PARA-4.
           Go To PARA-5.
       PARA-5.
           go To PARA-6.
       PARA-6.
           gO tO PARA-7.
       PARA-7.
           GO TO PARA-8.
       PARA-8.
           Go to PARA-9.
       PARA-9.
           GO To PARA-10.
       PARA-10.
           go TO PARA-11.
       PARA-11.
           GO to PARA-END.
       PARA-END.
           STOP RUN.
"""
        issues = self.analyzer.analyze("mixed_case.cbl", code)
        goto_issues = [i for i in issues if i.issue_type == AnalysisIssueType.COBOL_GOTO_EXCESSIVE]
        # Should detect all 11 GO TOs regardless of case
        assert len(goto_issues) == 1, "Should trigger GOTO_EXCESSIVE"
        assert "11" in goto_issues[0].message

    def test_accept_from_date_not_flagged(self):
        """ACCEPT FROM DATE/TIME/DAY are system calls, should NOT be flagged."""
        code = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. ACCEPT-SAFE.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-DATE PIC X(8).
       01  WS-TIME PIC X(8).
       01  WS-DAY  PIC 9(7).
       PROCEDURE DIVISION.
       MAIN.
           ACCEPT WS-DATE FROM DATE.
           ACCEPT WS-TIME FROM TIME.
           ACCEPT WS-DAY FROM DAY.
           STOP RUN.
"""
        issues = self.analyzer.analyze("accept_safe.cbl", code)
        accept_issues = [
            i for i in issues if i.issue_type == AnalysisIssueType.COBOL_ACCEPT_UNVALIDATED
        ]
        assert len(accept_issues) == 0, "ACCEPT FROM DATE/TIME/DAY should not be flagged"
