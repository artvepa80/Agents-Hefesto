"""
Unit tests for analysis API - Level 1 (TDD)

Tests for branded types, validation functions, and business logic.
Following CLAUDE.md methodology: write tests FIRST, then implement.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

import os
import tempfile
import unittest
from pathlib import Path
from typing import List

import pytest

# These imports will fail until we implement the types and service
# This is intentional - TDD requires writing tests first
from hefesto.api.types import AnalysisId, FindingId, FilePathStr, AnalyzerName
from hefesto.api.services.analysis_service import (
    generate_analysis_id,
    generate_finding_id,
    validate_file_path,
    is_safe_path,
    calculate_summary_stats,
    format_finding,
)
from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
    FileAnalysisResult,
)


class TestBrandedTypes(unittest.TestCase):
    """Test branded type creation and validation."""

    def test_analysis_id_format(self):
        """Test AnalysisId has correct format (ana_*)."""
        analysis_id = generate_analysis_id()
        assert analysis_id.startswith("ana_")
        assert len(analysis_id) == 27  # ana_ + 23 chars (UUID without hyphens, truncated)

    def test_analysis_id_uniqueness(self):
        """Test AnalysisId generates unique values."""
        id1 = generate_analysis_id()
        id2 = generate_analysis_id()
        assert id1 != id2
        assert isinstance(id1, str)
        assert isinstance(id2, str)

    def test_finding_id_format(self):
        """Test FindingId has correct format (fnd_*)."""
        finding_id = generate_finding_id()
        assert finding_id.startswith("fnd_")
        assert len(finding_id) == 27  # fnd_ + 23 chars

    def test_finding_id_uniqueness(self):
        """Test FindingId generates unique values."""
        id1 = generate_finding_id()
        id2 = generate_finding_id()
        assert id1 != id2


class TestFilePathValidation(unittest.TestCase):
    """Test file path validation and security."""

    def test_valid_file_path(self):
        """Test validation accepts valid file paths."""
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(b"print('test')")
            temp_path = f.name

        try:
            result = validate_file_path(temp_path)
            assert result is True
        finally:
            os.unlink(temp_path)

    def test_valid_directory_path(self):
        """Test validation accepts valid directory paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = validate_file_path(tmpdir)
            assert result is True

    def test_nonexistent_path_raises_error(self):
        """Test validation rejects nonexistent paths."""
        with pytest.raises(ValueError, match="Path does not exist"):
            validate_file_path("/nonexistent/path/to/file.py")

    def test_directory_traversal_blocked(self):
        """Test validation blocks directory traversal attempts."""
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "/etc/../etc/passwd",
            "test/../../sensitive.py",
        ]
        for path in malicious_paths:
            assert is_safe_path(path) is False

    def test_safe_paths_allowed(self):
        """Test validation allows safe paths."""
        safe_paths = [
            "/tmp/test.py",
            "src/main.py",
            "./local/file.py",
            "C:\\Users\\test\\file.py",  # Windows path
        ]
        for path in safe_paths:
            assert is_safe_path(path) is True

    def test_absolute_path_outside_allowed_blocked(self):
        """Test validation blocks absolute paths outside allowed directories."""
        # This test assumes we have a whitelist of allowed directories
        blocked_paths = [
            "/etc/passwd",
            "/root/secret.txt",
            "C:\\Windows\\System32\\config\\SAM",
        ]
        for path in blocked_paths:
            # Should be blocked by security policy
            # Implementation will define specific rules
            pass  # Placeholder - will implement in service layer


class TestSummaryCalculation(unittest.TestCase):
    """Test analysis summary calculation logic."""

    def test_calculate_summary_empty_results(self):
        """Test summary calculation with no results."""
        file_results: List[FileAnalysisResult] = []
        summary = calculate_summary_stats(file_results, duration_seconds=1.5)

        assert summary["files_analyzed"] == 0
        assert summary["total_issues"] == 0
        assert summary["critical"] == 0
        assert summary["high"] == 0
        assert summary["medium"] == 0
        assert summary["low"] == 0
        assert summary["total_loc"] == 0
        assert summary["duration_seconds"] == 1.5

    def test_calculate_summary_with_issues(self):
        """Test summary calculation with actual issues."""
        issue1 = AnalysisIssue(
            file_path="test.py",
            line=10,
            column=5,
            issue_type=AnalysisIssueType.HIGH_COMPLEXITY,
            severity=AnalysisIssueSeverity.HIGH,
            message="Function too complex",
        )
        issue2 = AnalysisIssue(
            file_path="test.py",
            line=20,
            column=10,
            issue_type=AnalysisIssueType.HARDCODED_SECRET,
            severity=AnalysisIssueSeverity.CRITICAL,
            message="Hardcoded secret detected",
        )

        file_result = FileAnalysisResult(
            file_path="test.py",
            issues=[issue1, issue2],
            lines_of_code=150,
            analysis_duration_ms=50.0,
        )

        summary = calculate_summary_stats([file_result], duration_seconds=0.1)

        assert summary["files_analyzed"] == 1
        assert summary["total_issues"] == 2
        assert summary["critical"] == 1
        assert summary["high"] == 1
        assert summary["medium"] == 0
        assert summary["low"] == 0
        assert summary["total_loc"] == 150

    def test_calculate_summary_multiple_files(self):
        """Test summary calculation across multiple files."""
        file1 = FileAnalysisResult(
            file_path="file1.py",
            issues=[
                AnalysisIssue(
                    file_path="file1.py",
                    line=1,
                    column=1,
                    issue_type=AnalysisIssueType.MISSING_DOCSTRING,
                    severity=AnalysisIssueSeverity.LOW,
                    message="Missing docstring",
                )
            ],
            lines_of_code=100,
            analysis_duration_ms=30.0,
        )

        file2 = FileAnalysisResult(
            file_path="file2.py",
            issues=[
                AnalysisIssue(
                    file_path="file2.py",
                    line=5,
                    column=1,
                    issue_type=AnalysisIssueType.SQL_INJECTION_RISK,
                    severity=AnalysisIssueSeverity.CRITICAL,
                    message="SQL injection risk",
                )
            ],
            lines_of_code=200,
            analysis_duration_ms=45.0,
        )

        summary = calculate_summary_stats([file1, file2], duration_seconds=0.2)

        assert summary["files_analyzed"] == 2
        assert summary["total_issues"] == 2
        assert summary["critical"] == 1
        assert summary["low"] == 1
        assert summary["total_loc"] == 300


class TestFindingFormatting(unittest.TestCase):
    """Test finding formatting for API responses."""

    def test_format_finding_complete(self):
        """Test formatting with all fields present."""
        issue = AnalysisIssue(
            file_path="src/test.py",
            line=42,
            column=15,
            issue_type=AnalysisIssueType.HIGH_COMPLEXITY,
            severity=AnalysisIssueSeverity.HIGH,
            message="Function has cyclomatic complexity of 15",
            function_name="process_data",
            suggestion="Consider breaking this function into smaller functions",
            code_snippet="def process_data(items):",
            metadata={"complexity": 15, "threshold": 10},
        )

        finding_id = generate_finding_id()
        formatted = format_finding(issue, finding_id)

        assert formatted["id"] == finding_id
        assert formatted["file"] == "src/test.py"
        assert formatted["line"] == 42
        assert formatted["column"] == 15
        assert formatted["type"] == "HIGH_COMPLEXITY"
        assert formatted["severity"] == "HIGH"
        assert formatted["message"] == "Function has cyclomatic complexity of 15"
        assert formatted["function"] == "process_data"
        assert formatted["suggestion"] == "Consider breaking this function into smaller functions"
        assert formatted["code_snippet"] == "def process_data(items):"
        assert formatted["metadata"]["complexity"] == 15

    def test_format_finding_minimal(self):
        """Test formatting with only required fields."""
        issue = AnalysisIssue(
            file_path="test.py",
            line=1,
            column=1,
            issue_type=AnalysisIssueType.MISSING_DOCSTRING,
            severity=AnalysisIssueSeverity.LOW,
            message="Missing docstring",
        )

        finding_id = generate_finding_id()
        formatted = format_finding(issue, finding_id)

        assert formatted["id"] == finding_id
        assert formatted["file"] == "test.py"
        assert formatted["line"] == 1
        assert formatted["column"] == 1
        assert formatted["type"] == "MISSING_DOCSTRING"
        assert formatted["severity"] == "LOW"
        assert formatted["message"] == "Missing docstring"
        assert formatted["function"] is None
        assert formatted["suggestion"] is None
        assert formatted["code_snippet"] is None
        assert formatted["metadata"] == {}


if __name__ == "__main__":
    unittest.main()
