"""
Security Vulnerability Analyzer

Detects 7 types of security issues:
1. Hardcoded secrets (API keys, passwords)
2. SQL injection risks (string concatenation in queries)
3. Command injection (os.system/subprocess with dynamic strings)
4. eval() usage (dangerous code execution)
5. pickle usage (unsafe deserialization)
6. assert in production code
7. bare except clauses (Exception swallowing)

Copyright © 2025 Narapa LLC, Miami, Florida
"""

import re
from typing import List, Tuple

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)
from hefesto.core.ast.generic_ast import GenericAST

# Sinks that indicate SQL strings are actually executed (not just built/logged).
_SQL_EXECUTE_SINKS = re.compile(
    r"\.\s*(?:execute|executemany|executescript|run|raw|mogrify)\s*\(",
    re.IGNORECASE,
)

# Command execution sinks (os.system, os.popen, subprocess with shell).
_CMD_INJECTION_SINKS = re.compile(
    r"\b(?:os\.system|os\.popen|subprocess\.call|subprocess\.Popen|subprocess\.run)\s*\("
)

_CMD_SHELL_TRUE = re.compile(r"\bshell\s*=\s*True\b")

# SQL keyword inside a string literal (single/double/triple quotes, f-strings).
_SQL_KW_IN_STRING = re.compile(
    r"""(?:f?(?:"{1,3}|'{1,3}))"""
    r"""[^"']*\b(?:SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\b""",
    re.IGNORECASE,
)

# Python ``%`` string-formatting operator: a closing quote followed by ``%``
# followed by an expression (variable, tuple, dict) — NOT a printf-style
# format specifier that is still part of the string literal.
#
# The key heuristic: a printf format-spec character is only a spec when
# *followed by a non-word character or end-of-line* (``%s`` → end of spec).
# If the character continues into an identifier (``% rows``, ``% uid``),
# it is the Python ``%`` operator with a variable argument.
#
# This distinguishes ``"..." % value`` (real Python interpolation — a
# genuine SQLi risk when concatenated into SQL) from
# ``cur.execute("SELECT WHERE id = %s", (x,))`` (a DB-API placeholder
# that lives entirely inside the string literal and is substituted
# server-side by the driver, not by Python). Phase 1c SQL_INJECTION FP fix.
_PY_PERCENT_OPERATOR = re.compile(r"""["']\s*%\s*(?!\s*[sdiouxXeEfFgGcrp%](?:\W|$))\S""")


def _sql_keyword_in_string(line: str) -> bool:
    """Return True if a SQL keyword appears inside a string literal on this line."""
    return bool(_SQL_KW_IN_STRING.search(line))


def _has_dynamic_concatenation(line: str) -> bool:
    """Return True if the line uses dynamic string building.

    The four signals of dynamic construction are:
    - f-string (``f"..."`` / ``f'...'``)
    - Python ``%`` operator after a closing quote (*not* DB-API placeholders
      like ``%s`` / ``%(name)s`` / ``%d`` which live inside the string and
      are substituted by the driver, not by Python)
    - ``.format(`` method call
    - explicit ``+`` concatenation near a quote

    DB-API-style placeholders are intentionally excluded from the ``%``
    signal because they describe a *parameterized* query — the opposite of
    a string-injection risk. This was the production false positive that
    motivated the Phase 1c precision cleanup.
    """
    if 'f"' in line or "f'" in line:
        return True
    if _PY_PERCENT_OPERATOR.search(line):
        return True
    if ".format(" in line:
        return True
    # String concat: any quote combined with + near the quote
    if "+" in line and ('"' in line or "'" in line):
        return True
    return False


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
        issues.extend(self._check_command_injection(tree, file_path, code))
        issues.extend(self._check_eval_usage(tree, file_path, code))

        if tree.language == "python":
            issues.extend(self._check_pickle_usage(tree, file_path, code))
            issues.extend(self._check_assert_usage(tree, file_path, code))
            issues.extend(self._check_bare_except(tree, file_path, code))

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

        Only flags lines where a SQL keyword appears inside a string literal
        AND the string uses dynamic concatenation (f-string, %, +, format).
        Requires a DB execute sink in the enclosing scope — lines without a
        nearby sink are skipped entirely to avoid false positives on logging,
        display, or comment text.
        """
        issues: List[AnalysisIssue] = []
        lines = code.split("\n")

        # Pre-compute: does this file contain any SQL execute sink at all?
        file_has_sink = bool(_SQL_EXECUTE_SINKS.search(code))
        if not file_has_sink:
            return issues

        # Build a map of function-scope boundaries (line ranges) for sink lookup.
        scope_sinks = self._build_scope_sink_map(lines)

        flagged_lines: set = set()

        for line_num, line in enumerate(lines, start=1):
            stripped = line.lstrip()

            # Skip comments
            if stripped.startswith("#") or stripped.startswith("//"):
                continue

            if not _sql_keyword_in_string(line):
                continue

            if not _has_dynamic_concatenation(line):
                continue

            # Require a DB execute sink in the enclosing scope (no file-level fallback)
            has_sink = self._scope_has_sink(line_num, scope_sinks, False)
            if not has_sink:
                continue

            flagged_lines.add(line_num)
            issues.append(
                AnalysisIssue(
                    file_path=file_path,
                    line=line_num,
                    column=0,
                    issue_type=AnalysisIssueType.SQL_INJECTION_RISK,
                    severity=AnalysisIssueSeverity.HIGH,
                    message="Potential SQL injection via string concatenation",
                    suggestion="Use parameterized queries with placeholders",
                    metadata={
                        "pattern": "sql_concatenation",
                        "sink_detected": True,
                    },
                )
            )

        # AST-based BinOp(Mod) check for Python: catches single-char
        # format-spec variables that the regex misses (Phase 1c debt).
        if tree is not None and tree.language == "python":
            issues.extend(
                self._check_sql_percent_binop(file_path, code, scope_sinks, flagged_lines)
            )

        return issues

    @staticmethod
    def _check_sql_percent_binop(
        file_path: str,
        code: str,
        scope_sinks: List[Tuple[int, int, bool]],
        already_flagged: set,
    ) -> List[AnalysisIssue]:
        """AST-based detection of ``"SQL ..." % var`` (BinOp with Mod).

        Complements the regex check by catching the single-char false
        negative class documented in Phase 1c: when the variable name
        is a single letter that matches a printf format-spec character
        (``s``, ``d``, ``i``, etc.), the regex classifier treats it as
        an in-string placeholder and skips the line.

        The AST approach is unambiguous: ``BinOp(op=Mod)`` with a string
        constant on the left side IS a Python ``%`` interpolation — it
        cannot be a DB-API placeholder (those are ``Call`` arguments to
        ``.execute(query, params)``).
        """
        import ast as python_ast

        issues: List[AnalysisIssue] = []
        try:
            py_tree = python_ast.parse(code)
        except SyntaxError:
            return issues

        sql_kw_re = re.compile(
            r"\b(?:SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\b",
            re.IGNORECASE,
        )

        for node in python_ast.walk(py_tree):
            if not isinstance(node, python_ast.BinOp):
                continue
            if not isinstance(node.op, python_ast.Mod):
                continue
            # Left side must be a string constant containing a SQL keyword
            left = node.left
            if not isinstance(left, python_ast.Constant) or not isinstance(left.value, str):
                continue
            if not sql_kw_re.search(left.value):
                continue

            line_num = node.lineno
            if line_num in already_flagged:
                continue

            # Require a DB execute sink in the enclosing scope
            has_sink = SecurityAnalyzer._scope_has_sink(line_num, scope_sinks, False)
            if not has_sink:
                continue

            issues.append(
                AnalysisIssue(
                    file_path=file_path,
                    line=line_num,
                    column=node.col_offset,
                    issue_type=AnalysisIssueType.SQL_INJECTION_RISK,
                    severity=AnalysisIssueSeverity.HIGH,
                    message="Potential SQL injection via string concatenation",
                    suggestion="Use parameterized queries with placeholders",
                    metadata={
                        "pattern": "sql_percent_binop",
                        "sink_detected": True,
                    },
                )
            )

        return issues

    @staticmethod
    def _build_scope_sink_map(lines: List[str]) -> List[Tuple[int, int, bool]]:
        """Return a list of (start_line, end_line, has_sink) for function scopes.

        Uses a simple indentation heuristic: a ``def `` or ``async def `` at
        column N starts a scope that extends until the next line at the same
        or lesser indentation (or EOF).
        """
        scopes: List[Tuple[int, int, bool]] = []
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
        scope_sinks: List[Tuple[int, int, bool]],
        file_has_sink: bool,
    ) -> bool:
        """Check whether *line_num* is in a scope that contains an execute sink."""
        for start, end, has_sink in scope_sinks:
            if start <= line_num <= end:
                return has_sink
        # Line is at module level → fall back to file-level check
        return file_has_sink

    def _check_command_injection(
        self, tree: GenericAST, file_path: str, code: str
    ) -> List[AnalysisIssue]:
        """Detect command injection via os.system/subprocess with dynamic strings.

        3-condition pattern (same as SQL injection):
        1. Line contains a command execution sink
        2. Line uses dynamic string concatenation
        3. For subprocess.*, requires shell=True (list form is safe)

        Known limitation: does not detect cross-line indirection where the
        string is built on one line and passed to the sink on another.
        Same limitation as SQL_INJECTION_RISK — acceptable for Phase 1.
        """
        issues: List[AnalysisIssue] = []
        lines = code.split("\n")

        for line_num, line in enumerate(lines, start=1):
            stripped = line.lstrip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue

            sink_match = _CMD_INJECTION_SINKS.search(line)
            if not sink_match:
                continue

            if not _has_dynamic_concatenation(line):
                continue

            # subprocess.call/Popen/run require shell=True to be dangerous
            sink_name = sink_match.group(0)
            if "subprocess." in sink_name:
                if not _CMD_SHELL_TRUE.search(line):
                    continue

            issues.append(
                AnalysisIssue(
                    file_path=file_path,
                    line=line_num,
                    column=0,
                    issue_type=AnalysisIssueType.COMMAND_INJECTION,
                    severity=AnalysisIssueSeverity.HIGH,
                    message="Potential command injection via string concatenation",
                    suggestion="Use subprocess with list arguments (no shell):\n"
                    "subprocess.run(['command', arg], check=True)",
                    metadata={"pattern": "command_concatenation"},
                )
            )

        return issues

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

    def _check_pickle_usage(
        self, tree: GenericAST, file_path: str, code: str = ""
    ) -> List[AnalysisIssue]:
        """Detect unsafe pickle module imports.

        Uses Python's ``ast`` module to match the exact module name ``pickle``
        (or ``cPickle``). The legacy detector walked the GenericAST with
        ``"pickle" in node.text`` as a substring, which caused false
        positives on any import whose module name *contained* the substring
        ``pickle`` — e.g. ``from unpickler_utils import safe_load`` or
        ``from hefesto_pro import PickleHandler``. Phase 1c FP fix.
        """
        issues: List[AnalysisIssue] = []

        if tree.language != "python" or not code:
            return issues

        import ast as python_ast

        try:
            py_tree = python_ast.parse(code)
        except SyntaxError:
            return issues

        def _report(line: int, col: int) -> None:
            issues.append(
                AnalysisIssue(
                    file_path=file_path,
                    line=line,
                    column=col,
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

        for node in python_ast.walk(py_tree):
            if isinstance(node, python_ast.Import):
                for alias in node.names:
                    if alias.name in ("pickle", "cPickle"):
                        _report(node.lineno, node.col_offset)
                        break
            elif isinstance(node, python_ast.ImportFrom):
                if node.module in ("pickle", "cPickle"):
                    _report(node.lineno, node.col_offset)

        return issues

    def _check_assert_usage(
        self, tree: GenericAST, file_path: str, code: str = ""
    ) -> List[AnalysisIssue]:
        """Detect assert statements in production code.

        Python files are analyzed via the built-in ``ast`` module so that
        only real ``ast.Assert`` statements are flagged — docstrings,
        comments, and string literals that merely *mention* the word
        ``assert`` no longer produce findings. This closes a high-volume
        false-positive class observed via dogfooding on the Hefesto repo
        itself (31 findings on ``hefesto/`` before the fix; 0 real
        assert statements in the offending files).

        Non-Python files are left untouched by this detector — ``assert``
        is a Python-specific keyword and other languages already have
        dedicated analyzers for their own contracts.
        """
        issues: List[AnalysisIssue] = []

        if "test" in file_path.lower():
            return issues

        if tree.language != "python" or not code:
            return issues

        import ast as python_ast

        try:
            py_tree = python_ast.parse(code)
        except SyntaxError:
            return issues

        for node in python_ast.walk(py_tree):
            if isinstance(node, python_ast.Assert):
                issues.append(
                    AnalysisIssue(
                        file_path=file_path,
                        line=node.lineno,
                        column=node.col_offset,
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

    def _check_bare_except(
        self, tree: GenericAST, file_path: str, code: str = ""
    ) -> List[AnalysisIssue]:
        """Detect bare ``except:`` clauses that swallow all exceptions.

        Uses ``ast.ExceptHandler`` on Python files to find handlers whose
        ``type`` is ``None`` (the AST representation of a bare ``except:``).
        The legacy detector used ``GenericAST.walk`` + a regex on
        ``node.text`` against ``NodeType.CATCH`` — empirical probing showed
        it emitted zero findings on real bare-except Python code, so the
        detector was effectively dead. Matches the same AST approach used
        by ``_check_eval_usage`` / ``_check_assert_usage`` / ``_check_pickle_usage``.
        """
        issues: List[AnalysisIssue] = []

        if tree.language != "python" or not code:
            return issues

        import ast as python_ast

        try:
            py_tree = python_ast.parse(code)
        except SyntaxError:
            return issues

        for node in python_ast.walk(py_tree):
            if isinstance(node, python_ast.ExceptHandler) and node.type is None:
                issues.append(
                    AnalysisIssue(
                        file_path=file_path,
                        line=node.lineno,
                        column=node.col_offset,
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
