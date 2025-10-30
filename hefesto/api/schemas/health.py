"""
Schemas for health check and system status endpoints.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, Literal

from pydantic import BaseModel, Field


class AnalyzerStatus(str, Enum):
    """Status of individual analyzer"""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"


class IntegrationStatus(str, Enum):
    """Status of external integration"""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ENABLED = "enabled"
    DISABLED = "disabled"


class HealthResponse(BaseModel):
    """
    Response for GET /health endpoint.

    Simple health check for load balancers and monitoring.
    Should respond in <10ms.
    """

    status: Literal["healthy", "unhealthy"] = Field(..., description="Overall health status")
    version: str = Field(..., description="Hefesto version", examples=["4.1.0"])
    timestamp: datetime = Field(..., description="Health check timestamp (UTC)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "healthy",
                "version": "4.1.0",
                "timestamp": "2025-10-30T12:00:00Z",
            }
        }
    }


class SystemStatusResponse(BaseModel):
    """
    Response for GET /api/v1/status endpoint.

    Detailed system status including analyzer and integration health.
    Should respond in <50ms.
    """

    status: Literal["operational", "degraded", "outage"] = Field(
        ..., description="Overall system status"
    )
    version: str = Field(..., description="Hefesto version", examples=["4.1.0"])
    analyzers: Dict[str, AnalyzerStatus] = Field(..., description="Status of each code analyzer")
    integrations: Dict[str, IntegrationStatus] = Field(
        ..., description="Status of external integrations"
    )
    uptime_seconds: int = Field(..., ge=0, description="Seconds since application start")
    last_health_check: datetime = Field(..., description="Last health check timestamp (UTC)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "operational",
                "version": "4.1.0",
                "analyzers": {
                    "complexity": "available",
                    "security": "available",
                    "code_smells": "available",
                    "best_practices": "available",
                },
                "integrations": {"bigquery": "connected", "iris": "enabled"},
                "uptime_seconds": 3600,
                "last_health_check": "2025-10-30T12:00:00Z",
            }
        }
    }


# Re-export
__all__ = ["HealthResponse", "SystemStatusResponse", "AnalyzerStatus", "IntegrationStatus"]
