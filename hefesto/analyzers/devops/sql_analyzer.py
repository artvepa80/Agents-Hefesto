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
            re.compile(r"\bDROP\s+(?:TABLE|DATABASE|SCHEMA)\b(?!.*\bIF\s+EXISTS\b)", re.IGNORECASE),
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
            re.compile(r"\bDELETE\s+FROM\s+\w+\s*(?:;|$)", re.IGNORECASE),
            "DELETE without WHERE clause (deletes all rows)",
            0.92,
            AnalysisIssueSeverity.CRITICAL,
            "SQL022",
        ),
        (
            re.compile(r"\bUPDATE\s+\w+\s+SET\s+.*(?:;|$)(?!.*WHERE)", re.IGNORECASE),
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

            # Check dangerous patterns
            for pattern, msg, conf, sev, rule in self.DANGEROUS_PATTERNS:
                if pattern.search(line):
                    issues.append(
                        self._create_issue(
                            file_path=file_path,
                            line=line_num,
                            column=1,
                            issue_type=AnalysisIssueType.SQL_DROP_WITHOUT_WHERE,
                            severity=sev,
                            message=msg,
                            suggestion=(
                                "Add WHERE clause or IF EXISTS to prevent " "accidental data loss."
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
                            issue_type=AnalysisIssueType.TF_OVERLY_PERMISSIVE,
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

        return issues


__all__ = ["SqlAnalyzer"]
