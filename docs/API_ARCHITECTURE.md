# Hefesto API Architecture Specification

**Version:** v4.1.0
**Status:** Design Phase
**Target Release:** November 2025
**Last Updated:** October 30, 2025

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Design Principles](#design-principles)
3. [Architecture Overview](#architecture-overview)
4. [Authentication & Authorization](#authentication--authorization)
5. [Rate Limiting](#rate-limiting)
6. [Versioning Strategy](#versioning-strategy)
7. [Error Handling](#error-handling)
8. [API Endpoints](#api-endpoints)
   - [Phase 1: Health & Monitoring](#phase-1-health--monitoring)
   - [Phase 2: Analysis Endpoints](#phase-2-analysis-endpoints)
   - [Phase 3: Findings Management](#phase-3-findings-management)
   - [Phase 4: Iris Integration](#phase-4-iris-integration)
   - [Phase 5: Metrics & Analytics](#phase-5-metrics--analytics)
   - [Phase 6: Configuration & Admin](#phase-6-configuration--admin)
9. [Data Models](#data-models)
10. [Performance Requirements](#performance-requirements)
11. [Security Considerations](#security-considerations)

---

## Executive Summary

This document specifies the complete REST API architecture for Hefesto v4.1.0, designed to support:

1. **Programmatic Access** - Developers using Hefesto as a service
2. **Iris Integration** - OMEGA Guardian production monitoring correlation
3. **Enterprise Features** - Metrics, analytics, and findings management

**Total Endpoints:** 15
**API Framework:** FastAPI
**Documentation:** OpenAPI 3.0 (auto-generated)
**Protocol:** REST over HTTPS

---

## Design Principles

### 1. RESTful Best Practices
- Resource-based URLs (`/api/v1/findings` not `/api/v1/getFindings`)
- HTTP verbs map to CRUD operations
- Stateless requests
- HATEOAS links in responses (future)

### 2. Developer Experience
- Clear, predictable naming
- Comprehensive error messages
- Self-documenting with OpenAPI/Swagger
- Consistent response formats

### 3. Scalability
- Async/await throughout
- Pagination for list endpoints
- Rate limiting support
- Caching headers

### 4. Security
- Authentication-ready (placeholder for v1)
- Input validation with Pydantic
- SQL injection prevention
- CORS configuration

### 5. Maintainability
- Versioned API paths (`/api/v1/`)
- Structured logging
- Health checks for monitoring
- Graceful degradation

---

## Architecture Overview

### Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Framework** | FastAPI 0.104+ | Modern async web framework |
| **Validation** | Pydantic 2.0+ | Request/response validation |
| **Server** | Uvicorn | ASGI server |
| **Documentation** | OpenAPI 3.0 | Auto-generated API docs |
| **Database** | BigQuery | Findings storage (PRO tier) |
| **Cache** | Redis (future) | Response caching |
| **Queue** | Celery (future) | Async task processing |

### Project Structure

```
hefesto/
├── api/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app initialization
│   ├── dependencies.py          # Dependency injection
│   ├── middleware.py            # CORS, logging, rate limiting
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── health.py            # Health & monitoring endpoints
│   │   ├── analysis.py          # Analysis endpoints
│   │   ├── findings.py          # Findings management
│   │   ├── iris.py              # Iris integration endpoints
│   │   ├── metrics.py           # Metrics & analytics
│   │   └── config.py            # Configuration endpoints
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── analysis.py          # Analysis schemas
│   │   ├── findings.py          # Finding schemas
│   │   ├── iris.py              # Iris schemas
│   │   ├── metrics.py           # Metrics schemas
│   │   └── common.py            # Shared schemas (pagination, errors)
│   └── services/
│       ├── __init__.py
│       ├── analysis_service.py  # Analysis business logic
│       ├── findings_service.py  # Findings persistence
│       └── correlation_service.py  # Iris correlation logic
```

---

## Authentication & Authorization

### V1 (Current Release)
**Status:** Not implemented
**Access:** Public (no authentication required)

### V2 (Future Release)
**Status:** Planned for Q2 2026

**Authentication Methods:**
1. **API Keys** - For programmatic access
2. **JWT Tokens** - For user sessions (future web UI)
3. **OAuth 2.0** - For third-party integrations

**Header Format:**
```
Authorization: Bearer <api_key_or_jwt>
```

**Scopes:**
- `read:analysis` - Read analysis results
- `write:analysis` - Trigger new analyses
- `read:findings` - Read findings
- `write:findings` - Update findings
- `admin` - Full access

---

## Rate Limiting

### Strategy
- **Window:** Sliding window (not fixed)
- **Storage:** Redis (future) or in-memory (v1)
- **Headers:** Standard `X-RateLimit-*` headers

### Tiers

| Tier | Requests/Min | Requests/Hour | Requests/Day |
|------|-------------|---------------|--------------|
| **Free** | 10 | 100 | 1,000 |
| **Pro** | 100 | 1,000 | 10,000 |
| **Enterprise** | 1,000 | 10,000 | 100,000 |

### Response Headers
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1698765600
```

### 429 Response
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Try again in 42 seconds.",
    "details": {
      "limit": 100,
      "window_seconds": 60,
      "retry_after": 42
    }
  },
  "timestamp": "2025-10-30T12:00:00Z"
}
```

---

## Versioning Strategy

### URL Versioning
- **Format:** `/api/v{major}/resource`
- **Current:** `/api/v1/`
- **Future:** `/api/v2/` (when breaking changes occur)

### Version Header (Optional)
```
X-API-Version: v1
```

### Breaking vs Non-Breaking Changes

**Non-Breaking (same version):**
- Adding new optional fields
- Adding new endpoints
- Adding new query parameters (optional)

**Breaking (new version):**
- Removing fields
- Changing field types
- Making optional fields required
- Changing response structure

### Deprecation Policy
- Deprecation announced 6 months before removal
- Deprecated endpoints return `X-API-Deprecated: true` header
- Support 2 major versions simultaneously

---

## Error Handling

### Standard Response Format

**Success:**
```json
{
  "success": true,
  "data": {
    "...": "actual data"
  },
  "error": null,
  "timestamp": "2025-10-30T12:00:00Z"
}
```

**Error:**
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      "field": "Additional context"
    }
  },
  "timestamp": "2025-10-30T12:00:00Z"
}
```

### HTTP Status Codes

| Code | Meaning | When to Use |
|------|---------|-------------|
| **200** | OK | Successful GET, PATCH, DELETE |
| **201** | Created | Successful POST |
| **202** | Accepted | Async operation queued |
| **204** | No Content | Successful DELETE with no body |
| **400** | Bad Request | Invalid request syntax |
| **401** | Unauthorized | Missing/invalid authentication |
| **403** | Forbidden | Valid auth, insufficient permissions |
| **404** | Not Found | Resource doesn't exist |
| **422** | Unprocessable Entity | Validation error (Pydantic) |
| **429** | Too Many Requests | Rate limit exceeded |
| **500** | Internal Server Error | Server error |
| **503** | Service Unavailable | Service temporarily down |

### Error Codes

| Code | Description | HTTP Status |
|------|-------------|-------------|
| `VALIDATION_ERROR` | Pydantic validation failed | 422 |
| `RESOURCE_NOT_FOUND` | Requested resource doesn't exist | 404 |
| `RATE_LIMIT_EXCEEDED` | Too many requests | 429 |
| `ANALYZER_UNAVAILABLE` | Analyzer service down | 503 |
| `ANALYSIS_FAILED` | Analysis execution failed | 500 |
| `INVALID_FILE_PATH` | File path doesn't exist or unreadable | 400 |
| `BIGQUERY_ERROR` | BigQuery query failed | 500 |
| `CORRELATION_FAILED` | Iris correlation failed | 500 |
| `AUTHENTICATION_REQUIRED` | Auth required but not provided | 401 |
| `INSUFFICIENT_PERMISSIONS` | User lacks required permissions | 403 |

### Validation Error Format (422)

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": {
      "errors": [
        {
          "field": "path",
          "message": "Field required",
          "type": "value_error.missing"
        },
        {
          "field": "severity_threshold",
          "message": "Value must be one of: LOW, MEDIUM, HIGH, CRITICAL",
          "type": "value_error.const"
        }
      ]
    }
  },
  "timestamp": "2025-10-30T12:00:00Z"
}
```

---

## API Endpoints

---

## Phase 1: Health & Monitoring

### Endpoint 1: GET /health

**Purpose:** Basic health check for load balancers and monitoring tools

**Authentication:** Not required

**Request:**
```http
GET /health HTTP/1.1
Host: api.hefesto.dev
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "version": "4.1.0",
    "timestamp": "2025-10-30T12:00:00Z"
  },
  "error": null,
  "timestamp": "2025-10-30T12:00:00Z"
}
```

**Response (503 Service Unavailable):**
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "SERVICE_UNAVAILABLE",
    "message": "Analyzer service is temporarily unavailable",
    "details": {
      "service": "complexity_analyzer",
      "reason": "initialization_failed"
    }
  },
  "timestamp": "2025-10-30T12:00:00Z"
}
```

**Pydantic Schema:**
```python
class HealthResponse(BaseModel):
    status: Literal["healthy", "unhealthy"]
    version: str
    timestamp: datetime
```

---

### Endpoint 2: GET /api/v1/status

**Purpose:** Detailed system status including all analyzers and integrations

**Authentication:** Not required

**Request:**
```http
GET /api/v1/status HTTP/1.1
Host: api.hefesto.dev
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "status": "operational",
    "version": "4.1.0",
    "analyzers": {
      "complexity": "available",
      "security": "available",
      "code_smells": "available",
      "best_practices": "available"
    },
    "integrations": {
      "bigquery": "connected",
      "iris": "enabled",
      "gemini_api": "available"
    },
    "uptime_seconds": 3600,
    "last_health_check": "2025-10-30T11:59:00Z"
  },
  "error": null,
  "timestamp": "2025-10-30T12:00:00Z"
}
```

**Pydantic Schema:**
```python
class AnalyzerStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"

class IntegrationStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ENABLED = "enabled"
    DISABLED = "disabled"

class SystemStatusResponse(BaseModel):
    status: Literal["operational", "degraded", "outage"]
    version: str
    analyzers: Dict[str, AnalyzerStatus]
    integrations: Dict[str, IntegrationStatus]
    uptime_seconds: int
    last_health_check: datetime
```

---

## Phase 2: Analysis Endpoints

### Endpoint 3: POST /api/v1/analyze

**Purpose:** Trigger code analysis programmatically (equivalent to CLI `hefesto analyze`)

**Authentication:** Required (future)

**Request:**
```http
POST /api/v1/analyze HTTP/1.1
Host: api.hefesto.dev
Content-Type: application/json

{
  "path": "src/payment_processor.py",
  "analyzers": ["complexity", "security", "code_smells"],
  "severity_threshold": "MEDIUM",
  "format": "json",
  "exclude_patterns": ["tests/", "docs/"]
}
```

**Request Schema:**
```python
class AnalysisRequest(BaseModel):
    path: str = Field(..., description="File path or directory to analyze")
    analyzers: Optional[List[str]] = Field(
        default=["complexity", "security", "code_smells", "best_practices"],
        description="List of analyzers to run"
    )
    severity_threshold: Optional[Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]] = "MEDIUM"
    format: Optional[Literal["json", "text", "html"]] = "json"
    exclude_patterns: Optional[List[str]] = Field(
        default=[],
        description="Glob patterns to exclude"
    )
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "analysis_id": "550e8400-e29b-41d4-a716-446655440000",
    "path": "src/payment_processor.py",
    "timestamp": "2025-10-30T12:00:00Z",
    "summary": {
      "total_issues": 23,
      "critical": 2,
      "high": 5,
      "medium": 11,
      "low": 5
    },
    "findings": [
      {
        "id": "finding_001",
        "analyzer": "security",
        "severity": "CRITICAL",
        "file": "src/payment_processor.py",
        "line": 145,
        "column": 12,
        "description": "Potential SQL injection vulnerability detected",
        "recommendation": "Use parameterized queries instead of string concatenation",
        "code_snippet": "query = f\"SELECT * FROM users WHERE id = {user_id}\"",
        "confidence": 0.95
      },
      {
        "id": "finding_002",
        "analyzer": "complexity",
        "severity": "HIGH",
        "file": "src/payment_processor.py",
        "line": 98,
        "description": "Function complexity exceeds threshold (score: 18)",
        "recommendation": "Refactor function into smaller, testable units",
        "complexity_score": 18,
        "confidence": 1.0
      }
    ],
    "execution_time_ms": 1250
  },
  "error": null,
  "timestamp": "2025-10-30T12:00:00Z"
}
```

**Response Schema:**
```python
class FindingSchema(BaseModel):
    id: str
    analyzer: str
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    file: str
    line: int
    column: Optional[int] = None
    description: str
    recommendation: str
    code_snippet: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    metadata: Optional[Dict[str, Any]] = None

class AnalysisSummary(BaseModel):
    total_issues: int
    critical: int
    high: int
    medium: int
    low: int

class AnalysisResponse(BaseModel):
    analysis_id: str
    path: str
    timestamp: datetime
    summary: AnalysisSummary
    findings: List[FindingSchema]
    execution_time_ms: int
```

**Error Response (400 Bad Request):**
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "INVALID_FILE_PATH",
    "message": "File path does not exist or is not readable",
    "details": {
      "path": "src/nonexistent.py",
      "reason": "file_not_found"
    }
  },
  "timestamp": "2025-10-30T12:00:00Z"
}
```

---

### Endpoint 4: GET /api/v1/analyze/{analysis_id}

**Purpose:** Retrieve results of a previous analysis

**Authentication:** Required (future)

**Request:**
```http
GET /api/v1/analyze/550e8400-e29b-41d4-a716-446655440000 HTTP/1.1
Host: api.hefesto.dev
```

**Response (200 OK):**
Same as POST /api/v1/analyze response

**Response (404 Not Found):**
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Analysis not found",
    "details": {
      "analysis_id": "550e8400-e29b-41d4-a716-446655440000",
      "resource_type": "analysis"
    }
  },
  "timestamp": "2025-10-30T12:00:00Z"
}
```

---

### Endpoint 5: POST /api/v1/analyze/batch

**Purpose:** Analyze multiple files or directories in a single batch request

**Authentication:** Required (future)

**Request:**
```http
POST /api/v1/analyze/batch HTTP/1.1
Host: api.hefesto.dev
Content-Type: application/json

{
  "paths": [
    "src/payment/",
    "src/authentication/",
    "src/utils/validator.py"
  ],
  "analyzers": ["security", "complexity"],
  "severity_threshold": "HIGH"
}
```

**Request Schema:**
```python
class BatchAnalysisRequest(BaseModel):
    paths: List[str] = Field(..., min_items=1, max_items=100)
    analyzers: Optional[List[str]] = None
    severity_threshold: Optional[Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]] = "MEDIUM"
```

**Response (202 Accepted):**
```json
{
  "success": true,
  "data": {
    "batch_id": "batch_7890-abcd-efgh",
    "total_paths": 3,
    "status": "processing",
    "completed": 0,
    "failed": 0,
    "results": []
  },
  "error": null,
  "timestamp": "2025-10-30T12:00:00Z"
}
```

**Response Schema:**
```python
class BatchAnalysisResult(BaseModel):
    path: str
    status: Literal["pending", "processing", "success", "failed"]
    analysis_id: Optional[str] = None
    error: Optional[str] = None

class BatchAnalysisResponse(BaseModel):
    batch_id: str
    total_paths: int
    status: Literal["processing", "completed", "partial_failure"]
    completed: int
    failed: int
    results: List[BatchAnalysisResult]
```

---

## Phase 3: Findings Management

### Endpoint 6: GET /api/v1/findings

**Purpose:** List findings with filtering and pagination

**Authentication:** Required (future)

**Request:**
```http
GET /api/v1/findings?file_path=src/payment_processor.py&severity=HIGH&limit=50&offset=0 HTTP/1.1
Host: api.hefesto.dev
```

**Query Parameters:**
```python
class FindingsQueryParams(BaseModel):
    file_path: Optional[str] = None
    analyzer: Optional[str] = None
    severity: Optional[Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[Literal["open", "resolved", "ignored", "wontfix"]] = "open"
    limit: int = Field(default=50, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "total_count": 235,
    "findings": [
      {
        "id": "finding_12345",
        "timestamp": "2025-10-29T15:30:00Z",
        "file_path": "src/payment_processor.py",
        "line": 145,
        "analyzer": "security",
        "severity": "HIGH",
        "description": "Potential SQL injection vulnerability",
        "status": "open",
        "first_seen": "2025-10-20T10:00:00Z",
        "last_seen": "2025-10-29T15:30:00Z",
        "occurrence_count": 12
      }
    ],
    "pagination": {
      "limit": 50,
      "offset": 0,
      "has_more": true,
      "next_offset": 50
    }
  },
  "error": null,
  "timestamp": "2025-10-30T12:00:00Z"
}
```

**Response Schema:**
```python
class FindingListItem(BaseModel):
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
    occurrence_count: int

class PaginationInfo(BaseModel):
    limit: int
    offset: int
    has_more: bool
    next_offset: Optional[int] = None

class FindingsListResponse(BaseModel):
    total_count: int
    findings: List[FindingListItem]
    pagination: PaginationInfo
```

---

### Endpoint 7: GET /api/v1/findings/{finding_id}

**Purpose:** Get detailed information about a specific finding

**Authentication:** Required (future)

**Request:**
```http
GET /api/v1/findings/finding_12345 HTTP/1.1
Host: api.hefesto.dev
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "id": "finding_12345",
    "timestamp": "2025-10-29T15:30:00Z",
    "file_path": "src/payment_processor.py",
    "line": 145,
    "column": 12,
    "analyzer": "security",
    "severity": "HIGH",
    "description": "Potential SQL injection vulnerability detected",
    "recommendation": "Use parameterized queries instead of string concatenation",
    "code_snippet": "query = f\"SELECT * FROM users WHERE id = {user_id}\"",
    "status": "open",
    "first_seen": "2025-10-20T10:00:00Z",
    "last_seen": "2025-10-29T15:30:00Z",
    "occurrence_count": 12,
    "history": [
      {
        "timestamp": "2025-10-20T10:00:00Z",
        "action": "created",
        "user": null,
        "details": "Initial detection"
      },
      {
        "timestamp": "2025-10-25T14:00:00Z",
        "action": "severity_updated",
        "user": null,
        "details": "Severity changed from MEDIUM to HIGH"
      }
    ],
    "related_findings": [
      {
        "id": "finding_12346",
        "file_path": "src/payment_processor.py",
        "line": 189,
        "description": "Similar SQL injection pattern",
        "similarity_score": 0.87
      }
    ]
  },
  "error": null,
  "timestamp": "2025-10-30T12:00:00Z"
}
```

**Response Schema:**
```python
class FindingHistoryEntry(BaseModel):
    timestamp: datetime
    action: str
    user: Optional[str] = None
    details: str

class RelatedFinding(BaseModel):
    id: str
    file_path: str
    line: int
    description: str
    similarity_score: float

class FindingDetailResponse(BaseModel):
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
    first_seen: datetime
    last_seen: datetime
    occurrence_count: int
    history: List[FindingHistoryEntry]
    related_findings: Optional[List[RelatedFinding]] = []
```

---

### Endpoint 8: PATCH /api/v1/findings/{finding_id}

**Purpose:** Update the status of a finding (mark as resolved, ignored, etc.)

**Authentication:** Required

**Request:**
```http
PATCH /api/v1/findings/finding_12345 HTTP/1.1
Host: api.hefesto.dev
Content-Type: application/json

{
  "status": "resolved",
  "comment": "Fixed by implementing parameterized queries in commit abc123"
}
```

**Request Schema:**
```python
class FindingUpdateRequest(BaseModel):
    status: Literal["resolved", "ignored", "wontfix", "reopen"]
    comment: Optional[str] = Field(None, max_length=1000)
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "id": "finding_12345",
    "status": "resolved",
    "updated_at": "2025-10-30T12:00:00Z",
    "updated_by": "user@example.com"
  },
  "error": null,
  "timestamp": "2025-10-30T12:00:00Z"
}
```

**Response Schema:**
```python
class FindingUpdateResponse(BaseModel):
    id: str
    status: str
    updated_at: datetime
    updated_by: Optional[str] = None
```

---

## Phase 4: Iris Integration

### Endpoint 9: GET /api/v1/iris/code-context

**Purpose:** Get code context for a specific file/line (used by Iris for alert enrichment)

**Authentication:** Required

**Request:**
```http
GET /api/v1/iris/code-context?file_path=src/payment_processor.py&line_number=145 HTTP/1.1
Host: api.hefesto.dev
```

**Query Parameters:**
```python
class CodeContextQuery(BaseModel):
    file_path: str = Field(..., description="Path to source file")
    line_number: Optional[int] = Field(None, description="Specific line number")
    commit_hash: Optional[str] = Field(None, description="Git commit hash")
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "file_path": "src/payment_processor.py",
    "line_number": 145,
    "function_name": "process_payment",
    "class_name": "PaymentProcessor",
    "complexity": {
      "score": 18,
      "grade": "C",
      "details": "High cyclomatic complexity (threshold: 10)"
    },
    "security_findings": [
      {
        "severity": "HIGH",
        "type": "sql_injection",
        "line": 145,
        "description": "Potential SQL injection vulnerability"
      }
    ],
    "code_smells": [
      {
        "type": "long_function",
        "severity": "MEDIUM",
        "line": 98,
        "description": "Function exceeds 50 lines"
      }
    ],
    "best_practices_violations": [],
    "recent_changes": {
      "last_modified": "2025-10-28T09:15:00Z",
      "commit_hash": "abc123def456",
      "author": "developer@example.com",
      "commit_message": "Add payment validation"
    },
    "risk_score": 0.78,
    "risk_factors": [
      "High complexity",
      "Security vulnerability detected",
      "Recently modified"
    ]
  },
  "error": null,
  "timestamp": "2025-10-30T12:00:00Z"
}
```

**Response Schema:**
```python
class ComplexityInfo(BaseModel):
    score: int
    grade: Literal["A", "B", "C", "D", "F"]
    details: str

class SecurityFinding(BaseModel):
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    type: str
    line: int
    description: str

class RecentChange(BaseModel):
    last_modified: datetime
    commit_hash: str
    author: str
    commit_message: str

class CodeContextResponse(BaseModel):
    file_path: str
    line_number: Optional[int]
    function_name: Optional[str]
    class_name: Optional[str]
    complexity: ComplexityInfo
    security_findings: List[SecurityFinding]
    code_smells: List[Dict[str, Any]]
    best_practices_violations: List[Dict[str, Any]]
    recent_changes: Optional[RecentChange]
    risk_score: float = Field(..., ge=0.0, le=1.0)
    risk_factors: List[str]
```

---

### Endpoint 10: POST /api/v1/iris/correlate-alert

**Purpose:** Correlate production alert with Hefesto findings (CRITICAL for OMEGA Guardian)

**Authentication:** Required

**Request:**
```http
POST /api/v1/iris/correlate-alert HTTP/1.1
Host: api.hefesto.dev
Content-Type: application/json

{
  "alert_id": "alert_prod_789",
  "error_type": "AttributeError",
  "error_message": "'NoneType' object has no attribute 'charge'",
  "stacktrace": "Traceback (most recent call last):\n  File \"src/payment_processor.py\", line 145, in process_payment\n    result = payment_gateway.charge(amount)\nAttributeError: 'NoneType' object has no attribute 'charge'",
  "timestamp": "2025-10-30T11:45:00Z",
  "service_name": "payment-service",
  "severity": "CRITICAL",
  "affected_users": 1234,
  "metadata": {
    "environment": "production",
    "region": "us-east-1"
  }
}
```

**Request Schema:**
```python
class AlertCorrelationRequest(BaseModel):
    alert_id: str
    error_type: str
    error_message: str
    stacktrace: str
    timestamp: datetime
    service_name: Optional[str] = None
    severity: Optional[Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]] = None
    affected_users: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = {}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "correlation_id": "corr_550e8400",
    "alert_id": "alert_prod_789",
    "correlation_found": true,
    "confidence_score": 0.92,
    "matching_findings": [
      {
        "finding_id": "finding_12345",
        "file_path": "src/payment_processor.py",
        "line_number": 145,
        "finding_type": "security",
        "severity": "HIGH",
        "description": "Potential null pointer dereference",
        "match_reason": "Stack trace line matches finding location",
        "match_confidence": 0.98
      },
      {
        "finding_id": "finding_12346",
        "file_path": "src/payment_processor.py",
        "line_number": 98,
        "finding_type": "complexity",
        "severity": "HIGH",
        "description": "High function complexity increases error probability",
        "match_reason": "Same file, complexity contributes to bugs",
        "match_confidence": 0.75
      }
    ],
    "suggested_root_cause": "Null reference error likely caused by missing validation. Complexity of function makes error handling difficult.",
    "related_files": [
      "src/payment_processor.py",
      "src/payment/gateway.py"
    ],
    "recommended_actions": [
      "Add null check before payment_gateway.charge() call",
      "Refactor process_payment() to reduce complexity",
      "Add unit tests for null payment gateway scenario",
      "Review error handling in payment flow"
    ],
    "cost_estimate": {
      "affected_users": 1234,
      "estimated_revenue_impact_usd": 45600,
      "calculation": "1234 users × $37 avg transaction value"
    }
  },
  "error": null,
  "timestamp": "2025-10-30T12:00:00Z"
}
```

**Response (200 OK - No Correlation):**
```json
{
  "success": true,
  "data": {
    "correlation_id": "corr_550e8401",
    "alert_id": "alert_prod_790",
    "correlation_found": false,
    "confidence_score": 0.0,
    "matching_findings": [],
    "suggested_root_cause": null,
    "related_files": [],
    "recommended_actions": [
      "No matching code quality findings. This may be a runtime environment issue.",
      "Check infrastructure logs",
      "Review recent deployments"
    ]
  },
  "error": null,
  "timestamp": "2025-10-30T12:00:00Z"
}
```

**Response Schema:**
```python
class MatchingFinding(BaseModel):
    finding_id: str
    file_path: str
    line_number: int
    finding_type: str
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    description: str
    match_reason: str
    match_confidence: float = Field(..., ge=0.0, le=1.0)

class CostEstimate(BaseModel):
    affected_users: int
    estimated_revenue_impact_usd: float
    calculation: str

class AlertCorrelationResponse(BaseModel):
    correlation_id: str
    alert_id: str
    correlation_found: bool
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    matching_findings: List[MatchingFinding]
    suggested_root_cause: Optional[str] = None
    related_files: List[str]
    recommended_actions: List[str]
    cost_estimate: Optional[CostEstimate] = None
```

---

### Endpoint 11: GET /api/v1/iris/findings-history

**Purpose:** Get historical findings for trend analysis (used by Iris dashboard)

**Authentication:** Required

**Request:**
```http
GET /api/v1/iris/findings-history?file_path=src/payment_processor.py&start_date=2025-10-01&end_date=2025-10-30&limit=100 HTTP/1.1
Host: api.hefesto.dev
```

**Query Parameters:**
```python
class FindingsHistoryQuery(BaseModel):
    file_path: Optional[str] = None
    finding_type: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = Field(default=50, ge=1, le=1000)
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "findings": [
      {
        "id": "finding_12345",
        "timestamp": "2025-10-29T15:30:00Z",
        "file_path": "src/payment_processor.py",
        "finding_type": "security",
        "severity": "HIGH",
        "description": "SQL injection vulnerability",
        "resolved": false,
        "resolution_date": null
      },
      {
        "id": "finding_11111",
        "timestamp": "2025-10-15T10:00:00Z",
        "file_path": "src/payment_processor.py",
        "finding_type": "complexity",
        "severity": "MEDIUM",
        "description": "Function complexity: 15",
        "resolved": true,
        "resolution_date": "2025-10-20T14:00:00Z"
      }
    ],
    "total_count": 87,
    "trend": {
      "direction": "degrading",
      "change_percentage": 15.3,
      "period_days": 30,
      "description": "15.3% increase in findings over last 30 days"
    },
    "summary": {
      "total_findings": 87,
      "resolved_findings": 34,
      "open_findings": 53,
      "average_resolution_time_hours": 72.5,
      "findings_by_severity": {
        "CRITICAL": 2,
        "HIGH": 15,
        "MEDIUM": 34,
        "LOW": 36
      }
    }
  },
  "error": null,
  "timestamp": "2025-10-30T12:00:00Z"
}
```

**Response Schema:**
```python
class FindingHistoryItem(BaseModel):
    id: str
    timestamp: datetime
    file_path: str
    finding_type: str
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    description: str
    resolved: bool
    resolution_date: Optional[datetime] = None

class TrendInfo(BaseModel):
    direction: Literal["improving", "degrading", "stable"]
    change_percentage: float
    period_days: int
    description: str

class FindingsSummary(BaseModel):
    total_findings: int
    resolved_findings: int
    open_findings: int
    average_resolution_time_hours: float
    findings_by_severity: Dict[str, int]

class FindingsHistoryResponse(BaseModel):
    findings: List[FindingHistoryItem]
    total_count: int
    trend: TrendInfo
    summary: FindingsSummary
```

---

### Endpoint 12: POST /api/v1/iris/webhook

**Purpose:** Webhook endpoint for Iris to push alerts to Hefesto (optional, future)

**Authentication:** Required (API key or webhook secret)

**Request:**
```http
POST /api/v1/iris/webhook HTTP/1.1
Host: api.hefesto.dev
Content-Type: application/json
X-Webhook-Signature: sha256=abc123def456...

{
  "alert_id": "alert_prod_789",
  "alert_type": "error_rate_spike",
  "timestamp": "2025-10-30T11:45:00Z",
  "payload": {
    "service": "payment-service",
    "error_count": 234,
    "time_window_minutes": 5,
    "severity": "CRITICAL"
  }
}
```

**Request Schema:**
```python
class WebhookRequest(BaseModel):
    alert_id: str
    alert_type: str
    timestamp: datetime
    payload: Dict[str, Any]
```

**Response (202 Accepted):**
```json
{
  "success": true,
  "data": {
    "received": true,
    "webhook_id": "webhook_550e8400",
    "processing_status": "queued",
    "estimated_processing_time_seconds": 5
  },
  "error": null,
  "timestamp": "2025-10-30T12:00:00Z"
}
```

**Response Schema:**
```python
class WebhookResponse(BaseModel):
    received: bool
    webhook_id: str
    processing_status: Literal["queued", "processing", "completed", "failed"]
    estimated_processing_time_seconds: int
```

---

## Phase 5: Metrics & Analytics

### Endpoint 13: GET /api/v1/metrics/summary

**Purpose:** Aggregate metrics of code quality across projects

**Authentication:** Required

**Request:**
```http
GET /api/v1/metrics/summary?start_date=2025-10-01&end_date=2025-10-30&project=payment-service HTTP/1.1
Host: api.hefesto.dev
```

**Query Parameters:**
```python
class MetricsSummaryQuery(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    project: Optional[str] = None
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "period": {
      "start": "2025-10-01T00:00:00Z",
      "end": "2025-10-30T23:59:59Z"
    },
    "total_analyses": 145,
    "total_findings": 1234,
    "findings_by_severity": {
      "CRITICAL": 23,
      "HIGH": 145,
      "MEDIUM": 567,
      "LOW": 499
    },
    "findings_by_analyzer": {
      "complexity": 456,
      "security": 234,
      "code_smells": 345,
      "best_practices": 199
    },
    "trend": "improving",
    "quality_score": 73.5,
    "quality_grade": "B",
    "comparison_previous_period": {
      "findings_change_percent": -12.3,
      "quality_score_change": 5.2
    }
  },
  "error": null,
  "timestamp": "2025-10-30T12:00:00Z"
}
```

**Response Schema:**
```python
class MetricsPeriod(BaseModel):
    start: datetime
    end: datetime

class PeriodComparison(BaseModel):
    findings_change_percent: float
    quality_score_change: float

class MetricsSummaryResponse(BaseModel):
    period: MetricsPeriod
    total_analyses: int
    total_findings: int
    findings_by_severity: Dict[str, int]
    findings_by_analyzer: Dict[str, int]
    trend: Literal["improving", "degrading", "stable"]
    quality_score: float = Field(..., ge=0.0, le=100.0)
    quality_grade: Literal["A", "B", "C", "D", "F"]
    comparison_previous_period: Optional[PeriodComparison] = None
```

---

### Endpoint 14: GET /api/v1/metrics/trends

**Purpose:** Time-series data of code quality trends

**Authentication:** Required

**Request:**
```http
GET /api/v1/metrics/trends?period=daily&days=30 HTTP/1.1
Host: api.hefesto.dev
```

**Query Parameters:**
```python
class MetricsTrendsQuery(BaseModel):
    period: Literal["daily", "weekly", "monthly"] = "daily"
    days: int = Field(default=30, ge=1, le=365)
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "period": "daily",
    "data_points": [
      {
        "date": "2025-10-01",
        "total_findings": 42,
        "critical": 2,
        "high": 8,
        "medium": 18,
        "low": 14,
        "quality_score": 71.2
      },
      {
        "date": "2025-10-02",
        "total_findings": 38,
        "critical": 1,
        "high": 7,
        "medium": 17,
        "low": 13,
        "quality_score": 73.8
      }
    ],
    "summary": {
      "average_quality_score": 73.5,
      "best_day": {
        "date": "2025-10-15",
        "quality_score": 85.2
      },
      "worst_day": {
        "date": "2025-10-03",
        "quality_score": 65.1
      }
    }
  },
  "error": null,
  "timestamp": "2025-10-30T12:00:00Z"
}
```

**Response Schema:**
```python
class TrendDataPoint(BaseModel):
    date: date
    total_findings: int
    critical: int
    high: int
    medium: int
    low: int
    quality_score: float

class DaySummary(BaseModel):
    date: date
    quality_score: float

class TrendsSummary(BaseModel):
    average_quality_score: float
    best_day: DaySummary
    worst_day: DaySummary

class MetricsTrendsResponse(BaseModel):
    period: Literal["daily", "weekly", "monthly"]
    data_points: List[TrendDataPoint]
    summary: TrendsSummary
```

---

## Phase 6: Configuration & Admin

### Endpoint 15: GET /api/v1/config

**Purpose:** Get current Hefesto configuration

**Authentication:** Required

**Request:**
```http
GET /api/v1/config HTTP/1.1
Host: api.hefesto.dev
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "version": "4.1.0",
    "analyzers": {
      "complexity": {
        "enabled": true,
        "thresholds": {
          "low": 5,
          "medium": 10,
          "high": 15,
          "critical": 20
        }
      },
      "security": {
        "enabled": true,
        "checks": [
          "sql_injection",
          "hardcoded_secrets",
          "eval_usage",
          "pickle_usage"
        ]
      },
      "code_smells": {
        "enabled": true,
        "max_function_lines": 50,
        "max_parameters": 5
      },
      "best_practices": {
        "enabled": true,
        "enforce_docstrings": true
      }
    },
    "integrations": {
      "bigquery": {
        "enabled": true,
        "project_id": "hefesto-prod",
        "dataset": "code_analysis"
      },
      "iris": {
        "enabled": true,
        "correlation_confidence_threshold": 0.7
      }
    },
    "license": {
      "tier": "pro",
      "features": [
        "ml_semantic_analysis",
        "duplicate_detection",
        "bigquery_analytics"
      ]
    }
  },
  "error": null,
  "timestamp": "2025-10-30T12:00:00Z"
}
```

**Response Schema:**
```python
class AnalyzerConfig(BaseModel):
    enabled: bool
    thresholds: Optional[Dict[str, int]] = None
    checks: Optional[List[str]] = None

class IntegrationConfig(BaseModel):
    enabled: bool

class BigQueryConfig(IntegrationConfig):
    project_id: Optional[str] = None
    dataset: Optional[str] = None

class IrisConfig(IntegrationConfig):
    correlation_confidence_threshold: float = 0.7

class LicenseInfo(BaseModel):
    tier: Literal["free", "pro", "enterprise"]
    features: List[str]

class ConfigResponse(BaseModel):
    version: str
    analyzers: Dict[str, AnalyzerConfig]
    integrations: Dict[str, Union[BigQueryConfig, IrisConfig, IntegrationConfig]]
    license: LicenseInfo
```

---

## Data Models

### Common Schemas

```python
# hefesto/api/schemas/common.py

from datetime import datetime
from typing import Any, Dict, Generic, Literal, Optional, TypeVar
from pydantic import BaseModel, Field

# Generic response wrapper
T = TypeVar("T")

class APIResponse(BaseModel, Generic[T]):
    """Standard API response format"""
    success: bool
    data: Optional[T] = None
    error: Optional["ErrorDetail"] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ErrorDetail(BaseModel):
    """Error information"""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None

class PaginationInfo(BaseModel):
    """Pagination metadata"""
    limit: int = Field(..., ge=1, le=1000)
    offset: int = Field(..., ge=0)
    has_more: bool
    next_offset: Optional[int] = None
    total_count: Optional[int] = None

# Re-export for convenience
__all__ = ["APIResponse", "ErrorDetail", "PaginationInfo"]
```

---

## Performance Requirements

### Latency Targets

| Endpoint | P50 | P95 | P99 |
|----------|-----|-----|-----|
| `GET /health` | <10ms | <20ms | <50ms |
| `GET /api/v1/status` | <50ms | <100ms | <200ms |
| `POST /api/v1/analyze` (single file) | <500ms | <1s | <2s |
| `POST /api/v1/analyze` (directory) | <2s | <5s | <10s |
| `GET /api/v1/findings` | <100ms | <200ms | <500ms |
| `POST /api/v1/iris/correlate-alert` | <200ms | <500ms | <1s |
| `GET /api/v1/metrics/summary` | <100ms | <300ms | <500ms |

### Throughput Targets

| Tier | Concurrent Requests | Requests/Second |
|------|-------------------|-----------------|
| **Free** | 10 | 10 |
| **Pro** | 100 | 100 |
| **Enterprise** | 1000 | 1000 |

### Database Query Limits
- Maximum query execution time: 5 seconds
- Pagination required for results >1000 rows
- Indexes on: `file_path`, `timestamp`, `severity`, `status`

---

## Security Considerations

### Input Validation
- All inputs validated with Pydantic
- File path sanitization (prevent directory traversal)
- SQL injection prevention (parameterized queries)
- Maximum request body size: 10MB

### Output Sanitization
- No raw stacktraces in production responses
- Mask sensitive data (API keys, tokens) in logs
- CORS configured per environment

### Rate Limiting
- Per-IP rate limiting (future)
- Per-API-key rate limiting (future)
- Exponential backoff for repeated 429s

### HTTPS Only
- Redirect HTTP → HTTPS
- HSTS header enabled
- TLS 1.2+ required

### Logging & Monitoring
- Structured JSON logs
- No PII in logs
- Request ID for tracing
- Performance metrics to Prometheus

---

## Deployment Considerations

### Environments

| Environment | URL | Purpose |
|-------------|-----|---------|
| **Development** | `http://localhost:8080` | Local development |
| **Staging** | `https://api-staging.hefesto.dev` | Pre-production testing |
| **Production** | `https://api.hefesto.dev` | Live production API |

### Health Checks
- Load balancer: `GET /health`
- Monitoring: `GET /api/v1/status`
- Kubernetes liveness: `GET /health`
- Kubernetes readiness: `GET /api/v1/status`

### Scaling Strategy
- Horizontal scaling (multiple uvicorn workers)
- Async/await for I/O-bound operations
- Connection pooling for BigQuery
- Redis for session/cache (future)

---

## OpenAPI Documentation

### Auto-Generated Docs

FastAPI automatically generates:
- **Swagger UI:** `https://api.hefesto.dev/docs`
- **ReDoc:** `https://api.hefesto.dev/redoc`
- **OpenAPI JSON:** `https://api.hefesto.dev/openapi.json`

### Example OpenAPI Snippet

```yaml
openapi: 3.0.0
info:
  title: Hefesto API
  version: 4.1.0
  description: AI-powered code quality analysis API
servers:
  - url: https://api.hefesto.dev
    description: Production
paths:
  /health:
    get:
      summary: Health check
      responses:
        '200':
          description: Service is healthy
  /api/v1/analyze:
    post:
      summary: Analyze code
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AnalysisRequest'
      responses:
        '200':
          description: Analysis completed successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AnalysisResponse'
```

---

## Appendix A: Migration from v1 to v2

When breaking changes are necessary:

1. Announce deprecation 6 months prior
2. Add `X-API-Deprecated: true` header to v1 responses
3. Document migration guide
4. Run both v1 and v2 in parallel for 6 months
5. Sunset v1 after transition period

Example deprecation header:
```
X-API-Deprecated: true
X-API-Sunset-Date: 2026-06-30T00:00:00Z
X-API-Replacement: /api/v2/analyze
```

---

## Appendix B: Testing Checklist

- [ ] Unit tests for all schemas (Pydantic validation)
- [ ] Unit tests for all service functions
- [ ] Integration tests for all endpoints
- [ ] Load tests (100 req/s sustained)
- [ ] Stress tests (500 req/s burst)
- [ ] Security tests (OWASP top 10)
- [ ] API contract tests (against OpenAPI spec)
- [ ] End-to-end tests with Iris integration

---

## Appendix C: Monitoring & Observability

### Metrics to Track
- Request latency (p50, p95, p99)
- Request volume by endpoint
- Error rate by endpoint
- Analysis execution time
- BigQuery query performance
- Cache hit rate (future)

### Alerts to Configure
- Health check failures
- Error rate >5%
- Latency p95 >2 seconds
- BigQuery query errors
- Rate limit exceeded patterns

---

**Document Version:** 1.0
**Status:** Ready for Implementation
**Next Steps:** See [API_IMPLEMENTATION_PLAN.md](./API_IMPLEMENTATION_PLAN.md)
