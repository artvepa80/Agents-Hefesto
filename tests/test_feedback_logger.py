"""
HEFESTO v3.5 - FeedbackLogger Test Suite

Comprehensive tests for the feedback loop tracking system.

Copyright © 2025 Narapa LLC, Miami, Florida
OMEGA Sports Analytics Foundation
"""

import pytest
from llm.feedback_logger import (
    FeedbackLogger,
    SuggestionFeedback,
    get_feedback_logger,
)


class TestFeedbackLoggerBasics:
    """Basic functionality tests"""

    def test_generate_suggestion_id(self):
        """Test ID generation format and uniqueness"""
        logger = FeedbackLogger()

        # Generate multiple IDs
        id1 = logger.generate_suggestion_id()
        id2 = logger.generate_suggestion_id()
        id3 = logger.generate_suggestion_id()

        # Check format
        assert id1.startswith("SUG-")
        assert len(id1) == 16  # SUG- (4 chars) + 12 hex chars
        assert id1[4:].isupper()  # Hex part should be uppercase
        assert id1[4:].isalnum()  # Should be alphanumeric only

        # Check uniqueness
        assert id1 != id2
        assert id2 != id3
        assert id1 != id3

    def test_get_feedback_logger_singleton(self):
        """Test singleton pattern returns same instance"""
        logger1 = get_feedback_logger()
        logger2 = get_feedback_logger()

        assert logger1 is logger2
        assert logger1.project_id == "hefesto-project"
        assert logger1.dataset_id == "omega_agent"
        assert logger1.table_id == "suggestion_feedback"


class TestSuggestionLogging:
    """Test logging suggestions to BigQuery"""

    def test_log_suggestion_shown(self):
        """Test logging suggestion shown to user"""
        logger = FeedbackLogger()

        suggestion_id = logger.log_suggestion_shown(
            file_path="test/file.py",
            issue_type="security",
            severity="HIGH",
            confidence_score=0.85,
            validation_passed=True,
            similarity_score=0.72,
        )

        # Check ID format
        assert suggestion_id.startswith("SUG-")
        assert len(suggestion_id) == 16

        # Note: Actual BigQuery insertion tested in integration tests
        # This tests the method doesn't raise exceptions

    def test_log_suggestion_with_minimal_data(self):
        """Test logging suggestion with only required fields"""
        logger = FeedbackLogger()

        suggestion_id = logger.log_suggestion_shown(
            file_path="minimal.py",
            issue_type="style",
            severity="LOW",
        )

        assert suggestion_id.startswith("SUG-")

    def test_log_suggestion_with_llm_event_id(self):
        """Test logging suggestion linked to LLM event"""
        logger = FeedbackLogger()

        suggestion_id = logger.log_suggestion_shown(
            file_path="test/api.py",
            issue_type="performance",
            severity="MEDIUM",
            llm_event_id="evt-12345",
            confidence_score=0.78,
        )

        assert suggestion_id.startswith("SUG-")


class TestUserActionLogging:
    """Test logging user feedback"""

    def test_log_user_action_accepted(self):
        """Test logging user acceptance"""
        logger = FeedbackLogger()

        # First log suggestion
        suggestion_id = logger.log_suggestion_shown(
            file_path="test/file.py",
            issue_type="security",
            severity="HIGH",
        )

        # Then log user action
        logger.log_user_action(
            suggestion_id=suggestion_id,
            accepted=True,
            applied_successfully=True,
            time_to_apply_seconds=30,
            user_comment="Worked great!",
        )

        # Should not raise exception

    def test_log_user_action_rejected(self):
        """Test logging user rejection"""
        logger = FeedbackLogger()

        suggestion_id = logger.log_suggestion_shown(
            file_path="test/file.py",
            issue_type="style",
            severity="LOW",
        )

        logger.log_user_action(
            suggestion_id=suggestion_id,
            accepted=False,
            rejection_reason="Doesn't fit our code style",
            user_comment="Not applicable for this project",
        )

        # Should not raise exception

    def test_log_user_action_minimal(self):
        """Test logging user action with minimal fields"""
        logger = FeedbackLogger()

        suggestion_id = logger.log_suggestion_shown(
            file_path="test/minimal.py",
            issue_type="maintainability",
            severity="INFO",
        )

        # Just accepted/rejected, no other data
        logger.log_user_action(
            suggestion_id=suggestion_id,
            accepted=True,
        )

        # Should not raise exception


class TestCIResultsLogging:
    """Test logging CI/CD pipeline results"""

    def test_log_ci_results(self):
        """Test logging CI pipeline results"""
        logger = FeedbackLogger()

        suggestion_id = logger.log_suggestion_shown(
            file_path="test/feature.py",
            issue_type="correctness",
            severity="MEDIUM",
        )

        logger.log_ci_results(
            suggestion_id=suggestion_id,
            ci_passed=True,
            tests_passed=True,
            coverage_improved=True,
        )

        # Should not raise exception

    def test_log_ci_results_failure(self):
        """Test logging CI failure"""
        logger = FeedbackLogger()

        suggestion_id = logger.log_suggestion_shown(
            file_path="test/buggy.py",
            issue_type="performance",
            severity="LOW",
        )

        logger.log_ci_results(
            suggestion_id=suggestion_id,
            ci_passed=False,
            tests_passed=False,
            coverage_improved=False,
        )

        # Should not raise exception


class TestAcceptanceRateMetrics:
    """Test querying acceptance rate metrics"""

    def test_get_acceptance_rate_all(self):
        """Test getting acceptance rate for all suggestions"""
        logger = FeedbackLogger()

        metrics = logger.get_acceptance_rate(days=30)

        # Check all expected fields exist
        assert "total" in metrics
        assert "accepted" in metrics
        assert "rejected" in metrics
        assert "pending" in metrics
        assert "acceptance_rate" in metrics
        assert "avg_confidence" in metrics
        assert "avg_similarity" in metrics
        assert "avg_time_to_apply" in metrics

        # Check types
        assert isinstance(metrics["total"], int)
        assert isinstance(metrics["accepted"], int)
        assert isinstance(metrics["rejected"], int)
        assert isinstance(metrics["pending"], int)
        assert isinstance(metrics["acceptance_rate"], float)
        assert isinstance(metrics["avg_confidence"], float)
        assert isinstance(metrics["avg_similarity"], float)
        assert isinstance(metrics["avg_time_to_apply"], float)

        # Check ranges
        assert 0.0 <= metrics["acceptance_rate"] <= 1.0
        assert 0.0 <= metrics["avg_confidence"] <= 1.0
        assert 0.0 <= metrics["avg_similarity"] <= 1.0

    def test_get_acceptance_rate_filtered_by_type(self):
        """Test getting acceptance rate filtered by issue type"""
        logger = FeedbackLogger()

        metrics = logger.get_acceptance_rate(
            issue_type="security",
            days=30,
        )

        assert "total" in metrics
        assert "acceptance_rate" in metrics

    def test_get_acceptance_rate_filtered_by_severity(self):
        """Test getting acceptance rate filtered by severity"""
        logger = FeedbackLogger()

        metrics = logger.get_acceptance_rate(
            severity="HIGH",
            days=30,
        )

        assert "total" in metrics
        assert "acceptance_rate" in metrics

    def test_get_acceptance_rate_filtered_both(self):
        """Test getting acceptance rate with multiple filters"""
        logger = FeedbackLogger()

        metrics = logger.get_acceptance_rate(
            issue_type="security",
            severity="HIGH",
            days=7,
        )

        assert "total" in metrics
        assert "acceptance_rate" in metrics

    def test_get_acceptance_rate_different_timeframes(self):
        """Test getting metrics for different time periods"""
        logger = FeedbackLogger()

        # 7 days
        metrics_7d = logger.get_acceptance_rate(days=7)
        assert "total" in metrics_7d

        # 30 days
        metrics_30d = logger.get_acceptance_rate(days=30)
        assert "total" in metrics_30d

        # 90 days
        metrics_90d = logger.get_acceptance_rate(days=90)
        assert "total" in metrics_90d


class TestSuggestionFeedbackDataclass:
    """Test SuggestionFeedback dataclass"""

    def test_create_feedback_minimal(self):
        """Test creating feedback with minimal fields"""
        feedback = SuggestionFeedback(
            suggestion_id="SUG-TEST123456",
            file_path="test.py",
            issue_type="style",
            severity="LOW",
        )

        assert feedback.suggestion_id == "SUG-TEST123456"
        assert feedback.file_path == "test.py"
        assert feedback.issue_type == "style"
        assert feedback.severity == "LOW"
        assert feedback.shown_to_user is True  # Default
        assert feedback.user_accepted is None  # Default

    def test_create_feedback_complete(self):
        """Test creating feedback with all fields"""
        feedback = SuggestionFeedback(
            suggestion_id="SUG-COMPLETE123",
            llm_event_id="evt-789",
            file_path="api/auth.py",
            issue_type="security",
            severity="CRITICAL",
            shown_to_user=True,
            user_accepted=True,
            applied_successfully=True,
            time_to_apply_seconds=45,
            ci_passed=True,
            tests_passed=True,
            coverage_improved=True,
            user_comment="Excellent fix!",
            rejection_reason=None,
            confidence_score=0.95,
            validation_passed=True,
            similarity_score=0.82,
        )

        assert feedback.suggestion_id == "SUG-COMPLETE123"
        assert feedback.confidence_score == 0.95
        assert feedback.validation_passed is True
        assert feedback.similarity_score == 0.82
        assert feedback.user_accepted is True
        assert feedback.applied_successfully is True


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_logger_without_bigquery_client(self):
        """Test logger behavior when BigQuery client fails"""
        # This tests graceful degradation
        # Actual client failure would be caught in the logger
        logger = FeedbackLogger()

        # Even if client is None, should not crash
        suggestion_id = logger.generate_suggestion_id()
        assert suggestion_id.startswith("SUG-")

    def test_empty_file_path(self):
        """Test logging with empty file path"""
        logger = FeedbackLogger()

        suggestion_id = logger.log_suggestion_shown(
            file_path="",  # Empty string
            issue_type="style",
            severity="INFO",
        )

        assert suggestion_id.startswith("SUG-")

    def test_none_optional_fields(self):
        """Test logging with None in optional fields"""
        logger = FeedbackLogger()

        suggestion_id = logger.log_suggestion_shown(
            file_path="test.py",
            issue_type="maintainability",
            severity="LOW",
            llm_event_id=None,
            confidence_score=None,
            validation_passed=None,
            similarity_score=None,
        )

        assert suggestion_id.startswith("SUG-")


# Parametrized tests for issue types and severities
@pytest.mark.parametrize("issue_type", [
    "security",
    "performance",
    "correctness",
    "style",
    "maintainability",
])
def test_log_different_issue_types(issue_type):
    """Test logging suggestions for different issue types"""
    logger = FeedbackLogger()

    suggestion_id = logger.log_suggestion_shown(
        file_path=f"test_{issue_type}.py",
        issue_type=issue_type,
        severity="MEDIUM",
    )

    assert suggestion_id.startswith("SUG-")


@pytest.mark.parametrize("severity", [
    "CRITICAL",
    "HIGH",
    "MEDIUM",
    "LOW",
    "INFO",
])
def test_log_different_severities(severity):
    """Test logging suggestions for different severities"""
    logger = FeedbackLogger()

    suggestion_id = logger.log_suggestion_shown(
        file_path="test_severity.py",
        issue_type="security",
        severity=severity,
    )

    assert suggestion_id.startswith("SUG-")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
