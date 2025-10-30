"""
Health check and system status endpoints.

Endpoints:
- GET /health - Basic health check (non-versioned, for load balancers)
- GET /api/v1/status - Detailed system status
"""

import time
from datetime import datetime

from fastapi import APIRouter

from hefesto.__version__ import __version__
from hefesto.api.schemas.common import APIResponse
from hefesto.api.schemas.health import (
    AnalyzerStatus,
    HealthResponse,
    IntegrationStatus,
    SystemStatusResponse,
)

router = APIRouter(tags=["Health & Monitoring"])

# Track application start time for uptime calculation
_app_start_time = time.time()


def get_uptime() -> int:
    """Get application uptime in seconds"""
    return int(time.time() - _app_start_time)


def check_analyzers() -> dict:
    """
    Check status of all code analyzers.

    Returns dict of analyzer_name -> AnalyzerStatus
    """
    # Import analyzers to verify they're available
    analyzers_status = {}

    try:
        from hefesto.analyzers import complexity  # noqa: F401

        analyzers_status["complexity"] = AnalyzerStatus.AVAILABLE
    except ImportError:
        analyzers_status["complexity"] = AnalyzerStatus.UNAVAILABLE

    try:
        from hefesto.analyzers import security  # noqa: F401

        analyzers_status["security"] = AnalyzerStatus.AVAILABLE
    except ImportError:
        analyzers_status["security"] = AnalyzerStatus.UNAVAILABLE

    try:
        from hefesto.analyzers import code_smells  # noqa: F401

        analyzers_status["code_smells"] = AnalyzerStatus.AVAILABLE
    except ImportError:
        analyzers_status["code_smells"] = AnalyzerStatus.UNAVAILABLE

    try:
        from hefesto.analyzers import best_practices  # noqa: F401

        analyzers_status["best_practices"] = AnalyzerStatus.AVAILABLE
    except ImportError:
        analyzers_status["best_practices"] = AnalyzerStatus.UNAVAILABLE

    return analyzers_status


def check_integrations() -> dict:
    """
    Check status of external integrations.

    Returns dict of integration_name -> IntegrationStatus
    """
    integrations_status = {}

    # Check BigQuery
    try:
        from google.cloud import bigquery  # noqa: F401

        # Could add actual connection test here
        integrations_status["bigquery"] = IntegrationStatus.ENABLED
    except ImportError:
        integrations_status["bigquery"] = IntegrationStatus.DISABLED

    # Iris integration (always enabled in v4.1.0+)
    integrations_status["iris"] = IntegrationStatus.ENABLED

    return integrations_status


@router.get(
    "/health",
    response_model=APIResponse[HealthResponse],
    summary="Basic health check",
    description="Simple health check endpoint for load balancers and monitoring systems. Returns healthy/unhealthy status.",  # noqa: E501
    responses={
        200: {
            "description": "Service is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": {
                            "status": "healthy",
                            "version": "4.1.0",
                            "timestamp": "2025-10-30T12:00:00Z",
                        },
                        "error": None,
                        "timestamp": "2025-10-30T12:00:00Z",
                    }
                }
            },
        }
    },
)
async def health_check():
    """
    Basic health check.

    Returns:
        APIResponse with HealthResponse data
    """
    return APIResponse(
        success=True,
        data=HealthResponse(status="healthy", version=__version__, timestamp=datetime.utcnow()),
    )


@router.get(
    "/api/v1/status",
    response_model=APIResponse[SystemStatusResponse],
    summary="Detailed system status",
    description="Comprehensive system status including analyzer health, integration status, and uptime.",  # noqa: E501
    responses={
        200: {
            "description": "System status retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": {
                            "status": "operational",
                            "version": "4.1.0",
                            "analyzers": {
                                "complexity": "available",
                                "security": "available",
                                "code_smells": "available",
                                "best_practices": "available",
                            },
                            "integrations": {"bigquery": "enabled", "iris": "enabled"},
                            "uptime_seconds": 3600,
                            "last_health_check": "2025-10-30T12:00:00Z",
                        },
                        "error": None,
                        "timestamp": "2025-10-30T12:00:00Z",
                    }
                }
            },
        }
    },
)
async def system_status():
    """
    Detailed system status.

    Checks:
    - Analyzer availability (complexity, security, code_smells, best_practices)
    - Integration status (BigQuery, Iris)
    - Application uptime

    Returns:
        APIResponse with SystemStatusResponse data
    """
    # Check analyzer health
    analyzers = check_analyzers()

    # Check integration status
    integrations = check_integrations()

    # Determine overall status
    all_analyzers_available = all(
        status == AnalyzerStatus.AVAILABLE for status in analyzers.values()
    )

    if all_analyzers_available:
        overall_status = "operational"
    else:
        overall_status = "degraded"

    return APIResponse(
        success=True,
        data=SystemStatusResponse(
            status=overall_status,
            version=__version__,
            analyzers=analyzers,
            integrations=integrations,
            uptime_seconds=get_uptime(),
            last_health_check=datetime.utcnow(),
        ),
    )
