"""
Tests for Patch D: fail-on gate exit code and EVAL false positive fix.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from hefesto.analyzers.security import SecurityAnalyzer
from hefesto.core.ast.generic_ast import GenericAST, GenericNode, NodeType


def _find_repo_root() -> Path:
    """Find repository root by searching upward for pyproject.toml."""
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("Could not find repo root (pyproject.toml not found)")


class TestFailOnExitCode:
    """Tests for --fail-on CLI exit code behavior."""

    def test_fail_on_critical_returns_exit_1_when_critical_found(self):
        """When --fail-on CRITICAL and CRITICAL issues exist, exit code should be 2."""
        # Create a temp file with actual eval() call (CRITICAL issue)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write('result = eval("1+1")\n')
            temp_file = f.name

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "hefesto.cli.main",
                    "analyze",
                    temp_file,
                    "--fail-on",
                    "CRITICAL",
                    "--quiet",
                ],
                capture_output=True,
                text=True,
                cwd=_find_repo_root(),
            )
            # Should exit with code 2 for gate failure
            assert result.returncode == 1, f"Expected exit code 1, got {result.returncode}"
        finally:
            Path(temp_file).unlink()

    def test_fail_on_critical_returns_exit_0_when_no_critical(self):
        """When --fail-on CRITICAL and no CRITICAL issues, exit code should be 0."""
        # Create a temp file with no issues
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write('def hello():\n    return "world"\n')
            temp_file = f.name

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "hefesto.cli.main",
                    "analyze",
                    temp_file,
                    "--fail-on",
                    "CRITICAL",
                    "--quiet",
                ],
                capture_output=True,
                text=True,
                cwd=_find_repo_root(),
            )
            # Should exit with code 0 (no CRITICAL issues)
            assert result.returncode == 0, f"Expected exit code 0, got {result.returncode}"
        finally:
            Path(temp_file).unlink()


class TestEvalFalsePositive:
    """Tests for EVAL_USAGE false positive fix."""

    @pytest.fixture
    def analyzer(self):
        return SecurityAnalyzer()

    @pytest.fixture
    def python_tree(self):
        """Create a minimal GenericAST for Python."""
        root = GenericNode(
            type=NodeType.UNKNOWN,
            name=None,
            text="",
            line_start=1,
            line_end=1,
            column_start=0,
            column_end=0,
            children=[],
        )
        return GenericAST(root=root, language="python", source="")

    def test_regex_pattern_does_not_trigger_eval_usage(self, analyzer, python_tree):
        """A file containing regex pattern for eval should NOT trigger EVAL_USAGE."""
        # This is the exact pattern from security.py that was causing false positive
        code = """
# Patterns for detecting eval
patterns = [
    (r"\\beval\\s*\\(", "eval"),
    (r"\\bexec\\s*\\(", "exec"),
]
"""
        issues = analyzer._check_eval_usage(python_tree, "test_file.py", code)

        eval_issues = [i for i in issues if i.issue_type.value == "EVAL_USAGE"]
        assert len(eval_issues) == 0, f"Regex pattern should not trigger. Found: {eval_issues}"

    def test_docstring_mentioning_eval_does_not_trigger(self, analyzer, python_tree):
        """A docstring mentioning eval() should NOT trigger EVAL_USAGE."""
        code = '''
def check_code():
    """Detect dangerous eval() usage in code."""
    pass
'''
        issues = analyzer._check_eval_usage(python_tree, "test_file.py", code)

        eval_issues = [i for i in issues if i.issue_type.value == "EVAL_USAGE"]
        assert len(eval_issues) == 0, f"Docstring should not trigger. Found: {eval_issues}"

    def test_comment_mentioning_eval_does_not_trigger(self, analyzer, python_tree):
        """A comment mentioning eval should NOT trigger EVAL_USAGE."""
        code = """
# Dangerous: never use eval() on user input
x = 1
"""
        issues = analyzer._check_eval_usage(python_tree, "test_file.py", code)

        eval_issues = [i for i in issues if i.issue_type.value == "EVAL_USAGE"]
        assert len(eval_issues) == 0, f"Comment should not trigger. Found: {eval_issues}"

    def test_actual_eval_call_triggers_eval_usage(self, analyzer, python_tree):
        """An actual eval() call MUST trigger EVAL_USAGE."""
        code = """
result = eval("1+1")
"""
        issues = analyzer._check_eval_usage(python_tree, "test_file.py", code)

        eval_issues = [i for i in issues if i.issue_type.value == "EVAL_USAGE"]
        assert (
            len(eval_issues) == 1
        ), f"Actual eval call should trigger once. Found: {len(eval_issues)}"
        assert eval_issues[0].severity.value == "CRITICAL"

    def test_actual_exec_call_triggers_eval_usage(self, analyzer, python_tree):
        """An actual exec() call MUST trigger EVAL_USAGE."""
        code = """
exec("print('hello')")
"""
        issues = analyzer._check_eval_usage(python_tree, "test_file.py", code)

        eval_issues = [i for i in issues if i.issue_type.value == "EVAL_USAGE"]
        assert (
            len(eval_issues) == 1
        ), f"Actual exec call should trigger once. Found: {len(eval_issues)}"

    def test_multiple_eval_calls_trigger_multiple_issues(self, analyzer, python_tree):
        """Multiple eval/exec calls should trigger multiple issues."""
        code = """
a = eval("1")
b = exec("x = 2")
c = eval("3")
"""
        issues = analyzer._check_eval_usage(python_tree, "test_file.py", code)

        eval_issues = [i for i in issues if i.issue_type.value == "EVAL_USAGE"]
        assert len(eval_issues) == 3, f"Expected 3 issues, found {len(eval_issues)}"
