"""
Tests for health check endpoints.

Tests:
- GET /health - Basic health check
- GET /api/v1/status - System status
- Response structure validation
- Performance requirements
"""

import time

import pytest
from fastapi.testclient import TestClient

from hefesto.api.main import create_app

app = create_app()
client = TestClient(app)


class TestHealthEndpoint:
    """Tests for GET /health"""

    def test_health_check_success(self):
        """Test health check returns 200 OK"""
        response = client.get("/health")
        assert response.status_code == 200

    def test_ping_endpoint(self):
        """Test ping endpoint returns 200 OK and simple JSON"""
        response = client.get("/ping")
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_health_check_structure(self):
        """Test health check response has correct structure"""
        response = client.get("/health")
        data = response.json()

        # Check top-level structure
        assert "success" in data
        assert "data" in data
        assert "error" in data
        assert "timestamp" in data

        # Check success flag
        assert data["success"] is True
        assert data["error"] is None

        # Check data structure
        assert "status" in data["data"]
        assert "version" in data["data"]
        assert "timestamp" in data["data"]

    def test_health_check_status_healthy(self):
        """Test health check returns healthy status"""
        response = client.get("/health")
        data = response.json()

        assert data["data"]["status"] == "healthy"

    def test_health_check_version(self):
        """Test health check returns version"""
        response = client.get("/health")
        data = response.json()

        version = data["data"]["version"]
        assert isinstance(version, str)
        assert len(version) > 0
        # Version is either semver (X.Y.Z) or dev string
        if version != "dev":
            parts = version.split(".")
            assert len(parts) >= 2  # At least major.minor

    def test_health_check_response_time(self):
        """Test health check responds in <50ms (target: <10ms)"""
        start_time = time.time()
        response = client.get("/health")
        duration_ms = (time.time() - start_time) * 1000

        assert response.status_code == 200
        assert duration_ms < 50  # Should be well under 50ms

    def test_health_check_headers(self):
        """Test health check includes expected headers"""
        response = client.get("/health")

        # Should have request ID from middleware
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) > 0

        # Should have timing from middleware
        assert "X-Process-Time" in response.headers


class TestSystemStatusEndpoint:
    """Tests for GET /api/v1/status"""

    def test_system_status_success(self):
        """Test system status returns 200 OK"""
        response = client.get("/api/v1/status")
        assert response.status_code == 200

    def test_system_status_structure(self):
        """Test system status response has correct structure"""
        response = client.get("/api/v1/status")
        data = response.json()

        # Check top-level structure
        assert "success" in data
        assert "data" in data
        assert data["success"] is True

        # Check data structure
        status_data = data["data"]
        assert "status" in status_data
        assert "version" in status_data
        assert "analyzers" in status_data
        assert "integrations" in status_data
        assert "uptime_seconds" in status_data
        assert "last_health_check" in status_data

    def test_system_status_operational(self):
        """Test system status is operational"""
        response = client.get("/api/v1/status")
        data = response.json()

        status = data["data"]["status"]
        # Should be operational or degraded (depending on analyzer availability)
        assert status in ["operational", "degraded", "outage"]

    def test_system_status_analyzers(self):
        """Test system status includes all 4 analyzers"""
        response = client.get("/api/v1/status")
        data = response.json()

        analyzers = data["data"]["analyzers"]

        # Should have all 4 analyzers
        expected_analyzers = ["complexity", "security", "code_smells", "best_practices"]
        for analyzer in expected_analyzers:
            assert analyzer in analyzers
            # Status should be one of: available, unavailable, degraded
            assert analyzers[analyzer] in ["available", "unavailable", "degraded"]

    def test_system_status_integrations(self):
        """Test system status includes integrations"""
        response = client.get("/api/v1/status")
        data = response.json()

        integrations = data["data"]["integrations"]

        # Should have bigquery and iris
        assert "bigquery" in integrations
        assert "iris" in integrations

        # Iris should always be enabled
        assert integrations["iris"] == "enabled"

    def test_system_status_uptime(self):
        """Test uptime increases over time"""
        # First call
        response1 = client.get("/api/v1/status")
        uptime1 = response1.json()["data"]["uptime_seconds"]

        # Wait 1 second
        time.sleep(1.1)

        # Second call
        response2 = client.get("/api/v1/status")
        uptime2 = response2.json()["data"]["uptime_seconds"]

        # Uptime should have increased by at least 1 second
        assert uptime2 > uptime1
        assert uptime2 - uptime1 >= 1

    def test_system_status_response_time(self):
        """Test system status responds in <200ms (target: <50ms)"""
        start_time = time.time()
        response = client.get("/api/v1/status")
        duration_ms = (time.time() - start_time) * 1000

        assert response.status_code == 200
        assert duration_ms < 200  # Should be well under 200ms


class TestRootEndpoint:
    """Tests for GET / (root)"""

    def test_root_success(self):
        """Test root endpoint returns 200 OK"""
        response = client.get("/")
        assert response.status_code == 200

    def test_root_structure(self):
        """Test root endpoint returns expected information"""
        response = client.get("/")
        data = response.json()

        assert "message" in data
        assert "version" in data
        assert "documentation" in data
        assert "endpoints" in data

        # Check documentation links
        docs = data["documentation"]
        assert "swagger" in docs
        assert "redoc" in docs
        assert "openapi_json" in docs


class TestOpenAPIDocumentation:
    """Tests for auto-generated API documentation"""

    def test_openapi_json_accessible(self):
        """Test OpenAPI JSON is generated and accessible"""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        openapi_spec = response.json()
        assert "openapi" in openapi_spec
        assert "info" in openapi_spec
        assert "paths" in openapi_spec

    def test_swagger_ui_accessible(self):
        """Test Swagger UI is accessible"""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_redoc_accessible(self):
        """Test ReDoc is accessible"""
        response = client.get("/redoc")
        assert response.status_code == 200

    def test_openapi_includes_health_endpoints(self):
        """Test OpenAPI spec includes health endpoints"""
        response = client.get("/openapi.json")
        openapi_spec = response.json()

        paths = openapi_spec["paths"]

        # Should include health endpoints
        assert "/health" in paths
        assert "/api/v1/status" in paths

        # Health endpoint should have GET method
        assert "get" in paths["/health"]
        assert "get" in paths["/api/v1/status"]


class TestMiddleware:
    """Tests for custom middleware"""

    def test_request_id_header(self):
        """Test Request ID middleware adds X-Request-ID header"""
        response = client.get("/health")

        assert "X-Request-ID" in response.headers
        request_id = response.headers["X-Request-ID"]

        # Should be UUID format (36 characters with dashes)
        assert len(request_id) == 36
        assert request_id.count("-") == 4

    def test_timing_header(self):
        """Test Timing middleware adds X-Process-Time header"""
        response = client.get("/health")

        assert "X-Process-Time" in response.headers
        process_time = response.headers["X-Process-Time"]

        # Should end with "ms"
        assert process_time.endswith("ms")

        # Should be a number when "ms" is stripped
        time_value = float(process_time[:-2])
        assert time_value >= 0

    def test_unique_request_ids(self):
        """Test each request gets unique request ID"""
        response1 = client.get("/health")
        response2 = client.get("/health")

        id1 = response1.headers["X-Request-ID"]
        id2 = response2.headers["X-Request-ID"]

        # IDs should be different
        assert id1 != id2


class TestErrorHandling:
    """Tests for error handling"""

    def test_404_not_found(self):
        """Test non-existent endpoint returns 404"""
        response = client.get("/nonexistent")
        assert response.status_code == 404

    def test_method_not_allowed(self):
        """Test wrong HTTP method returns 405"""
        # /health only supports GET, try POST
        response = client.post("/health")
        assert response.status_code == 405


# Run tests with coverage
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=hefesto.api", "--cov-report=html"])
