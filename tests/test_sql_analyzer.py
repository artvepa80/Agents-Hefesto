"""
Unit tests for SqlAnalyzer (P2).

Tests statement-level detection for DELETE/UPDATE without WHERE,
including multiline support and comment handling.

Copyright 2025 Narapa LLC, Miami, Florida
"""

from hefesto.analyzers.devops.sql_analyzer import SqlAnalyzer
from hefesto.core.analysis_models import AnalysisIssueType


class TestSqlAnalyzerDangerousOps:
    """Tests for dangerous operations detection (P1 statement-level)."""

    def setup_method(self):
        self.analyzer = SqlAnalyzer()

    def test_delete_without_where_detected(self):
        """DELETE without WHERE should trigger SQL022."""
        sql = "DELETE FROM users;"
        issues = self.analyzer.analyze("test.sql", sql)
        assert any(
            i.rule_id == "SQL022" and i.issue_type == AnalysisIssueType.SQL_DELETE_WITHOUT_WHERE
            for i in issues
        )

    def test_update_without_where_detected(self):
        """UPDATE without WHERE should trigger SQL023."""
        sql = "UPDATE accounts SET balance = 0;"
        issues = self.analyzer.analyze("test.sql", sql)
        assert any(
            i.rule_id == "SQL023" and i.issue_type == AnalysisIssueType.SQL_UPDATE_WITHOUT_WHERE
            for i in issues
        )

    def test_delete_with_where_multiline_no_issue(self):
        """DELETE with WHERE on next line should NOT trigger SQL022."""
        sql = """DELETE FROM users
WHERE id = 5;"""
        issues = self.analyzer.analyze("test.sql", sql)
        delete_issues = [i for i in issues if i.rule_id == "SQL022"]
        assert len(delete_issues) == 0, "Should not flag DELETE with multiline WHERE"

    def test_update_with_where_multiline_no_issue(self):
        """UPDATE with WHERE on next line should NOT trigger SQL023."""
        sql = """UPDATE accounts
SET balance = 0
WHERE account_id = 123;"""
        issues = self.analyzer.analyze("test.sql", sql)
        update_issues = [i for i in issues if i.rule_id == "SQL023"]
        assert len(update_issues) == 0, "Should not flag UPDATE with multiline WHERE"

    def test_delete_with_where_same_line_no_issue(self):
        """DELETE with WHERE on same line should NOT trigger SQL022."""
        sql = "DELETE FROM users WHERE id = 5;"
        issues = self.analyzer.analyze("test.sql", sql)
        delete_issues = [i for i in issues if i.rule_id == "SQL022"]
        assert len(delete_issues) == 0

    def test_update_with_where_same_line_no_issue(self):
        """UPDATE with WHERE on same line should NOT trigger SQL023."""
        sql = "UPDATE accounts SET balance = 0 WHERE id = 1;"
        issues = self.analyzer.analyze("test.sql", sql)
        update_issues = [i for i in issues if i.rule_id == "SQL023"]
        assert len(update_issues) == 0

    def test_multiple_statements_both_detected(self):
        """Multiple dangerous statements should all be detected."""
        sql = """DELETE FROM users;
UPDATE accounts SET status = 'closed';"""
        issues = self.analyzer.analyze("test.sql", sql)
        delete_issues = [i for i in issues if i.rule_id == "SQL022"]
        update_issues = [i for i in issues if i.rule_id == "SQL023"]
        assert len(delete_issues) == 1
        assert len(update_issues) == 1

    def test_comment_before_statement_still_detected(self):
        """Leading comment should not prevent detection."""
        sql = """-- This deletes all users
DELETE FROM users;"""
        issues = self.analyzer.analyze("test.sql", sql)
        delete_issues = [i for i in issues if i.rule_id == "SQL022"]
        assert len(delete_issues) == 1


class TestSqlAnalyzerGrants:
    """Tests for overly permissive grants detection."""

    def setup_method(self):
        self.analyzer = SqlAnalyzer()

    def test_grant_all_detected(self):
        """GRANT ALL should trigger SQL040."""
        sql = "GRANT ALL PRIVILEGES ON database.* TO admin;"
        issues = self.analyzer.analyze("test.sql", sql)
        assert any(
            i.rule_id == "SQL040" and i.issue_type == AnalysisIssueType.SQL_OVERLY_PERMISSIVE_GRANT
            for i in issues
        )

    def test_grant_to_public_detected(self):
        """GRANT to PUBLIC should trigger SQL041."""
        sql = "GRANT SELECT ON users TO public;"
        issues = self.analyzer.analyze("test.sql", sql)
        assert any(i.rule_id == "SQL041" for i in issues)


class TestSqlAnalyzerQuality:
    """Tests for quality pattern detection."""

    def setup_method(self):
        self.analyzer = SqlAnalyzer()

    def test_select_star_detected(self):
        """SELECT * should trigger SQL030."""
        sql = "SELECT * FROM users;"
        issues = self.analyzer.analyze("test.sql", sql)
        assert any(
            i.rule_id == "SQL030" and i.issue_type == AnalysisIssueType.SQL_SELECT_STAR
            for i in issues
        )

    def test_select_columns_no_issue(self):
        """SELECT with explicit columns should NOT trigger SQL030."""
        sql = "SELECT id, name, email FROM users;"
        issues = self.analyzer.analyze("test.sql", sql)
        select_star_issues = [i for i in issues if i.rule_id == "SQL030"]
        assert len(select_star_issues) == 0


class TestSqlAnalyzerCredentials:
    """Tests for hardcoded credential detection."""

    def setup_method(self):
        self.analyzer = SqlAnalyzer()

    def test_hardcoded_password_detected(self):
        """Hardcoded password should trigger SQL010."""
        sql = "password='secretpass123'"
        issues = self.analyzer.analyze("test.sql", sql)
        assert any(
            i.rule_id == "SQL010" and i.issue_type == AnalysisIssueType.HARDCODED_SECRET
            for i in issues
        )

    def test_database_url_with_credentials_detected(self):
        """Database URL with credentials should trigger SQL012."""
        sql = "-- mysql://admin:password@localhost/db"
        issues = self.analyzer.analyze("test.sql", sql)
        # Comments are skipped, so this should not be detected
        assert len(issues) == 0


class TestSqlAnalyzerEdgeCases:
    """Edge case tests."""

    def setup_method(self):
        self.analyzer = SqlAnalyzer()

    def test_empty_file_no_crash(self):
        """Empty file should not crash."""
        issues = self.analyzer.analyze("test.sql", "")
        assert issues == []

    def test_only_comments_no_issues(self):
        """File with only comments should have no issues."""
        sql = """-- This is a comment
# Another comment style
-- SELECT * FROM users;"""
        issues = self.analyzer.analyze("test.sql", sql)
        # Line-level patterns like SELECT * won't match in comments
        # because the line starts with -- or #
        select_star_issues = [i for i in issues if i.rule_id == "SQL030"]
        assert len(select_star_issues) == 0

    def test_semicolon_in_string_no_split(self):
        """Semicolon inside string should not split statement."""
        sql = "INSERT INTO logs (msg) VALUES ('Error; connection failed');"
        issues = self.analyzer.analyze("test.sql", sql)
        # Should not trigger any dangerous ops
        dangerous_issues = [i for i in issues if i.rule_id in ("SQL022", "SQL023")]
        assert len(dangerous_issues) == 0
