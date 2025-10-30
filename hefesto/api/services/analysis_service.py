"""
Analysis service layer for Hefesto API.

Business logic for code analysis operations including:
- ID generation (branded types)
- Path validation and security
- Summary calculation
- Finding formatting

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

import os
import uuid
from pathlib import Path
from typing import Any, Dict, List

from hefesto.api.types import AnalysisId, FindingId  # noqa: F401
from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    FileAnalysisResult,
)


def generate_analysis_id() -> str:
    """
    Generate unique analysis identifier.

    Format: ana_{23_char_uuid}

    Returns:
        Analysis ID string (branded as AnalysisId in type system)
    """
    random_part = uuid.uuid4().hex[:23]
    return f"ana_{random_part}"


def generate_finding_id() -> str:
    """
    Generate unique finding identifier.

    Format: fnd_{23_char_uuid}

    Returns:
        Finding ID string (branded as FindingId in type system)
    """
    random_part = uuid.uuid4().hex[:23]
    return f"fnd_{random_part}"


def is_safe_path(path: str) -> bool:
    """
    Check if path is safe from directory traversal attacks.

    Blocks:
    - Paths containing .. (parent directory references)
    - Paths attempting to access sensitive system directories

    Args:
        path: File or directory path to validate

    Returns:
        True if path is safe, False otherwise
    """
    # Block directory traversal patterns
    if ".." in path:
        return False

    # Normalize path to check if it attempts to escape
    try:
        normalized = os.path.normpath(path)
        if ".." in normalized:
            return False
    except (ValueError, TypeError):
        return False

    return True


def validate_file_path(path: str) -> bool:
    """
    Validate that file path exists and is safe.

    Performs:
    1. Security validation (directory traversal check)
    2. Existence check (file or directory must exist)

    Args:
        path: File or directory path to validate

    Returns:
        True if path is valid

    Raises:
        ValueError: If path is invalid or unsafe
    """
    # Security check
    if not is_safe_path(path):
        raise ValueError(f"Path contains unsafe directory traversal: {path}")

    # Existence check
    path_obj = Path(path)
    if not path_obj.exists():
        raise ValueError(f"Path does not exist: {path}")

    return True


def calculate_summary_stats(
    file_results: List[FileAnalysisResult], duration_seconds: float
) -> Dict[str, Any]:
    """
    Calculate summary statistics from analysis results.

    Aggregates:
    - Total files analyzed
    - Total issues by severity (critical, high, medium, low)
    - Total lines of code
    - Analysis duration

    Args:
        file_results: List of per-file analysis results
        duration_seconds: Total analysis duration

    Returns:
        Dictionary with summary statistics
    """
    total_issues = 0
    critical_count = 0
    high_count = 0
    medium_count = 0
    low_count = 0
    total_loc = 0

    for file_result in file_results:
        total_issues += len(file_result.issues)
        total_loc += file_result.lines_of_code

        for issue in file_result.issues:
            if issue.severity == AnalysisIssueSeverity.CRITICAL:
                critical_count += 1
            elif issue.severity == AnalysisIssueSeverity.HIGH:
                high_count += 1
            elif issue.severity == AnalysisIssueSeverity.MEDIUM:
                medium_count += 1
            elif issue.severity == AnalysisIssueSeverity.LOW:
                low_count += 1

    return {
        "files_analyzed": len(file_results),
        "total_issues": total_issues,
        "critical": critical_count,
        "high": high_count,
        "medium": medium_count,
        "low": low_count,
        "total_loc": total_loc,
        "duration_seconds": duration_seconds,
    }


def format_finding(issue: AnalysisIssue, finding_id: str) -> Dict[str, Any]:
    """
    Format AnalysisIssue as API finding response.

    Converts internal AnalysisIssue model to API response format with:
    - Unique finding ID
    - All issue metadata
    - Optional fields (function, suggestion, code_snippet, metadata)

    Args:
        issue: Analysis issue from AnalyzerEngine
        finding_id: Unique identifier for this finding

    Returns:
        Dictionary formatted for API response
    """
    return {
        "id": finding_id,
        "file": issue.file_path,
        "line": issue.line,
        "column": issue.column,
        "type": issue.issue_type.value,
        "severity": issue.severity.value,
        "message": issue.message,
        "function": issue.function_name,
        "suggestion": issue.suggestion,
        "code_snippet": issue.code_snippet,
        "metadata": issue.metadata,
    }


__all__ = [
    "generate_analysis_id",
    "generate_finding_id",
    "validate_file_path",
    "is_safe_path",
    "calculate_summary_stats",
    "format_finding",
]
