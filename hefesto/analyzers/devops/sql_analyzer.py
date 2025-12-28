"""
SQL Analyzer for Hefesto DevOps Support (internal).

Detects SQL security and quality issues:
- SQL injection patterns (dynamic SQL, string concatenation)
- Hardcoded credentials (passwords in connection strings)
- Dangerous operations (DROP/TRUNCATE/DELETE without WHERE)
- SELECT * usage (performance anti-pattern)
- Overly permissive grants (GRANT ALL)

Copyright 2025 Narapa LLC, Miami, Florida
"""

import re
from typing import List, Optional, Tuple

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)


class SqlAnalyzer:
    ENGINE = "internal:sql_analyzer"

    # SQL Injection patterns
    INJECTION_PATTERNS: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(r"\bEXEC(?:UTE)?\s*\(\s*['\"]?\s*\+", re.IGNORECASE),
            "Dynamic SQL with string concatenation (SQL injection risk)",
            0.95,
            AnalysisIssueSeverity.CRITICAL,
            "SQL001",
        ),
        (
            re.compile(r"\bEXEC(?:UTE)?\s+(?:sp_executesql|xp_cmdshell)", re.IGNORECASE),
            "Dynamic SQL execution (potential injection vector)",
            0.88,
            AnalysisIssueSeverity.HIGH,
            "SQL002",
        ),
        (
            re.compile(r"(?:SELECT|INSERT|UPDATE|DELETE|WHERE)\s+.*\|\|.*\$", re.IGNORECASE),
            "String concatenation in SQL query (injection risk)",
            0.85,
            AnalysisIssueSeverity.HIGH,
            "SQL003",
        ),
        (
            re.compile(r"(?:f['\"]|%s|%d|\{\}).*(?:SELECT|INSERT|UPDATE|DELETE)", re.IGNORECASE),
            "Format string in SQL query (potential injection)",
            0.80,
            AnalysisIssueSeverity.HIGH,
            "SQL004",
        ),
    ]

    # Credential exposure patterns
    CREDENTIAL_PATTERNS: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(r"\bpassword\s*=\s*['\"][^'\"]{4,}['\"]", re.IGNORECASE),
            "Hardcoded password in SQL/connection string",
            0.92,
            AnalysisIssueSeverity.CRITICAL,
            "SQL010",
        ),
        (
            re.compile(r"\bpwd\s*=\s*['\"][^'\"]{4,}['\"]", re.IGNORECASE),
            "Hardcoded password (pwd) in connection string",
            0.90,
            AnalysisIssueSeverity.CRITICAL,
            "SQL011",
        ),
        (
            re.compile(r"(?:mysql|postgres|sqlserver|oracle)://[^:]+:[^@]+@", re.IGNORECASE),
            "Database URL with embedded credentials",
            0.95,
            AnalysisIssueSeverity.CRITICAL,
            "SQL012",
        ),
    ]

    # Dangerous operations patterns
    DANGEROUS_PATTERNS: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(
                r"\bDROP\s+(?:TABLE|DATABASE|SCHEMA)\b(?!.*\bIF\s+EXISTS\b)",
                re.IGNORECASE | re.DOTALL,
            ),
            "DROP statement without IF EXISTS (data loss risk)",
            0.85,
            AnalysisIssueSeverity.HIGH,
            "SQL020",
        ),
        (
            re.compile(r"\bTRUNCATE\s+TABLE\b", re.IGNORECASE),
            "TRUNCATE TABLE removes all data without logging",
            0.88,
            AnalysisIssueSeverity.HIGH,
            "SQL021",
        ),
        (
            re.compile(r"\bDELETE\s+FROM\s+\w+\b(?!.*\bWHERE\b)", re.IGNORECASE | re.DOTALL),
            "DELETE without WHERE clause (deletes all rows)",
            0.92,
            AnalysisIssueSeverity.CRITICAL,
            "SQL022",
        ),
        (
            re.compile(r"\bUPDATE\s+\w+\s+SET\b(?!.*\bWHERE\b)", re.IGNORECASE | re.DOTALL),
            "UPDATE without WHERE clause (updates all rows)",
            0.90,
            AnalysisIssueSeverity.CRITICAL,
            "SQL023",
        ),
    ]

    # Quality/Performance patterns
    QUALITY_PATTERNS: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(r"\bSELECT\s+\*\s+FROM\b", re.IGNORECASE),
            "SELECT * is a performance anti-pattern",
            0.75,
            AnalysisIssueSeverity.LOW,
            "SQL030",
        ),
        (
            re.compile(r"\bSELECT\s+.*\bINTO\s+#", re.IGNORECASE),
            "SELECT INTO temp table (consider explicit CREATE)",
            0.65,
            AnalysisIssueSeverity.LOW,
            "SQL031",
        ),
    ]

    # Permission patterns
    PERMISSION_PATTERNS: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(r"\bGRANT\s+ALL\s+(?:PRIVILEGES\s+)?ON\b", re.IGNORECASE),
            "GRANT ALL gives excessive permissions",
            0.88,
            AnalysisIssueSeverity.HIGH,
            "SQL040",
        ),
        (
            re.compile(r"\bGRANT\s+.*\bTO\s+['\"]?public['\"]?", re.IGNORECASE),
            "GRANT to PUBLIC exposes to all users",
            0.90,
            AnalysisIssueSeverity.HIGH,
            "SQL041",
        ),
        (
            re.compile(r"\bGRANT\s+.*\bWITH\s+GRANT\s+OPTION\b", re.IGNORECASE),
            "WITH GRANT OPTION allows privilege escalation",
            0.85,
            AnalysisIssueSeverity.MEDIUM,
            "SQL042",
        ),
    ]

    def _iter_sql_statements(self, content: str) -> List[Tuple[str, int, int]]:
        """
        Split SQL content into statements by semicolon, respecting quotes.
        Returns list of (statement_text, start_line, start_col) 1-based.
        """
        NL = chr(10)
        TAB = chr(9)
        CR = chr(13)

        statements: List[Tuple[str, int, int]] = []
        in_single = False
        in_double = False

        buf: List[str] = []
        line = 1
        col = 1

        stmt_start_line = 1
        stmt_start_col = 1
        started = False

        def flush():
            nonlocal buf, started
            text = "".join(buf).strip()
            if text:
                statements.append((text, stmt_start_line, stmt_start_col))
            buf = []
            started = False

        for ch in content:
            if (not started) and (ch not in (" ", TAB, CR, NL)):
                stmt_start_line, stmt_start_col = line, col
                started = True

            if ch == "'" and (not in_double):
                in_single = not in_single
            elif ch == '"' and (not in_single):
                in_double = not in_double

            if ch == ";" and (not in_single) and (not in_double):
                buf.append(ch)
                flush()
            else:
                buf.append(ch)

            if ch == NL:
                line += 1
                col = 1
            else:
                col += 1

        flush()
        return statements

    def _pos_from_stmt_offset(
        self, stmt: str, stmt_line: int, stmt_col: int, offset: int
    ) -> Tuple[int, int]:
        """Convert character offset inside stmt to (line, col) 1-based."""
        NL = chr(10)
        prefix = stmt[:offset]
        if NL not in prefix:
            return stmt_line, stmt_col + offset

        line_offset = prefix.count(NL)
        last_nl = prefix.rfind(NL)
        col_in_line = len(prefix) - last_nl
        return stmt_line + line_offset, col_in_line

    def _create_issue(
        self,
        file_path: str,
        line: int,
        column: int,
        issue_type: AnalysisIssueType,
        severity: AnalysisIssueSeverity,
        message: str,
        suggestion: str,
        confidence: float,
        rule_id: str,
        line_content: Optional[str] = None,
    ) -> AnalysisIssue:
        md = {"line_content": (line_content or "").strip()[:200]}
        return AnalysisIssue(
            file_path=file_path,
            line=line,
            column=column,
            issue_type=issue_type,
            severity=severity,
            message=message,
            suggestion=suggestion,
            engine=self.ENGINE,
            confidence=confidence,
            rule_id=rule_id,
            metadata=md,
        )

    def analyze(self, file_path: str, content: str) -> List[AnalysisIssue]:
        issues: List[AnalysisIssue] = []
        lines = content.split("\n")

        for line_num, line in enumerate(lines, start=1):
            # Skip empty lines and comments
            stripped = line.strip()
            if not stripped or stripped.startswith("--") or stripped.startswith("#"):
                continue

            # Check injection patterns
            for pattern, msg, conf, sev, rule in self.INJECTION_PATTERNS:
                if pattern.search(line):
                    issues.append(
                        self._create_issue(
                            file_path=file_path,
                            line=line_num,
                            column=1,
                            issue_type=AnalysisIssueType.SQL_INJECTION_RISK,
                            severity=sev,
                            message=msg,
                            suggestion=(
                                "Use parameterized queries or prepared statements "
                                "instead of string concatenation."
                            ),
                            confidence=conf,
                            rule_id=rule,
                            line_content=line,
                        )
                    )
                    break

            # Check credential patterns
            for pattern, msg, conf, sev, rule in self.CREDENTIAL_PATTERNS:
                if pattern.search(line):
                    issues.append(
                        self._create_issue(
                            file_path=file_path,
                            line=line_num,
                            column=1,
                            issue_type=AnalysisIssueType.HARDCODED_SECRET,
                            severity=sev,
                            message=msg,
                            suggestion=(
                                "Use environment variables or secret management "
                                "for database credentials."
                            ),
                            confidence=conf,
                            rule_id=rule,
                            line_content=line,
                        )
                    )
                    break

            # Check quality patterns
            for pattern, msg, conf, sev, rule in self.QUALITY_PATTERNS:
                if pattern.search(line):
                    issues.append(
                        self._create_issue(
                            file_path=file_path,
                            line=line_num,
                            column=1,
                            issue_type=AnalysisIssueType.SQL_SELECT_STAR,
                            severity=sev,
                            message=msg,
                            suggestion=(
                                "Specify explicit column names for better "
                                "performance and maintainability."
                            ),
                            confidence=conf,
                            rule_id=rule,
                            line_content=line,
                        )
                    )
                    break

            # Check permission patterns
            for pattern, msg, conf, sev, rule in self.PERMISSION_PATTERNS:
                if pattern.search(line):
                    issues.append(
                        self._create_issue(
                            file_path=file_path,
                            line=line_num,
                            column=1,
                            issue_type=AnalysisIssueType.SQL_OVERLY_PERMISSIVE_GRANT,
                            severity=sev,
                            message=msg,
                            suggestion=(
                                "Apply least privilege principle with specific "
                                "permissions and roles."
                            ),
                            confidence=conf,
                            rule_id=rule,
                            line_content=line,
                        )
                    )
                    break

        # Statement-level checks (dangerous ops) for multi-line WHERE handling
        NL = chr(10)
        statements = self._iter_sql_statements(content)
        for stmt, stmt_line, stmt_col in statements:
            # Remove only leading full-line comments (preserves offsets within scan)
            stmt_lines = stmt.splitlines(True)  # keep newlines
            skip = 0
            while skip < len(stmt_lines):
                s = stmt_lines[skip].strip()
                if not s or s.startswith("--") or s.startswith("#"):
                    skip += 1
                else:
                    break

            stmt_scan = "".join(stmt_lines[skip:])
            if not stmt_scan.strip():
                continue

            scan_start_line = stmt_line + skip
            scan_start_col = stmt_col if skip == 0 else 1

            for pattern, msg, conf, sev, rule in self.DANGEROUS_PATTERNS:
                mm = pattern.search(stmt_scan)
                if mm:
                    if rule == "SQL022":
                        issue_type = AnalysisIssueType.SQL_DELETE_WITHOUT_WHERE
                    elif rule == "SQL023":
                        issue_type = AnalysisIssueType.SQL_UPDATE_WITHOUT_WHERE
                    else:
                        issue_type = AnalysisIssueType.SQL_DROP_WITHOUT_WHERE

                    issue_line, issue_col = self._pos_from_stmt_offset(
                        stmt_scan, scan_start_line, scan_start_col, mm.start()
                    )

                    issues.append(
                        self._create_issue(
                            file_path=file_path,
                            line=issue_line,
                            column=issue_col,
                            issue_type=issue_type,
                            severity=sev,
                            message=msg,
                            suggestion=(
                                "Add WHERE clause or IF EXISTS to prevent " "accidental data loss."
                            ),
                            confidence=conf,
                            rule_id=rule,
                            line_content=stmt_scan.split(NL)[0] if stmt_scan else "",
                        )
                    )
                    break

        return issues


__all__ = ["SqlAnalyzer"]
