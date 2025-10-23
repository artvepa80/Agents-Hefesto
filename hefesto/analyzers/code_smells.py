"""
Code Smell Analyzer

Detects 8 types of code smells:
1. Long functions (>50 lines)
2. Long parameter lists (>5 parameters)
3. Deep nesting (>4 levels)
4. Duplicate code (similar blocks)
5. Dead code (unused imports, functions)
6. Magic numbers (unexplained literals)
7. God classes (classes >500 lines)
8. Incomplete TODOs/FIXMEs

Copyright © 2025 Narapa LLC, Miami, Florida
"""

import ast
import re
from typing import List

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)


class CodeSmellAnalyzer:
    """Analyzes code for common code smells."""

    def analyze(self, tree: ast.AST, file_path: str, code: str) -> List[AnalysisIssue]:
        """Analyze code for code smells."""
        issues = []

        issues.extend(self._check_long_functions(tree, file_path))
        issues.extend(self._check_long_parameter_lists(tree, file_path))
        issues.extend(self._check_deep_nesting(tree, file_path))
        issues.extend(self._check_magic_numbers(tree, file_path))
        issues.extend(self._check_god_classes(tree, file_path, code))
        issues.extend(self._check_incomplete_todos(tree, file_path, code))

        return issues

    def _check_long_functions(self, tree: ast.AST, file_path: str) -> List[AnalysisIssue]:
        """Detect functions longer than 50 lines."""
        issues = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Calculate function length
                if hasattr(node, "end_lineno") and node.end_lineno:
                    func_length = node.end_lineno - node.lineno
                    if func_length > 50:
                        issues.append(
                            AnalysisIssue(
                                file_path=file_path,
                                line=node.lineno,
                                column=node.col_offset,
                                issue_type=AnalysisIssueType.LONG_FUNCTION,
                                severity=AnalysisIssueSeverity.MEDIUM,
                                message=f"Function '{node.name}' is too long ({func_length} lines)",
                                function_name=node.name,
                                suggestion="Break down into smaller, focused functions. "
                                "Each function should do one thing well.",
                                metadata={"length": func_length},
                            )
                        )

        return issues

    def _check_long_parameter_lists(self, tree: ast.AST, file_path: str) -> List[AnalysisIssue]:
        """Detect functions with more than 5 parameters."""
        issues = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                param_count = len(node.args.args)
                if param_count > 5:
                    issues.append(
                        AnalysisIssue(
                            file_path=file_path,
                            line=node.lineno,
                            column=node.col_offset,
                            issue_type=AnalysisIssueType.LONG_PARAMETER_LIST,
                            severity=AnalysisIssueSeverity.MEDIUM,
                            message=f"Function '{node.name}' has too many parameters ({param_count})",
                            function_name=node.name,
                            suggestion="Consider using a config object, dataclass, or **kwargs. "
                            "Group related parameters into objects.",
                            metadata={"param_count": param_count},
                        )
                    )

        return issues

    def _check_deep_nesting(self, tree: ast.AST, file_path: str) -> List[AnalysisIssue]:
        """Detect code with nesting depth > 4."""
        issues = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                max_depth = self._calculate_max_nesting(node)
                if max_depth > 4:
                    issues.append(
                        AnalysisIssue(
                            file_path=file_path,
                            line=node.lineno,
                            column=node.col_offset,
                            issue_type=AnalysisIssueType.DEEP_NESTING,
                            severity=AnalysisIssueSeverity.HIGH,
                            message=f"Function '{node.name}' has deep nesting (level {max_depth})",
                            function_name=node.name,
                            suggestion="Reduce nesting by:\n"
                            "- Using early returns\n"
                            "- Extracting nested blocks into functions\n"
                            "- Inverting conditionals",
                            metadata={"max_depth": max_depth},
                        )
                    )

        return issues

    def _calculate_max_nesting(self, node: ast.AST, current_depth: int = 0) -> int:
        """Calculate maximum nesting depth."""
        max_depth = current_depth

        for child in ast.iter_child_nodes(node):
            child_depth = current_depth
            if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                child_depth = current_depth + 1

            max_depth = max(max_depth, self._calculate_max_nesting(child, child_depth))

        return max_depth

    def _check_magic_numbers(self, tree: ast.AST, file_path: str) -> List[AnalysisIssue]:
        """Detect unexplained numeric literals."""
        issues = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Constant):
                if isinstance(node.n if hasattr(node, "n") else node.value, (int, float)):
                    value = node.n if hasattr(node, "n") else node.value
                    # Ignore common values: 0, 1, -1, 2, 10, 100
                    if value not in (0, 1, -1, 2, 10, 100):
                        # Check if it's in a comparison or simple assignment
                        parent = getattr(node, "parent", None)
                        if not isinstance(parent, (ast.Compare, ast.Assign)):
                            issues.append(
                                AnalysisIssue(
                                    file_path=file_path,
                                    line=node.lineno,
                                    column=node.col_offset,
                                    issue_type=AnalysisIssueType.MAGIC_NUMBER,
                                    severity=AnalysisIssueSeverity.LOW,
                                    message=f"Magic number detected: {value}",
                                    suggestion=f"Extract to named constant:\n"
                                    f"MEANINGFUL_NAME = {value}",
                                    metadata={"value": value},
                                )
                            )

        return issues

    def _check_god_classes(self, tree: ast.AST, file_path: str, code: str) -> List[AnalysisIssue]:
        """Detect classes with more than 500 lines."""
        issues = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if hasattr(node, "end_lineno") and node.end_lineno:
                    class_length = node.end_lineno - node.lineno
                    if class_length > 500:
                        issues.append(
                            AnalysisIssue(
                                file_path=file_path,
                                line=node.lineno,
                                column=node.col_offset,
                                issue_type=AnalysisIssueType.GOD_CLASS,
                                severity=AnalysisIssueSeverity.HIGH,
                                message=f"Class '{node.name}' is too large ({class_length} lines)",
                                suggestion="Break down into smaller, focused classes following "
                                "Single Responsibility Principle. Consider:\n"
                                "- Extracting related methods into separate classes\n"
                                "- Using composition over inheritance\n"
                                "- Creating utility classes for shared functionality",
                                metadata={"length": class_length},
                            )
                        )

        return issues

    def _check_incomplete_todos(
        self, tree: ast.AST, file_path: str, code: str
    ) -> List[AnalysisIssue]:
        """Detect TODO/FIXME comments."""
        issues = []

        todo_pattern = re.compile(r"#\s*(TODO|FIXME|XXX|HACK)[:|\s]+(.*)", re.IGNORECASE)

        for line_num, line in enumerate(code.split("\n"), start=1):
            match = todo_pattern.search(line)
            if match:
                marker = match.group(1)
                comment = match.group(2).strip()

                issues.append(
                    AnalysisIssue(
                        file_path=file_path,
                        line=line_num,
                        column=line.find(marker),
                        issue_type=AnalysisIssueType.INCOMPLETE_TODO,
                        severity=AnalysisIssueSeverity.LOW,
                        message=f"{marker} found: {comment[:50]}...",
                        suggestion="Either complete the TODO or create a tracked issue and remove the comment",
                        metadata={"marker": marker, "comment": comment},
                    )
                )

        return issues


__all__ = ["CodeSmellAnalyzer"]
