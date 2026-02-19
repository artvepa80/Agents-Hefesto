"""Tests for deliverable (B): SQLi sink detection.

Verifies:
1. SQL concat WITH execute sink → HIGH
2. SQL concat WITHOUT execute sink → MEDIUM (downgraded)
3. Comment lines with SQL keywords are skipped
4. Existing secret detection is unaffected (regression guard)
"""

import pytest

from hefesto.analyzers.security import SecurityAnalyzer
from hefesto.core.analysis_models import AnalysisIssueSeverity, AnalysisIssueType


def _run_sqli_check(code: str, file_path: str = "app.py"):
    """Helper: run only _check_sql_injection on given code."""
    analyzer = SecurityAnalyzer()
    return analyzer._check_sql_injection(None, file_path, code)


# ---------------------------------------------------------------------------
# 1. SQL concat WITH execute sink → HIGH
# ---------------------------------------------------------------------------


class TestSinkDetected:
    def test_execute_in_same_function(self):
        code = '''\
def get_user(name):
    query = "SELECT * FROM users WHERE name = '" + name + "'"
    cursor.execute(query)
    return cursor.fetchone()
'''
        issues = _run_sqli_check(code)
        assert len(issues) >= 1
        high_issues = [i for i in issues if i.severity == AnalysisIssueSeverity.HIGH]
        assert len(high_issues) >= 1, "Should be HIGH when execute() sink is in scope"
        assert high_issues[0].metadata.get("sink_detected") is True

    def test_executemany_sink(self):
        code = '''\
def bulk_insert(rows):
    q = "INSERT INTO items (name) VALUES (%s)" % rows[0]
    conn.executemany(q, rows)
'''
        issues = _run_sqli_check(code)
        high = [i for i in issues if i.severity == AnalysisIssueSeverity.HIGH]
        assert len(high) >= 1, "executemany should count as a sink"

    def test_raw_query_sink(self):
        code = '''\
def raw_lookup(uid):
    sql = "SELECT * FROM accounts WHERE id = %s" % uid
    return Model.objects.raw(sql)
'''
        issues = _run_sqli_check(code)
        high = [i for i in issues if i.severity == AnalysisIssueSeverity.HIGH]
        assert len(high) >= 1, ".raw() should count as a sink"


# ---------------------------------------------------------------------------
# 2. SQL concat WITHOUT execute sink → MEDIUM
# ---------------------------------------------------------------------------


class TestNoSink:
    def test_string_building_for_logging(self):
        code = '''\
def build_debug_msg(table):
    msg = "SELECT count(*) FROM " + table
    logger.info(msg)
    return msg
'''
        issues = _run_sqli_check(code)
        assert len(issues) >= 1
        # All issues should be MEDIUM (no sink)
        for issue in issues:
            assert issue.severity == AnalysisIssueSeverity.MEDIUM, (
                f"Expected MEDIUM without sink, got {issue.severity}"
            )
            assert issue.metadata.get("sink_detected") is False

    def test_config_string_with_percent(self):
        code = '''\
# Database configuration
QUERY_TEMPLATE = "SELECT * FROM %s WHERE active = 1"
'''
        issues = _run_sqli_check(code)
        # The comment line should be skipped, but the QUERY_TEMPLATE line
        # has SQL keyword + %, so it flags — but as MEDIUM (no sink in file)
        for issue in issues:
            assert issue.severity == AnalysisIssueSeverity.MEDIUM

    def test_module_level_no_sink(self):
        code = '''\
SQL = "DELETE FROM sessions WHERE expired + interval"
print(SQL)
'''
        issues = _run_sqli_check(code)
        for issue in issues:
            assert issue.severity == AnalysisIssueSeverity.MEDIUM


# ---------------------------------------------------------------------------
# 3. Comment lines should be skipped
# ---------------------------------------------------------------------------


class TestCommentSkip:
    def test_python_comment_skipped(self):
        code = '''\
# SELECT * FROM users WHERE id = %s
x = 1
'''
        issues = _run_sqli_check(code)
        assert len(issues) == 0, "Comment lines should not trigger SQLi detection"

    def test_js_comment_skipped(self):
        code = '''\
// DELETE FROM table WHERE id = ${id}
const x = 1;
'''
        issues = _run_sqli_check(code, "app.js")
        assert len(issues) == 0, "JS comment lines should not trigger SQLi detection"


# ---------------------------------------------------------------------------
# 4. File-level sink fallback for module-level code
# ---------------------------------------------------------------------------


class TestFileLevelFallback:
    def test_module_level_with_execute_elsewhere(self):
        """Module-level SQL concat in a file that has execute() somewhere → HIGH."""
        code = '''\
QUERY = "SELECT * FROM users WHERE name = '" + username + "'"

def run():
    cursor.execute(QUERY)
'''
        issues = _run_sqli_check(code)
        # The QUERY line is at module level; file has execute() → HIGH
        high = [i for i in issues if i.severity == AnalysisIssueSeverity.HIGH]
        assert len(high) >= 1


# ---------------------------------------------------------------------------
# 5. Regression: secret detection unaffected
# ---------------------------------------------------------------------------


class TestSecretDetectionRegression:
    def test_secret_still_detected(self):
        """Ensure secret detection is not broken by SQLi changes."""
        from pathlib import Path

        fixtures = Path(__file__).parent / "fixtures" / "action"
        if not fixtures.exists():
            pytest.skip("Action fixtures not available")

        critical_file = fixtures / "critical_secret.py"
        if not critical_file.exists():
            pytest.skip("critical_secret.py fixture not available")

        code = critical_file.read_text()
        analyzer = SecurityAnalyzer()
        issues = analyzer._check_hardcoded_secrets(None, str(critical_file), code)
        secret_issues = [i for i in issues if i.issue_type == AnalysisIssueType.HARDCODED_SECRET]
        assert len(secret_issues) >= 1, "Secret detection must still work"
