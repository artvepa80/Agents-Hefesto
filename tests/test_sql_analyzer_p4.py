"""
P4 SQL Dialect Coverage Tests for SqlAnalyzer.
Tests schema-qualified tables, quoted identifiers, and DELETE/UPDATE variants.
"""

import pytest

from hefesto.analyzers.devops.sql_analyzer import SqlAnalyzer


class TestDeleteDialectCoverage:
    """DELETE statement dialect coverage tests."""

    @pytest.fixture
    def analyzer(self):
        return SqlAnalyzer()

    # === DELETE without WHERE (should trigger SQL022) ===

    def test_delete_schema_table_no_where(self, analyzer):
        """DELETE FROM schema.table without WHERE should trigger."""
        issues = analyzer.analyze("test.sql", "DELETE FROM schema.users;")
        assert any(i.rule_id == "SQL022" for i in issues)

    def test_delete_db_schema_table_no_where(self, analyzer):
        """DELETE FROM db.schema.table without WHERE should trigger."""
        issues = analyzer.analyze("test.sql", "DELETE FROM mydb.dbo.users;")
        assert any(i.rule_id == "SQL022" for i in issues)

    def test_delete_double_quoted_table_no_where(self, analyzer):
        """DELETE FROM "table" without WHERE should trigger."""
        issues = analyzer.analyze("test.sql", 'DELETE FROM "users";')
        assert any(i.rule_id == "SQL022" for i in issues)

    def test_delete_bracket_quoted_table_no_where(self, analyzer):
        """DELETE FROM [table] (SQL Server) without WHERE should trigger."""
        issues = analyzer.analyze("test.sql", "DELETE FROM [users];")
        assert any(i.rule_id == "SQL022" for i in issues)

    def test_delete_backtick_quoted_table_no_where(self, analyzer):
        """DELETE FROM `table` (MySQL) without WHERE should trigger."""
        issues = analyzer.analyze("test.sql", "DELETE FROM `users`;")
        assert any(i.rule_id == "SQL022" for i in issues)

    def test_delete_alias_mysql_no_where(self, analyzer):
        """DELETE u FROM users u (MySQL style) without WHERE should trigger."""
        issues = analyzer.analyze("test.sql", "DELETE u FROM users u;")
        assert any(i.rule_id == "SQL022" for i in issues)

    def test_delete_using_postgres_no_where(self, analyzer):
        """DELETE FROM t USING (Postgres) without WHERE should trigger."""
        issues = analyzer.analyze("test.sql", "DELETE FROM users USING accounts a;")
        assert any(i.rule_id == "SQL022" for i in issues)

    # === DELETE with WHERE (should NOT trigger) ===

    def test_delete_schema_table_with_where(self, analyzer):
        """DELETE FROM schema.table WITH WHERE should NOT trigger."""
        issues = analyzer.analyze("test.sql", "DELETE FROM schema.users WHERE id = 1;")
        assert not any(i.rule_id == "SQL022" for i in issues)

    def test_delete_multiline_with_where(self, analyzer):
        """DELETE multiline with WHERE should NOT trigger."""
        content = """DELETE FROM users
WHERE id = 1;"""
        issues = analyzer.analyze("test.sql", content)
        assert not any(i.rule_id == "SQL022" for i in issues)

    def test_delete_quoted_with_where(self, analyzer):
        """DELETE FROM "table" with WHERE should NOT trigger."""
        issues = analyzer.analyze("test.sql", 'DELETE FROM "users" WHERE id = 1;')
        assert not any(i.rule_id == "SQL022" for i in issues)


class TestUpdateDialectCoverage:
    """UPDATE statement dialect coverage tests."""

    @pytest.fixture
    def analyzer(self):
        return SqlAnalyzer()

    # === UPDATE without WHERE (should trigger SQL023) ===

    def test_update_schema_table_no_where(self, analyzer):
        """UPDATE schema.table without WHERE should trigger."""
        issues = analyzer.analyze("test.sql", "UPDATE schema.logs SET status = 1;")
        assert any(i.rule_id == "SQL023" for i in issues)

    def test_update_double_quoted_table_no_where(self, analyzer):
        """UPDATE "table" without WHERE should trigger."""
        issues = analyzer.analyze("test.sql", 'UPDATE "logs" SET status = 1;')
        assert any(i.rule_id == "SQL023" for i in issues)

    def test_update_with_from_no_where(self, analyzer):
        """UPDATE ... SET ... FROM ... without WHERE should trigger."""
        content = "UPDATE logs SET status = 1 FROM users u;"
        issues = analyzer.analyze("test.sql", content)
        assert any(i.rule_id == "SQL023" for i in issues)

    def test_update_backtick_table_no_where(self, analyzer):
        """UPDATE `table` (MySQL) without WHERE should trigger."""
        issues = analyzer.analyze("test.sql", "UPDATE `logs` SET status = 1;")
        assert any(i.rule_id == "SQL023" for i in issues)

    # === UPDATE with WHERE (should NOT trigger) ===

    def test_update_with_where(self, analyzer):
        """UPDATE with WHERE should NOT trigger."""
        issues = analyzer.analyze("test.sql", "UPDATE logs SET status = 1 WHERE id = 1;")
        assert not any(i.rule_id == "SQL023" for i in issues)

    def test_update_multiline_from_with_where(self, analyzer):
        """UPDATE multiline with FROM and WHERE should NOT trigger."""
        content = """UPDATE logs SET status = 1
FROM users u
WHERE logs.user_id = u.id;"""
        issues = analyzer.analyze("test.sql", content)
        assert not any(i.rule_id == "SQL023" for i in issues)

    def test_update_schema_table_with_where(self, analyzer):
        """UPDATE schema.table with WHERE should NOT trigger."""
        issues = analyzer.analyze("test.sql", "UPDATE dbo.logs SET status = 1 WHERE id = 1;")
        assert not any(i.rule_id == "SQL023" for i in issues)


class TestP3RegressionSuite:
    """Regression tests to ensure P3 (comment/string masking) still works."""

    @pytest.fixture
    def analyzer(self):
        return SqlAnalyzer()

    def test_where_in_line_comment_still_triggers(self, analyzer):
        """WHERE in line comment should NOT save the statement (P3.1)."""
        issues = analyzer.analyze("test.sql", "DELETE FROM users -- WHERE id = 1;")
        assert any(i.rule_id == "SQL022" for i in issues)

    def test_where_in_string_still_triggers(self, analyzer):
        """WHERE in string should NOT save the statement (P3.1)."""
        issues = analyzer.analyze("test.sql", "UPDATE logs SET msg = 'WHERE x=1';")
        assert any(i.rule_id == "SQL023" for i in issues)

    def test_where_in_block_comment_still_triggers(self, analyzer):
        """WHERE in block comment should NOT save the statement (P3.1)."""
        issues = analyzer.analyze("test.sql", "DELETE FROM temp /* WHERE id=9 */;")
        assert any(i.rule_id == "SQL022" for i in issues)


class TestStatementSplittingRobustness:
    """Tests for statement splitting edge cases."""

    @pytest.fixture
    def analyzer(self):
        return SqlAnalyzer()

    def test_semicolon_in_string_no_break(self, analyzer):
        """Semicolon inside string should not break statement."""
        content = "UPDATE logs SET msg = 'a;b;c'; DELETE FROM temp;"
        issues = analyzer.analyze("test.sql", content)
        # Should detect DELETE without WHERE
        delete_issues = [i for i in issues if i.rule_id == "SQL022"]
        assert len(delete_issues) == 1

    def test_statement_without_trailing_semicolon(self, analyzer):
        """Statement without trailing semicolon should still be analyzed."""
        issues = analyzer.analyze("test.sql", "DELETE FROM users")
        assert any(i.rule_id == "SQL022" for i in issues)

    def test_multiple_statements_correct_count(self, analyzer):
        """Multiple dangerous statements should all be detected."""
        content = """
DELETE FROM safe WHERE id = 1;
DELETE FROM danger1;
UPDATE safe SET x = 1 WHERE y = 2;
UPDATE danger2 SET x = 1;
DELETE FROM danger3;
"""
        issues = analyzer.analyze("test.sql", content)
        sql022 = [i for i in issues if i.rule_id == "SQL022"]
        sql023 = [i for i in issues if i.rule_id == "SQL023"]
        assert len(sql022) == 2  # danger1, danger3
        assert len(sql023) == 1  # danger2
