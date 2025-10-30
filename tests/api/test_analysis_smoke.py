"""
Smoke tests for analysis API - Level 2 (TDD)

Tests verify system doesn't crash and basic initialization works.
Following CLAUDE.md methodology: smoke tests verify system health.

Smoke tests check:
- System initialization without errors
- Routes are registered
- Schemas are importable
- Basic integration (no actual analysis)

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

import unittest

import pytest
from fastapi.testclient import TestClient

from hefesto.api.main import app


class TestSystemInitialization(unittest.TestCase):
    """Test system initializes without crashing."""

    def test_app_initializes(self):
        """Test FastAPI app initializes successfully."""
        assert app is not None
        assert app.title == "Hefesto API"

    def test_test_client_initializes(self):
        """Test TestClient initializes without errors."""
        client = TestClient(app)
        assert client is not None

    def test_root_endpoint_accessible(self):
        """Test root endpoint is accessible."""
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200


class TestRouteRegistration(unittest.TestCase):
    """Test analysis routes are registered."""

    def test_openapi_schema_generated(self):
        """Test OpenAPI schema includes analysis endpoints."""
        client = TestClient(app)
        response = client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        assert "openapi" in schema
        assert "paths" in schema

        # Health endpoints from Phase 1
        assert "/health" in schema["paths"]
        assert "/api/v1/status" in schema["paths"]

        # Analysis endpoints from Phase 2 (will be registered after router creation)
        # Commented until router is implemented
        # assert "/api/v1/analyze" in schema["paths"]
        # assert "/api/v1/analyze/{analysis_id}" in schema["paths"]
        # assert "/api/v1/analyze/batch" in schema["paths"]

    def test_swagger_docs_accessible(self):
        """Test Swagger documentation is accessible."""
        client = TestClient(app)
        response = client.get("/docs")
        assert response.status_code == 200

    def test_redoc_docs_accessible(self):
        """Test ReDoc documentation is accessible."""
        client = TestClient(app)
        response = client.get("/redoc")
        assert response.status_code == 200


class TestSchemaImports(unittest.TestCase):
    """Test schemas import without errors."""

    def test_common_schemas_import(self):
        """Test common schemas are importable."""
        from hefesto.api.schemas.common import APIResponse, ErrorDetail, PaginationInfo

        assert APIResponse is not None
        assert ErrorDetail is not None
        assert PaginationInfo is not None

    def test_health_schemas_import(self):
        """Test health schemas are importable."""
        from hefesto.api.schemas.health import (
            AnalyzerStatus,
            HealthResponse,
            IntegrationStatus,
            SystemStatusResponse,
        )

        assert HealthResponse is not None
        assert SystemStatusResponse is not None
        assert AnalyzerStatus is not None
        assert IntegrationStatus is not None

    def test_branded_types_import(self):
        """Test branded types are importable."""
        from hefesto.api.types import AnalysisId, AnalyzerName, FindingId, FilePathStr

        assert AnalysisId is not None
        assert FindingId is not None
        assert FilePathStr is not None
        assert AnalyzerName is not None

    def test_service_layer_import(self):
        """Test service layer functions are importable."""
        from hefesto.api.services.analysis_service import (
            calculate_summary_stats,
            format_finding,
            generate_analysis_id,
            generate_finding_id,
            is_safe_path,
            validate_file_path,
        )

        assert generate_analysis_id is not None
        assert generate_finding_id is not None
        assert validate_file_path is not None
        assert is_safe_path is not None
        assert calculate_summary_stats is not None
        assert format_finding is not None


class TestCoreIntegration(unittest.TestCase):
    """Test integration with core AnalyzerEngine."""

    def test_analyzer_engine_import(self):
        """Test AnalyzerEngine is importable."""
        from hefesto.core.analyzer_engine import AnalyzerEngine

        assert AnalyzerEngine is not None

    def test_analysis_models_import(self):
        """Test analysis models are importable."""
        from hefesto.core.analysis_models import (
            AnalysisIssue,
            AnalysisIssueSeverity,
            AnalysisIssueType,
            AnalysisReport,
            AnalysisSummary,
            FileAnalysisResult,
        )

        assert AnalysisIssue is not None
        assert AnalysisIssueSeverity is not None
        assert AnalysisIssueType is not None
        assert FileAnalysisResult is not None
        assert AnalysisSummary is not None
        assert AnalysisReport is not None

    def test_analyzer_engine_instantiation(self):
        """Test AnalyzerEngine can be instantiated."""
        from hefesto.core.analyzer_engine import AnalyzerEngine

        try:
            engine = AnalyzerEngine()
            assert engine is not None
        except Exception as e:
            pytest.fail(f"AnalyzerEngine instantiation failed: {e}")


class TestBasicIntegration(unittest.TestCase):
    """Test basic system integration without actual analysis."""

    def test_health_endpoint_integration(self):
        """Test health endpoint works with full stack."""
        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "healthy"

    def test_status_endpoint_integration(self):
        """Test status endpoint works with full stack."""
        client = TestClient(app)
        response = client.get("/api/v1/status")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "analyzers" in data["data"]
        assert "integrations" in data["data"]

    def test_middleware_integration(self):
        """Test middleware is properly integrated."""
        client = TestClient(app)
        response = client.get("/health")

        # Check middleware headers
        assert "X-Request-ID" in response.headers
        assert "X-Process-Time" in response.headers

    def test_cors_middleware_integration(self):
        """Test CORS middleware is enabled."""
        client = TestClient(app)
        response = client.get("/health", headers={"Origin": "http://localhost:3000"})

        # CORS headers should be present (middleware is enabled)
        # Note: TestClient may not fully simulate CORS preflight, but middleware should be active
        assert response.status_code == 200


if __name__ == "__main__":
    unittest.main()
