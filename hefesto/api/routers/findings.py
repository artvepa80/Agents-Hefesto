"""
Findings management endpoints.

Endpoints:
- GET /api/v1/findings - List findings with pagination and filters
- GET /api/v1/findings/{finding_id} - Get single finding by ID
- PATCH /api/v1/findings/{finding_id} - Update finding status

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Path, Query, status

from hefesto.api.schemas.common import APIResponse, ErrorDetail
from hefesto.api.schemas.findings import (
    FindingDetailResponse,
    FindingListResponse,
    FindingUpdateRequest,
    FindingUpdateResponse,
    PaginationMeta,
)
from hefesto.api.services.bigquery_service import get_bigquery_client

router = APIRouter(tags=["Findings Management"], prefix="/api/v1")


@router.get(
    "/findings",
    response_model=APIResponse[FindingListResponse],
    summary="List findings",
    description="List code quality findings with pagination and filters. "
    "Retrieves findings from BigQuery if configured, otherwise returns empty list.",
    responses={
        200: {"description": "Findings retrieved successfully"},
        400: {"description": "Invalid query parameters"},
        500: {"description": "Internal server error"},
    },
)
async def list_findings(
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of findings to return",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of findings to skip",
    ),
    severity: Optional[str] = Query(
        default=None,
        description="Filter by severity (CRITICAL, HIGH, MEDIUM, LOW)",
    ),
    file_path: Optional[str] = Query(
        default=None,
        description="Filter by file path (exact match)",
    ),
    analyzer: Optional[str] = Query(
        default=None,
        description="Filter by analyzer name",
    ),
    status: Optional[str] = Query(
        default=None,
        description="Filter by finding status (new, in_progress, resolved, ignored, false_positive)",  # noqa: E501
    ),
    start_date: Optional[str] = Query(
        default=None,
        description="Filter by created_at >= start_date (ISO format)",
    ),
    end_date: Optional[str] = Query(
        default=None,
        description="Filter by created_at <= end_date (ISO format)",
    ),
):
    """
    List code quality findings with pagination and filters.

    Phase 3: Retrieves findings from user's BigQuery project if configured.
    Gracefully degrades to empty results if BigQuery not configured.

    Args:
        limit: Maximum number of results (1-1000)
        offset: Number of results to skip
        severity: Filter by severity level
        file_path: Filter by exact file path
        analyzer: Filter by analyzer name
        status: Filter by finding status
        start_date: Filter by created_at >= start_date
        end_date: Filter by created_at <= end_date

    Returns:
        APIResponse with FindingListResponse data
    """
    try:
        # Build filters dictionary
        filters: Dict[str, Any] = {}

        if severity:
            # Validate severity
            valid_severities = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
            if severity not in valid_severities:
                return APIResponse(
                    success=False,
                    error=ErrorDetail(
                        code="INVALID_SEVERITY",
                        message=f"Invalid severity: {severity}. "
                        f"Valid options: {', '.join(valid_severities)}",
                    ),
                )
            filters["severity"] = severity

        if file_path:
            filters["file_path"] = file_path

        if analyzer:
            # Validate analyzer
            valid_analyzers = {"complexity", "security", "code_smells", "best_practices"}
            if analyzer not in valid_analyzers:
                return APIResponse(
                    success=False,
                    error=ErrorDetail(
                        code="INVALID_ANALYZER",
                        message=f"Invalid analyzer: {analyzer}. "
                        f"Valid options: {', '.join(valid_analyzers)}",
                    ),
                )
            filters["analyzer"] = analyzer

        if status:
            # Validate status
            valid_statuses = {"new", "in_progress", "resolved", "ignored", "false_positive"}
            if status not in valid_statuses:
                return APIResponse(
                    success=False,
                    error=ErrorDetail(
                        code="INVALID_STATUS",
                        message=f"Invalid status: {status}. "
                        f"Valid options: {', '.join(valid_statuses)}",
                    ),
                )
            filters["status"] = status

        if start_date:
            filters["start_date"] = start_date

        if end_date:
            filters["end_date"] = end_date

        # Get BigQuery client
        bq_client = get_bigquery_client()

        # Query findings
        findings = bq_client.list_findings(limit=limit, offset=offset, filters=filters)

        # Build pagination metadata
        # Note: For Phase 3, we approximate has_more by checking if we got a full page
        # Phase 4 can enhance this with COUNT queries
        has_more = len(findings) == limit

        pagination = PaginationMeta(
            total=len(findings) + offset,  # Approximate total
            limit=limit,
            offset=offset,
            has_more=has_more,
        )

        # Build response
        response_data = FindingListResponse(
            findings=findings,
            pagination=pagination,
            filters_applied=filters,
            bigquery_available=bq_client.is_configured,
        )

        return APIResponse(success=True, data=response_data)

    except Exception as e:
        return APIResponse(
            success=False,
            error=ErrorDetail(
                code="FINDINGS_LIST_ERROR",
                message=f"Failed to list findings: {str(e)}",
                details={"exception_type": type(e).__name__},
            ),
        )


@router.get(
    "/findings/{finding_id}",
    response_model=APIResponse[FindingDetailResponse],
    summary="Get finding by ID",
    description="Retrieve detailed information for a specific finding by its ID. "
    "Retrieves from BigQuery if configured.",
    responses={
        200: {"description": "Finding retrieved successfully"},
        404: {"description": "Finding not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_finding(
    finding_id: str = Path(
        ...,
        description="Finding identifier (format: fnd_*)",
        min_length=4,
        max_length=100,
    ),
):
    """
    Get detailed information for a specific finding.

    Phase 3: Retrieves from BigQuery if configured.

    Args:
        finding_id: Finding identifier (fnd_*)

    Returns:
        APIResponse with FindingDetailResponse data

    Raises:
        404: Finding not found
    """
    try:
        # Validate finding_id format
        if not finding_id.startswith("fnd_"):
            return APIResponse(
                success=False,
                error=ErrorDetail(
                    code="INVALID_FINDING_ID",
                    message=f"Invalid finding_id format: {finding_id}. " f"Must start with 'fnd_'",
                ),
            )

        # Get BigQuery client
        bq_client = get_bigquery_client()

        # Query finding
        finding = bq_client.get_finding_by_id(finding_id)

        if not finding:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Finding not found: {finding_id}",
            )

        # Build response
        response_data = FindingDetailResponse(
            finding=finding,
            related_findings=None,  # Phase 4 enhancement
            history=None,  # Phase 4 enhancement
            bigquery_available=bq_client.is_configured,
        )

        return APIResponse(success=True, data=response_data)

    except HTTPException:
        # Re-raise HTTP exceptions (404)
        raise
    except Exception as e:
        return APIResponse(
            success=False,
            error=ErrorDetail(
                code="FINDING_GET_ERROR",
                message=f"Failed to retrieve finding: {str(e)}",
                details={"finding_id": finding_id, "exception_type": type(e).__name__},
            ),
        )


@router.patch(
    "/findings/{finding_id}",
    response_model=APIResponse[FindingUpdateResponse],
    summary="Update finding status",
    description="Update the status of a finding (e.g., mark as resolved, ignored, false positive). "
    "Updates BigQuery if configured and creates history entry.",
    responses={
        200: {"description": "Finding updated successfully"},
        404: {"description": "Finding not found"},
        400: {"description": "Invalid update request"},
        500: {"description": "Internal server error"},
    },
)
async def update_finding(
    request: FindingUpdateRequest,
    finding_id: str = Path(
        ...,
        description="Finding identifier (format: fnd_*)",
        min_length=4,
        max_length=100,
    ),
):
    """
    Update finding status and create history entry.

    Phase 3: Updates BigQuery if configured, creates history record.

    Args:
        finding_id: Finding identifier (fnd_*)
        request: Update request with new status and optional notes

    Returns:
        APIResponse with FindingUpdateResponse data

    Raises:
        404: Finding not found
        400: Invalid update request
    """
    try:
        # Validate finding_id format
        if not finding_id.startswith("fnd_"):
            return APIResponse(
                success=False,
                error=ErrorDetail(
                    code="INVALID_FINDING_ID",
                    message=f"Invalid finding_id format: {finding_id}. " f"Must start with 'fnd_'",
                ),
            )

        # Get BigQuery client
        bq_client = get_bigquery_client()

        if not bq_client.is_configured:
            return APIResponse(
                success=False,
                error=ErrorDetail(
                    code="BIGQUERY_NOT_CONFIGURED",
                    message="Cannot update finding: BigQuery not configured. "
                    "See docs/BIGQUERY_SETUP_GUIDE.md for setup instructions.",
                    details={"finding_id": finding_id},
                ),
            )

        # Get current finding to retrieve previous status
        current_finding = bq_client.get_finding_by_id(finding_id)

        if not current_finding:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Finding not found: {finding_id}",
            )

        previous_status = current_finding.get("metadata", {}).get("status")

        # Update finding status
        success = bq_client.update_finding_status(
            finding_id=finding_id,
            new_status=request.status,
            updated_by=request.updated_by,
            notes=request.notes,
        )

        if not success:
            return APIResponse(
                success=False,
                error=ErrorDetail(
                    code="FINDING_UPDATE_FAILED",
                    message="Failed to update finding status in BigQuery",
                    details={"finding_id": finding_id},
                ),
            )

        # Build response
        response_data = FindingUpdateResponse(
            finding_id=finding_id,
            previous_status=previous_status,
            new_status=request.status,
            updated_at=datetime.utcnow(),
            updated_by=request.updated_by,
            bigquery_available=True,
        )

        return APIResponse(success=True, data=response_data)

    except HTTPException:
        # Re-raise HTTP exceptions (404)
        raise
    except Exception as e:
        return APIResponse(
            success=False,
            error=ErrorDetail(
                code="FINDING_UPDATE_ERROR",
                message=f"Failed to update finding: {str(e)}",
                details={"finding_id": finding_id, "exception_type": type(e).__name__},
            ),
        )


__all__ = ["router"]
