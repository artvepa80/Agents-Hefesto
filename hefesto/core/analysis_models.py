"""
Analysis Data Models for Hefesto Analyze Command

Data structures for code analysis results, issues, and reports.

Copyright © 2025 Narapa LLC, Miami, Florida
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class AnalysisIssueSeverity(str, Enum):
    """Analysis issue severity levels."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AnalysisIssueType(str, Enum):
    """Types of analysis issues."""

    # Complexity
    HIGH_COMPLEXITY = "HIGH_COMPLEXITY"
    VERY_HIGH_COMPLEXITY = "VERY_HIGH_COMPLEXITY"

    # Code Smells
    LONG_FUNCTION = "LONG_FUNCTION"
    LONG_PARAMETER_LIST = "LONG_PARAMETER_LIST"
    DEEP_NESTING = "DEEP_NESTING"
    DUPLICATE_CODE = "DUPLICATE_CODE"
    DEAD_CODE = "DEAD_CODE"
    MAGIC_NUMBER = "MAGIC_NUMBER"
    GOD_CLASS = "GOD_CLASS"
    INCOMPLETE_TODO = "INCOMPLETE_TODO"

    # Security
    HARDCODED_SECRET = "HARDCODED_SECRET"
    SQL_INJECTION_RISK = "SQL_INJECTION_RISK"
    EVAL_USAGE = "EVAL_USAGE"
    PICKLE_USAGE = "PICKLE_USAGE"
    ASSERT_IN_PRODUCTION = "ASSERT_IN_PRODUCTION"
    BARE_EXCEPT = "BARE_EXCEPT"

    # Best Practices
    MISSING_DOCSTRING = "MISSING_DOCSTRING"
    POOR_NAMING = "POOR_NAMING"
    STYLE_VIOLATION = "STYLE_VIOLATION"


@dataclass
class AnalysisIssue:
    """Represents a single code analysis issue."""

    file_path: str
    line: int
    column: int
    issue_type: AnalysisIssueType
    severity: AnalysisIssueSeverity
    message: str
    function_name: Optional[str] = None
    suggestion: Optional[str] = None
    code_snippet: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "file": self.file_path,
            "line": self.line,
            "column": self.column,
            "type": self.issue_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "function": self.function_name,
            "suggestion": self.suggestion,
            "code_snippet": self.code_snippet,
            "metadata": self.metadata,
        }


@dataclass
class FileAnalysisResult:
    """Analysis results for a single file."""

    file_path: str
    issues: List[AnalysisIssue]
    lines_of_code: int
    analysis_duration_ms: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "file": self.file_path,
            "issues": [issue.to_dict() for issue in self.issues],
            "loc": self.lines_of_code,
            "duration_ms": self.analysis_duration_ms,
        }


@dataclass
class AnalysisSummary:
    """Summary statistics for analysis run."""

    files_analyzed: int
    total_issues: int
    critical_issues: int
    high_issues: int
    medium_issues: int
    low_issues: int
    total_loc: int
    duration_seconds: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "files_analyzed": self.files_analyzed,
            "total_issues": self.total_issues,
            "critical": self.critical_issues,
            "high": self.high_issues,
            "medium": self.medium_issues,
            "low": self.low_issues,
            "total_loc": self.total_loc,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class AnalysisReport:
    """Complete analysis report."""

    summary: AnalysisSummary
    file_results: List[FileAnalysisResult]
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def get_all_issues(self) -> List[AnalysisIssue]:
        """Get all issues across all files."""
        issues = []
        for file_result in self.file_results:
            issues.extend(file_result.issues)
        return issues

    def get_issues_by_severity(self, severity: AnalysisIssueSeverity) -> List[AnalysisIssue]:
        """Get all issues of a specific severity."""
        return [issue for issue in self.get_all_issues() if issue.severity == severity]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "summary": self.summary.to_dict(),
            "files": [file_result.to_dict() for file_result in self.file_results],
            "timestamp": self.timestamp.isoformat(),
        }


__all__ = [
    "AnalysisIssueSeverity",
    "AnalysisIssueType",
    "AnalysisIssue",
    "FileAnalysisResult",
    "AnalysisSummary",
    "AnalysisReport",
]
