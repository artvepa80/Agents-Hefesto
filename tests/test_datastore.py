"""
HEFESTO v4.5 - Datastore Abstraction Test Suite

Comprehensive tests for the platform-agnostic datastore layer.
Tests SQLite and Mock backends (GCP BigQuery requires credentials).

Copyright 2025 Narapa LLC, Miami, Florida
OMEGA Sports Analytics Foundation
"""

import os
import tempfile
from datetime import datetime

import pytest

from hefesto.llm.datastore import (
    GCPBigQueryClient,
    MockClient,
    QueryParameter,
    QueryResult,
    SQLiteClient,
    get_datastore_client,
    reset_datastore_client,
)


class TestQueryResult:
    """Test QueryResult dataclass."""

    def test_create_query_result(self):
        """Test creating QueryResult."""
        result = QueryResult(
            rows=[{"id": 1, "name": "test"}],
            row_count=1,
            columns=["id", "name"],
            success=True,
        )
        assert result.success is True
        assert result.row_count == 1
        assert len(result.rows) == 1
        assert result.columns == ["id", "name"]

    def test_query_result_iteration(self):
        """Test iterating over QueryResult."""
        result = QueryResult(
            rows=[{"id": 1}, {"id": 2}, {"id": 3}],
            row_count=3,
            columns=["id"],
        )
        ids = [row["id"] for row in result]
        assert ids == [1, 2, 3]

    def test_query_result_length(self):
        """Test len() on QueryResult."""
        result = QueryResult(rows=[{"a": 1}, {"a": 2}], row_count=2, columns=["a"])
        assert len(result) == 2

    def test_query_result_indexing(self):
        """Test indexing QueryResult."""
        result = QueryResult(
            rows=[{"x": "first"}, {"x": "second"}],
            row_count=2,
            columns=["x"],
        )
        assert result[0]["x"] == "first"
        assert result[1]["x"] == "second"

    def test_query_result_with_error(self):
        """Test QueryResult with error."""
        result = QueryResult(
            rows=[],
            row_count=0,
            columns=[],
            success=False,
            error="Connection failed",
        )
        assert result.success is False
        assert result.error == "Connection failed"


class TestSQLiteClient:
    """Test SQLite backend implementation."""

    def test_create_in_memory_client(self):
        """Test creating in-memory SQLite client."""
        client = SQLiteClient(db_path=":memory:")
        assert client._connection is not None

    def test_create_file_based_client(self):
        """Test creating file-based SQLite client."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            client = SQLiteClient(db_path=db_path)
            assert client._connection is not None
            client.close()
        finally:
            os.unlink(db_path)

    def test_ensure_table_exists(self):
        """Test creating table if not exists."""
        client = SQLiteClient(db_path=":memory:")

        schema = [
            {"name": "id", "type": "STRING"},
            {"name": "count", "type": "INT64"},
            {"name": "value", "type": "FLOAT64"},
            {"name": "active", "type": "BOOL"},
            {"name": "created_at", "type": "TIMESTAMP"},
        ]

        result = client.ensure_table_exists("test_table", schema)
        assert result is True

        result = client.ensure_table_exists("test_table", schema)
        assert result is True

    def test_insert_and_query_rows(self):
        """Test inserting and querying rows."""
        client = SQLiteClient(db_path=":memory:")

        schema = [
            {"name": "id", "type": "STRING"},
            {"name": "name", "type": "STRING"},
            {"name": "count", "type": "INT64"},
        ]
        client.ensure_table_exists("items", schema)

        rows = [
            {"id": "1", "name": "Item A", "count": 10},
            {"id": "2", "name": "Item B", "count": 20},
            {"id": "3", "name": "Item C", "count": 30},
        ]
        success = client.insert_rows("items", rows)
        assert success is True

        result = client.query("SELECT * FROM items ORDER BY id")
        assert result.success is True
        assert result.row_count == 3
        assert result.rows[0]["name"] == "Item A"
        assert result.rows[1]["count"] == 20

    def test_parameterized_query(self):
        """Test query with parameters."""
        client = SQLiteClient(db_path=":memory:")

        schema = [{"name": "name", "type": "STRING"}, {"name": "score", "type": "INT64"}]
        client.ensure_table_exists("scores", schema)

        rows = [
            {"name": "Alice", "score": 85},
            {"name": "Bob", "score": 90},
            {"name": "Charlie", "score": 75},
        ]
        client.insert_rows("scores", rows)

        result = client.query(
            "SELECT * FROM scores WHERE score >= @min_score",
            parameters=[QueryParameter("min_score", "INT64", 80)],
        )

        assert result.success is True
        assert result.row_count == 2
        names = {row["name"] for row in result}
        assert names == {"Alice", "Bob"}

    def test_execute_update(self):
        """Test executing UPDATE statement."""
        client = SQLiteClient(db_path=":memory:")

        schema = [{"name": "id", "type": "STRING"}, {"name": "status", "type": "STRING"}]
        client.ensure_table_exists("tasks", schema)

        client.insert_rows("tasks", [{"id": "1", "status": "pending"}])

        success = client.execute(
            "UPDATE tasks SET status = :new_status WHERE id = :task_id",
            parameters=[
                QueryParameter("new_status", "STRING", "completed"),
                QueryParameter("task_id", "STRING", "1"),
            ],
        )
        assert success is True

        result = client.query("SELECT status FROM tasks WHERE id = '1'")
        assert result.rows[0]["status"] == "completed"

    def test_boolean_handling(self):
        """Test boolean type handling (SQLite uses INTEGER)."""
        client = SQLiteClient(db_path=":memory:")

        schema = [{"name": "name", "type": "STRING"}, {"name": "active", "type": "BOOL"}]
        client.ensure_table_exists("flags", schema)

        rows = [
            {"name": "Feature A", "active": True},
            {"name": "Feature B", "active": False},
        ]
        client.insert_rows("flags", rows)

        result = client.query("SELECT * FROM flags ORDER BY name")
        assert result.success is True
        assert result.rows[0]["active"] == 1
        assert result.rows[1]["active"] == 0

    def test_timestamp_handling(self):
        """Test timestamp handling."""
        client = SQLiteClient(db_path=":memory:")

        schema = [{"name": "event", "type": "STRING"}, {"name": "ts", "type": "TIMESTAMP"}]
        client.ensure_table_exists("events", schema)

        now = datetime.utcnow()
        rows = [{"event": "login", "ts": now}]
        client.insert_rows("events", rows)

        result = client.query("SELECT * FROM events")
        assert result.success is True
        assert result.rows[0]["event"] == "login"
        assert isinstance(result.rows[0]["ts"], str)

    def test_sql_conversion_safe_divide(self):
        """Test SAFE_DIVIDE conversion."""
        client = SQLiteClient(db_path=":memory:")

        schema = [{"name": "num", "type": "INT64"}, {"name": "denom", "type": "INT64"}]
        client.ensure_table_exists("ratios", schema)

        rows = [
            {"num": 10, "denom": 2},
            {"num": 5, "denom": 0},
        ]
        client.insert_rows("ratios", rows)

        result = client.query(
            "SELECT num, denom, SAFE_DIVIDE(num, denom) as ratio FROM ratios ORDER BY num DESC"
        )
        assert result.success is True
        assert result.rows[0]["ratio"] == 5.0
        assert result.rows[1]["ratio"] is None

    def test_sql_conversion_countif(self):
        """Test COUNTIF conversion."""
        client = SQLiteClient(db_path=":memory:")

        schema = [{"name": "name", "type": "STRING"}, {"name": "passed", "type": "BOOL"}]
        client.ensure_table_exists("tests", schema)

        rows = [
            {"name": "test1", "passed": True},
            {"name": "test2", "passed": True},
            {"name": "test3", "passed": False},
        ]
        client.insert_rows("tests", rows)

        result = client.query(
            "SELECT COUNT(*) as total, COUNTIF(passed = 1) as passed_count FROM tests"
        )
        assert result.success is True
        assert result.rows[0]["total"] == 3
        assert result.rows[0]["passed_count"] == 2

    def test_close_connection(self):
        """Test closing SQLite connection."""
        client = SQLiteClient(db_path=":memory:")
        assert client._connection is not None

        client.close()
        assert client._connection is None


class TestMockClient:
    """Test Mock backend implementation."""

    def test_create_mock_client(self):
        """Test creating MockClient."""
        client = MockClient()
        assert client is not None

    def test_set_query_response(self):
        """Test setting mock query response."""
        client = MockClient()

        client.set_query_response([{"count": 42}])

        result = client.query("SELECT COUNT(*) as count FROM anything")
        assert result.success is True
        assert result.rows[0]["count"] == 42

    def test_multiple_query_responses(self):
        """Test multiple query responses cycle."""
        client = MockClient()

        client.set_query_response([{"value": "first"}])
        client.set_query_response([{"value": "second"}])

        result1 = client.query("SELECT 1")
        result2 = client.query("SELECT 2")

        assert result1.rows[0]["value"] == "first"
        assert result2.rows[0]["value"] == "second"

    def test_insert_rows_stored(self):
        """Test that inserted rows are stored."""
        client = MockClient()

        rows = [{"id": 1, "name": "Test"}]
        success = client.insert_rows("test_table", rows)

        assert success is True
        stored = client.get_inserted_rows("test_table")
        assert len(stored) == 1
        assert stored[0]["name"] == "Test"

    def test_execute_always_succeeds(self):
        """Test execute always returns True."""
        client = MockClient()

        result = client.execute("UPDATE table SET x = 1")
        assert result is True

    def test_ensure_table_exists(self):
        """Test ensure_table_exists always succeeds."""
        client = MockClient()

        result = client.ensure_table_exists("any_table", [])
        assert result is True

    def test_reset_client(self):
        """Test resetting mock client state."""
        client = MockClient()

        client.insert_rows("table1", [{"a": 1}])
        client.set_query_response([{"b": 2}])

        client.reset()

        assert client.get_inserted_rows("table1") == []
        result = client.query("SELECT 1")
        assert result.rows == []

    def test_set_error_response(self):
        """Test setting error response."""
        client = MockClient()

        client.set_query_response([], success=False, error="Simulated error")

        result = client.query("SELECT 1")
        assert result.success is False
        assert result.error == "Simulated error"


class TestGetDatastoreClient:
    """Test factory function."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_datastore_client()

    def teardown_method(self):
        """Reset singleton after each test."""
        reset_datastore_client()

    def test_get_sqlite_client(self):
        """Test getting SQLite client."""
        client = get_datastore_client(backend="sqlite", db_path=":memory:")
        assert isinstance(client, SQLiteClient)

    def test_get_mock_client(self):
        """Test getting Mock client."""
        client = get_datastore_client(backend="mock")
        assert isinstance(client, MockClient)

    def test_singleton_pattern(self):
        """Test that factory returns singleton."""
        client1 = get_datastore_client(backend="mock")
        client2 = get_datastore_client()

        assert client1 is client2

    def test_invalid_backend_raises(self):
        """Test that invalid backend raises ValueError."""
        with pytest.raises(ValueError, match="Unknown datastore backend"):
            get_datastore_client(backend="invalid_backend")

    def test_environment_variable_backend(self, monkeypatch):
        """Test backend selection from environment variable."""
        reset_datastore_client()
        monkeypatch.setenv("HEFESTO_DATASTORE_BACKEND", "mock")

        client = get_datastore_client()
        assert isinstance(client, MockClient)


class TestBudgetTrackerWithMock:
    """Test BudgetTracker with Mock backend."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_datastore_client()

    def teardown_method(self):
        """Reset singleton after each test."""
        reset_datastore_client()

    def test_budget_tracker_with_mock_client(self):
        """Test BudgetTracker with injected mock client."""
        from hefesto.llm.budget_tracker import BudgetTracker

        mock = MockClient()
        mock.set_query_response(
            [
                {
                    "request_count": 10,
                    "total_input_tokens": 10000,
                    "total_output_tokens": 5000,
                    "total_tokens": 15000,
                    "active_days": 1,
                }
            ]
        )

        tracker = BudgetTracker(
            daily_limit_usd=10.0,
            datastore_client=mock,
        )

        summary = tracker.get_usage_summary(period="today")
        assert summary["request_count"] == 10
        assert summary["total_tokens"] == 15000

    def test_budget_tracker_cost_calculation(self):
        """Test cost calculation without backend."""
        from hefesto.llm.budget_tracker import BudgetTracker

        tracker = BudgetTracker(datastore_client=MockClient())

        cost = tracker.calculate_cost(
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            model="gemini-2.0-flash",
        )

        assert cost == 0.375

    def test_budget_tracker_free_model(self):
        """Test free model cost calculation."""
        from hefesto.llm.budget_tracker import BudgetTracker

        tracker = BudgetTracker(datastore_client=MockClient())

        cost = tracker.calculate_cost(
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            model="gemini-2.0-flash-exp",
        )

        assert cost == 0.0


class TestFeedbackLoggerWithMock:
    """Test FeedbackLogger with Mock backend."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_datastore_client()

    def teardown_method(self):
        """Reset singleton after each test."""
        reset_datastore_client()

    def test_feedback_logger_with_mock_client(self):
        """Test FeedbackLogger with injected mock client."""
        from hefesto.llm.feedback_logger import FeedbackLogger

        mock = MockClient()

        logger = FeedbackLogger(datastore_client=mock)

        suggestion_id = logger.log_suggestion_shown(
            file_path="test.py",
            issue_type="security",
            severity="HIGH",
            confidence_score=0.85,
        )

        assert suggestion_id.startswith("SUG-")
        assert len(suggestion_id) == 16

        inserted = mock.get_inserted_rows(logger.full_table_id)
        assert len(inserted) == 1
        assert inserted[0]["file_path"] == "test.py"
        assert inserted[0]["confidence_score"] == 0.85

    def test_feedback_logger_acceptance_rate(self):
        """Test getting acceptance rate metrics."""
        from hefesto.llm.feedback_logger import FeedbackLogger

        mock = MockClient()
        mock.set_query_response(
            [
                {
                    "total": 100,
                    "accepted": 75,
                    "rejected": 20,
                    "pending": 5,
                    "acceptance_rate": 0.789,
                    "avg_confidence": 0.82,
                    "avg_similarity": 0.71,
                    "avg_time_to_apply": 45.5,
                }
            ]
        )

        logger = FeedbackLogger(datastore_client=mock)

        metrics = logger.get_acceptance_rate(issue_type="security", days=30)

        assert metrics["total"] == 100
        assert metrics["accepted"] == 75
        assert metrics["acceptance_rate"] == 0.789


class TestIntegrationSQLite:
    """Integration tests using SQLite backend."""

    def test_full_budget_workflow_sqlite(self):
        """Test complete budget workflow with SQLite."""
        from hefesto.llm.budget_tracker import BudgetTracker, LLM_EVENTS_SCHEMA

        client = SQLiteClient(db_path=":memory:")

        client.ensure_table_exists("test.omega_agent.llm_events", LLM_EVENTS_SCHEMA)

        tracker = BudgetTracker(
            project_id="test",
            daily_limit_usd=10.0,
            monthly_limit_usd=200.0,
            datastore_client=client,
        )

        available = tracker.check_budget_available(period="today")
        assert available is True

        usage = tracker.track_usage(
            event_id="evt-001",
            input_tokens=2000,
            output_tokens=1000,
            model="gemini-2.0-flash",
        )
        assert usage.total_tokens == 3000
        assert usage.estimated_cost_usd > 0

    def test_full_feedback_workflow_sqlite(self):
        """Test complete feedback workflow with SQLite."""
        from hefesto.llm.feedback_logger import FeedbackLogger, SUGGESTION_FEEDBACK_SCHEMA

        client = SQLiteClient(db_path=":memory:")

        client.ensure_table_exists(
            "test.omega_agent.suggestion_feedback", SUGGESTION_FEEDBACK_SCHEMA
        )

        logger = FeedbackLogger(
            project_id="test",
            datastore_client=client,
        )

        suggestion_id = logger.log_suggestion_shown(
            file_path="api/auth.py",
            issue_type="security",
            severity="HIGH",
            confidence_score=0.92,
        )

        assert suggestion_id.startswith("SUG-")

        result = client.query(
            f"SELECT * FROM suggestion_feedback WHERE suggestion_id = :sid",
            parameters=[QueryParameter("sid", "STRING", suggestion_id)],
        )
        assert result.row_count == 1
        assert result.rows[0]["file_path"] == "api/auth.py"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
