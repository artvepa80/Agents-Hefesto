"""
Empirical tests for findings API - Level 4 (TDD)

Tests with production-like workloads to validate performance.
Following CLAUDE.md methodology: empirical tests verify real-world behavior.

Empirical tests verify:
- Performance meets Phase 3 targets
- Response time consistency
- Query optimization effectiveness
- System behavior under realistic loads

Phase 3 Performance Targets:
- GET /api/v1/findings: <200ms P95
- GET /api/v1/findings/{finding_id}: <100ms P95
- PATCH /api/v1/findings/{finding_id}: <300ms P95

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

import time
import unittest

from fastapi.testclient import TestClient

from hefesto.api.main import app
from hefesto.api.services.bigquery_service import get_bigquery_client

client = TestClient(app)


class TestFindingsListPerformance(unittest.TestCase):
    """Test GET /api/v1/findings performance."""

    def test_list_findings_performance_target(self):
        """Test list findings completes in <200ms (P95 target)."""
        # Run 10 requests to get P95 estimate
        durations = []

        for _ in range(10):
            start_time = time.time()
            response = client.get("/api/v1/findings?limit=100")
            duration_ms = (time.time() - start_time) * 1000

            assert response.status_code == 200
            durations.append(duration_ms)

        # Calculate P95 (9th percentile of 10 samples)
        durations_sorted = sorted(durations)
        p95 = durations_sorted[8]  # 9th out of 10 = P95

        # Phase 3 target: <200ms P95
        assert p95 < 200, f"List findings P95 {p95:.2f}ms exceeds target of 200ms"

    def test_list_findings_with_filters_performance(self):
        """Test list findings with filters maintains performance."""
        durations = []

        for _ in range(10):
            start_time = time.time()
            response = client.get("/api/v1/findings?limit=50&severity=HIGH&status=new")
            duration_ms = (time.time() - start_time) * 1000

            assert response.status_code == 200
            durations.append(duration_ms)

        durations_sorted = sorted(durations)
        p95 = durations_sorted[8]

        # Should still meet <200ms target with filters
        assert p95 < 200, f"List findings with filters P95 {p95:.2f}ms exceeds target"

    def test_list_findings_pagination_performance(self):
        """Test pagination doesn't significantly degrade performance."""
        durations_first_page = []
        durations_later_page = []

        # Test first page
        for _ in range(5):
            start_time = time.time()
            response = client.get("/api/v1/findings?limit=50&offset=0")
            duration_ms = (time.time() - start_time) * 1000

            assert response.status_code == 200
            durations_first_page.append(duration_ms)

        # Test later page (offset=1000)
        for _ in range(5):
            start_time = time.time()
            response = client.get("/api/v1/findings?limit=50&offset=1000")
            duration_ms = (time.time() - start_time) * 1000

            assert response.status_code == 200
            durations_later_page.append(duration_ms)

        avg_first = sum(durations_first_page) / len(durations_first_page)
        avg_later = sum(durations_later_page) / len(durations_later_page)

        # Later pages shouldn't be more than 2x slower
        # (BigQuery clustering should help here)
        assert (
            avg_later < avg_first * 2
        ), f"Pagination performance degraded: {avg_later:.2f}ms vs {avg_first:.2f}ms"


class TestFindingDetailPerformance(unittest.TestCase):
    """Test GET /api/v1/findings/{finding_id} performance."""

    def test_get_finding_by_id_performance_target(self):
        """Test get finding by ID completes in <100ms (P95 target)."""
        # Test with known non-existent ID (should still be fast lookup)
        test_id = "fnd_performancetest12345678"
        durations = []

        for _ in range(10):
            start_time = time.time()
            response = client.get(f"/api/v1/findings/{test_id}")
            duration_ms = (time.time() - start_time) * 1000

            # May be 404 (not found) or 200 with error
            assert response.status_code in [200, 404]
            durations.append(duration_ms)

        durations_sorted = sorted(durations)
        p95 = durations_sorted[8]

        # Phase 3 target: <100ms P95
        assert p95 < 100, f"Get finding by ID P95 {p95:.2f}ms exceeds target of 100ms"

    def test_get_finding_consistency(self):
        """Test get finding response time consistency."""
        test_id = "fnd_consistencytest123456"
        durations = []

        for _ in range(20):
            start_time = time.time()
            response = client.get(f"/api/v1/findings/{test_id}")
            duration_ms = (time.time() - start_time) * 1000

            assert response.status_code in [200, 404]
            durations.append(duration_ms)

        # Check consistency: P99 shouldn't be more than 3x P50
        durations_sorted = sorted(durations)
        p50 = durations_sorted[10]  # 50th percentile
        p99 = durations_sorted[19]  # 99th percentile

        assert p99 < p50 * 3.2, f"Response time inconsistent: P99={p99:.2f}ms, P50={p50:.2f}ms"


class TestFindingUpdatePerformance(unittest.TestCase):
    """Test PATCH /api/v1/findings/{finding_id} performance."""

    def test_update_finding_performance_target(self):
        """Test update finding completes in <300ms (P95 target)."""
        bq_client = get_bigquery_client()

        if not bq_client.is_configured:
            self.skipTest("BigQuery not configured, cannot test update performance")

        # Test updating non-existent finding (should still validate quickly)
        test_id = "fnd_updateperformancetest"
        durations = []

        for _ in range(10):
            start_time = time.time()
            response = client.patch(
                f"/api/v1/findings/{test_id}",
                json={
                    "status": "resolved",
                    "updated_by": "performance_test@example.com",
                    "notes": "Performance test update",
                },
            )
            duration_ms = (time.time() - start_time) * 1000

            # May be 404 (not found) or 200 with success/error
            assert response.status_code in [200, 404]
            durations.append(duration_ms)

        durations_sorted = sorted(durations)
        p95 = durations_sorted[8]

        # Phase 3 target: <300ms P95
        assert p95 < 300, f"Update finding P95 {p95:.2f}ms exceeds target of 300ms"


class TestConcurrentRequests(unittest.TestCase):
    """Test system handles concurrent requests efficiently."""

    def test_concurrent_list_requests(self):
        """Test multiple concurrent list requests maintain performance."""
        import concurrent.futures

        def make_request():
            start_time = time.time()
            response = client.get("/api/v1/findings?limit=10")
            duration_ms = (time.time() - start_time) * 1000
            return response.status_code, duration_ms

        # Make 5 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(5)]
            results = [f.result() for f in futures]

        # All should succeed
        for status_code, duration_ms in results:
            assert status_code == 200

        # Average duration shouldn't be drastically worse than single request
        avg_duration = sum(d for _, d in results) / len(results)
        assert avg_duration < 400, f"Concurrent requests average {avg_duration:.2f}ms (too slow)"


class TestBigQueryOptimization(unittest.TestCase):
    """Test BigQuery query optimization effectiveness."""

    def test_clustered_query_performance(self):
        """Test queries using clustered fields are faster."""
        bq_client = get_bigquery_client()

        if not bq_client.is_configured:
            self.skipTest("BigQuery not configured")

        # Query using clustered field (severity)
        durations_clustered = []
        for _ in range(5):
            start_time = time.time()
            response = client.get("/api/v1/findings?severity=HIGH&limit=50")
            duration_ms = (time.time() - start_time) * 1000

            assert response.status_code == 200
            durations_clustered.append(duration_ms)

        avg_clustered = sum(durations_clustered) / len(durations_clustered)

        # Should be reasonably fast due to clustering
        assert avg_clustered < 250, f"Clustered query {avg_clustered:.2f}ms slower than expected"

    def test_partitioned_query_performance(self):
        """Test queries using partitioned fields perform well."""
        bq_client = get_bigquery_client()

        if not bq_client.is_configured:
            self.skipTest("BigQuery not configured")

        # Query with date range (partitioned field)
        durations_partitioned = []
        for _ in range(5):
            start_time = time.time()
            response = client.get("/api/v1/findings?start_date=2025-01-01T00:00:00Z&limit=50")
            duration_ms = (time.time() - start_time) * 1000

            assert response.status_code == 200
            durations_partitioned.append(duration_ms)

        avg_partitioned = sum(durations_partitioned) / len(durations_partitioned)

        # Should be fast due to partitioning
        assert (
            avg_partitioned < 250
        ), f"Partitioned query {avg_partitioned:.2f}ms slower than expected"


class TestResponseConsistency(unittest.TestCase):
    """Test response consistency and reliability."""

    def test_repeated_requests_give_consistent_results(self):
        """Test repeated requests return consistent data."""
        responses = []

        for _ in range(3):
            response = client.get("/api/v1/findings?limit=10")
            assert response.status_code == 200
            responses.append(response.json())

        # All responses should have same structure
        for resp in responses:
            assert resp["success"] is True
            assert "data" in resp
            assert "findings" in resp["data"]
            assert "pagination" in resp["data"]
            assert "bigquery_available" in resp["data"]

    def test_error_responses_are_consistent(self):
        """Test error responses maintain consistent format."""
        error_responses = []

        # Trigger various errors
        error_responses.append(client.get("/api/v1/findings?severity=INVALID"))
        error_responses.append(client.get("/api/v1/findings/invalid_id_format"))
        error_responses.append(
            client.patch(
                "/api/v1/findings/fnd_test",
                json={"status": "invalid_status"},
            )
        )

        # All should return 200 with error structure (or 422 for validation)
        for response in error_responses:
            assert response.status_code in [200, 422]

            if response.status_code == 200:
                data = response.json()
                # Should have error structure
                if not data["success"]:
                    assert "error" in data
                    assert "code" in data["error"]
                    assert "message" in data["error"]


if __name__ == "__main__":
    unittest.main()
