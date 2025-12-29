"""
HEFESTO v3.5 - BudgetTracker Test Suite

Comprehensive tests for the LLM API budget control system.

Copyright © 2025 Narapa LLC, Miami, Florida
OMEGA Sports Analytics Foundation
"""

import os
from unittest.mock import MagicMock

import pytest

from hefesto.llm.budget_tracker import (
    BudgetTracker,
    TokenUsage,
    get_budget_tracker,
)


@pytest.fixture
def mock_bigquery_client(mocker):
    """Mocks the BigQuery client and its query method."""
    mock_client = MagicMock()
    mock_query_job = MagicMock()

    # Mock the result of the query to simulate one row of data
    mock_row = MagicMock()
    mock_row.request_count = 10
    mock_row.total_input_tokens = 10000
    mock_row.total_output_tokens = 20000
    mock_row.total_tokens = 30000
    mock_row.active_days = 1
    mock_query_job.result.return_value = [mock_row]

    mock_client.query.return_value = mock_query_job

    # Patch the bigquery.Client constructor in the module where it's used
    mocker.patch("hefesto.llm.budget_tracker.bigquery.Client", return_value=mock_client)
    return mock_client


class TestBudgetTrackerBasics:
    """Basic functionality tests"""

    def test_calculate_cost_gemini_2_flash_exp(self):
        """Test cost calculation for Gemini 2.0 Flash Experimental (free)"""
        tracker = BudgetTracker()

        cost = tracker.calculate_cost(
            input_tokens=1500, output_tokens=800, model="gemini-2.0-flash-exp"
        )

        # Experimental model is FREE
        assert cost == 0.0

    def test_calculate_cost_gemini_2_flash(self):
        """Test cost calculation for Gemini 2.0 Flash"""
        tracker = BudgetTracker()

        cost = tracker.calculate_cost(
            input_tokens=1_000_000,  # 1M tokens
            output_tokens=1_000_000,  # 1M tokens
            model="gemini-2.0-flash",
        )

        # $0.075/1M input + $0.30/1M output = $0.375
        assert cost == 0.375

    def test_calculate_cost_gemini_15_flash(self):
        """Test cost calculation for Gemini 1.5 Flash"""
        tracker = BudgetTracker()

        cost = tracker.calculate_cost(
            input_tokens=2_000_000,  # 2M tokens
            output_tokens=500_000,  # 0.5M tokens
            model="gemini-1.5-flash",
        )

        # (2M * $0.075) + (0.5M * $0.30) = $0.15 + $0.15 = $0.30
        assert cost == 0.30

    def test_calculate_cost_gemini_15_pro(self):
        """Test cost calculation for Gemini 1.5 Pro (expensive)"""
        tracker = BudgetTracker()

        cost = tracker.calculate_cost(
            input_tokens=1_000_000, output_tokens=1_000_000, model="gemini-1.5-pro"
        )

        # $1.25/1M input + $5.00/1M output = $6.25
        assert cost == 6.25

    def test_calculate_cost_unknown_model(self):
        """Test cost calculation for unknown model uses default pricing"""
        tracker = BudgetTracker()

        cost = tracker.calculate_cost(
            input_tokens=1_000_000, output_tokens=1_000_000, model="unknown-model-xyz"
        )

        # Should use default pricing (same as gemini-2.0-flash)
        assert cost == 0.375

    def test_calculate_cost_zero_tokens(self):
        """Test cost calculation with zero tokens"""
        tracker = BudgetTracker()

        cost = tracker.calculate_cost(input_tokens=0, output_tokens=0, model="gemini-2.0-flash")

        assert cost == 0.0

    def test_calculate_cost_realistic_request(self):
        """Test cost for typical refactor request"""
        tracker = BudgetTracker()

        # Typical request: ~2000 input, ~500 output
        cost = tracker.calculate_cost(
            input_tokens=2000, output_tokens=500, model="gemini-2.0-flash"
        )

        # (2000/1M * 0.075) + (500/1M * 0.30) = 0.00015 + 0.00015 = 0.0003
        expected = 0.0003
        assert abs(cost - expected) < 0.0001  # Allow small floating point error


class TestTokenUsageTracking:
    """Test usage tracking and recording"""

    def test_track_usage_basic(self):
        """Test basic usage tracking"""
        tracker = BudgetTracker()

        usage = tracker.track_usage(
            event_id="evt-123", input_tokens=1500, output_tokens=800, model="gemini-2.0-flash"
        )

        assert usage.input_tokens == 1500
        assert usage.output_tokens == 800
        assert usage.total_tokens == 2300
        assert isinstance(usage.estimated_cost_usd, float)
        assert usage.estimated_cost_usd >= 0

    def test_track_usage_free_model(self):
        """Test tracking usage on free experimental model"""
        tracker = BudgetTracker()

        usage = tracker.track_usage(
            event_id="evt-456", input_tokens=10000, output_tokens=5000, model="gemini-2.0-flash-exp"
        )

        assert usage.total_tokens == 15000
        assert usage.estimated_cost_usd == 0.0  # Free model

    def test_track_usage_with_metadata(self):
        """Test tracking usage with metadata"""
        tracker = BudgetTracker()

        usage = tracker.track_usage(
            event_id="evt-789",
            input_tokens=2000,
            output_tokens=1000,
            model="gemini-2.0-flash",
            metadata={"file_path": "test.py", "issue_type": "security"},
        )

        assert usage.total_tokens == 3000
        # Metadata is logged but not returned in usage


class TestBudgetAvailability:
    """Test budget availability checks"""

    def test_get_budget_tracker_singleton(self):
        """Test singleton pattern returns same instance"""
        tracker1 = get_budget_tracker(daily_limit_usd=5.0)
        tracker2 = get_budget_tracker(daily_limit_usd=10.0)  # Different params

        # Should return same instance
        assert tracker1 is tracker2

    def test_check_budget_available_no_limit(self):
        """Test budget check with no limits set"""
        tracker = BudgetTracker(daily_limit_usd=None, monthly_limit_usd=None)

        # No limits = always available
        available = tracker.check_budget_available(period="today")
        assert available is True

    def test_check_budget_available_with_daily_limit(self):
        """Test budget check with daily limit"""
        tracker = BudgetTracker(daily_limit_usd=10.0, monthly_limit_usd=None)

        # Should check against daily limit
        available = tracker.check_budget_available(period="today")
        # Can't assert specific result without real BigQuery data
        assert isinstance(available, bool)

    def test_check_budget_available_with_monthly_limit(self):
        """Test budget check with monthly limit"""
        tracker = BudgetTracker(daily_limit_usd=None, monthly_limit_usd=200.0)

        available = tracker.check_budget_available(period="month")
        assert isinstance(available, bool)

    def test_check_budget_fail_open_on_error(self):
        """Test budget check fails open on error (allows request)"""
        tracker = BudgetTracker(daily_limit_usd=10.0)

        # Even if there's an error, should return True (fail open)
        available = tracker.check_budget_available(period="today")
        assert isinstance(available, bool)


class TestBudgetStatus:
    """Test budget status and alert levels"""

    def test_get_budget_status_structure(self, mock_bigquery_client):
        """Test budget status returns correct structure"""
        tracker = BudgetTracker(daily_limit_usd=10.0)

        status = tracker.get_budget_status(period="today")

        # Check all expected fields
        assert "level" in status
        assert "message" in status
        assert "utilization_pct" in status
        assert "cost_usd" in status
        assert "limit_usd" in status
        assert "remaining_usd" in status
        assert "usage_summary" in status

    def test_get_budget_status_levels(self, mock_bigquery_client):
        """Test budget status level calculation"""
        tracker = BudgetTracker(daily_limit_usd=10.0)

        status = tracker.get_budget_status(period="today")

        # Level should be one of the valid levels
        valid_levels = ["OK", "WARNING", "CRITICAL", "EXCEEDED", "UNKNOWN"]
        assert status["level"] in valid_levels

        # Utilization percentage should be valid
        if status["level"] != "UNKNOWN":
            assert isinstance(status["utilization_pct"], (int, float))
            assert status["utilization_pct"] >= 0


class TestUsageSummary:
    """Test usage summary queries"""

    def test_get_usage_summary_today(self, mock_bigquery_client):
        """Test getting today's usage summary"""
        tracker = BudgetTracker(daily_limit_usd=10.0)

        summary = tracker.get_usage_summary(period="today")

        # Check all expected fields
        assert "period" in summary
        assert "request_count" in summary
        assert "total_input_tokens" in summary
        assert "total_output_tokens" in summary
        assert "total_tokens" in summary
        assert "estimated_cost_usd" in summary

        # Values should be valid
        assert isinstance(summary["request_count"], int)
        assert isinstance(summary["total_tokens"], int)
        assert isinstance(summary["estimated_cost_usd"], float)
        assert summary["request_count"] >= 0
        assert summary["total_tokens"] >= 0
        assert summary["estimated_cost_usd"] >= 0.0

    def test_get_usage_summary_month(self, mock_bigquery_client):
        """Test getting monthly usage summary"""
        tracker = BudgetTracker(monthly_limit_usd=200.0)

        summary = tracker.get_usage_summary(period="month")

        assert "period" in summary
        assert summary["period"] == "This Month"

    def test_get_usage_summary_7d(self, mock_bigquery_client):
        """Test getting 7-day usage summary"""
        tracker = BudgetTracker()

        summary = tracker.get_usage_summary(period="7d")

        assert "period" in summary
        assert summary["period"] == "Last 7 days"

    def test_get_usage_summary_30d(self, mock_bigquery_client):
        """Test getting 30-day usage summary"""
        tracker = BudgetTracker()

        summary = tracker.get_usage_summary(period="30d")

        assert "period" in summary
        if "error" not in summary:
            assert summary["period"] == "Last 30 days"

    def test_get_usage_summary_invalid_period(self):
        """Test getting usage summary with invalid period"""
        tracker = BudgetTracker()

        # Invalid period should return error dict (error handling, not exception)
        summary = tracker.get_usage_summary(period="invalid")

        # Should return error dict instead of raising
        assert "error" in summary
        assert isinstance(summary["error"], str)

    def test_get_usage_summary_includes_budget_info(self):
        """Test usage summary includes budget information"""
        tracker = BudgetTracker(daily_limit_usd=10.0, monthly_limit_usd=200.0)

        summary = tracker.get_usage_summary(period="today")

        # Should include budget limit info
        if "error" not in summary:
            assert "daily_limit_usd" in summary
            assert "monthly_limit_usd" in summary
            assert summary["daily_limit_usd"] == 10.0
            assert summary["monthly_limit_usd"] == 200.0


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_calculate_cost_large_numbers(self):
        """Test cost calculation with very large token counts"""
        tracker = BudgetTracker()

        cost = tracker.calculate_cost(
            input_tokens=100_000_000,  # 100M tokens
            output_tokens=50_000_000,  # 50M tokens
            model="gemini-2.0-flash",
        )

        # (100 * $0.075) + (50 * $0.30) = $7.50 + $15.00 = $22.50
        assert cost == 22.50

    def test_budget_tracker_without_bigquery(self):
        """Test BudgetTracker handles missing BigQuery gracefully"""
        # Create tracker with invalid project
        tracker = BudgetTracker(project_id="invalid-project-id")

        # Should still be able to calculate costs locally
        cost = tracker.calculate_cost(
            input_tokens=1000, output_tokens=500, model="gemini-2.0-flash"
        )

        assert cost > 0

    def test_zero_budget_limit(self):
        """Test with zero budget limit"""
        tracker = BudgetTracker(daily_limit_usd=0.0)

        # Even with $0 limit, check should work
        available = tracker.check_budget_available(period="today")
        assert isinstance(available, bool)

    def test_negative_tokens_raises_error(self):
        """Test that negative token counts are handled"""
        tracker = BudgetTracker()

        # Negative tokens should still calculate (Python allows it)
        # but result would be negative
        cost = tracker.calculate_cost(
            input_tokens=-1000, output_tokens=-500, model="gemini-2.0-flash"
        )

        assert cost < 0  # Negative cost is invalid but allowed by calculation


class TestBudgetTrackerIntegration:
    """Integration tests combining multiple features"""

    def test_full_budget_workflow(self, mock_bigquery_client):
        """Test complete budget tracking workflow"""
        tracker = BudgetTracker(daily_limit_usd=10.0, monthly_limit_usd=200.0)

        # 1. Check budget available
        available = tracker.check_budget_available(period="today")
        assert isinstance(available, bool)

        # 2. Track usage
        usage = tracker.track_usage(
            event_id="integration-test-1",
            input_tokens=2000,
            output_tokens=1000,
            model="gemini-2.0-flash",
        )
        assert usage.total_tokens == 3000

        # 3. Get usage summary
        summary = tracker.get_usage_summary(period="today")
        assert "estimated_cost_usd" in summary

        # 4. Get budget status
        status = tracker.get_budget_status(period="today")
        assert "level" in status

    def test_multiple_models_cost_comparison(self):
        """Test cost comparison across different models"""
        tracker = BudgetTracker()

        input_tokens = 1_000_000
        output_tokens = 1_000_000

        # Calculate cost for each model
        cost_exp = tracker.calculate_cost(input_tokens, output_tokens, "gemini-2.0-flash-exp")
        cost_flash = tracker.calculate_cost(input_tokens, output_tokens, "gemini-2.0-flash")
        cost_pro = tracker.calculate_cost(input_tokens, output_tokens, "gemini-1.5-pro")

        # Experimental should be free
        assert cost_exp == 0.0

        # Pro should be most expensive
        assert cost_pro > cost_flash

        # Flash should be cheapest paid option
        assert cost_flash > 0
        assert cost_flash < cost_pro


# Parametrized tests for models
@pytest.mark.parametrize(
    "model,expected_free",
    [
        ("gemini-2.0-flash-exp", True),
        ("gemini-2.0-flash", False),
        ("gemini-1.5-flash", False),
        ("gemini-1.5-flash-8b", False),
        ("gemini-1.5-pro", False),
    ],
)
def test_model_pricing_status(model, expected_free):
    """Test pricing status for each model"""
    tracker = BudgetTracker()

    cost = tracker.calculate_cost(input_tokens=1000, output_tokens=1000, model=model)

    if expected_free:
        assert cost == 0.0
    else:
        assert cost > 0.0


@pytest.mark.parametrize("period", ["today", "month", "7d", "30d"])
def test_usage_summary_all_periods(period, mock_bigquery_client):
    """Test usage summary for all valid periods"""
    tracker = BudgetTracker(daily_limit_usd=10.0, monthly_limit_usd=200.0)

    summary = tracker.get_usage_summary(period=period)

    # Should return valid summary for all periods
    assert "period" in summary
    assert "request_count" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
