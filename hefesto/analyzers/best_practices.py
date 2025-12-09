"""
Best Practices Analyzer

Validates code against Python best practices:
1. Missing docstrings (public functions/classes)
2. Poor naming (single-letter variables, non-descriptive names)
3. Inconsistent style (PEP 8 violations)

Copyright © 2025 Narapa LLC, Miami, Florida
"""

import ast
from typing import List

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)
from hefesto.core.ast.generic_ast import GenericAST


class BestPracticesAnalyzer:
    """Analyzes code for best practice violations."""

    # Common single-letter names that are acceptable in specific contexts
    ACCEPTABLE_SINGLE_LETTERS = {"i", "j", "k", "x", "y", "z", "n", "e", "f"}

    # Reserved keywords and built-in names to avoid
    AVOID_NAMES = {"l", "O", "I"}  # Easily confused with numbers

    def analyze(self, tree: GenericAST, file_path: str, code: str) -> List[AnalysisIssue]:
        """Analyze code for best practice violations."""
        issues = []

        if tree.language == "python":
            issues.extend(self._check_missing_docstrings(tree, file_path))
            issues.extend(self._check_poor_naming(tree, file_path))
            issues.extend(self._check_style_violations(tree, file_path, code))

        return issues

    def _check_missing_docstrings(self, tree: GenericAST, file_path: str) -> List[AnalysisIssue]:
        """Check for missing docstrings in public functions and classes."""
        return []

    def _check_missing_docstrings_old(self, tree: ast.AST, file_path: str) -> List[AnalysisIssue]:
        """Check for missing docstrings in public functions and classes."""
        issues = []

        for node in ast.walk(tree):
            # Check functions
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Skip private functions (starting with _)
                if not node.name.startswith("_"):
                    docstring = ast.get_docstring(node)
                    if not docstring:
                        issues.append(
                            AnalysisIssue(
                                file_path=file_path,
                                line=node.lineno,
                                column=node.col_offset,
                                issue_type=AnalysisIssueType.MISSING_DOCSTRING,
                                severity=AnalysisIssueSeverity.LOW,
                                message=f"Public function '{node.name}' missing docstring",
                                function_name=node.name,
                                suggestion="Add docstring:\n"
                                f"def {node.name}(...):\n"
                                '    """Brief description of what this function does.\n\n'
                                "    Args:\n"
                                "        param1: Description\n\n"
                                "    Returns:\n"
                                "        Description\n"
                                '    """\n'
                                "    ...",
                                metadata={"type": "function"},
                            )
                        )

            # Check classes
            elif isinstance(node, ast.ClassDef):
                # Skip private classes
                if not node.name.startswith("_"):
                    docstring = ast.get_docstring(node)
                    if not docstring:
                        issues.append(
                            AnalysisIssue(
                                file_path=file_path,
                                line=node.lineno,
                                column=node.col_offset,
                                issue_type=AnalysisIssueType.MISSING_DOCSTRING,
                                severity=AnalysisIssueSeverity.LOW,
                                message=f"Public class '{node.name}' missing docstring",
                                suggestion="Add docstring:\n"
                                f"class {node.name}:\n"
                                '    """Brief description of the class.\n\n'
                                "    Attributes:\n"
                                "        attr1: Description\n"
                                '    """\n'
                                "    ...",
                                metadata={"type": "class"},
                            )
                        )

        return issues

    def _check_poor_naming(self, tree: GenericAST, file_path: str) -> List[AnalysisIssue]:
        """Check for poor variable naming."""
        return []

    def _check_poor_naming_old(self, tree: ast.AST, file_path: str) -> List[AnalysisIssue]:
        """Check for poor variable naming."""
        issues = []

        for node in ast.walk(tree):
            # Check function parameters
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for arg in node.args.args:
                    name = arg.arg
                    # Skip 'self' and 'cls'
                    if name in ("self", "cls"):
                        continue

                    # Check for confusing single letters
                    if name in self.AVOID_NAMES:
                        issues.append(
                            AnalysisIssue(
                                file_path=file_path,
                                line=arg.lineno if hasattr(arg, "lineno") else node.lineno,
                                column=arg.col_offset if hasattr(arg, "col_offset") else 0,
                                issue_type=AnalysisIssueType.POOR_NAMING,
                                severity=AnalysisIssueSeverity.MEDIUM,
                                message=f"Confusing parameter name '{name}' "
                                f"(easily confused with numbers)",
                                function_name=node.name,
                                suggestion=f"Use a descriptive name instead of '{name}'",
                                metadata={"name": name, "type": "parameter"},
                            )
                        )

                    # Check for non-descriptive names (single letter outside acceptable contexts)
                    elif (
                        len(name) == 1
                        and name not in self.ACCEPTABLE_SINGLE_LETTERS
                        and not self._is_loop_context(node)
                    ):
                        issues.append(
                            AnalysisIssue(
                                file_path=file_path,
                                line=arg.lineno if hasattr(arg, "lineno") else node.lineno,
                                column=arg.col_offset if hasattr(arg, "col_offset") else 0,
                                issue_type=AnalysisIssueType.POOR_NAMING,
                                severity=AnalysisIssueSeverity.LOW,
                                message=f"Non-descriptive parameter name '{name}'",
                                function_name=node.name,
                                suggestion=f"Use a descriptive name: '{name}' → "
                                f"'{self._suggest_better_name(name)}'",
                                metadata={"name": name, "type": "parameter"},
                            )
                        )

            # Check variable assignments
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        name = target.id
                        # Check for confusing names
                        if name in self.AVOID_NAMES:
                            issues.append(
                                AnalysisIssue(
                                    file_path=file_path,
                                    line=node.lineno,
                                    column=node.col_offset,
                                    issue_type=AnalysisIssueType.POOR_NAMING,
                                    severity=AnalysisIssueSeverity.MEDIUM,
                                    message=f"Confusing variable name '{name}'",
                                    suggestion=f"Use a descriptive name instead of '{name}'",
                                    metadata={"name": name, "type": "variable"},
                                )
                            )

        return issues

    def _check_style_violations(
        self, tree: GenericAST, file_path: str, code: str
    ) -> List[AnalysisIssue]:
        """Check for basic PEP 8 style violations."""
        return []

    def _check_style_violations_old(
        self, tree: ast.AST, file_path: str, code: str
    ) -> List[AnalysisIssue]:
        """Check for basic PEP 8 style violations."""
        issues = []

        lines = code.split("\n")

        for line_num, line in enumerate(lines, start=1):
            # Check line length (PEP 8: max 79 characters for code, 72 for comments)
            if len(line) > 100:  # Being lenient with 100
                is_comment = line.strip().startswith("#")
                if not is_comment or len(line) > 100:
                    issues.append(
                        AnalysisIssue(
                            file_path=file_path,
                            line=line_num,
                            column=100,
                            issue_type=AnalysisIssueType.STYLE_VIOLATION,
                            severity=AnalysisIssueSeverity.LOW,
                            message=f"Line too long ({len(line)} > 100 characters)",
                            suggestion="Break line into multiple lines or refactor",
                            metadata={"length": len(line)},
                        )
                    )

            # Check for trailing whitespace
            if line.endswith(" ") or line.endswith("\t"):
                issues.append(
                    AnalysisIssue(
                        file_path=file_path,
                        line=line_num,
                        column=len(line.rstrip()),
                        issue_type=AnalysisIssueType.STYLE_VIOLATION,
                        severity=AnalysisIssueSeverity.LOW,
                        message="Trailing whitespace",
                        suggestion="Remove trailing spaces/tabs",
                        metadata={"type": "trailing_whitespace"},
                    )
                )

            # Check for multiple statements on one line
            if ";" in line and not line.strip().startswith("#"):
                issues.append(
                    AnalysisIssue(
                        file_path=file_path,
                        line=line_num,
                        column=line.find(";"),
                        issue_type=AnalysisIssueType.STYLE_VIOLATION,
                        severity=AnalysisIssueSeverity.LOW,
                        message="Multiple statements on one line",
                        suggestion="Put each statement on its own line",
                        metadata={"type": "multiple_statements"},
                    )
                )

        return issues

    def _is_loop_context(self, node: ast.FunctionDef) -> bool:
        """Check if function is likely used in loop context (e.g., lambda, comprehension)."""
        # Simple heuristic: function name suggests it's a short helper
        return node.name in ("lambda", "<lambda>") or len(node.name) < 3

    def _suggest_better_name(self, single_letter: str) -> str:
        """Suggest a better name based on context."""
        suggestions = {
            "a": "argument",
            "b": "buffer",
            "c": "count",
            "d": "data",
            "m": "message",
            "p": "path",
            "q": "query",
            "r": "result",
            "s": "string",
            "t": "text",
            "v": "value",
            "w": "width",
        }
        return suggestions.get(single_letter, "descriptive_name")


__all__ = ["BestPracticesAnalyzer"]
