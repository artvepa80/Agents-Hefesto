"""
P3.2 Edge Case Tests for SqlAnalyzer._build_stmt_scan() and statement parsing.
Tests comment handling, string masking, and statement splitting edge cases.
"""

import pytest

from hefesto.analyzers.devops.sql_analyzer import SqlAnalyzer


class TestBuildStmtScan:
    """Tests for _build_stmt_scan() method."""

    @pytest.fixture
    def analyzer(self):
        return SqlAnalyzer()

    def test_where_in_line_comment_not_counted(self, analyzer):
        """WHERE in -- comment should be masked, not count as real WHERE."""
        stmt = "DELETE FROM users -- WHERE id = 1"
        scan = analyzer._build_stmt_scan(stmt)
        # The scan should mask the comment, leaving no WHERE visible
        assert "WHERE" not in scan or scan.find("WHERE") > scan.find("--")

    def test_where_in_block_comment_not_counted(self, analyzer):
        """WHERE in /* */ block comment should be masked."""
        stmt = "DELETE FROM temp /* WHERE id = 1 */"
        scan = analyzer._build_stmt_scan(stmt)
        # WHERE should be replaced with spaces
        assert "WHERE" not in scan

    def test_where_in_string_literal_not_counted(self, analyzer):
        """WHERE inside single-quoted string should be masked."""
        stmt = "UPDATE logs SET msg = 'WHERE x = 1'"
        scan = analyzer._build_stmt_scan(stmt)
        # The WHERE inside the string should be masked
        assert scan.count("WHERE") == 0 or "'" in scan

    def test_where_in_double_quoted_identifier_preserved(self, analyzer):
        """Double-quoted identifiers should be preserved (not masked)."""
        stmt = 'SELECT * FROM "WHERE_TABLE"'
        scan = analyzer._build_stmt_scan(stmt)
        # Double-quoted identifiers are preserved
        assert '"WHERE_TABLE"' in scan

    def test_multiline_block_comment(self, analyzer):
        """Multi-line block comments should be fully masked."""
        stmt = """DELETE FROM users
/* This is a multi-line
   comment with WHERE
   inside it */"""
        scan = analyzer._build_stmt_scan(stmt)
        assert "WHERE" not in scan

    def test_hash_comment_mysql_style(self, analyzer):
        """MySQL-style # comments should be masked."""
        stmt = "DELETE FROM users # WHERE id = 1"
        scan = analyzer._build_stmt_scan(stmt)
        # Everything after # should be masked
        assert "WHERE" not in scan or scan.find("WHERE") < scan.find("#")

    def test_escaped_single_quote_in_string(self, analyzer):
        """Escaped single quotes '' inside strings should be handled."""
        stmt = "UPDATE logs SET msg = 'It''s WHERE we go'"
        scan = analyzer._build_stmt_scan(stmt)
        # The WHERE inside string should be masked
        assert scan.count("WHERE") == 0

    def test_semicolon_in_string_not_statement_break(self, analyzer):
        """Semicolons inside strings should not break statement parsing."""
        content = "UPDATE logs SET msg = 'a;b;c'; DELETE FROM temp"
        stmts = analyzer._iter_sql_statements(content)
        # Should be 2 statements, not more
        assert len(stmts) == 2

    def test_preserves_length_for_offset_mapping(self, analyzer):
        """Scan string should preserve length for accurate offset mapping."""
        stmt = "DELETE FROM users -- WHERE id = 1"
        scan = analyzer._build_stmt_scan(stmt)
        assert len(scan) == len(stmt)


class TestDangerousOpsEdgeCases:
    """Integration tests for dangerous ops with edge cases."""

    @pytest.fixture
    def analyzer(self):
        return SqlAnalyzer()

    def test_delete_with_where_in_comment_triggers(self, analyzer):
        """DELETE with WHERE only in comment should trigger SQL022."""
        content = "DELETE FROM users -- WHERE id = 1;"
        issues = analyzer.analyze("test.sql", content)
        danger = [i for i in issues if i.rule_id == "SQL022"]
        assert len(danger) == 1

    def test_update_with_where_in_string_triggers(self, analyzer):
        """UPDATE with WHERE only in string should trigger SQL023."""
        content = "UPDATE logs SET msg = 'WHERE x';"
        issues = analyzer.analyze("test.sql", content)
        danger = [i for i in issues if i.rule_id == "SQL023"]
        assert len(danger) == 1

    def test_delete_with_where_in_block_comment_triggers(self, analyzer):
        """DELETE with WHERE only in block comment should trigger SQL022."""
        content = "DELETE FROM temp /* WHERE id = 9 */;"
        issues = analyzer.analyze("test.sql", content)
        danger = [i for i in issues if i.rule_id == "SQL022"]
        assert len(danger) == 1

    def test_delete_with_real_where_no_trigger(self, analyzer):
        """DELETE with real WHERE clause should NOT trigger."""
        content = """DELETE FROM users
WHERE id = 1;"""
        issues = analyzer.analyze("test.sql", content)
        danger = [i for i in issues if i.rule_id == "SQL022"]
        assert len(danger) == 0

    def test_update_with_real_where_multiline_no_trigger(self, analyzer):
        """UPDATE with real WHERE on different line should NOT trigger."""
        content = """UPDATE accounts SET balance = 0
WHERE account_id = 10;"""
        issues = analyzer.analyze("test.sql", content)
        danger = [i for i in issues if i.rule_id == "SQL023"]
        assert len(danger) == 0

    def test_multiple_statements_mixed(self, analyzer):
        """Multiple statements with mixed dangerous/safe should detect correctly."""
        content = """
DELETE FROM safe_table WHERE id = 1;
DELETE FROM danger_table;
UPDATE safe SET x = 1 WHERE y = 2;
UPDATE danger SET x = 1;
"""
        issues = analyzer.analyze("test.sql", content)
        sql022 = [i for i in issues if i.rule_id == "SQL022"]
        sql023 = [i for i in issues if i.rule_id == "SQL023"]
        assert len(sql022) == 1  # danger_table DELETE
        assert len(sql023) == 1  # danger UPDATE

    def test_statement_without_trailing_semicolon(self, analyzer):
        """Last statement without semicolon should still be analyzed."""
        content = "DELETE FROM users"
        issues = analyzer.analyze("test.sql", content)
        danger = [i for i in issues if i.rule_id == "SQL022"]
        assert len(danger) == 1
