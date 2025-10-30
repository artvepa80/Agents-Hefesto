"""
Empirical tests for analysis API - Level 4 (TDD)

Tests with production-like workloads to validate performance.
Following CLAUDE.md methodology: empirical tests verify real-world behavior.

Empirical tests verify:
- Performance meets Phase 2 targets
- System behavior under realistic loads
- Response time consistency
- Resource usage patterns

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from hefesto.api.main import app

client = TestClient(app)


class TestPerformanceTargets(unittest.TestCase):
    """Test API meets Phase 2 performance targets."""

    def test_single_file_analysis_performance(self):
        """Test single file analysis completes in <500ms."""
        # Create temp file with moderate complexity
        code = '''
def moderate_function(x, y, z):
    """Function with moderate complexity."""
    result = 0
    for i in range(x):
        if i % 2 == 0:
            result += y
        else:
            result += z
    return result

class ExampleClass:
    """Example class."""

    def method_one(self):
        pass

    def method_two(self):
        pass
'''

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            start_time = time.time()
            response = client.post("/api/v1/analyze", json={"path": temp_path})
            duration_ms = (time.time() - start_time) * 1000

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

            # Phase 2 target: <500ms
            assert duration_ms < 500, f"Analysis took {duration_ms:.2f}ms, expected <500ms"

        finally:
            Path(temp_path).unlink()

    def test_batch_analysis_performance(self):
        """Test batch analysis of 5 files completes in <5s."""
        temp_files = []

        try:
            # Create 5 temp files
            for i in range(5):
                code = f'''
def function_{i}(a, b):
    """Function {i}."""
    if a > b:
        return a + b
    else:
        return a - b

class Class_{i}:
    """Class {i}."""

    def method(self):
        return {i}
'''
                f = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)
                f.write(code)
                f.close()
                temp_files.append(f.name)

            start_time = time.time()
            response = client.post("/api/v1/analyze/batch", json={"paths": temp_files})
            duration_s = time.time() - start_time

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["completed"] == 5

            # Phase 2 target: <5s for small batch
            assert duration_s < 5.0, f"Batch analysis took {duration_s:.2f}s, expected <5s"

        finally:
            for temp_file in temp_files:
                Path(temp_file).unlink()


class TestResponseConsistency(unittest.TestCase):
    """Test response consistency across multiple requests."""

    def test_repeated_analysis_consistency(self):
        """Test analyzing same file multiple times gives consistent results."""
        code = "def test():\\n    pass"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            responses = []
            for _ in range(3):
                response = client.post("/api/v1/analyze", json={"path": temp_path})
                assert response.status_code == 200
                responses.append(response.json())

            # Verify all responses have same structure
            for resp in responses:
                assert resp["success"] is True
                assert resp["data"]["status"] == "completed"
                # Analysis IDs should be different (unique per request)
                assert resp["data"]["analysis_id"].startswith("ana_")

            # Verify summary consistency (same file should have same stats)
            summaries = [r["data"]["summary"]["files_analyzed"] for r in responses]
            assert all(s == summaries[0] for s in summaries), "File count should be consistent"

        finally:
            Path(temp_path).unlink()


class TestCacheEffectiveness(unittest.TestCase):
    """Test in-memory cache works correctly."""

    def test_cache_stores_analysis_results(self):
        """Test analysis results are cached and retrievable."""
        code = "def cached_test():\\n    return 42"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            # Run analysis
            analyze_response = client.post("/api/v1/analyze", json={"path": temp_path})
            assert analyze_response.status_code == 200

            analysis_id = analyze_response.json()["data"]["analysis_id"]

            # Retrieve from cache multiple times
            for _ in range(3):
                cache_response = client.get(f"/api/v1/analyze/{analysis_id}")
                assert cache_response.status_code == 200
                assert cache_response.json()["data"]["analysis_id"] == analysis_id

        finally:
            Path(temp_path).unlink()

    def test_cache_miss_returns_404(self):
        """Test retrieving non-existent analysis returns 404."""
        # Valid format but non-existent ID
        non_existent_id = "ana_zzzzzzzzzzzzzzzzzzzzzzz"
        response = client.get(f"/api/v1/analyze/{non_existent_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestAPIDocumentation(unittest.TestCase):
    """Test API documentation is complete and accessible."""

    def test_analysis_endpoints_in_openapi(self):
        """Test analysis endpoints appear in OpenAPI schema."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        paths = schema["paths"]

        # Verify all 3 Phase 2 endpoints are documented
        assert "/api/v1/analyze" in paths
        assert "/api/v1/analyze/{analysis_id}" in paths
        assert "/api/v1/analyze/batch" in paths

        # Verify POST /api/v1/analyze has proper documentation
        analyze_endpoint = paths["/api/v1/analyze"]["post"]
        assert "summary" in analyze_endpoint
        assert "description" in analyze_endpoint
        assert "requestBody" in analyze_endpoint
        assert "responses" in analyze_endpoint

    def test_swagger_ui_renders_analysis_endpoints(self):
        """Test Swagger UI is accessible with analysis endpoints."""
        response = client.get("/docs")
        assert response.status_code == 200
        # Swagger UI should return HTML
        assert "text/html" in response.headers["content-type"]


class TestErrorRecovery(unittest.TestCase):
    """Test system recovers gracefully from errors."""

    def test_invalid_json_returns_422(self):
        """Test invalid JSON request returns 422 Unprocessable Entity."""
        # Missing required 'path' field
        response = client.post("/api/v1/analyze", json={})
        assert response.status_code == 422  # FastAPI validation error

    def test_invalid_analyzer_name_returns_422(self):
        """Test invalid analyzer name returns validation error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def test(): pass")
            temp_path = f.name

        try:
            response = client.post(
                "/api/v1/analyze", json={"path": temp_path, "analyzers": ["invalid_analyzer"]}
            )

            assert response.status_code == 422  # Validation error

        finally:
            Path(temp_path).unlink()


if __name__ == "__main__":
    unittest.main()
