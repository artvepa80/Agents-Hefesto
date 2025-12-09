"""
Cyclomatic Complexity Analyzer

Detects overly complex functions using cyclomatic complexity metrics.

Thresholds:
- 1-5: Simple (good)
- 6-10: Moderate (warning)
- 11-20: Complex (error)
- 21+: Very complex (critical)

Copyright © 2025 Narapa LLC, Miami, Florida
"""

from typing import List, Optional

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)
from hefesto.core.ast.generic_ast import GenericAST, NodeType


class ComplexityAnalyzer:
    """Analyzes cyclomatic complexity of functions."""

    def analyze(self, tree: GenericAST, file_path: str, code: str) -> List[AnalysisIssue]:
        """
        Analyze code for complexity issues.

        Args:
            tree: GenericAST of the code
            file_path: Path to the file being analyzed
            code: Source code as string

        Returns:
            List of AnalysisIssue instances
        """
        issues = []

        for node in tree.walk():
            if node.type in [NodeType.FUNCTION, NodeType.ASYNC_FUNCTION, NodeType.METHOD]:
                complexity = self._calculate_complexity(node)
                severity = self._get_severity(complexity)

                if severity:
                    issue = AnalysisIssue(
                        file_path=file_path,
                        line=node.line_start,
                        column=node.column_start,
                        issue_type=(
                            AnalysisIssueType.HIGH_COMPLEXITY
                            if severity != AnalysisIssueSeverity.CRITICAL
                            else AnalysisIssueType.VERY_HIGH_COMPLEXITY
                        ),
                        severity=severity,
                        message=f"Cyclomatic complexity too high ({complexity})",
                        function_name=node.name,
                        suggestion=self._get_suggestion(complexity),
                        metadata={"complexity": complexity},
                    )
                    issues.append(issue)

        return issues

    def _calculate_complexity(self, node) -> int:
        """
        Calculate cyclomatic complexity of a function.

        Complexity = 1 + number of decision points
        """
        complexity = 1

        for child in node.walk():
            if child.type == NodeType.CONDITIONAL:
                complexity += 1
            elif child.type == NodeType.LOOP:
                complexity += 1
            elif child.type == NodeType.TRY:
                complexity += 1
            elif child.type == NodeType.CATCH:
                complexity += 1

        return complexity

    def _get_severity(self, complexity: int) -> Optional[AnalysisIssueSeverity]:
        """Determine severity based on complexity."""
        if complexity >= 21:
            return AnalysisIssueSeverity.CRITICAL
        elif complexity >= 11:
            return AnalysisIssueSeverity.HIGH
        elif complexity >= 6:
            return AnalysisIssueSeverity.MEDIUM
        return None

    def _get_suggestion(self, complexity: int) -> str:
        """Generate actionable suggestion."""
        if complexity >= 21:
            return (
                "Break down into smaller functions. Consider extracting:\n"
                "- Complex conditional logic into separate functions\n"
                "- Loop bodies into helper functions\n"
                "- Error handling into dedicated functions"
            )
        elif complexity >= 11:
            return (
                "Refactor to reduce complexity. Consider:\n"
                "- Extracting nested conditions\n"
                "- Using early returns\n"
                "- Breaking into smaller functions"
            )
        else:
            return "Consider simplifying the logic or extracting helper functions"


__all__ = ["ComplexityAnalyzer"]
