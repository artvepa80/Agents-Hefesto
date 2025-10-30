"""
Common schemas used across all API endpoints.
These provide consistent response formats and error handling.
"""

from datetime import datetime
from typing import Any, Dict, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

# Generic type for APIResponse wrapper
T = TypeVar("T")


class ErrorDetail(BaseModel):
    """
    Structured error information.

    Used when success=False in APIResponse.
    """

    code: str = Field(
        ...,
        description="Machine-readable error code (e.g., VALIDATION_ERROR, FILE_NOT_FOUND)",
        examples=["VALIDATION_ERROR", "RESOURCE_NOT_FOUND", "ANALYZER_UNAVAILABLE"],
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
        examples=["File path does not exist", "Analysis failed due to syntax error"],
    )
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional error context (optional)",
        examples=[{"file": "test.py", "line": 42}],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "code": "INVALID_FILE_PATH",
                "message": "The specified file path does not exist",
                "details": {"path": "/nonexistent/file.py", "attempted_at": "2025-10-30T12:00:00Z"},
            }
        }
    }


class APIResponse(BaseModel, Generic[T]):
    """
    Standard wrapper for all API responses.

    Provides consistent structure:
    - success: bool indicating if request succeeded
    - data: actual response data (when success=True)
    - error: error details (when success=False)
    - timestamp: when response was generated

    Usage:
        @app.get("/example", response_model=APIResponse[ExampleData])
        async def example():
            return APIResponse(success=True, data=ExampleData(...))
    """

    success: bool = Field(..., description="Whether the request succeeded")
    data: Optional[T] = Field(default=None, description="Response data (present when success=True)")
    error: Optional[ErrorDetail] = Field(
        default=None, description="Error details (present when success=False)"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Response generation timestamp (UTC)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "data": {"example": "data"},
                "error": None,
                "timestamp": "2025-10-30T12:00:00Z",
            }
        }
    }


class PaginationInfo(BaseModel):
    """
    Pagination metadata for list endpoints.

    Used by endpoints that return paginated results (e.g., GET /api/v1/findings).
    """

    limit: int = Field(..., ge=1, le=1000, description="Maximum items per page")
    offset: int = Field(..., ge=0, description="Number of items skipped")
    has_more: bool = Field(..., description="Whether more items exist beyond current page")
    next_offset: Optional[int] = Field(
        default=None, description="Offset value for next page (null if no more items)"
    )
    total_count: Optional[int] = Field(default=None, description="Total number of items (if known)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "limit": 50,
                "offset": 0,
                "has_more": True,
                "next_offset": 50,
                "total_count": 347,
            }
        }
    }


# Re-export for convenience
__all__ = ["APIResponse", "ErrorDetail", "PaginationInfo"]
