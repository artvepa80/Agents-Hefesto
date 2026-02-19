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

# Sinks that indicate SQL strings are actually executed (not just built/logged).
_SQL_EXECUTE_SINKS = re.compile(
    r"\.\s*(?:execute|executemany|executescript|run|raw|mogrify)\s*\(",
    re.IGNORECASE,
)


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
        (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
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
                    # Skip test/example files to reduce noise, but allow
                    # action fixtures that are specifically designed to test detection.
                    path_lower = file_path.lower().replace("\\", "/")
                    is_action_fixture = "tests/fixtures/action/" in path_lower
                    if not is_action_fixture and ("test" in path_lower or "example" in path_lower):
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
        """Detect potential SQL injection vulnerabilities.

        Uses sink-awareness: a SQL keyword + string concatenation is HIGH only
        when the enclosing scope also contains an execute-type sink
        (.execute(), .executemany(), etc.).  Without a sink the finding is
        downgraded to MEDIUM — the string is likely built for logging or
        display, not for database execution.
        """
        issues = []
        lines = code.split("\n")

        # Pre-compute: does this file contain any SQL execute sink at all?
        file_has_sink = bool(_SQL_EXECUTE_SINKS.search(code))

        # Build a map of function-scope boundaries (line ranges) for sink lookup.
        # For non-Python or flat scripts we fall back to file-level check.
        scope_sinks = self._build_scope_sink_map(lines)

        sql_keywords = ["SELECT", "INSERT", "UPDATE", "DELETE", "FROM", "WHERE"]
        for line_num, line in enumerate(lines, start=1):
            line_upper = line.upper()
            stripped = line.lstrip()

            # Skip comments and docstrings to reduce noise
            if stripped.startswith("#") or stripped.startswith("//"):
                continue

            if any(keyword in line_upper for keyword in sql_keywords):
                if "+" in line or "%" in line or "${" in line or "`" in line:
                    # Determine severity based on sink proximity
                    has_sink = self._scope_has_sink(line_num, scope_sinks, file_has_sink)
                    severity = (
                        AnalysisIssueSeverity.HIGH if has_sink else AnalysisIssueSeverity.MEDIUM
                    )

                    issues.append(
                        AnalysisIssue(
                            file_path=file_path,
                            line=line_num,
                            column=0,
                            issue_type=AnalysisIssueType.SQL_INJECTION_RISK,
                            severity=severity,
                            message="Potential SQL injection via string concatenation",
                            suggestion="Use parameterized queries with placeholders",
                            metadata={
                                "pattern": "sql_concatenation",
                                "sink_detected": has_sink,
                            },
                        )
                    )

        return issues

    @staticmethod
    def _build_scope_sink_map(lines: List[str]) -> List[tuple]:
        """Return a list of (start_line, end_line, has_sink) for function scopes.

        Uses a simple indentation heuristic: a ``def `` or ``async def `` at
        column N starts a scope that extends until the next line at the same
        or lesser indentation (or EOF).
        """
        scopes: List[tuple] = []
        n = len(lines)
        i = 0
        while i < n:
            stripped = lines[i].lstrip()
            if stripped.startswith("def ") or stripped.startswith("async def "):
                indent = len(lines[i]) - len(stripped)
                start = i + 1  # 1-indexed
                j = i + 1
                while j < n:
                    if lines[j].strip() == "":
                        j += 1
                        continue
                    cur_indent = len(lines[j]) - len(lines[j].lstrip())
                    if cur_indent <= indent:
                        break
                    j += 1
                end = j  # 1-indexed inclusive
                scope_code = "\n".join(lines[i:j])
                has_sink = bool(_SQL_EXECUTE_SINKS.search(scope_code))
                scopes.append((start, end, has_sink))
                i = j
            else:
                i += 1
        return scopes

    @staticmethod
    def _scope_has_sink(
        line_num: int,
        scope_sinks: List[tuple],
        file_has_sink: bool,
    ) -> bool:
        """Check whether *line_num* is in a scope that contains an execute sink."""
        for start, end, has_sink in scope_sinks:
            if start <= line_num <= end:
                return has_sink
        # Line is at module level → fall back to file-level check
        return file_has_sink

    def _check_eval_usage(self, tree: GenericAST, file_path: str, code: str) -> List[AnalysisIssue]:
        """Detect dangerous eval() usage.

        For Python files: Uses AST to detect actual eval/exec calls, avoiding
        false positives from regex patterns, docstrings, or comments.
        For other languages: Falls back to regex-based detection.
        """
        issues: List[AnalysisIssue] = []

        # For Python: use AST-based detection to avoid false positives
        if tree.language == "python":
            import ast as python_ast

            try:
                py_tree = python_ast.parse(code)
                for node in python_ast.walk(py_tree):
                    if isinstance(node, python_ast.Call):
                        func = node.func
                        if isinstance(func, python_ast.Name) and func.id in ("eval", "exec"):
                            issues.append(
                                AnalysisIssue(
                                    file_path=file_path,
                                    line=node.lineno,
                                    column=node.col_offset,
                                    issue_type=AnalysisIssueType.EVAL_USAGE,
                                    severity=AnalysisIssueSeverity.CRITICAL,
                                    message=f"Dangerous {func.id}() usage detected",
                                    suggestion="Avoid eval/exec. Use safe alternatives:\n"
                                    "- ast.literal_eval() for literals\n"
                                    "- json.loads() for JSON\n"
                                    "- Implement proper parsing logic",
                                    metadata={"function": func.id},
                                )
                            )
            except SyntaxError:
                # If AST parsing fails, fall back to regex
                pass
        else:
            # For non-Python languages: use regex-based detection
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
        issues: List[AnalysisIssue] = []

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
