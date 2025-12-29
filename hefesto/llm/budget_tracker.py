"""
HEFESTO v4.5 - Budget Control System

Purpose: Track LLM API usage and costs to prevent budget overruns.
Location: llm/budget_tracker.py

This module provides budget monitoring and enforcement:
- Calculate costs based on token usage
- Track daily/monthly spending
- Enforce budget limits
- Generate usage reports
- Alert when thresholds exceeded

v4.5.0: Now uses abstracted DatastoreClient for platform-agnostic storage.
        Supports GCP BigQuery, SQLite, and custom backends.

Copyright 2025 Narapa LLC, Miami, Florida
OMEGA Sports Analytics Foundation
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union

from hefesto.llm.datastore import (
    DatastoreClient,
    GCPBigQueryClient,
    MockClient,
    QueryParameter,
    SQLiteClient,
    get_datastore_client,
)

logger = logging.getLogger(__name__)


LLM_EVENTS_SCHEMA = [
    {"name": "event_id", "type": "STRING"},
    {"name": "timestamp", "type": "TIMESTAMP"},
    {"name": "model", "type": "STRING"},
    {"name": "prompt_tokens", "type": "INT64"},
    {"name": "completion_tokens", "type": "INT64"},
    {"name": "total_tokens", "type": "INT64"},
    {"name": "estimated_cost_usd", "type": "FLOAT64"},
    {"name": "request_type", "type": "STRING"},
    {"name": "metadata", "type": "STRING"},
]


@dataclass
class TokenUsage:
    """
    Token usage and cost for a single LLM request.

    Attributes:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        total_tokens: Total tokens (input + output)
        estimated_cost_usd: Estimated cost in USD
    """

    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float


class BudgetTracker:
    """
    Tracks LLM API usage and enforces budget limits.

    Monitors token usage and costs to prevent unexpected bills.
    Queries existing llm_events table for usage data.

    Now supports multiple backends through the DatastoreClient abstraction:
    - GCP BigQuery (production)
    - SQLite (local development)
    - Mock (testing)

    Usage:
        >>> tracker = BudgetTracker(
        ...     daily_limit_usd=10.0,
        ...     monthly_limit_usd=200.0
        ... )
        >>>
        >>> # Check budget before expensive operation
        >>> if not tracker.check_budget_available():
        ...     raise BudgetExceededError("Daily budget exceeded")
        >>>
        >>> # Track usage after LLM call
        >>> usage = tracker.track_usage(
        ...     event_id="evt_123",
        ...     input_tokens=1500,
        ...     output_tokens=800,
        ...     model="gemini-2.0-flash-exp"
        ... )
        >>> print(f"Cost: ${usage.estimated_cost_usd:.4f}")
        >>>
        >>> # Get usage summary
        >>> summary = tracker.get_usage_summary(period="today")
        >>> print(f"Today: ${summary['estimated_cost_usd']:.2f}")
    """

    PRICING = {
        "gemini-2.0-flash-exp": {
            "input": 0.00,
            "output": 0.00,
        },
        "gemini-2.0-flash": {
            "input": 0.075,
            "output": 0.30,
        },
        "gemini-1.5-flash": {
            "input": 0.075,
            "output": 0.30,
        },
        "gemini-1.5-flash-8b": {
            "input": 0.0375,
            "output": 0.15,
        },
        "gemini-1.5-pro": {
            "input": 1.25,
            "output": 5.00,
        },
        "default": {
            "input": 0.075,
            "output": 0.30,
        },
    }

    def __init__(
        self,
        project_id: str = "your-project-id",
        daily_limit_usd: Optional[float] = None,
        monthly_limit_usd: Optional[float] = None,
        enable_alerts: bool = True,
        datastore_client: Optional[
            Union[GCPBigQueryClient, SQLiteClient, MockClient, DatastoreClient]
        ] = None,
        backend: Optional[str] = None,
    ):
        """
        Initialize BudgetTracker.

        Args:
            project_id: Project ID (for table naming)
            daily_limit_usd: Daily budget limit in USD (None = no limit)
            monthly_limit_usd: Monthly budget limit in USD (None = no limit)
            enable_alerts: Whether to enable budget alerts
            datastore_client: Optional pre-configured datastore client
            backend: Force specific backend ("gcp", "sqlite", "mock")
        """
        self.project_id = project_id
        self.daily_limit = daily_limit_usd
        self.monthly_limit = monthly_limit_usd
        self.enable_alerts = enable_alerts

        dataset_id = os.getenv("HEFESTO_DATASET_ID", "omega_agent")
        self.llm_events_table = f"{project_id}.{dataset_id}.llm_events"

        if datastore_client is not None:
            self.client = datastore_client
        else:
            try:
                self.client = get_datastore_client(
                    backend=backend,
                    project_id=project_id,
                )
            except Exception as e:
                logger.error(f"Failed to initialize datastore client: {e}")
                self.client = None

        if self.client:
            try:
                self.client.ensure_table_exists(self.llm_events_table, LLM_EVENTS_SCHEMA)
            except Exception as e:
                logger.warning(f"Could not ensure table exists: {e}")

        logger.info(
            f"BudgetTracker initialized - "
            f"Daily: ${daily_limit_usd}, Monthly: ${monthly_limit_usd}"
        )

    def calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str,
    ) -> float:
        """
        Calculate cost in USD for token usage.

        Uses current pricing for Gemini models. If model unknown,
        uses default conservative pricing.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model name (e.g., "gemini-2.0-flash-exp")

        Returns:
            Estimated cost in USD

        Example:
            >>> tracker = BudgetTracker()
            >>> cost = tracker.calculate_cost(
            ...     input_tokens=1500,
            ...     output_tokens=800,
            ...     model="gemini-2.0-flash"
            ... )
            >>> print(f"Cost: ${cost:.4f}")
            Cost: $0.0024
        """
        if model not in self.PRICING:
            logger.warning(f"Unknown model '{model}', using default pricing")
            pricing = self.PRICING["default"]
        else:
            pricing = self.PRICING[model]

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        total_cost = input_cost + output_cost

        logger.debug(
            f"Cost calculation: {input_tokens} in + {output_tokens} out = ${total_cost:.6f}"
        )

        return total_cost

    def track_usage(
        self,
        event_id: str,
        input_tokens: int,
        output_tokens: int,
        model: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TokenUsage:
        """
        Track LLM usage for a request.

        NOTE: This calculates cost only. Actual logging to the datastore
        happens in llm_tracking module. This method is for cost
        calculation and monitoring.

        Args:
            event_id: Unique event ID
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model name
            metadata: Optional metadata dictionary

        Returns:
            TokenUsage with cost information

        Example:
            >>> tracker = BudgetTracker()
            >>> usage = tracker.track_usage(
            ...     event_id="req-123",
            ...     input_tokens=1500,
            ...     output_tokens=800,
            ...     model="gemini-2.0-flash"
            ... )
            >>> print(f"Total tokens: {usage.total_tokens}")
            Total tokens: 2300
        """
        total_tokens = input_tokens + output_tokens
        cost = self.calculate_cost(input_tokens, output_tokens, model)

        usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=cost,
        )

        logger.info(
            f"[{event_id}] Usage tracked: {total_tokens} tokens "
            f"(in: {input_tokens}, out: {output_tokens}), "
            f"Cost: ${cost:.6f}, Model: {model}"
        )

        return usage

    def get_usage_summary(
        self,
        period: str = "today",
    ) -> Dict[str, Any]:
        """
        Get usage summary for a time period.

        Queries the datastore to calculate total usage and cost.
        Returns aggregated statistics including token counts and costs.

        Args:
            period: Time period to query:
                - "today": Current day (midnight to now)
                - "month": Current month (1st to now)
                - "7d": Last 7 days
                - "30d": Last 30 days

        Returns:
            Dictionary with usage statistics:
            - period: Period name
            - request_count: Number of requests
            - total_input_tokens: Sum of input tokens
            - total_output_tokens: Sum of output tokens
            - total_tokens: Sum of all tokens
            - estimated_cost_usd: Estimated cost
            - daily_limit_usd: Daily budget limit
            - monthly_limit_usd: Monthly budget limit
            - budget_remaining_usd: Remaining budget
            - budget_utilization_pct: Percentage used

        Example:
            >>> tracker = BudgetTracker(daily_limit_usd=10.0)
            >>> summary = tracker.get_usage_summary(period="today")
            >>> print(f"Today: ${summary['estimated_cost_usd']:.2f}")
            >>> print(f"Remaining: ${summary['budget_remaining_usd']:.2f}")
        """
        if not self.client:
            return {"error": "Datastore client not initialized"}

        try:
            if period == "today":
                start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                period_name = "Today"
            elif period == "month":
                start_time = datetime.now().replace(
                    day=1, hour=0, minute=0, second=0, microsecond=0
                )
                period_name = "This Month"
            elif period.endswith("d"):
                days = int(period[:-1])
                start_time = datetime.now() - timedelta(days=days)
                period_name = f"Last {days} days"
            else:
                return {"error": f"Invalid period: {period}"}

            query = f"""
            SELECT
                COUNT(*) as request_count,
                COALESCE(SUM(prompt_tokens), 0) as total_input_tokens,
                COALESCE(SUM(completion_tokens), 0) as total_output_tokens,
                COALESCE(SUM(prompt_tokens + completion_tokens), 0) as total_tokens,
                COUNT(DISTINCT DATE(timestamp)) as active_days
            FROM `{self.llm_events_table}`
            WHERE timestamp >= @start_time
            """

            result = self.client.query(
                query,
                parameters=[
                    QueryParameter("start_time", "TIMESTAMP", start_time.isoformat())
                ],
            )

            if not result.success:
                return {"error": result.error or "Query failed"}

            if not result.rows or result.rows[0].get("request_count", 0) == 0:
                return {
                    "period": period_name,
                    "start_time": start_time.isoformat(),
                    "request_count": 0,
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "total_tokens": 0,
                    "active_days": 0,
                    "estimated_cost_usd": 0.0,
                    "daily_limit_usd": self.daily_limit,
                    "monthly_limit_usd": self.monthly_limit,
                    "budget_remaining_usd": (
                        self.daily_limit if period == "today" else self.monthly_limit
                    ),
                    "budget_utilization_pct": 0.0,
                }

            row = result.rows[0]

            estimated_cost = self.calculate_cost(
                input_tokens=row.get("total_input_tokens", 0),
                output_tokens=row.get("total_output_tokens", 0),
                model="gemini-2.0-flash",
            )

            if period == "today" and self.daily_limit:
                budget_limit = self.daily_limit
                budget_remaining = max(0.0, self.daily_limit - estimated_cost)
                budget_utilization = (estimated_cost / self.daily_limit) * 100
            elif period == "month" and self.monthly_limit:
                budget_limit = self.monthly_limit
                budget_remaining = max(0.0, self.monthly_limit - estimated_cost)
                budget_utilization = (estimated_cost / self.monthly_limit) * 100
            else:
                budget_limit = None
                budget_remaining = None
                budget_utilization = 0.0

            return {
                "period": period_name,
                "start_time": start_time.isoformat(),
                "request_count": row.get("request_count", 0),
                "total_input_tokens": row.get("total_input_tokens", 0),
                "total_output_tokens": row.get("total_output_tokens", 0),
                "total_tokens": row.get("total_tokens", 0),
                "active_days": row.get("active_days", 0),
                "estimated_cost_usd": estimated_cost,
                "daily_limit_usd": self.daily_limit,
                "monthly_limit_usd": self.monthly_limit,
                "budget_limit_usd": budget_limit,
                "budget_remaining_usd": budget_remaining,
                "budget_utilization_pct": budget_utilization,
            }

        except Exception as e:
            logger.error(f"Failed to get usage summary: {e}", exc_info=True)
            return {"error": str(e)}

    def check_budget_available(self, period: str = "today") -> bool:
        """
        Check if budget is available for more requests.

        Queries current usage and compares against budget limits.
        Returns True if within budget, False if exceeded.

        NOTE: Fails open (returns True) if check fails, to avoid
        blocking requests due to monitoring issues.

        Args:
            period: Period to check ("today" or "month")

        Returns:
            True if budget available, False if exceeded

        Example:
            >>> tracker = BudgetTracker(daily_limit_usd=10.0)
            >>> if not tracker.check_budget_available():
            ...     print("Budget exceeded!")
            Budget exceeded!
        """
        try:
            usage = self.get_usage_summary(period=period)

            if "error" in usage:
                logger.warning("Budget check failed, allowing request (fail open)")
                return True

            if period == "today" and self.daily_limit:
                if usage["estimated_cost_usd"] >= self.daily_limit:
                    logger.warning(
                        f"Daily budget exceeded: "
                        f"${usage['estimated_cost_usd']:.2f} >= ${self.daily_limit:.2f}"
                    )
                    return False

            if period == "month" and self.monthly_limit:
                if usage["estimated_cost_usd"] >= self.monthly_limit:
                    logger.warning(
                        f"Monthly budget exceeded: "
                        f"${usage['estimated_cost_usd']:.2f} >= ${self.monthly_limit:.2f}"
                    )
                    return False

            return True

        except Exception as e:
            logger.error(f"Budget check error: {e}", exc_info=True)
            return True

    def get_budget_status(self, period: str = "today") -> Dict[str, Any]:
        """
        Get comprehensive budget status including alert levels.

        Returns budget status with warning/critical thresholds:
        - OK: < 80% of budget
        - WARNING: 80-95% of budget
        - CRITICAL: 95-100% of budget
        - EXCEEDED: >= 100% of budget

        Args:
            period: Period to check ("today" or "month")

        Returns:
            Dictionary with status information

        Example:
            >>> tracker = BudgetTracker(daily_limit_usd=10.0)
            >>> status = tracker.get_budget_status()
            >>> print(f"Status: {status['level']}")
            Status: OK
        """
        usage = self.get_usage_summary(period=period)

        if "error" in usage:
            return {
                "level": "UNKNOWN",
                "message": "Failed to check budget",
                "error": usage["error"],
            }

        utilization = usage.get("budget_utilization_pct", 0.0)

        if utilization >= 100:
            level = "EXCEEDED"
            message = f"Budget exceeded ({utilization:.1f}%)"
        elif utilization >= 95:
            level = "CRITICAL"
            message = f"Budget critical ({utilization:.1f}% used)"
        elif utilization >= 80:
            level = "WARNING"
            message = f"Budget warning ({utilization:.1f}% used)"
        else:
            level = "OK"
            message = f"Budget OK ({utilization:.1f}% used)"

        return {
            "level": level,
            "message": message,
            "utilization_pct": utilization,
            "cost_usd": usage.get("estimated_cost_usd", 0.0),
            "limit_usd": usage.get("budget_limit_usd"),
            "remaining_usd": usage.get("budget_remaining_usd"),
            "usage_summary": usage,
        }


_budget_tracker_instance: Optional[BudgetTracker] = None


def get_budget_tracker(
    daily_limit_usd: Optional[float] = 10.0,
    monthly_limit_usd: Optional[float] = 200.0,
) -> BudgetTracker:
    """
    Get singleton BudgetTracker instance.

    Creates tracker with specified limits on first call,
    returns same instance on subsequent calls.

    Args:
        daily_limit_usd: Daily budget limit (default: $10)
        monthly_limit_usd: Monthly budget limit (default: $200)

    Returns:
        Singleton BudgetTracker instance

    Example:
        >>> tracker1 = get_budget_tracker(daily_limit_usd=5.0)
        >>> tracker2 = get_budget_tracker()
        >>> assert tracker1 is tracker2  # Same instance
    """
    global _budget_tracker_instance

    if _budget_tracker_instance is None:
        _budget_tracker_instance = BudgetTracker(
            daily_limit_usd=daily_limit_usd,
            monthly_limit_usd=monthly_limit_usd,
        )

    return _budget_tracker_instance


__all__ = [
    "BudgetTracker",
    "TokenUsage",
    "get_budget_tracker",
]
