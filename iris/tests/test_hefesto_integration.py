#!/usr/bin/env python3
"""
IRIS-HEFESTO Integration Tests
===============================
Test suite for automatic alert enrichment with Hefesto code findings.

Copyright © 2025 Narapa LLC, Miami, Florida
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Optional Google Cloud imports
try:
    from google.cloud import bigquery

    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    GOOGLE_CLOUD_AVAILABLE = False
    bigquery = None

# Import modules to test
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.hefesto_enricher import HefestoEnricher, get_hefesto_enricher


# ============================================================================
# T-1: UNIT TESTS
# ============================================================================


class TestFilePathExtraction:
    """Test file path extraction from alert messages"""

    def test_extract_simple_file_path(self):
        """Should extract standard Python file path"""
        enricher = HefestoEnricher(project_id="test-project", dry_run=True)
        message = "Error in api/endpoints.py at line 145"

        paths = enricher.extract_file_paths(message)

        assert "api/endpoints.py" in paths

    def test_extract_multiple_file_paths(self):
        """Should extract multiple file paths from message"""
        enricher = HefestoEnricher(project_id="test-project", dry_run=True)
        message = "Error in api/endpoints.py and core/utils.py"

        paths = enricher.extract_file_paths(message)

        assert "api/endpoints.py" in paths
        assert "core/utils.py" in paths

    def test_extract_with_line_numbers(self):
        """Should extract file path with line number reference"""
        enricher = HefestoEnricher(project_id="test-project", dry_run=True)
        message = "Exception in api/endpoints.py:145"

        paths = enricher.extract_file_paths(message)

        assert "api/endpoints.py" in paths

    def test_extract_module_path(self):
        """Should convert module path to file path"""
        enricher = HefestoEnricher(project_id="test-project", dry_run=True)
        message = "Error in api.endpoints module"

        paths = enricher.extract_file_paths(message)

        assert len(paths) == 1
        assert "api/endpoints.py" in paths

    def test_no_file_paths_found(self):
        """Should return empty list if no file paths"""
        enricher = HefestoEnricher(project_id="test-project", dry_run=True)
        message = "General system error occurred"

        paths = enricher.extract_file_paths(message)

        assert len(paths) == 0


class TestFindingScoring:
    """Test finding relevance scoring algorithm"""

    def test_score_critical_severity(self):
        """CRITICAL findings should get highest base score"""
        enricher = HefestoEnricher(project_id="test-project", dry_run=True)
        finding = {"severity": "CRITICAL", "status": "open", "days_before_alert": 1}

        score = enricher.score_finding(finding)

        assert score >= 3.5  # CRITICAL=4.0 × 1.0 × ~0.99

    def test_score_ignored_status_multiplier(self):
        """Ignored findings should get 2x multiplier"""
        enricher = HefestoEnricher(project_id="test-project", dry_run=True)
        finding_open = {"severity": "HIGH", "status": "open", "days_before_alert": 1}
        finding_ignored = {"severity": "HIGH", "status": "ignored", "days_before_alert": 1}

        score_open = enricher.score_finding(finding_open)
        score_ignored = enricher.score_finding(finding_ignored)

        assert score_ignored > score_open
        assert score_ignored >= score_open * 1.9  # Should be ~2x

    def test_score_recency_decay(self):
        """Recent findings should score higher"""
        enricher = HefestoEnricher(project_id="test-project", dry_run=True)
        finding_recent = {"severity": "HIGH", "status": "open", "days_before_alert": 1}
        finding_old = {"severity": "HIGH", "status": "open", "days_before_alert": 89}

        score_recent = enricher.score_finding(finding_recent)
        score_old = enricher.score_finding(finding_old)

        assert score_recent > score_old


# ============================================================================
# T-2: SMOKE TESTS
# ============================================================================


class TestComponentInitialization:
    """Test that components initialize without crashing"""

    def test_hefesto_enricher_initialization(self):
        """HefestoEnricher should initialize in dry-run mode"""
        enricher = HefestoEnricher(project_id="test-project", dry_run=True)

        assert enricher is not None
        assert enricher.dry_run is True
        assert enricher.project_id == "test-project"

    def test_singleton_pattern(self):
        """get_hefesto_enricher should return same instance"""
        enricher1 = get_hefesto_enricher("test-project", dry_run=True)
        enricher2 = get_hefesto_enricher("test-project", dry_run=True)

        assert enricher1 is enricher2

    def test_enrichment_with_no_file_paths(self):
        """Should handle alert without file paths gracefully"""
        enricher = HefestoEnricher(project_id="test-project", dry_run=True)

        result = enricher.enrich_alert_context(
            alert_message="Generic error occurred", alert_timestamp=datetime.utcnow()
        )

        assert result is not None
        assert result["correlation_attempted"] is True
        assert result["correlation_successful"] is False
        assert result["reason"] == "no_file_paths_extracted"


# ============================================================================
# T-3: CANARY TESTS (with Mocks)
# ============================================================================


class TestBigQueryIntegration:
    """Test BigQuery queries with mocked responses"""

    @patch("google.cloud.bigquery.Client")
    def test_query_related_findings_success(self, mock_client_class):
        """Should query BigQuery and return findings"""
        # Setup mock
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_query_job = Mock()
        mock_client.query.return_value = mock_query_job

        # Mock finding row
        mock_row = {
            "finding_id": "HEF-SEC-ABC123",
            "ts": datetime.utcnow(),
            "file_path": "api/endpoints.py",
            "line_number": 145,
            "function_name": "get_user_data",
            "issue_type": "security",
            "severity": "CRITICAL",
            "description": "SQL injection vulnerability",
            "rule_id": "sql-injection-001",
            "code_snippet": "SELECT * FROM users WHERE id = ?",
            "suggested_fix": "Use parameterized queries",
            "llm_event_id": "evt-123",
            "status": "ignored",
            "metadata": "{}",
            "created_at": datetime.utcnow(),
            "days_before_alert": 3,
        }
        mock_query_job.result.return_value = [mock_row]

        # Test
        enricher = HefestoEnricher(project_id="test-project", dry_run=False)
        enricher.client = mock_client  # Inject mock

        findings = enricher.query_related_findings(
            file_paths=["api/endpoints.py"], alert_timestamp=datetime.utcnow(), limit=5
        )

        assert len(findings) == 1
        assert findings[0]["finding_id"] == "HEF-SEC-ABC123"
        assert findings[0]["severity"] == "CRITICAL"
        assert findings[0]["status"] == "ignored"

    @patch("google.cloud.bigquery.Client")
    def test_end_to_end_enrichment_with_finding(self, mock_client_class):
        """Should enrich alert with Hefesto finding"""
        # Setup mock
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_query_job = Mock()
        mock_client.query.return_value = mock_query_job

        # Mock finding
        mock_row = {
            "finding_id": "HEF-SEC-ABC123",
            "ts": datetime.utcnow() - timedelta(days=3),
            "file_path": "api/endpoints.py",
            "line_number": 145,
            "function_name": "get_user_data",
            "issue_type": "security",
            "severity": "CRITICAL",
            "description": "SQL injection vulnerability",
            "rule_id": "sql-injection-001",
            "code_snippet": None,
            "suggested_fix": "Use parameterized queries",
            "llm_event_id": None,
            "status": "ignored",
            "metadata": None,
            "created_at": datetime.utcnow() - timedelta(days=3),
            "days_before_alert": 3,
        }
        mock_query_job.result.return_value = [mock_row]

        # Test
        enricher = HefestoEnricher(project_id="test-project", dry_run=False)
        enricher.client = mock_client

        result = enricher.enrich_alert_context(
            alert_message="API error rate 8.5% in api/endpoints.py",
            alert_timestamp=datetime.utcnow(),
        )

        # Assertions
        assert result["correlation_attempted"] is True
        assert result["correlation_successful"] is True
        assert result["hefesto_finding_id"] == "HEF-SEC-ABC123"

        context = result["hefesto_context"]
        assert context["finding_id"] == "HEF-SEC-ABC123"
        assert context["severity"] == "CRITICAL"
        assert context["status"] == "ignored"
        assert context["detected_days_ago"] == 3
        assert context["file_path"] == "api/endpoints.py"

    @patch("google.cloud.bigquery.Client")
    def test_enrichment_no_matching_findings(self, mock_client_class):
        """Should handle case where no findings match"""
        # Setup mock
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_query_job = Mock()
        mock_client.query.return_value = mock_query_job
        mock_query_job.result.return_value = []  # No findings

        # Test
        enricher = HefestoEnricher(project_id="test-project", dry_run=False)
        enricher.client = mock_client

        result = enricher.enrich_alert_context(
            alert_message="Error in api/endpoints.py", alert_timestamp=datetime.utcnow()
        )

        assert result["correlation_attempted"] is True
        assert result["correlation_successful"] is False
        assert result["reason"] == "no_matching_findings"
        assert result["hefesto_finding_id"] is None


# ============================================================================
# T-4: EMPIRICAL TESTS (requires actual BigQuery)
# ============================================================================


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("INTEGRATION_TESTS") != "true",
    reason="Integration tests only run with INTEGRATION_TESTS=true",
)
class TestRealBigQueryIntegration:
    """Integration tests with real BigQuery (opt-in)"""

    def test_query_code_findings_table_exists(self):
        """Verify code_findings table exists in BigQuery"""
        client = bigquery.Client(project="eminent-carver-469323-q2")

        query = """
        SELECT COUNT(*) as count
        FROM `eminent-carver-469323-q2.omega_audit.code_findings`
        WHERE ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 DAY)
        """

        query_job = client.query(query)
        results = query_job.result()

        for row in results:
            # Should not raise exception
            assert row.count >= 0

    def test_alerts_sent_has_hefesto_columns(self):
        """Verify alerts_sent table has Hefesto columns"""
        client = bigquery.Client(project="eminent-carver-469323-q2")

        query = """
        SELECT
            hefesto_finding_id,
            hefesto_context
        FROM `eminent-carver-469323-q2.omega_audit.alerts_sent`
        LIMIT 1
        """

        query_job = client.query(query)
        results = query_job.result()

        # Should not raise exception
        schema_fields = [field.name for field in results.schema]
        assert "hefesto_finding_id" in schema_fields
        assert "hefesto_context" in schema_fields

    def test_analytical_views_exist(self):
        """Verify all analytical views exist"""
        client = bigquery.Client(project="eminent-carver-469323-q2")

        views = [
            "omega_audit.v_code_findings_recent",
            "omega_audit.v_findings_to_alerts",
            "omega_audit.v_ignored_critical_findings",
            "omega_audit.v_problematic_files",
        ]

        for view in views:
            query = f"SELECT COUNT(*) FROM `eminent-carver-469323-q2.{view}` LIMIT 1"
            query_job = client.query(query)
            query_job.result()  # Should not raise exception


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_finding():
    """Sample code finding for testing"""
    return {
        "finding_id": "HEF-SEC-ABC123",
        "ts": datetime.utcnow() - timedelta(days=3),
        "file_path": "api/endpoints.py",
        "line_number": 145,
        "function_name": "get_user_data",
        "issue_type": "security",
        "severity": "CRITICAL",
        "description": "SQL injection vulnerability",
        "rule_id": "sql-injection-001",
        "code_snippet": "SELECT * FROM users WHERE id = " + str(123),
        "suggested_fix": "Use parameterized queries",
        "llm_event_id": "evt-123",
        "status": "ignored",
        "metadata": {"confidence": 0.95},
        "created_at": datetime.utcnow() - timedelta(days=3),
        "days_before_alert": 3,
    }


@pytest.fixture
def sample_alert_context():
    """Sample Iris alert context"""
    return {
        "alert_id": "iris-20251012-120000",
        "severity": "CRITICAL",
        "rule_name": "API Error Rate High",
        "message": "API error rate 8.5% in api/endpoints.py",
        "details": {"error_rate": 0.085, "file_path": "api/endpoints.py", "threshold": 0.01},
        "timestamp": datetime.utcnow().isoformat(),
        "channel": "Email_OnCall",
    }


# ============================================================================
# Test Execution
# ============================================================================

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short", "--color=yes"])
