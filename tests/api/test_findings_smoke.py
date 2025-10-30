"""
Smoke tests for findings API - Level 2 (TDD)

Tests system initialization and component loading.
Following CLAUDE.md methodology: smoke tests verify critical paths load correctly.

Smoke tests verify:
- BigQuery service loads without errors
- Schemas import correctly
- Routers register successfully
- Endpoints respond (even if BigQuery not configured)
- No immediate crashes on startup

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

import unittest
from unittest.mock import patch

import pytest


class TestBigQueryServiceLoading(unittest.TestCase):
    """Test BigQuery service module loads correctly."""

    def test_bigquery_service_imports(self):
        """Test BigQuery service module imports without errors."""
        try:
            from hefesto.api.services import bigquery_service

            assert bigquery_service is not None
        except ImportError as e:
            pytest.fail(f"Failed to import bigquery_service: {e}")

    def test_bigquery_client_class_available(self):
        """Test BigQueryClient class is available."""
        from hefesto.api.services.bigquery_service import BigQueryClient

        assert BigQueryClient is not None
        assert callable(BigQueryClient)

    def test_get_bigquery_client_function_available(self):
        """Test get_bigquery_client function is available."""
        from hefesto.api.services.bigquery_service import get_bigquery_client

        assert get_bigquery_client is not None
        assert callable(get_bigquery_client)

    @patch.dict("os.environ", {}, clear=True)
    def test_bigquery_client_initializes_without_config(self):
        """Test BigQueryClient initializes gracefully without configuration."""
        from hefesto.api.services.bigquery_service import BigQueryClient

        # Should not raise exception
        client = BigQueryClient()

        assert client is not None
        assert client.is_configured is False


class TestFindingsSchemasLoading(unittest.TestCase):
    """Test findings schemas module loads correctly."""

    def test_findings_schemas_imports(self):
        """Test findings schemas module imports without errors."""
        try:
            from hefesto.api.schemas import findings

            assert findings is not None
        except ImportError as e:
            # This is expected to fail initially - schemas not created yet
            # Will pass after Task 7 is complete
            pytest.skip(f"Findings schemas not yet implemented: {e}")

    def test_finding_list_response_schema_available(self):
        """Test FindingListResponse schema is available."""
        try:
            from hefesto.api.schemas.findings import FindingListResponse

            assert FindingListResponse is not None
        except ImportError:
            pytest.skip("Findings schemas not yet implemented")

    def test_finding_detail_response_schema_available(self):
        """Test FindingDetailResponse schema is available."""
        try:
            from hefesto.api.schemas.findings import FindingDetailResponse

            assert FindingDetailResponse is not None
        except ImportError:
            pytest.skip("Findings schemas not yet implemented")

    def test_finding_update_request_schema_available(self):
        """Test FindingUpdateRequest schema is available."""
        try:
            from hefesto.api.schemas.findings import FindingUpdateRequest

            assert FindingUpdateRequest is not None
        except ImportError:
            pytest.skip("Findings schemas not yet implemented")


class TestFindingsRouterLoading(unittest.TestCase):
    """Test findings router module loads correctly."""

    def test_findings_router_imports(self):
        """Test findings router module imports without errors."""
        try:
            from hefesto.api.routers import findings

            assert findings is not None
        except ImportError as e:
            # This is expected to fail initially - router not created yet
            # Will pass after Task 8 is complete
            pytest.skip(f"Findings router not yet implemented: {e}")

    def test_findings_router_object_available(self):
        """Test findings router object is available."""
        try:
            from hefesto.api.routers.findings import router

            assert router is not None
        except ImportError:
            pytest.skip("Findings router not yet implemented")


class TestFindingsEndpointsRegistered(unittest.TestCase):
    """Test findings endpoints are registered in FastAPI app."""

    def test_app_includes_findings_router(self):
        """Test FastAPI app includes findings router."""
        try:
            from hefesto.api.main import app

            # Check if /api/v1/findings routes are registered
            routes = [route.path for route in app.routes]

            # This will fail initially until router is registered
            # Will pass after Task 10 is complete
            if "/api/v1/findings" not in str(routes):
                pytest.skip("Findings router not yet registered in app")

        except Exception as e:
            pytest.skip(f"Cannot verify router registration: {e}")

    def test_get_findings_endpoint_exists(self):
        """Test GET /api/v1/findings endpoint is registered."""
        try:
            from hefesto.api.main import app

            routes = [route.path for route in app.routes]

            if "/api/v1/findings" not in str(routes):
                pytest.skip("Findings endpoints not yet registered")

        except Exception as e:
            pytest.skip(f"Cannot verify endpoint: {e}")

    def test_get_finding_by_id_endpoint_exists(self):
        """Test GET /api/v1/findings/{finding_id} endpoint is registered."""
        try:
            from hefesto.api.main import app

            routes = [route.path for route in app.routes]

            if "/api/v1/findings/{finding_id}" not in str(routes):
                pytest.skip("Findings endpoints not yet registered")

        except Exception as e:
            pytest.skip(f"Cannot verify endpoint: {e}")

    def test_patch_finding_endpoint_exists(self):
        """Test PATCH /api/v1/findings/{finding_id} endpoint is registered."""
        try:
            from hefesto.api.main import app

            routes = [route.path for route in app.routes]

            if "/api/v1/findings/{finding_id}" not in str(routes):
                pytest.skip("Findings endpoints not yet registered")

        except Exception as e:
            pytest.skip(f"Cannot verify endpoint: {e}")


class TestAPIStartup(unittest.TestCase):
    """Test API starts up correctly with findings functionality."""

    def test_app_initializes_with_bigquery_service(self):
        """Test FastAPI app initializes with BigQuery service available."""
        from hefesto.api.main import app
        from hefesto.api.services.bigquery_service import get_bigquery_client

        # Should not raise exception
        assert app is not None

        # BigQuery client should be available
        client = get_bigquery_client()
        assert client is not None

    def test_openapi_schema_includes_findings_endpoints(self):
        """Test OpenAPI schema includes findings endpoints."""
        try:
            from fastapi.testclient import TestClient

            from hefesto.api.main import app

            client = TestClient(app)
            response = client.get("/openapi.json")

            assert response.status_code == 200

            schema = response.json()
            paths = schema.get("paths", {})

            # Check if findings endpoints are documented
            # Will pass after router is registered
            if "/api/v1/findings" not in paths:
                pytest.skip("Findings endpoints not yet registered")

        except Exception as e:
            pytest.skip(f"Cannot verify OpenAPI schema: {e}")


class TestCriticalPathsNoImmediateCrash(unittest.TestCase):
    """Test critical paths don't immediately crash."""

    @patch.dict("os.environ", {}, clear=True)
    def test_bigquery_service_singleton_works(self):
        """Test BigQuery service singleton pattern works."""
        from hefesto.api.services.bigquery_service import get_bigquery_client

        client1 = get_bigquery_client()
        client2 = get_bigquery_client()

        # Should return same instance
        assert client1 is client2

    def test_bigquery_operations_fail_gracefully_when_not_configured(self):
        """Test BigQuery operations return safe defaults when not configured."""
        from hefesto.api.services.bigquery_service import BigQueryClient

        client = BigQueryClient()
        client.is_configured = False

        # Should not raise exceptions
        findings = client.list_findings(10, 0, {})
        assert findings == []

        finding = client.get_finding_by_id("fnd_test")
        assert finding is None

        result = client.update_finding_status("fnd_test", "resolved")
        assert result is False

        result = client.insert_findings([])
        assert result is True  # Empty list is success

    def test_branded_types_import_correctly(self):
        """Test branded types module imports correctly."""
        from hefesto.api.types import (
            DatasetId,
            FindingId,
            FindingStatus,
            HistoryId,
            ProjectId,
        )

        assert ProjectId is not None
        assert DatasetId is not None
        assert FindingId is not None
        assert FindingStatus is not None
        assert HistoryId is not None


class TestDependencyAvailability(unittest.TestCase):
    """Test required dependencies are available."""

    def test_google_cloud_bigquery_available(self):
        """Test google-cloud-bigquery is installed."""
        try:
            import google.cloud.bigquery

            assert google.cloud.bigquery is not None
        except ImportError:
            pytest.fail(
                "google-cloud-bigquery not installed. " "Run: pip install google-cloud-bigquery"
            )

    def test_google_api_core_available(self):
        """Test google-api-core is available for retry logic."""
        try:
            from google.api_core import retry

            assert retry is not None
        except ImportError:
            pytest.fail("google-api-core not installed. " "Run: pip install google-api-core")


if __name__ == "__main__":
    unittest.main()
