"""
Schemas for analysis endpoints.

Data models for:
- POST /api/v1/analyze (single file/directory analysis)
- GET /api/v1/analyze/{analysis_id} (retrieve results)
- POST /api/v1/analyze/batch (batch analysis)

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class AnalysisRequest(BaseModel):
    """
    Request for code analysis.

    POST /api/v1/analyze
    """

    path: str = Field(
        ...,
        description="File or directory path to analyze",
        examples=["/path/to/project", "src/main.py"],
        min_length=1,
        max_length=4096,
    )
    exclude_patterns: Optional[List[str]] = Field(
        default=None,
        description="Glob patterns to exclude from analysis",
        examples=[["*.test.py", "node_modules/*", "__pycache__/*"]],
        max_length=100,
    )
    analyzers: Optional[List[str]] = Field(
        default=None,
        description="Specific analyzers to run (default: all)",
        examples=[["complexity", "security"]],
    )

    @field_validator("path")
    @classmethod
    def validate_path_format(cls, v: str) -> str:
        """Validate path format."""
        if not v or v.strip() == "":
            raise ValueError("Path cannot be empty")
        return v

    @field_validator("analyzers")
    @classmethod
    def validate_analyzers(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate analyzer names."""
        if v is None:
            return v

        valid_analyzers = {"complexity", "security", "code_smells", "best_practices"}
        for analyzer in v:
            if analyzer not in valid_analyzers:
                raise ValueError(
                    f"Invalid analyzer: {analyzer}. " f"Valid options: {', '.join(valid_analyzers)}"
                )
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "path": "/path/to/project",
                "exclude_patterns": ["*.test.py", "__pycache__/*"],
                "analyzers": ["complexity", "security"],
            }
        }
    }


class FindingSchema(BaseModel):
    """Individual code quality finding."""

    id: str = Field(..., description="Unique finding identifier (fnd_*)")
    file: str = Field(..., description="File path where issue was found")
    line: int = Field(..., ge=1, description="Line number")
    column: int = Field(..., ge=1, description="Column number")
    type: str = Field(..., description="Issue type (e.g., HIGH_COMPLEXITY)")
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] = Field(
        ..., description="Issue severity level"
    )
    message: str = Field(..., description="Human-readable issue description")
    function: Optional[str] = Field(default=None, description="Function name (if applicable)")
    suggestion: Optional[str] = Field(default=None, description="How to fix the issue")
    code_snippet: Optional[str] = Field(default=None, description="Relevant code snippet")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional issue-specific data"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "fnd_a1b2c3d4e5f6g7h8i9j0k1l",
                "file": "src/main.py",
                "line": 42,
                "column": 5,
                "type": "HIGH_COMPLEXITY",
                "severity": "HIGH",
                "message": "Function has cyclomatic complexity of 15 (threshold: 10)",
                "function": "process_data",
                "suggestion": "Consider breaking this function into smaller functions",
                "code_snippet": "def process_data(items):",
                "metadata": {"complexity": 15, "threshold": 10},
            }
        }
    }


class AnalysisSummarySchema(BaseModel):
    """Summary statistics for analysis results."""

    files_analyzed: int = Field(..., ge=0, description="Number of files analyzed")
    total_issues: int = Field(..., ge=0, description="Total issues found")
    critical: int = Field(..., ge=0, description="Critical severity issues")
    high: int = Field(..., ge=0, description="High severity issues")
    medium: int = Field(..., ge=0, description="Medium severity issues")
    low: int = Field(..., ge=0, description="Low severity issues")
    total_loc: int = Field(..., ge=0, description="Total lines of code analyzed")
    duration_seconds: float = Field(..., ge=0, description="Analysis duration in seconds")

    model_config = {
        "json_schema_extra": {
            "example": {
                "files_analyzed": 127,
                "total_issues": 45,
                "critical": 2,
                "high": 8,
                "medium": 20,
                "low": 15,
                "total_loc": 15234,
                "duration_seconds": 12.456,
            }
        }
    }


class AnalysisResponse(BaseModel):
    """
    Response for analysis operations.

    Used by:
    - POST /api/v1/analyze (immediate response for synchronous analysis)
    - GET /api/v1/analyze/{analysis_id} (retrieve completed analysis)
    """

    analysis_id: str = Field(..., description="Unique analysis identifier (ana_*)")
    status: Literal["completed", "failed"] = Field(
        ..., description="Analysis status (Phase 2: synchronous only)"
    )
    path: str = Field(..., description="Path that was analyzed")
    summary: AnalysisSummarySchema = Field(..., description="Analysis summary statistics")
    findings: List[FindingSchema] = Field(..., description="List of code quality findings")
    started_at: datetime = Field(..., description="Analysis start timestamp (UTC)")
    completed_at: datetime = Field(..., description="Analysis completion timestamp (UTC)")
    error_message: Optional[str] = Field(
        default=None, description="Error message (if status=failed)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "analysis_id": "ana_a1b2c3d4e5f6g7h8i9j0k1l",
                "status": "completed",
                "path": "/path/to/project",
                "summary": {
                    "files_analyzed": 127,
                    "total_issues": 45,
                    "critical": 2,
                    "high": 8,
                    "medium": 20,
                    "low": 15,
                    "total_loc": 15234,
                    "duration_seconds": 12.456,
                },
                "findings": [
                    {
                        "id": "fnd_a1b2c3d4e5f6g7h8i9j0k1l",
                        "file": "src/main.py",
                        "line": 42,
                        "column": 5,
                        "type": "HIGH_COMPLEXITY",
                        "severity": "HIGH",
                        "message": "Function has cyclomatic complexity of 15",
                        "function": "process_data",
                        "suggestion": "Consider breaking into smaller functions",
                        "code_snippet": "def process_data(items):",
                        "metadata": {"complexity": 15},
                    }
                ],
                "started_at": "2025-10-30T12:00:00Z",
                "completed_at": "2025-10-30T12:00:12Z",
                "error_message": None,
            }
        }
    }


class BatchAnalysisRequest(BaseModel):
    """
    Request for batch code analysis.

    POST /api/v1/analyze/batch
    """

    paths: List[str] = Field(
        ...,
        description="List of file or directory paths to analyze",
        min_length=1,
        max_length=100,  # Phase 2 limit
    )
    exclude_patterns: Optional[List[str]] = Field(
        default=None,
        description="Glob patterns to exclude from analysis",
        examples=[["*.test.py", "node_modules/*"]],
        max_length=100,
    )
    analyzers: Optional[List[str]] = Field(
        default=None,
        description="Specific analyzers to run (default: all)",
        examples=[["complexity", "security"]],
    )

    @field_validator("paths")
    @classmethod
    def validate_paths(cls, v: List[str]) -> List[str]:
        """Validate paths list."""
        if not v:
            raise ValueError("Paths list cannot be empty")
        for path in v:
            if not path or path.strip() == "":
                raise ValueError("Path cannot be empty")
        return v

    @field_validator("analyzers")
    @classmethod
    def validate_analyzers(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate analyzer names."""
        if v is None:
            return v

        valid_analyzers = {"complexity", "security", "code_smells", "best_practices"}
        for analyzer in v:
            if analyzer not in valid_analyzers:
                raise ValueError(
                    f"Invalid analyzer: {analyzer}. " f"Valid options: {', '.join(valid_analyzers)}"
                )
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "paths": ["/path/to/project1", "/path/to/project2"],
                "exclude_patterns": ["*.test.py", "__pycache__/*"],
                "analyzers": ["complexity", "security"],
            }
        }
    }


class BatchAnalysisResponse(BaseModel):
    """
    Response for batch analysis operations.

    POST /api/v1/analyze/batch
    """

    batch_id: str = Field(..., description="Unique batch identifier")
    total_analyses: int = Field(..., ge=1, description="Total number of analyses in batch")
    completed: int = Field(..., ge=0, description="Number of completed analyses")
    failed: int = Field(..., ge=0, description="Number of failed analyses")
    results: List[AnalysisResponse] = Field(..., description="Individual analysis results")
    started_at: datetime = Field(..., description="Batch start timestamp (UTC)")
    completed_at: datetime = Field(..., description="Batch completion timestamp (UTC)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "batch_id": "batch_a1b2c3d4e5f6g7h8i9j0k1l",
                "total_analyses": 2,
                "completed": 2,
                "failed": 0,
                "results": [
                    {
                        "analysis_id": "ana_a1b2c3d4e5f6g7h8i9j0k1l",
                        "status": "completed",
                        "path": "/path/to/project1",
                        "summary": {
                            "files_analyzed": 50,
                            "total_issues": 20,
                            "critical": 1,
                            "high": 3,
                            "medium": 10,
                            "low": 6,
                            "total_loc": 5000,
                            "duration_seconds": 5.2,
                        },
                        "findings": [],
                        "started_at": "2025-10-30T12:00:00Z",
                        "completed_at": "2025-10-30T12:00:05Z",
                        "error_message": None,
                    }
                ],
                "started_at": "2025-10-30T12:00:00Z",
                "completed_at": "2025-10-30T12:00:10Z",
            }
        }
    }


__all__ = [
    "AnalysisRequest",
    "AnalysisResponse",
    "BatchAnalysisRequest",
    "BatchAnalysisResponse",
    "FindingSchema",
    "AnalysisSummarySchema",
]
