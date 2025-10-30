"""
Canary tests for findings API - Level 3 (TDD)

Tests with real BigQuery operations (if configured).
Following CLAUDE.md methodology: canary tests use real systems at small scale.

Canary tests verify:
- Real BigQuery queries (if configured)
- End-to-end finding list/get/update flow
- API response correctness with real BigQuery data
- Graceful degradation when BigQuery not configured

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from hefesto.api.main import app
from hefesto.api.services.bigquery_service import get_bigquery_client

client = TestClient(app)


class TestFindingsEndpointsWithBigQuery(unittest.TestCase):
    """Test findings endpoints with real BigQuery (if configured)."""

    def test_list_findings_endpoint_responds(self):
        """Test GET /api/v1/findings responds successfully."""
        response = client.get("/api/v1/findings?limit=10")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "data" in data
        assert "findings" in data["data"]
        assert "pagination" in data["data"]
        assert "bigquery_available" in data["data"]

    def test_list_findings_with_filters(self):
        """Test GET /api/v1/findings with severity filter."""
        response = client.get("/api/v1/findings?limit=10&severity=HIGH")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["data"]["filters_applied"].get("severity") == "HIGH"

        # If findings returned, verify they match filter
        for finding in data["data"]["findings"]:
            assert finding["severity"] == "HIGH"

    def test_list_findings_with_invalid_severity(self):
        """Test GET /api/v1/findings with invalid severity returns error."""
        response = client.get("/api/v1/findings?severity=INVALID")

        assert response.status_code == 200  # API returns 200 with error in body
        data = response.json()

        assert data["success"] is False
        assert data["error"]["code"] == "INVALID_SEVERITY"

    def test_list_findings_pagination(self):
        """Test findings pagination works correctly."""
        # First page
        response1 = client.get("/api/v1/findings?limit=5&offset=0")
        assert response1.status_code == 200
        data1 = response1.json()

        assert data1["success"] is True
        assert data1["data"]["pagination"]["limit"] == 5
        assert data1["data"]["pagination"]["offset"] == 0

        # Second page
        response2 = client.get("/api/v1/findings?limit=5&offset=5")
        assert response2.status_code == 200
        data2 = response2.json()

        assert data2["success"] is True
        assert data2["data"]["pagination"]["limit"] == 5
        assert data2["data"]["pagination"]["offset"] == 5

    def test_get_finding_by_id_not_found(self):
        """Test GET /api/v1/findings/{id} returns 404 for non-existent finding."""
        response = client.get("/api/v1/findings/fnd_nonexistent12345678901")

        # Should return 404 for not found
        assert response.status_code == 404

    def test_get_finding_by_id_invalid_format(self):
        """Test GET /api/v1/findings/{id} validates ID format."""
        response = client.get("/api/v1/findings/invalid_format")

        assert response.status_code == 200  # API returns 200 with error in body
        data = response.json()

        assert data["success"] is False
        assert data["error"]["code"] == "INVALID_FINDING_ID"

    def test_update_finding_without_bigquery_configured(self):
        """Test PATCH /api/v1/findings/{id} when BigQuery not configured."""
        bq_client = get_bigquery_client()

        if bq_client.is_configured:
            self.skipTest("BigQuery is configured, cannot test unconfigured behavior")

        response = client.patch(
            "/api/v1/findings/fnd_test123",
            json={"status": "resolved", "updated_by": "test@example.com"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is False
        assert data["error"]["code"] == "BIGQUERY_NOT_CONFIGURED"

    def test_update_finding_invalid_id_format(self):
        """Test PATCH /api/v1/findings/{id} validates ID format."""
        response = client.patch(
            "/api/v1/findings/invalid_format",
            json={"status": "resolved", "updated_by": "test@example.com"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is False
        assert data["error"]["code"] == "INVALID_FINDING_ID"


class TestEndToEndWithAnalysis(unittest.TestCase):
    """Test end-to-end flow: analyze -> list findings."""

    def test_analyze_then_list_findings(self):
        """Test analyzing code then listing findings (if BigQuery configured)."""
        # Create temp file with intentional issues
        code = '''
def complex_function(a, b, c, d, e, f):
    """Function with high complexity."""
    if a > 0:
        if b > 0:
            if c > 0:
                if d > 0:
                    if e > 0:
                        if f > 0:
                            return a + b + c + d + e + f
    return 0
'''

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            # Run analysis
            analyze_response = client.post("/api/v1/analyze", json={"path": temp_path})

            assert analyze_response.status_code == 200
            analyze_data = analyze_response.json()
            assert analyze_data["success"] is True

            # If BigQuery configured, findings should be queryable
            bq_client = get_bigquery_client()
            if bq_client.is_configured:
                # List findings (may include our newly created findings)
                list_response = client.get("/api/v1/findings?limit=100")

                assert list_response.status_code == 200
                list_data = list_response.json()

                assert list_data["success"] is True
                assert list_data["data"]["bigquery_available"] is True

        finally:
            Path(temp_path).unlink()


class TestGracefulDegradation(unittest.TestCase):
    """Test system works correctly when BigQuery not configured."""

    def test_findings_endpoints_work_without_bigquery(self):
        """Test all findings endpoints respond gracefully without BigQuery."""
        bq_client = get_bigquery_client()

        # List findings
        list_response = client.get("/api/v1/findings?limit=10")
        assert list_response.status_code == 200
        list_data = list_response.json()

        assert list_data["success"] is True
        assert list_data["data"]["bigquery_available"] == bq_client.is_configured

        if not bq_client.is_configured:
            # Should return empty findings
            assert list_data["data"]["findings"] == []

        # Get finding by ID (should return 404 or not found)
        get_response = client.get("/api/v1/findings/fnd_test123")
        assert get_response.status_code in [200, 404]

        # Update finding (should return error)
        update_response = client.patch(
            "/api/v1/findings/fnd_test123",
            json={"status": "resolved", "updated_by": "test@example.com"},
        )
        assert update_response.status_code == 200

        if not bq_client.is_configured:
            update_data = update_response.json()
            assert update_data["success"] is False


class TestOpenAPIDocumentation(unittest.TestCase):
    """Test findings endpoints are documented in OpenAPI schema."""

    def test_findings_endpoints_in_openapi_schema(self):
        """Test findings endpoints appear in OpenAPI schema."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        paths = schema["paths"]

        # Verify all 3 Phase 3 endpoints are documented
        assert "/api/v1/findings" in paths
        assert "/api/v1/findings/{finding_id}" in paths

        # Verify GET /api/v1/findings has proper documentation
        list_endpoint = paths["/api/v1/findings"]["get"]
        assert "summary" in list_endpoint
        assert "description" in list_endpoint
        assert "parameters" in list_endpoint
        assert "responses" in list_endpoint

        # Verify GET /api/v1/findings/{finding_id} exists
        get_endpoint = paths["/api/v1/findings/{finding_id}"]["get"]
        assert "summary" in get_endpoint

        # Verify PATCH /api/v1/findings/{finding_id} exists
        patch_endpoint = paths["/api/v1/findings/{finding_id}"]["patch"]
        assert "summary" in patch_endpoint
        assert "requestBody" in patch_endpoint

    def test_swagger_ui_includes_findings_endpoints(self):
        """Test Swagger UI renders findings endpoints."""
        response = client.get("/docs")
        assert response.status_code == 200
        # Swagger UI should return HTML
        assert "text/html" in response.headers["content-type"]


class TestBigQueryIntegration(unittest.TestCase):
    """Test BigQuery integration (only if configured)."""

    def test_bigquery_service_available(self):
        """Test BigQuery service initializes correctly."""
        bq_client = get_bigquery_client()

        assert bq_client is not None
        # is_configured may be True or False depending on environment

        if bq_client.is_configured:
            # If configured, should have project_id and dataset_id
            assert bq_client.project_id is not None
            assert bq_client.dataset_id is not None
            assert bq_client.client is not None
        else:
            # If not configured, operations should return safe defaults
            assert bq_client.list_findings(10, 0, {}) == []
            assert bq_client.get_finding_by_id("fnd_test") is None


if __name__ == "__main__":
    unittest.main()
