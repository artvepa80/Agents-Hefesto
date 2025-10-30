# Hefesto API Schemas Guide

**Purpose:** Developer guide for working with Pydantic schemas in Hefesto API
**Audience:** Backend developers implementing API endpoints
**Prerequisites:** Basic understanding of Pydantic v2 and FastAPI

---

## Table of Contents

1. [Overview](#overview)
2. [Schema Organization](#schema-organization)
3. [Common Schemas](#common-schemas)
4. [Analysis Schemas](#analysis-schemas)
5. [Findings Schemas](#findings-schemas)
6. [Iris Schemas](#iris-schemas)
7. [Metrics Schemas](#metrics-schemas)
8. [Validation Rules](#validation-rules)
9. [Best Practices](#best-practices)
10. [Examples](#examples)

---

## Overview

Hefesto API uses **Pydantic v2** for:
- Request validation
- Response serialization
- OpenAPI documentation generation
- Type safety

### Why Pydantic?

```python
# Without Pydantic
def analyze(path: str, severity: str):
    if not path:
        raise ValueError("path is required")
    if severity not in ["LOW", "MEDIUM", "HIGH"]:
        raise ValueError("invalid severity")
    # ... more validation

# With Pydantic
class AnalysisRequest(BaseModel):
    path: str = Field(..., description="File path")
    severity: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"

# FastAPI handles validation automatically!
@app.post("/analyze")
async def analyze(request: AnalysisRequest):
    # request is already validated ✅
    pass
```

---

## Schema Organization

```
hefesto/api/schemas/
├── __init__.py           # Re-exports all schemas
├── common.py             # Shared schemas (APIResponse, Pagination)
├── health.py             # Health check schemas
├── analysis.py           # Analysis endpoint schemas
├── findings.py           # Findings management schemas
├── iris.py               # Iris integration schemas
├── metrics.py            # Metrics & analytics schemas
└── config.py             # Configuration schemas
```

### Import Convention

```python
# ✅ Good: Import from specific module
from hefesto.api.schemas.analysis import AnalysisRequest, AnalysisResponse

# ✅ Also good: Import from main package
from hefesto.api.schemas import AnalysisRequest, AnalysisResponse

# ❌ Bad: Wildcard imports
from hefesto.api.schemas import *
```

---

## Common Schemas

**File:** `hefesto/api/schemas/common.py`

### APIResponse[T]

Standard response wrapper for all API endpoints.

```python
from datetime import datetime
from typing import Generic, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")

class APIResponse(BaseModel, Generic[T]):
    """Standard API response wrapper"""
    success: bool = Field(..., description="Whether request succeeded")
    data: Optional[T] = Field(None, description="Response data")
    error: Optional[ErrorDetail] = Field(None, description="Error details if failed")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Response timestamp"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": true,
                "data": {...},
                "error": null,
                "timestamp": "2025-10-30T12:00:00Z"
            }
        }
    }
```

**Usage:**

```python
from fastapi import APIRouter
from hefesto.api.schemas.common import APIResponse
from hefesto.api.schemas.analysis import AnalysisResponse

router = APIRouter()

@router.post("/analyze", response_model=APIResponse[AnalysisResponse])
async def analyze(request: AnalysisRequest):
    result = await analysis_service.analyze(request)
    return APIResponse(success=True, data=result)
```

### ErrorDetail

Error information structure.

```python
class ErrorDetail(BaseModel):
    """Error information"""
    code: str = Field(..., description="Error code (e.g., VALIDATION_ERROR)")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional error context"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "code": "INVALID_FILE_PATH",
                "message": "File path does not exist",
                "details": {"path": "nonexistent.py"}
            }
        }
    }
```

**Usage:**

```python
from fastapi import HTTPException
from hefesto.api.schemas.common import APIResponse, ErrorDetail

@router.post("/analyze")
async def analyze(request: AnalysisRequest):
    if not Path(request.path).exists():
        return APIResponse(
            success=False,
            error=ErrorDetail(
                code="INVALID_FILE_PATH",
                message=f"File not found: {request.path}",
                details={"path": request.path}
            )
        )
```

### PaginationInfo

Pagination metadata for list endpoints.

```python
class PaginationInfo(BaseModel):
    """Pagination metadata"""
    limit: int = Field(..., ge=1, le=1000, description="Items per page")
    offset: int = Field(..., ge=0, description="Number of items to skip")
    has_more: bool = Field(..., description="Whether more items exist")
    next_offset: Optional[int] = Field(None, description="Offset for next page")
    total_count: Optional[int] = Field(None, description="Total items (if known)")
```

**Usage:**

```python
@router.get("/findings", response_model=APIResponse[FindingsListResponse])
async def list_findings(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    findings = await findings_service.get_findings(limit, offset)
    total = await findings_service.count_findings()

    return APIResponse(
        success=True,
        data=FindingsListResponse(
            findings=findings,
            pagination=PaginationInfo(
                limit=limit,
                offset=offset,
                has_more=(offset + limit) < total,
                next_offset=offset + limit if (offset + limit) < total else None,
                total_count=total
            )
        )
    )
```

---

## Analysis Schemas

**File:** `hefesto/api/schemas/analysis.py`

### AnalysisRequest

Request schema for code analysis.

```python
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

class AnalysisRequest(BaseModel):
    """Request to analyze code"""
    path: str = Field(
        ...,
        description="File or directory path to analyze",
        examples=["src/payment_processor.py", "src/"]
    )
    analyzers: Optional[List[str]] = Field(
        default=["complexity", "security", "code_smells", "best_practices"],
        description="List of analyzers to run"
    )
    severity_threshold: Optional[Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]] = Field(
        default="MEDIUM",
        description="Minimum severity level to report"
    )
    format: Optional[Literal["json", "text", "html"]] = Field(
        default="json",
        description="Output format"
    )
    exclude_patterns: Optional[List[str]] = Field(
        default=[],
        description="Glob patterns to exclude (e.g., ['tests/', '*.test.py'])"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "path": "src/payment_processor.py",
                "analyzers": ["security", "complexity"],
                "severity_threshold": "HIGH",
                "format": "json",
                "exclude_patterns": ["tests/", "docs/"]
            }
        }
    }
```

### FindingSchema

Individual finding from analysis.

```python
class FindingSchema(BaseModel):
    """Single code quality finding"""
    id: str = Field(..., description="Unique finding identifier")
    analyzer: str = Field(..., description="Analyzer that found the issue")
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = Field(
        ...,
        description="Issue severity"
    )
    file: str = Field(..., description="File path")
    line: int = Field(..., ge=1, description="Line number")
    column: Optional[int] = Field(None, ge=1, description="Column number")
    description: str = Field(..., description="Issue description")
    recommendation: str = Field(..., description="Suggested fix")
    code_snippet: Optional[str] = Field(None, description="Code snippet")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional data")
```

### AnalysisSummary

Summary statistics for analysis.

```python
class AnalysisSummary(BaseModel):
    """Analysis summary statistics"""
    total_issues: int = Field(..., ge=0, description="Total issues found")
    critical: int = Field(..., ge=0, description="Critical severity count")
    high: int = Field(..., ge=0, description="High severity count")
    medium: int = Field(..., ge=0, description="Medium severity count")
    low: int = Field(..., ge=0, description="Low severity count")

    @property
    def has_critical_issues(self) -> bool:
        """Check if any critical issues exist"""
        return self.critical > 0
```

---

## Findings Schemas

**File:** `hefesto/api/schemas/findings.py`

### FindingListItem

Simplified finding for list views.

```python
class FindingListItem(BaseModel):
    """Finding in list view (simplified)"""
    id: str
    timestamp: datetime
    file_path: str
    line: int
    analyzer: str
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    description: str
    status: Literal["open", "resolved", "ignored", "wontfix"]
    first_seen: datetime
    last_seen: datetime
    occurrence_count: int = Field(..., ge=1)
```

### FindingDetailResponse

Detailed finding with history.

```python
class FindingHistoryEntry(BaseModel):
    """Finding history entry"""
    timestamp: datetime
    action: str = Field(..., description="Action taken (created, updated, resolved)")
    user: Optional[str] = Field(None, description="User who performed action")
    details: str = Field(..., description="Action details")

class FindingDetailResponse(BaseModel):
    """Detailed finding information"""
    # All fields from FindingListItem
    id: str
    timestamp: datetime
    file_path: str
    line: int
    column: Optional[int] = None
    analyzer: str
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    description: str
    recommendation: str
    code_snippet: Optional[str] = None
    status: Literal["open", "resolved", "ignored", "wontfix"]

    # Additional fields for detail view
    first_seen: datetime
    last_seen: datetime
    occurrence_count: int
    history: List[FindingHistoryEntry] = Field(default=[], description="Status history")
    related_findings: Optional[List[RelatedFinding]] = Field(
        default=[],
        description="Similar findings"
    )
```

### FindingUpdateRequest

Update finding status.

```python
class FindingUpdateRequest(BaseModel):
    """Request to update finding status"""
    status: Literal["resolved", "ignored", "wontfix", "reopen"] = Field(
        ...,
        description="New status"
    )
    comment: Optional[str] = Field(
        None,
        max_length=1000,
        description="Reason for status change"
    )

    @field_validator("comment")
    @classmethod
    def validate_comment(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        """Validate comment based on status"""
        status = info.data.get("status")
        if status in ["ignored", "wontfix"] and not v:
            raise ValueError("Comment required when marking as ignored/wontfix")
        return v
```

---

## Iris Schemas

**File:** `hefesto/api/schemas/iris.py`

### AlertCorrelationRequest

Request to correlate production alert.

```python
class AlertCorrelationRequest(BaseModel):
    """Request to correlate production alert with findings"""
    alert_id: str = Field(..., description="Unique alert identifier")
    error_type: str = Field(..., description="Error type (e.g., AttributeError)")
    error_message: str = Field(..., description="Error message")
    stacktrace: str = Field(..., description="Full stacktrace")
    timestamp: datetime = Field(..., description="Alert timestamp")
    service_name: Optional[str] = Field(None, description="Service name")
    severity: Optional[Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]] = None
    affected_users: Optional[int] = Field(None, ge=0, description="Users affected")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Additional context")

    model_config = {
        "json_schema_extra": {
            "example": {
                "alert_id": "alert_prod_789",
                "error_type": "AttributeError",
                "error_message": "'NoneType' object has no attribute 'charge'",
                "stacktrace": "Traceback (most recent call last):\\n...",
                "timestamp": "2025-10-30T11:45:00Z",
                "service_name": "payment-service",
                "severity": "CRITICAL",
                "affected_users": 1234
            }
        }
    }
```

### MatchingFinding

Finding that matches alert.

```python
class MatchingFinding(BaseModel):
    """Finding that correlates with alert"""
    finding_id: str
    file_path: str
    line_number: int
    finding_type: str
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    description: str
    match_reason: str = Field(..., description="Why this finding matches")
    match_confidence: float = Field(..., ge=0.0, le=1.0, description="Match confidence")
```

### AlertCorrelationResponse

Correlation result.

```python
class CostEstimate(BaseModel):
    """Estimated cost impact"""
    affected_users: int = Field(..., ge=0)
    estimated_revenue_impact_usd: float = Field(..., ge=0.0)
    calculation: str = Field(..., description="How cost was calculated")

class AlertCorrelationResponse(BaseModel):
    """Alert correlation result"""
    correlation_id: str = Field(..., description="Unique correlation ID")
    alert_id: str = Field(..., description="Original alert ID")
    correlation_found: bool = Field(..., description="Whether correlation was found")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Overall confidence")
    matching_findings: List[MatchingFinding] = Field(
        default=[],
        description="Findings that match alert"
    )
    suggested_root_cause: Optional[str] = Field(
        None,
        description="AI-generated root cause analysis"
    )
    related_files: List[str] = Field(default=[], description="Related file paths")
    recommended_actions: List[str] = Field(default=[], description="Recommended fixes")
    cost_estimate: Optional[CostEstimate] = Field(
        None,
        description="Estimated business impact"
    )
```

---

## Metrics Schemas

**File:** `hefesto/api/schemas/metrics.py`

### MetricsSummaryResponse

Aggregate metrics.

```python
class MetricsPeriod(BaseModel):
    """Time period for metrics"""
    start: datetime
    end: datetime

class PeriodComparison(BaseModel):
    """Comparison with previous period"""
    findings_change_percent: float = Field(..., description="% change in findings")
    quality_score_change: float = Field(..., description="Points change in score")

class MetricsSummaryResponse(BaseModel):
    """Aggregate code quality metrics"""
    period: MetricsPeriod
    total_analyses: int = Field(..., ge=0)
    total_findings: int = Field(..., ge=0)
    findings_by_severity: Dict[str, int] = Field(
        ...,
        description="Findings grouped by severity"
    )
    findings_by_analyzer: Dict[str, int] = Field(
        ...,
        description="Findings grouped by analyzer"
    )
    trend: Literal["improving", "degrading", "stable"]
    quality_score: float = Field(..., ge=0.0, le=100.0, description="Overall quality score")
    quality_grade: Literal["A", "B", "C", "D", "F"]
    comparison_previous_period: Optional[PeriodComparison] = None
```

---

## Validation Rules

### Field Validators

Use `@field_validator` for custom validation logic:

```python
from pydantic import field_validator

class AnalysisRequest(BaseModel):
    path: str
    severity_threshold: str

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        """Validate file path exists and is readable"""
        path = Path(v)
        if not path.exists():
            raise ValueError(f"Path does not exist: {v}")
        if not os.access(path, os.R_OK):
            raise ValueError(f"Path is not readable: {v}")
        return v

    @field_validator("severity_threshold")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        """Normalize severity to uppercase"""
        return v.upper()
```

### Model Validators

Use `@model_validator` for cross-field validation:

```python
from pydantic import model_validator

class DateRangeQuery(BaseModel):
    start_date: datetime
    end_date: datetime

    @model_validator(mode="after")
    def validate_date_range(self) -> "DateRangeQuery":
        """Ensure start_date < end_date"""
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")

        # Limit to 90 days
        delta = (self.end_date - self.start_date).days
        if delta > 90:
            raise ValueError("Date range cannot exceed 90 days")

        return self
```

---

## Best Practices

### 1. Use Descriptive Field Names

```python
# ❌ Bad: Unclear names
class Request(BaseModel):
    p: str
    s: str
    e: List[str]

# ✅ Good: Clear names
class AnalysisRequest(BaseModel):
    path: str
    severity_threshold: str
    exclude_patterns: List[str]
```

### 2. Add Field Descriptions

```python
# ❌ Bad: No descriptions
class Finding(BaseModel):
    file: str
    line: int

# ✅ Good: With descriptions
class Finding(BaseModel):
    file: str = Field(..., description="Path to source file")
    line: int = Field(..., ge=1, description="Line number where issue occurs")
```

### 3. Provide Examples

```python
class AnalysisRequest(BaseModel):
    path: str = Field(
        ...,
        description="File or directory path",
        examples=["src/main.py", "tests/", "*.py"]
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "path": "src/payment_processor.py",
                "severity_threshold": "HIGH"
            }
        }
    }
```

### 4. Use Type Annotations

```python
from typing import List, Optional, Literal

# ✅ Good: Strong typing
class Request(BaseModel):
    severity: Literal["LOW", "MEDIUM", "HIGH"]  # Enum
    limit: int = Field(..., ge=1, le=1000)       # Constrained int
    tags: Optional[List[str]] = None             # Optional list
```

### 5. Separate Request/Response Schemas

```python
# ❌ Bad: Reusing same schema
class Finding(BaseModel):
    id: str
    file_path: str
    # ... all fields

# ✅ Good: Separate schemas
class FindingCreateRequest(BaseModel):
    """Request to create finding (no ID)"""
    file_path: str
    # ... fields user provides

class FindingResponse(BaseModel):
    """Response with finding (includes ID)"""
    id: str
    file_path: str
    created_at: datetime  # Server-generated
    # ... all fields
```

### 6. Use Composition

```python
# Define base schemas
class FindingBase(BaseModel):
    file_path: str
    line: int
    severity: str
    description: str

# Extend for different use cases
class FindingCreate(FindingBase):
    """Creating a new finding"""
    pass

class FindingInDB(FindingBase):
    """Finding as stored in database"""
    id: str
    created_at: datetime
    updated_at: datetime

class FindingResponse(FindingBase):
    """Finding in API response"""
    id: str
    created_at: datetime
```

---

## Examples

### Example 1: Simple GET Endpoint

```python
from fastapi import APIRouter, HTTPException
from hefesto.api.schemas.common import APIResponse
from hefesto.api.schemas.health import HealthResponse

router = APIRouter()

@router.get("/health", response_model=APIResponse[HealthResponse])
async def health_check():
    """Health check endpoint"""
    return APIResponse(
        success=True,
        data=HealthResponse(
            status="healthy",
            version="4.1.0",
            timestamp=datetime.utcnow()
        )
    )
```

### Example 2: POST with Validation

```python
from fastapi import APIRouter, HTTPException
from hefesto.api.schemas.common import APIResponse, ErrorDetail
from hefesto.api.schemas.analysis import AnalysisRequest, AnalysisResponse

router = APIRouter()

@router.post("/analyze", response_model=APIResponse[AnalysisResponse])
async def analyze_code(request: AnalysisRequest):
    """Analyze code with validation"""
    try:
        # Pydantic automatically validates request
        result = await analysis_service.analyze(request)
        return APIResponse(success=True, data=result)

    except FileNotFoundError as e:
        # Return structured error
        return APIResponse(
            success=False,
            error=ErrorDetail(
                code="FILE_NOT_FOUND",
                message=str(e),
                details={"path": request.path}
            )
        )
```

### Example 3: List with Pagination

```python
from fastapi import APIRouter, Query
from hefesto.api.schemas.common import APIResponse, PaginationInfo
from hefesto.api.schemas.findings import FindingsListResponse

router = APIRouter()

@router.get("/findings", response_model=APIResponse[FindingsListResponse])
async def list_findings(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    severity: Optional[str] = None
):
    """List findings with pagination"""
    # Query with pagination
    findings = await findings_service.get_findings(
        limit=limit,
        offset=offset,
        severity=severity
    )
    total = await findings_service.count_findings(severity=severity)

    return APIResponse(
        success=True,
        data=FindingsListResponse(
            findings=findings,
            total_count=total,
            pagination=PaginationInfo(
                limit=limit,
                offset=offset,
                has_more=(offset + limit) < total,
                next_offset=offset + limit if (offset + limit) < total else None
            )
        )
    )
```

### Example 4: Complex Validation

```python
from pydantic import field_validator, model_validator

class DateRangeQuery(BaseModel):
    start_date: datetime
    end_date: datetime
    max_results: int = Field(100, ge=1, le=10000)

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_dates(cls, v: datetime) -> datetime:
        """Validate dates are not in future"""
        if v > datetime.utcnow():
            raise ValueError("Date cannot be in the future")
        return v

    @model_validator(mode="after")
    def validate_range(self) -> "DateRangeQuery":
        """Validate date range"""
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")

        days = (self.end_date - self.start_date).days
        if days > 365:
            raise ValueError("Date range cannot exceed 365 days")

        return self
```

---

## Testing Schemas

### Unit Tests

```python
import pytest
from pydantic import ValidationError
from hefesto.api.schemas.analysis import AnalysisRequest

def test_analysis_request_valid():
    """Test valid analysis request"""
    request = AnalysisRequest(
        path="src/test.py",
        severity_threshold="HIGH"
    )
    assert request.path == "src/test.py"
    assert request.severity_threshold == "HIGH"

def test_analysis_request_invalid_severity():
    """Test invalid severity value"""
    with pytest.raises(ValidationError):
        AnalysisRequest(
            path="src/test.py",
            severity_threshold="INVALID"  # Should fail
        )

def test_analysis_request_defaults():
    """Test default values"""
    request = AnalysisRequest(path="src/test.py")
    assert request.severity_threshold == "MEDIUM"  # Default
    assert request.analyzers == ["complexity", "security", "code_smells", "best_practices"]
```

### Integration Tests

```python
from fastapi.testclient import TestClient
from hefesto.api.main import app

client = TestClient(app)

def test_analyze_endpoint_validation():
    """Test endpoint validates request schema"""
    # Valid request
    response = client.post("/api/v1/analyze", json={
        "path": "test.py",
        "severity_threshold": "HIGH"
    })
    assert response.status_code == 200

    # Invalid request (missing required field)
    response = client.post("/api/v1/analyze", json={
        "severity_threshold": "HIGH"
        # Missing 'path'
    })
    assert response.status_code == 422  # Validation error
```

---

## Troubleshooting

### Common Issues

**Issue 1: "Field required" error**

```python
# Problem: Missing required field
{
  "error": {
    "code": "VALIDATION_ERROR",
    "details": {
      "errors": [{"field": "path", "message": "Field required"}]
    }
  }
}

# Solution: Provide required field or make it optional
class Request(BaseModel):
    path: Optional[str] = None  # Now optional
```

**Issue 2: Type mismatch**

```python
# Problem: Wrong type provided
request = {"limit": "fifty"}  # Should be int

# Solution: Ensure correct types or use validators
class Query(BaseModel):
    limit: int

    @field_validator("limit", mode="before")
    @classmethod
    def coerce_to_int(cls, v):
        """Convert string to int if possible"""
        if isinstance(v, str):
            return int(v)
        return v
```

**Issue 3: Circular imports**

```python
# Problem: Circular dependency
# file1.py imports file2.py
# file2.py imports file1.py

# Solution: Use forward references and TYPE_CHECKING
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .file2 import OtherModel

class MyModel(BaseModel):
    other: "OtherModel"  # Forward reference
```

---

## References

- [Pydantic Documentation](https://docs.pydantic.dev/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [API Architecture](../../docs/API_ARCHITECTURE.md)
- [Implementation Plan](../../docs/API_IMPLEMENTATION_PLAN.md)

---

**Last Updated:** October 30, 2025
**Version:** 1.0
**Maintained By:** Hefesto Development Team
