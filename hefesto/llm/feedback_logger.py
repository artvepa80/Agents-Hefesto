"""
HEFESTO v4.5 - Feedback Loop Logger

Purpose: Track user acceptance/rejection of LLM suggestions for continuous improvement.
Location: llm/feedback_logger.py

This module enables the feedback loop by logging:
- When suggestions are shown to users
- User acceptance/rejection decisions
- Application success/failure
- CI/CD results (future)

v4.5.0: Now uses abstracted DatastoreClient for platform-agnostic storage.
        Supports GCP BigQuery, SQLite, and custom backends.

Copyright 2025 Narapa LLC, Miami, Florida
OMEGA Sports Analytics Foundation
"""

import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from hefesto.llm.datastore import (
    DatastoreClient,
    GCPBigQueryClient,
    MockClient,
    QueryParameter,
    SQLiteClient,
    get_datastore_client,
)

logger = logging.getLogger(__name__)


SUGGESTION_FEEDBACK_SCHEMA = [
    {"name": "suggestion_id", "type": "STRING"},
    {"name": "llm_event_id", "type": "STRING"},
    {"name": "ts", "type": "TIMESTAMP"},
    {"name": "file_path", "type": "STRING"},
    {"name": "issue_type", "type": "STRING"},
    {"name": "severity", "type": "STRING"},
    {"name": "shown_to_user", "type": "BOOL"},
    {"name": "user_accepted", "type": "BOOL"},
    {"name": "applied_successfully", "type": "BOOL"},
    {"name": "time_to_apply_seconds", "type": "INT64"},
    {"name": "ci_passed", "type": "BOOL"},
    {"name": "tests_passed", "type": "BOOL"},
    {"name": "coverage_improved", "type": "BOOL"},
    {"name": "user_comment", "type": "STRING"},
    {"name": "rejection_reason", "type": "STRING"},
    {"name": "confidence_score", "type": "FLOAT64"},
    {"name": "validation_passed", "type": "BOOL"},
    {"name": "similarity_score", "type": "FLOAT64"},
]


@dataclass
class SuggestionFeedback:
    """
    Feedback data for a code refactoring suggestion.

    Attributes:
        suggestion_id: Unique identifier (SUG-XXXXXXXXXXXX format)
        llm_event_id: Foreign key to llm_events table
        file_path: File where issue was detected
        issue_type: Type of issue (security, performance, etc.)
        severity: Issue severity level
        shown_to_user: Whether suggestion was displayed
        user_accepted: User's decision (None = pending)
        applied_successfully: Whether application succeeded
        time_to_apply_seconds: Time taken to apply
        ci_passed: CI pipeline result
        tests_passed: Test suite result
        coverage_improved: Code coverage change
        user_comment: Free-text feedback
        rejection_reason: Why suggestion was rejected
        confidence_score: LLM confidence (0.0-1.0)
        validation_passed: Validation result
        similarity_score: Code similarity (0.0-1.0)
    """

    suggestion_id: str
    llm_event_id: Optional[str] = None
    file_path: Optional[str] = None
    issue_type: Optional[str] = None
    severity: Optional[str] = None
    shown_to_user: bool = True
    user_accepted: Optional[bool] = None
    applied_successfully: Optional[bool] = None
    time_to_apply_seconds: Optional[int] = None
    ci_passed: Optional[bool] = None
    tests_passed: Optional[bool] = None
    coverage_improved: Optional[bool] = None
    user_comment: Optional[str] = None
    rejection_reason: Optional[str] = None
    confidence_score: Optional[float] = None
    validation_passed: Optional[bool] = None
    similarity_score: Optional[float] = None


class FeedbackLogger:
    """
    Logs suggestion feedback for analysis and improvement.

    Now supports multiple backends through the DatastoreClient abstraction:
    - GCP BigQuery (production)
    - SQLite (local development)
    - Mock (testing)

    This class handles the complete feedback loop:
    1. Log when suggestion is shown
    2. Update when user accepts/rejects
    3. Track application results
    4. Query metrics for analysis

    Usage:
        >>> logger = FeedbackLogger(project_id="your-project-id")
        >>> suggestion_id = logger.log_suggestion_shown(
        ...     file_path="api/users.py",
        ...     issue_type="security",
        ...     severity="HIGH",
        ...     confidence_score=0.85
        ... )
        >>> logger.log_user_action(
        ...     suggestion_id=suggestion_id,
        ...     accepted=True,
        ...     time_to_apply_seconds=30
        ... )
        >>> metrics = logger.get_acceptance_rate(issue_type="security")
        >>> print(f"Acceptance rate: {metrics['acceptance_rate']:.1%}")
    """

    def __init__(
        self,
        project_id: str = "your-project-id",
        dataset_id: str = "omega_agent",
        table_id: str = "suggestion_feedback",
        datastore_client: Optional[
            Union[GCPBigQueryClient, SQLiteClient, MockClient, DatastoreClient]
        ] = None,
        backend: Optional[str] = None,
    ):
        """
        Initialize FeedbackLogger.

        Args:
            project_id: Project ID (for table naming)
            dataset_id: Dataset ID
            table_id: Table name
            datastore_client: Optional pre-configured datastore client
            backend: Force specific backend ("gcp", "sqlite", "mock")
        """
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.table_id = table_id
        self.full_table_id = f"{project_id}.{dataset_id}.{table_id}"

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
                self.client.ensure_table_exists(self.full_table_id, SUGGESTION_FEEDBACK_SCHEMA)
            except Exception as e:
                logger.warning(f"Could not ensure table exists: {e}")

        logger.info(f"FeedbackLogger initialized for {self.full_table_id}")

    def generate_suggestion_id(self) -> str:
        """
        Generate unique suggestion ID in format: SUG-XXXXXXXXXXXX

        Returns:
            Unique suggestion ID (16 characters total)

        Example:
            >>> logger = FeedbackLogger()
            >>> id = logger.generate_suggestion_id()
            >>> print(id)
            SUG-A1B2C3D4E5F6
        """
        return f"SUG-{uuid.uuid4().hex[:12].upper()}"

    def log_suggestion_shown(
        self,
        file_path: str,
        issue_type: str,
        severity: str,
        llm_event_id: Optional[str] = None,
        confidence_score: Optional[float] = None,
        validation_passed: Optional[bool] = None,
        similarity_score: Optional[float] = None,
    ) -> str:
        """
        Log when a suggestion is shown to the user.

        Call this immediately after generating a refactoring suggestion
        and returning it to the user. Returns a suggestion_id that can
        be used to track user actions later.

        Args:
            file_path: File where issue was detected
            issue_type: Type of issue (security, performance, etc.)
            severity: Issue severity (CRITICAL, HIGH, MEDIUM, LOW, INFO)
            llm_event_id: Optional foreign key to llm_events table
            confidence_score: LLM confidence score (0.0-1.0)
            validation_passed: Whether validation checks passed
            similarity_score: Code similarity score (0.0-1.0)

        Returns:
            Unique suggestion_id for tracking

        Example:
            >>> logger = FeedbackLogger()
            >>> suggestion_id = logger.log_suggestion_shown(
            ...     file_path="api/auth.py",
            ...     issue_type="security",
            ...     severity="HIGH",
            ...     confidence_score=0.85,
            ...     validation_passed=True,
            ...     similarity_score=0.72
            ... )
            >>> print(suggestion_id)
            SUG-A1B2C3D4E5F6
        """
        suggestion_id = self.generate_suggestion_id()

        feedback = SuggestionFeedback(
            suggestion_id=suggestion_id,
            llm_event_id=llm_event_id,
            file_path=file_path,
            issue_type=issue_type,
            severity=severity,
            shown_to_user=True,
            confidence_score=confidence_score,
            validation_passed=validation_passed,
            similarity_score=similarity_score,
        )

        try:
            self._insert_feedback(feedback)
            logger.info(
                f"Logged suggestion shown: {suggestion_id} "
                f"(file={file_path}, type={issue_type}, severity={severity})"
            )
            return suggestion_id
        except Exception as e:
            logger.error(f"Failed to log suggestion: {e}", exc_info=True)
            return suggestion_id

    def log_user_action(
        self,
        suggestion_id: str,
        accepted: bool,
        applied_successfully: Optional[bool] = None,
        time_to_apply_seconds: Optional[int] = None,
        rejection_reason: Optional[str] = None,
        user_comment: Optional[str] = None,
    ):
        """
        Log user's decision on a suggestion.

        Call this when user accepts or rejects a suggestion. This updates
        the existing feedback row with user decision and outcome.

        Args:
            suggestion_id: Suggestion ID from log_suggestion_shown()
            accepted: Whether user accepted the suggestion
            applied_successfully: Whether suggestion applied without errors
            time_to_apply_seconds: Time taken to apply (seconds)
            rejection_reason: Why suggestion was rejected
            user_comment: Additional user feedback

        Example:
            >>> logger = FeedbackLogger()
            >>> logger.log_user_action(
            ...     suggestion_id="SUG-A1B2C3D4E5F6",
            ...     accepted=True,
            ...     applied_successfully=True,
            ...     time_to_apply_seconds=45,
            ...     user_comment="Worked perfectly, thanks!"
            ... )
        """
        if not self.client:
            logger.error("Datastore client not initialized, cannot log user action")
            return

        try:
            table_name = self.full_table_id.split(".")[-1]
            query = f"""
            UPDATE `{self.full_table_id}`
            SET
                user_accepted = @accepted,
                applied_successfully = @applied_successfully,
                time_to_apply_seconds = @time_to_apply_seconds,
                rejection_reason = @rejection_reason,
                user_comment = @user_comment
            WHERE suggestion_id = @suggestion_id
            """

            success = self.client.execute(
                query,
                parameters=[
                    QueryParameter("suggestion_id", "STRING", suggestion_id),
                    QueryParameter("accepted", "BOOL", accepted),
                    QueryParameter("applied_successfully", "BOOL", applied_successfully),
                    QueryParameter("time_to_apply_seconds", "INT64", time_to_apply_seconds),
                    QueryParameter("rejection_reason", "STRING", rejection_reason),
                    QueryParameter("user_comment", "STRING", user_comment),
                ],
            )

            if success:
                action = "accepted" if accepted else "rejected"
                logger.info(
                    f"Logged user action for {suggestion_id}: {action} "
                    f"(applied={applied_successfully}, time={time_to_apply_seconds}s)"
                )
            else:
                logger.error(f"Failed to update user action for {suggestion_id}")

        except Exception as e:
            logger.error(f"Failed to log user action: {e}", exc_info=True)

    def log_ci_results(
        self,
        suggestion_id: str,
        ci_passed: bool,
        tests_passed: Optional[bool] = None,
        coverage_improved: Optional[bool] = None,
    ):
        """
        Log CI/CD pipeline results after applying suggestion.

        Call this after suggestion is applied and CI pipeline runs.
        This helps track whether suggestions break builds or tests.

        Args:
            suggestion_id: Suggestion ID from log_suggestion_shown()
            ci_passed: Whether CI pipeline passed
            tests_passed: Whether test suite passed
            coverage_improved: Whether code coverage increased

        Example:
            >>> logger = FeedbackLogger()
            >>> logger.log_ci_results(
            ...     suggestion_id="SUG-A1B2C3D4E5F6",
            ...     ci_passed=True,
            ...     tests_passed=True,
            ...     coverage_improved=True
            ... )
        """
        if not self.client:
            logger.error("Datastore client not initialized, cannot log CI results")
            return

        try:
            query = f"""
            UPDATE `{self.full_table_id}`
            SET
                ci_passed = @ci_passed,
                tests_passed = @tests_passed,
                coverage_improved = @coverage_improved
            WHERE suggestion_id = @suggestion_id
            """

            success = self.client.execute(
                query,
                parameters=[
                    QueryParameter("suggestion_id", "STRING", suggestion_id),
                    QueryParameter("ci_passed", "BOOL", ci_passed),
                    QueryParameter("tests_passed", "BOOL", tests_passed),
                    QueryParameter("coverage_improved", "BOOL", coverage_improved),
                ],
            )

            if success:
                logger.info(
                    f"Logged CI results for {suggestion_id}: "
                    f"ci_passed={ci_passed}, tests_passed={tests_passed}, "
                    f"coverage_improved={coverage_improved}"
                )

        except Exception as e:
            logger.error(f"Failed to log CI results: {e}", exc_info=True)

    def get_acceptance_rate(
        self,
        issue_type: Optional[str] = None,
        severity: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get suggestion acceptance rate metrics.

        Query the datastore to calculate acceptance rates, average confidence,
        and other metrics for analysis.

        Args:
            issue_type: Filter by issue type (optional)
            severity: Filter by severity (optional)
            days: Number of days to include (default: 30)

        Returns:
            Dictionary with metrics:
            - total: Total suggestions
            - accepted: Number accepted
            - rejected: Number rejected
            - pending: Number with no decision yet
            - acceptance_rate: Percentage accepted (0.0-1.0)
            - avg_confidence: Average confidence score
            - avg_similarity: Average similarity score
            - avg_time_to_apply: Average application time (seconds)

        Example:
            >>> logger = FeedbackLogger()
            >>> metrics = logger.get_acceptance_rate(
            ...     issue_type="security",
            ...     days=30
            ... )
            >>> print(f"Acceptance rate: {metrics['acceptance_rate']:.1%}")
            Acceptance rate: 75.0%
        """
        if not self.client:
            logger.error("Datastore client not initialized")
            return {"error": "Datastore client not initialized"}

        try:
            where_clauses = ["ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)"]

            query_params: List[QueryParameter] = [
                QueryParameter("days", "INT64", days)
            ]

            if issue_type:
                where_clauses.append("issue_type = @issue_type")
                query_params.append(QueryParameter("issue_type", "STRING", issue_type))

            if severity:
                where_clauses.append("severity = @severity")
                query_params.append(QueryParameter("severity", "STRING", severity))

            where_clause = " AND ".join(where_clauses)

            query = f"""
            SELECT
                COUNT(*) as total,
                COUNTIF(user_accepted = TRUE) as accepted,
                COUNTIF(user_accepted = FALSE) as rejected,
                COUNTIF(user_accepted IS NULL) as pending,
                SAFE_DIVIDE(
                    COUNTIF(user_accepted = TRUE),
                    COUNTIF(user_accepted IS NOT NULL)
                ) as acceptance_rate,
                AVG(confidence_score) as avg_confidence,
                AVG(similarity_score) as avg_similarity,
                AVG(time_to_apply_seconds) as avg_time_to_apply
            FROM `{self.full_table_id}`
            WHERE {where_clause}
            """

            result = self.client.query(query, parameters=query_params)

            if not result.success:
                return {"error": result.error or "Query failed"}

            if result.rows:
                row = result.rows[0]
                return {
                    "total": int(row.get("total", 0) or 0),
                    "accepted": int(row.get("accepted", 0) or 0),
                    "rejected": int(row.get("rejected", 0) or 0),
                    "pending": int(row.get("pending", 0) or 0),
                    "acceptance_rate": float(row.get("acceptance_rate", 0) or 0.0),
                    "avg_confidence": float(row.get("avg_confidence", 0) or 0.0),
                    "avg_similarity": float(row.get("avg_similarity", 0) or 0.0),
                    "avg_time_to_apply": float(row.get("avg_time_to_apply", 0) or 0.0),
                }

            return {
                "total": 0,
                "accepted": 0,
                "rejected": 0,
                "pending": 0,
                "acceptance_rate": 0.0,
                "avg_confidence": 0.0,
                "avg_similarity": 0.0,
                "avg_time_to_apply": 0.0,
            }

        except Exception as e:
            logger.error(f"Failed to get acceptance rate: {e}", exc_info=True)
            return {"error": str(e)}

    def _insert_feedback(self, feedback: SuggestionFeedback):
        """
        Insert feedback row to datastore.

        Internal method to insert new feedback record.

        Args:
            feedback: SuggestionFeedback dataclass instance

        Raises:
            Exception: If insert fails
        """
        if not self.client:
            raise Exception("Datastore client not initialized")

        rows_to_insert = [
            {
                "suggestion_id": feedback.suggestion_id,
                "llm_event_id": feedback.llm_event_id,
                "ts": datetime.utcnow().isoformat(),
                "file_path": feedback.file_path,
                "issue_type": feedback.issue_type,
                "severity": feedback.severity,
                "shown_to_user": feedback.shown_to_user,
                "user_accepted": feedback.user_accepted,
                "applied_successfully": feedback.applied_successfully,
                "time_to_apply_seconds": feedback.time_to_apply_seconds,
                "ci_passed": feedback.ci_passed,
                "tests_passed": feedback.tests_passed,
                "coverage_improved": feedback.coverage_improved,
                "user_comment": feedback.user_comment,
                "rejection_reason": feedback.rejection_reason,
                "confidence_score": feedback.confidence_score,
                "validation_passed": feedback.validation_passed,
                "similarity_score": feedback.similarity_score,
            }
        ]

        success = self.client.insert_rows(self.full_table_id, rows_to_insert)
        if not success:
            raise Exception("Failed to insert feedback row")


_feedback_logger_instance: Optional[FeedbackLogger] = None


def get_feedback_logger(project_id: str = "your-project-id") -> FeedbackLogger:
    """
    Get singleton FeedbackLogger instance.

    This ensures only one datastore client is created for the lifetime
    of the application, improving performance.

    Args:
        project_id: Project ID (default: your-project-id)

    Returns:
        Singleton FeedbackLogger instance

    Example:
        >>> logger1 = get_feedback_logger()
        >>> logger2 = get_feedback_logger()
        >>> assert logger1 is logger2  # Same instance
    """
    global _feedback_logger_instance

    if _feedback_logger_instance is None:
        _feedback_logger_instance = FeedbackLogger(project_id=project_id)

    return _feedback_logger_instance


__all__ = [
    "FeedbackLogger",
    "SuggestionFeedback",
    "get_feedback_logger",
]
