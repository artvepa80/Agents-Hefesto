"""
Security Vulnerability Analyzer

Detects 6 types of security issues:
1. Hardcoded secrets (API keys, passwords)
2. SQL injection risks (string concatenation in queries)
3. eval() usage (dangerous code execution)
4. pickle usage (unsafe deserialization)
5. assert in production code
6. bare except clauses (Exception swallowing)

Copyright © 2025 Narapa LLC, Miami, Florida
"""

import re
from typing import List

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)
from hefesto.core.ast.generic_ast import GenericAST, NodeType


class SecurityAnalyzer:
    """Analyzes code for security vulnerabilities."""

    # Patterns for detecting secrets
    SECRET_PATTERNS = [
        (r"api[_-]?key\s*=\s*['\"]([a-zA-Z0-9_\-]{20,})['\"]", "API key"),
        (r"secret[_-]?key\s*=\s*['\"]([a-zA-Z0-9_\-]{20,})['\"]", "Secret key"),
        (r"password\s*=\s*['\"]([^'\"]{8,})['\"]", "Password"),
        (r"token\s*=\s*['\"]([a-zA-Z0-9_\-]{20,})['\"]", "Token"),
        (r"sk-[a-zA-Z0-9]{20,}", "OpenAI API key"),
        (r"ghp_[a-zA-Z0-9]{36}", "GitHub token"),
        (r"AWS[A-Z0-9]{16,}", "AWS key"),
    ]

    def analyze(self, tree: GenericAST, file_path: str, code: str) -> List[AnalysisIssue]:
        """Analyze code for security vulnerabilities."""
        issues = []

        issues.extend(self._check_hardcoded_secrets(tree, file_path, code))
        issues.extend(self._check_sql_injection(tree, file_path, code))
        issues.extend(self._check_eval_usage(tree, file_path, code))

        if tree.language == "python":
            issues.extend(self._check_pickle_usage(tree, file_path))
            issues.extend(self._check_assert_usage(tree, file_path))
            issues.extend(self._check_bare_except(tree, file_path))

        return issues

    def _check_hardcoded_secrets(
        self, tree: GenericAST, file_path: str, code: str
    ) -> List[AnalysisIssue]:
        """Detect hardcoded secrets in code."""
        issues = []

        for line_num, line in enumerate(code.split("\n"), start=1):
            for pattern, secret_type in self.SECRET_PATTERNS:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    # Skip if it's in a test file or example
                    if "test" in file_path.lower() or "example" in file_path.lower():
                        continue

                    issues.append(
                        AnalysisIssue(
                            file_path=file_path,
                            line=line_num,
                            column=line.find(match.group(0)),
                            issue_type=AnalysisIssueType.HARDCODED_SECRET,
                            severity=AnalysisIssueSeverity.CRITICAL,
                            message=f"Hardcoded {secret_type} detected",
                            suggestion="Move to environment variable or secrets manager:\n"
                            f"Use: os.getenv('{secret_type.upper().replace(' ', '_')}')\n"
                            "Or use a secrets management service like AWS Secrets Manager",
                            metadata={"secret_type": secret_type},
                        )
                    )

        return issues

    def _check_sql_injection(
        self, tree: GenericAST, file_path: str, code: str
    ) -> List[AnalysisIssue]:
        """Detect potential SQL injection vulnerabilities."""
        issues = []

        sql_keywords = ["SELECT", "INSERT", "UPDATE", "DELETE", "FROM", "WHERE"]
        for line_num, line in enumerate(code.split("\n"), start=1):
            line_upper = line.upper()
            if any(keyword in line_upper for keyword in sql_keywords):
                if "+" in line or "%" in line or "${" in line or "`" in line:
                    issues.append(
                        AnalysisIssue(
                            file_path=file_path,
                            line=line_num,
                            column=0,
                            issue_type=AnalysisIssueType.SQL_INJECTION_RISK,
                            severity=AnalysisIssueSeverity.HIGH,
                            message="Potential SQL injection via string concatenation",
                            suggestion="Use parameterized queries with placeholders",
                            metadata={"pattern": "sql_concatenation"},
                        )
                    )

        return issues

    def _check_eval_usage(self, tree: GenericAST, file_path: str, code: str) -> List[AnalysisIssue]:
        """Detect dangerous eval() usage."""
        issues = []

        patterns = [
            (r"\beval\s*\(", "eval"),
            (r"\bexec\s*\(", "exec"),
        ]

        for line_num, line in enumerate(code.split("\n"), start=1):
            for pattern, func_name in patterns:
                if re.search(pattern, line):
                    issues.append(
                        AnalysisIssue(
                            file_path=file_path,
                            line=line_num,
                            column=0,
                            issue_type=AnalysisIssueType.EVAL_USAGE,
                            severity=AnalysisIssueSeverity.CRITICAL,
                            message=f"Dangerous {func_name}() usage detected",
                            suggestion="Avoid eval/exec. Use safe alternatives:\n"
                            "- ast.literal_eval() for literals\n"
                            "- json.loads() for JSON\n"
                            "- Implement proper parsing logic",
                            metadata={"function": func_name},
                        )
                    )

        return issues

    def _check_pickle_usage(self, tree: GenericAST, file_path: str) -> List[AnalysisIssue]:
        """Detect unsafe pickle usage."""
        issues = []

        for node in tree.walk():
            if node.type == NodeType.IMPORT:
                if "pickle" in node.text:
                    issues.append(
                        AnalysisIssue(
                            file_path=file_path,
                            line=node.line_start,
                            column=node.column_start,
                            issue_type=AnalysisIssueType.PICKLE_USAGE,
                            severity=AnalysisIssueSeverity.HIGH,
                            message="Unsafe pickle module usage",
                            suggestion="Use safer alternatives:\n"
                            "- json module for simple data\n"
                            "- msgpack for binary data\n"
                            "- protobuf for structured data\n"
                            "Only use pickle with trusted data sources",
                            metadata={"module": "pickle"},
                        )
                    )

        return issues

    def _check_assert_usage(self, tree: GenericAST, file_path: str) -> List[AnalysisIssue]:
        """Detect assert statements in production code."""
        issues = []

        if "test" in file_path.lower():
            return issues

        for node in tree.walk():
            if "assert " in node.text.lower() and node.type != NodeType.COMMENT:
                issues.append(
                    AnalysisIssue(
                        file_path=file_path,
                        line=node.line_start,
                        column=node.column_start,
                        issue_type=AnalysisIssueType.ASSERT_IN_PRODUCTION,
                        severity=AnalysisIssueSeverity.MEDIUM,
                        message="Assert statement in production code",
                        suggestion="Use explicit checks with proper error handling:\n"
                        "if not condition:\n"
                        "    raise ValueError('Clear error message')",
                        metadata={"type": "assert"},
                    )
                )

        return issues

    def _check_bare_except(self, tree: GenericAST, file_path: str) -> List[AnalysisIssue]:
        """Detect bare except clauses that swallow all exceptions."""
        issues = []

        for node in tree.walk():
            if node.type == NodeType.CATCH:
                if re.search(r"except\s*:", node.text):
                    issues.append(
                        AnalysisIssue(
                            file_path=file_path,
                            line=node.line_start,
                            column=node.column_start,
                            issue_type=AnalysisIssueType.BARE_EXCEPT,
                            severity=AnalysisIssueSeverity.MEDIUM,
                            message="Bare except clause catches all exceptions",
                            suggestion="Catch specific exceptions:\n"
                            "try:\n"
                            "    ...\n"
                            "except (ValueError, TypeError) as e:\n"
                            "    handle_error(e)",
                            metadata={"type": "bare_except"},
                        )
                    )

        return issues


__all__ = ["SecurityAnalyzer"]
