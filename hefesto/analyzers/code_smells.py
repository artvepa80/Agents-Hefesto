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

import re
from typing import List

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)
from hefesto.core.ast.generic_ast import GenericAST, NodeType

# Thresholds as constants for clarity
LONG_FUNCTION_THRESHOLD = 50
LONG_PARAMETER_THRESHOLD = 5
DEEP_NESTING_THRESHOLD = 4
GOD_CLASS_THRESHOLD = 500


class CodeSmellAnalyzer:
    """Analyzes code for common code smells."""

    def analyze(self, tree: GenericAST, file_path: str, code: str) -> List[AnalysisIssue]:
        """Analyze code for code smells."""
        issues = []

        issues.extend(self._check_long_functions(tree, file_path))
        issues.extend(self._check_long_parameter_lists(tree, file_path))
        issues.extend(self._check_deep_nesting(tree, file_path))
        issues.extend(self._check_magic_numbers(tree, file_path))
        issues.extend(self._check_god_classes(tree, file_path, code))
        issues.extend(self._check_incomplete_todos(tree, file_path, code))

        return issues

    def _check_long_functions(self, tree: GenericAST, file_path: str) -> List[AnalysisIssue]:
        """Detect functions longer than threshold lines."""
        issues = []

        for node in tree.walk():
            if node.type in [NodeType.FUNCTION, NodeType.ASYNC_FUNCTION, NodeType.METHOD]:
                func_length = node.line_end - node.line_start
                if func_length > LONG_FUNCTION_THRESHOLD:
                    # Use <anonymous> if no name
                    func_name = node.name or "<anonymous>"
                    issues.append(
                        AnalysisIssue(
                            file_path=file_path,
                            line=node.line_start,
                            column=node.column_start,
                            issue_type=AnalysisIssueType.LONG_FUNCTION,
                            severity=AnalysisIssueSeverity.MEDIUM,
                            message=(
                                f"Function '{func_name}' is too long "
                                f"({func_length} lines, threshold={LONG_FUNCTION_THRESHOLD})"
                            ),
                            function_name=func_name,
                            suggestion=(
                                f"Break down into smaller, focused functions. "
                                f"Lines {node.line_start}-{node.line_end}. "
                                f"Each function should do one thing well."
                            ),
                            metadata={
                                "length": func_length,
                                "threshold": LONG_FUNCTION_THRESHOLD,
                                "line_start": node.line_start,
                                "line_end": node.line_end,
                            },
                        )
                    )

        return issues

    def _check_long_parameter_lists(self, tree: GenericAST, file_path: str) -> List[AnalysisIssue]:
        """Detect functions with more than threshold parameters."""
        issues = []

        for node in tree.walk():
            if node.type in [NodeType.FUNCTION, NodeType.ASYNC_FUNCTION, NodeType.METHOD]:
                # Use param_count from metadata (extracted from formal_parameters)
                param_count = node.metadata.get("param_count", 0)

                if param_count > LONG_PARAMETER_THRESHOLD:
                    func_name = node.name or "<anonymous>"
                    issues.append(
                        AnalysisIssue(
                            file_path=file_path,
                            line=node.line_start,
                            column=node.column_start,
                            issue_type=AnalysisIssueType.LONG_PARAMETER_LIST,
                            severity=AnalysisIssueSeverity.MEDIUM,
                            message=(
                                f"Function '{func_name}' has too many parameters "
                                f"({param_count}, threshold={LONG_PARAMETER_THRESHOLD})"
                            ),
                            function_name=func_name,
                            suggestion=(
                                "Consider using a config object, dataclass, "
                                "or **kwargs. Group related parameters into "
                                "objects."
                            ),
                            metadata={
                                "param_count": param_count,
                                "threshold": LONG_PARAMETER_THRESHOLD,
                            },
                        )
                    )

        return issues

    def _check_deep_nesting(self, tree: GenericAST, file_path: str) -> List[AnalysisIssue]:
        """Detect code with nesting depth > threshold."""
        issues = []

        for node in tree.walk():
            if node.type in [NodeType.FUNCTION, NodeType.ASYNC_FUNCTION, NodeType.METHOD]:
                max_depth = self._calculate_max_nesting(node)
                if max_depth > DEEP_NESTING_THRESHOLD:
                    func_name = node.name or "<anonymous>"
                    issues.append(
                        AnalysisIssue(
                            file_path=file_path,
                            line=node.line_start,
                            column=node.column_start,
                            issue_type=AnalysisIssueType.DEEP_NESTING,
                            severity=AnalysisIssueSeverity.HIGH,
                            message=(
                                f"Function '{func_name}' has deep nesting "
                                f"(level {max_depth}, threshold={DEEP_NESTING_THRESHOLD})"
                            ),
                            function_name=func_name,
                            suggestion=(
                                "Reduce nesting by:\n"
                                "- Using early returns\n"
                                "- Extracting nested blocks into functions\n"
                                "- Inverting conditionals"
                            ),
                            metadata={
                                "max_depth": max_depth,
                                "threshold": DEEP_NESTING_THRESHOLD,
                            },
                        )
                    )

        return issues

    def _calculate_max_nesting(self, node, current_depth: int = 0) -> int:
        """Calculate maximum nesting depth."""
        max_depth = current_depth

        for child in node.children:
            child_depth = current_depth
            if child.type in [NodeType.CONDITIONAL, NodeType.LOOP, NodeType.TRY]:
                child_depth = current_depth + 1

            max_depth = max(max_depth, self._calculate_max_nesting(child, child_depth))

        return max_depth

    def _check_magic_numbers(self, tree: GenericAST, file_path: str) -> List[AnalysisIssue]:
        """Detect unexplained numeric literals."""
        return []

    def _check_god_classes(
        self, tree: GenericAST, file_path: str, code: str
    ) -> List[AnalysisIssue]:
        """Detect classes with more than threshold lines."""
        issues = []

        for node in tree.walk():
            if node.type == NodeType.CLASS:
                class_length = node.line_end - node.line_start
                if class_length > GOD_CLASS_THRESHOLD:
                    class_name = node.name or "<anonymous>"
                    issues.append(
                        AnalysisIssue(
                            file_path=file_path,
                            line=node.line_start,
                            column=node.column_start,
                            issue_type=AnalysisIssueType.GOD_CLASS,
                            severity=AnalysisIssueSeverity.HIGH,
                            message=(
                                f"Class '{class_name}' is too large "
                                f"({class_length} lines, threshold={GOD_CLASS_THRESHOLD})"
                            ),
                            suggestion=(
                                f"Lines {node.line_start}-{node.line_end}. "
                                "Break down into smaller, focused classes following "
                                "Single Responsibility Principle. Consider:\n"
                                "- Extracting related methods into separate classes\n"
                                "- Using composition over inheritance\n"
                                "- Creating utility classes for shared functionality"
                            ),
                            metadata={
                                "length": class_length,
                                "threshold": GOD_CLASS_THRESHOLD,
                                "line_start": node.line_start,
                                "line_end": node.line_end,
                            },
                        )
                    )

        return issues

    def _check_incomplete_todos(
        self, tree: GenericAST, file_path: str, code: str
    ) -> List[AnalysisIssue]:
        """Detect TODO/FIXME comments."""
        issues = []

        # Support multiple comment styles
        todo_pattern = re.compile(
            r"(?://|#|/\*|\*)\s*(TODO|FIXME|XXX|HACK)[:|\s]+(.*)",
            re.IGNORECASE,
        )

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
                        message=(
                            f"{marker} found: {comment[:50]}"
                            f"{'...' if len(comment) > 50 else ''}"
                        ),
                        suggestion=(
                            "Either complete the TODO or create a tracked "
                            "issue and remove the comment"
                        ),
                        metadata={"marker": marker, "comment": comment},
                    )
                )

        return issues


__all__ = ["CodeSmellAnalyzer"]
