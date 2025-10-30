"""
API Schemas

Pydantic models for request validation and response serialization.
"""

from hefesto.api.schemas.analysis import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisSummarySchema,
    BatchAnalysisRequest,
    BatchAnalysisResponse,
    FindingSchema,
)
from hefesto.api.schemas.common import APIResponse, ErrorDetail, PaginationInfo
from hefesto.api.schemas.findings import (
    FindingDetailResponse,
    FindingListRequest,
    FindingListResponse,
    FindingUpdateRequest,
    FindingUpdateResponse,
    PaginationMeta,
)
from hefesto.api.schemas.health import (
    AnalyzerStatus,
    HealthResponse,
    IntegrationStatus,
    SystemStatusResponse,
)

__all__ = [
    # Common
    "APIResponse",
    "ErrorDetail",
    "PaginationInfo",
    # Health
    "HealthResponse",
    "SystemStatusResponse",
    "AnalyzerStatus",
    "IntegrationStatus",
    # Analysis
    "AnalysisRequest",
    "AnalysisResponse",
    "AnalysisSummarySchema",
    "FindingSchema",
    "BatchAnalysisRequest",
    "BatchAnalysisResponse",
    # Findings
    "FindingListRequest",
    "FindingListResponse",
    "FindingDetailResponse",
    "FindingUpdateRequest",
    "FindingUpdateResponse",
    "PaginationMeta",
]
