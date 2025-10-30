"""
Schemas for findings endpoints.

Data models for:
- GET /api/v1/findings (list findings with filters)
- GET /api/v1/findings/{finding_id} (get single finding)
- PATCH /api/v1/findings/{finding_id} (update finding status)

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

# Re-export FindingSchema from analysis for consistency
from hefesto.api.schemas.analysis import FindingSchema


class FindingListRequest(BaseModel):
    """
    Request parameters for listing findings.

    GET /api/v1/findings?limit=10&offset=0&severity=HIGH
    """

    limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of results to return",
        examples=[10, 50, 100],
    )
    offset: int = Field(
        default=0, ge=0, description="Number of results to skip", examples=[0, 10, 100]
    )
    severity: Optional[Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]] = Field(
        default=None,
        description="Filter by severity level",
        examples=["HIGH", "CRITICAL"],
    )
    file_path: Optional[str] = Field(
        default=None,
        description="Filter by file path (exact match)",
        examples=["src/main.py", "lib/utils.py"],
        max_length=4096,
    )
    analyzer: Optional[str] = Field(
        default=None,
        description="Filter by analyzer name",
        examples=["complexity", "security"],
    )
    status: Optional[Literal["new", "in_progress", "resolved", "ignored", "false_positive"]] = (
        Field(
            default=None,
            description="Filter by finding status",
            examples=["new", "resolved"],
        )
    )
    start_date: Optional[datetime] = Field(
        default=None,
        description="Filter by created_at >= start_date (ISO format)",
        examples=["2025-01-01T00:00:00Z"],
    )
    end_date: Optional[datetime] = Field(
        default=None,
        description="Filter by created_at <= end_date (ISO format)",
        examples=["2025-12-31T23:59:59Z"],
    )

    @field_validator("analyzer")
    @classmethod
    def validate_analyzer(cls, v: Optional[str]) -> Optional[str]:
        """Validate analyzer name."""
        if v is None:
            return v

        valid_analyzers = {"complexity", "security", "code_smells", "best_practices"}
        if v not in valid_analyzers:
            raise ValueError(
                f"Invalid analyzer: {v}. " f"Valid options: {', '.join(valid_analyzers)}"
            )
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "limit": 50,
                "offset": 0,
                "severity": "HIGH",
                "analyzer": "security",
                "status": "new",
                "start_date": "2025-01-01T00:00:00Z",
            }
        }
    }


class PaginationMeta(BaseModel):
    """Pagination metadata."""

    total: int = Field(..., ge=0, description="Total number of findings matching filters")
    limit: int = Field(..., ge=1, description="Results per page")
    offset: int = Field(..., ge=0, description="Number of results skipped")
    has_more: bool = Field(..., description="Whether more results are available")

    model_config = {
        "json_schema_extra": {"example": {"total": 142, "limit": 50, "offset": 0, "has_more": True}}
    }


class FindingListResponse(BaseModel):
    """
    Response for listing findings.

    GET /api/v1/findings
    """

    findings: List[FindingSchema] = Field(..., description="List of findings matching filters")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")
    filters_applied: Dict[str, Any] = Field(
        default_factory=dict, description="Filters that were applied to this query"
    )
    bigquery_available: bool = Field(
        ...,
        description="Whether BigQuery is configured (false = in-memory only)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
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
                        "metadata": {
                            "analyzer": "complexity",
                            "confidence": 0.95,
                            "status": "new",
                        },
                    }
                ],
                "pagination": {"total": 142, "limit": 50, "offset": 0, "has_more": True},
                "filters_applied": {"severity": "HIGH", "status": "new"},
                "bigquery_available": True,
            }
        }
    }


class FindingDetailResponse(BaseModel):
    """
    Response for getting single finding by ID.

    GET /api/v1/findings/{finding_id}
    """

    finding: FindingSchema = Field(..., description="Finding details")
    related_findings: Optional[List[FindingSchema]] = Field(
        default=None,
        description="Related findings in same file (future enhancement)",
    )
    history: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Status change history (future enhancement)"
    )
    bigquery_available: bool = Field(
        ...,
        description="Whether BigQuery is configured",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "finding": {
                    "id": "fnd_a1b2c3d4e5f6g7h8i9j0k1l",
                    "file": "src/main.py",
                    "line": 42,
                    "column": 5,
                    "type": "HIGH_COMPLEXITY",
                    "severity": "HIGH",
                    "message": "Function has cyclomatic complexity of 15",
                    "function": "process_data",
                    "suggestion": "Consider breaking into smaller functions",
                    "metadata": {
                        "analyzer": "complexity",
                        "status": "new",
                        "created_at": "2025-10-30T12:00:00Z",
                    },
                },
                "bigquery_available": True,
            }
        }
    }


class FindingUpdateRequest(BaseModel):
    """
    Request for updating finding status.

    PATCH /api/v1/findings/{finding_id}
    """

    status: Literal["new", "in_progress", "resolved", "ignored", "false_positive"] = Field(
        ..., description="New status for the finding"
    )
    updated_by: Optional[str] = Field(
        default=None,
        description="User or system that made the update",
        examples=["user@example.com", "automated-scanner"],
        max_length=255,
    )
    notes: Optional[str] = Field(
        default=None,
        description="Optional notes about the status change",
        examples=["Fixed in PR #123", "False positive - intentional pattern"],
        max_length=2000,
    )

    @field_validator("updated_by")
    @classmethod
    def validate_updated_by(cls, v: Optional[str]) -> Optional[str]:
        """Validate updated_by format."""
        if v and len(v.strip()) == 0:
            raise ValueError("updated_by cannot be empty string")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "resolved",
                "updated_by": "user@example.com",
                "notes": "Fixed in PR #123 by refactoring into smaller functions",
            }
        }
    }


class FindingUpdateResponse(BaseModel):
    """
    Response for finding status update.

    PATCH /api/v1/findings/{finding_id}
    """

    finding_id: str = Field(..., description="Finding identifier that was updated")
    previous_status: Optional[str] = Field(default=None, description="Previous status value")
    new_status: str = Field(..., description="New status value")
    updated_at: datetime = Field(..., description="Timestamp of update (UTC)")
    updated_by: Optional[str] = Field(default=None, description="Who made the update")
    bigquery_available: bool = Field(..., description="Whether change was persisted to BigQuery")

    model_config = {
        "json_schema_extra": {
            "example": {
                "finding_id": "fnd_a1b2c3d4e5f6g7h8i9j0k1l",
                "previous_status": "new",
                "new_status": "resolved",
                "updated_at": "2025-10-30T15:30:00Z",
                "updated_by": "user@example.com",
                "bigquery_available": True,
            }
        }
    }


__all__ = [
    "FindingSchema",
    "FindingListRequest",
    "FindingListResponse",
    "FindingDetailResponse",
    "FindingUpdateRequest",
    "FindingUpdateResponse",
    "PaginationMeta",
]
