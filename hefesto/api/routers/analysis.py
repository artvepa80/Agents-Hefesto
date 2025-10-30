"""
Code analysis endpoints.

Endpoints:
- POST /api/v1/analyze - Analyze single file or directory
- GET /api/v1/analyze/{analysis_id} - Retrieve analysis results
- POST /api/v1/analyze/batch - Batch analysis

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

import time
from datetime import datetime
from typing import Dict

from fastapi import APIRouter, HTTPException, Path, status

from hefesto.api.schemas.analysis import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisSummarySchema,
    BatchAnalysisRequest,
    BatchAnalysisResponse,
    FindingSchema,
)
from hefesto.api.schemas.common import APIResponse, ErrorDetail
from hefesto.api.services.analysis_service import (
    calculate_summary_stats,
    format_finding,
    generate_analysis_id,
    generate_finding_id,
    validate_file_path,
)
from hefesto.api.services.bigquery_service import get_bigquery_client
from hefesto.core.analyzer_engine import AnalyzerEngine

router = APIRouter(tags=["Code Analysis"], prefix="/api/v1")

# In-memory cache for Phase 2 (synchronous analysis)
# Phase 3 will use BigQuery for persistence
_analysis_cache: Dict[str, AnalysisResponse] = {}


@router.post(
    "/analyze",
    response_model=APIResponse[AnalysisResponse],
    summary="Analyze code (single path)",
    description="Analyze a single file or directory for code quality issues. Returns immediate results (synchronous).",  # noqa: E501
    responses={
        200: {"description": "Analysis completed successfully"},
        400: {"description": "Invalid request (path validation failed)"},
        500: {"description": "Analysis failed due to internal error"},
    },
)
async def analyze_code(request: AnalysisRequest):
    """
    Analyze code quality for a single file or directory.

    Phase 2: Synchronous analysis with in-memory caching.

    Args:
        request: Analysis request with path and options

    Returns:
        APIResponse with AnalysisResponse data
    """
    started_at = datetime.utcnow()
    analysis_id = generate_analysis_id()

    try:
        # Validate path security and existence
        validate_file_path(request.path)

        # Initialize analyzer engine
        engine = AnalyzerEngine()

        # Run analysis
        start_time = time.time()
        report = engine.analyze_path(path=request.path, exclude_patterns=request.exclude_patterns)
        duration = time.time() - start_time

        # Calculate summary stats
        summary_dict = calculate_summary_stats(report.file_results, duration_seconds=duration)
        summary = AnalysisSummarySchema(**summary_dict)

        # Format findings
        findings = []
        for issue in report.get_all_issues():
            finding_id = generate_finding_id()
            formatted = format_finding(issue, finding_id)
            findings.append(FindingSchema(**formatted))

        # Create response
        completed_at = datetime.utcnow()
        analysis_response = AnalysisResponse(
            analysis_id=analysis_id,
            status="completed",
            path=request.path,
            summary=summary,
            findings=findings,
            started_at=started_at,
            completed_at=completed_at,
            error_message=None,
        )

        # Cache result for GET endpoint
        _analysis_cache[analysis_id] = analysis_response

        # Phase 3: Persist to BigQuery if configured
        bq_client = get_bigquery_client()
        if bq_client.is_configured:
            try:
                # Prepare findings data for BigQuery
                findings_data = []
                for finding in findings:
                    finding_data = {
                        "id": finding.id,
                        "analysis_id": analysis_id,
                        "file": finding.file,
                        "line": finding.line,
                        "column": finding.column,
                        "type": finding.type,
                        "severity": finding.severity,
                        "message": finding.message,
                        "function": finding.function,
                        "suggestion": finding.suggestion,
                        "code_snippet": finding.code_snippet,
                        "metadata": finding.metadata,
                    }
                    findings_data.append(finding_data)

                # Insert findings
                if findings_data:
                    bq_client.insert_findings(findings_data)

                # Insert analysis run metadata
                analysis_data = {
                    "analysis_id": analysis_id,
                    "path": request.path,
                    "analyzers": request.analyzers or [],
                    "summary": {
                        "total_issues": summary.total_issues,
                        "critical": summary.critical,
                        "high": summary.high,
                        "medium": summary.medium,
                        "low": summary.low,
                        "duration_seconds": summary.duration_seconds,
                    },
                }
                bq_client.insert_analysis_run(analysis_data)

            except Exception as bq_error:
                # Log BigQuery error but don't fail the analysis
                # Findings are still available in cache
                import logging

                logging.warning(f"Failed to persist analysis {analysis_id} to BigQuery: {bq_error}")

        return APIResponse(success=True, data=analysis_response)

    except ValueError as e:
        # Path validation errors
        return APIResponse(
            success=False,
            data=None,
            error=ErrorDetail(
                code="INVALID_PATH",
                message=str(e),
                details={"path": request.path, "analysis_id": analysis_id},
            ),
        )

    except Exception as e:
        # Analysis execution errors
        completed_at = datetime.utcnow()
        error_response = AnalysisResponse(
            analysis_id=analysis_id,
            status="failed",
            path=request.path,
            summary=AnalysisSummarySchema(
                files_analyzed=0,
                total_issues=0,
                critical=0,
                high=0,
                medium=0,
                low=0,
                total_loc=0,
                duration_seconds=0.0,
            ),
            findings=[],
            started_at=started_at,
            completed_at=completed_at,
            error_message=str(e),
        )

        # Cache failed result
        _analysis_cache[analysis_id] = error_response

        return APIResponse(
            success=False,
            data=error_response,
            error=ErrorDetail(
                code="ANALYSIS_FAILED", message=f"Analysis failed: {str(e)}", details={}
            ),
        )


@router.get(
    "/analyze/{analysis_id}",
    response_model=APIResponse[AnalysisResponse],
    summary="Get analysis results",
    description="Retrieve results for a previously run analysis by analysis_id.",
    responses={
        200: {"description": "Analysis results retrieved successfully"},
        404: {"description": "Analysis not found"},
    },
)
async def get_analysis(
    analysis_id: str = Path(..., description="Analysis ID (ana_*)", pattern="^ana_[a-z0-9]{23}$")
):
    """
    Retrieve analysis results by ID.

    Phase 2: Results retrieved from in-memory cache.
    Phase 3: Will query BigQuery for persistence.

    Args:
        analysis_id: Unique analysis identifier

    Returns:
        APIResponse with AnalysisResponse data
    """
    if analysis_id not in _analysis_cache:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis not found: {analysis_id}",
        )

    analysis = _analysis_cache[analysis_id]
    return APIResponse(success=True, data=analysis)


@router.post(
    "/analyze/batch",
    response_model=APIResponse[BatchAnalysisResponse],
    summary="Batch code analysis",
    description="Analyze multiple files or directories in a single request. Returns immediate results (synchronous).",  # noqa: E501
    responses={
        200: {"description": "Batch analysis completed"},
        400: {"description": "Invalid request (validation failed)"},
    },
)
async def analyze_batch(request: BatchAnalysisRequest):
    """
    Analyze multiple paths in a single batch.

    Phase 2: Synchronous batch processing (sequential execution).
    Phase 3: May add async processing for large batches.

    Args:
        request: Batch analysis request with multiple paths

    Returns:
        APIResponse with BatchAnalysisResponse data
    """
    batch_id = generate_analysis_id()  # Reuse analysis ID generator
    started_at = datetime.utcnow()
    results = []
    completed_count = 0
    failed_count = 0

    # Process each path sequentially
    for path in request.paths:
        # Create individual analysis request
        individual_request = AnalysisRequest(
            path=path, exclude_patterns=request.exclude_patterns, analyzers=request.analyzers
        )

        # Run analysis (reuse single analysis logic)
        response = await analyze_code(individual_request)

        if response.success and response.data:
            results.append(response.data)
            if response.data.status == "completed":
                completed_count += 1
            else:
                failed_count += 1
        else:
            # Create failed response for this path
            failed_response = AnalysisResponse(
                analysis_id=generate_analysis_id(),
                status="failed",
                path=path,
                summary=AnalysisSummarySchema(
                    files_analyzed=0,
                    total_issues=0,
                    critical=0,
                    high=0,
                    medium=0,
                    low=0,
                    total_loc=0,
                    duration_seconds=0.0,
                ),
                findings=[],
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                error_message=response.error.message if response.error else "Unknown error",
            )
            results.append(failed_response)
            failed_count += 1

    completed_at = datetime.utcnow()

    batch_response = BatchAnalysisResponse(
        batch_id=batch_id,
        total_analyses=len(request.paths),
        completed=completed_count,
        failed=failed_count,
        results=results,
        started_at=started_at,
        completed_at=completed_at,
    )

    return APIResponse(success=True, data=batch_response)


__all__ = ["router"]
