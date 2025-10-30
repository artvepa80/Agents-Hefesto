"""
BigQuery service layer for findings persistence.

Handles:
- Connection to user's BigQuery project
- CRUD operations for findings, analysis_runs, finding_history
- Query building with filters and pagination
- Data transformation between API and BigQuery formats
- Graceful degradation when BigQuery not configured
- Retry logic for transient errors

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from google.api_core import retry
from google.cloud import bigquery
from google.cloud.exceptions import GoogleCloudError

from hefesto.api.types import DatasetId, FindingId, FindingStatus, ProjectId  # noqa: F401

logger = logging.getLogger(__name__)


class BigQueryClient:
    """
    Client for BigQuery operations.

    Manages connection to user's BigQuery project and provides
    methods for findings persistence and retrieval.

    Gracefully degrades when BigQuery not configured.
    """

    def __init__(self):
        """
        Initialize BigQuery client.

        Reads configuration from environment variables:
        - BIGQUERY_PROJECT_ID: GCP project ID
        - BIGQUERY_DATASET_ID: BigQuery dataset name (default: hefesto_findings)
        - GOOGLE_APPLICATION_CREDENTIALS: Path to service account key

        If not configured, sets is_configured=False and operations return safe defaults.
        """
        self.project_id: Optional[ProjectId] = None
        self.dataset_id: Optional[DatasetId] = None
        self.client: Optional[bigquery.Client] = None
        self.is_configured: bool = False

        try:
            # Read configuration from environment
            project_id = os.getenv("BIGQUERY_PROJECT_ID")
            dataset_id = os.getenv("BIGQUERY_DATASET_ID", "hefesto_findings")

            if not project_id:
                logger.info(
                    "BigQuery not configured (missing BIGQUERY_PROJECT_ID). "
                    "Findings will not be persisted. See docs/BIGQUERY_SETUP_GUIDE.md"
                )
                return

            # Initialize BigQuery client
            self.client = bigquery.Client(project=project_id)
            self.project_id = ProjectId(project_id)
            self.dataset_id = DatasetId(dataset_id)
            self.is_configured = True

            logger.info(f"BigQuery client initialized: {self.project_id}.{self.dataset_id}")

        except Exception as e:
            logger.warning(
                f"Failed to initialize BigQuery client: {e}. "
                f"Findings will not be persisted. See docs/BIGQUERY_SETUP_GUIDE.md"
            )
            self.is_configured = False

    def _build_list_query(self, limit: int, offset: int, filters: Dict[str, Any]) -> str:
        """
        Build SQL query for listing findings with filters.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip
            filters: Dictionary of filter conditions:
                - severity: Filter by severity (CRITICAL, HIGH, MEDIUM, LOW)
                - file_path: Filter by file path (exact match)
                - analyzer: Filter by analyzer name
                - status: Filter by status (new, in_progress, resolved, etc.)
                - start_date: Filter by created_at >= start_date (ISO format)
                - end_date: Filter by created_at <= end_date (ISO format)

        Returns:
            SQL query string
        """
        query = f"""
        SELECT
            finding_id,
            analysis_id,
            file_path,
            line_number,
            column_number,
            severity,
            analyzer,
            issue_type,
            description,
            recommendation,
            code_snippet,
            confidence,
            status,
            status_updated_at,
            status_updated_by,
            notes,
            created_at,
            updated_at
        FROM `{self.project_id}.{self.dataset_id}.findings`
        """

        # Build WHERE clause from filters
        where_clauses = []

        if "severity" in filters:
            where_clauses.append(f"severity = '{filters['severity']}'")

        if "file_path" in filters:
            where_clauses.append(f"file_path = '{filters['file_path']}'")

        if "analyzer" in filters:
            where_clauses.append(f"analyzer = '{filters['analyzer']}'")

        if "status" in filters:
            where_clauses.append(f"status = '{filters['status']}'")

        if "start_date" in filters:
            where_clauses.append(f"created_at >= TIMESTAMP('{filters['start_date']}')")

        if "end_date" in filters:
            where_clauses.append(f"created_at <= TIMESTAMP('{filters['end_date']}')")

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        # Order by created_at DESC (newest first)
        query += " ORDER BY created_at DESC"

        # Add pagination
        query += f" LIMIT {limit} OFFSET {offset}"

        return query

    def _build_get_by_id_query(self, finding_id: str) -> str:
        """
        Build SQL query for getting single finding by ID.

        Args:
            finding_id: Finding identifier (fnd_*)

        Returns:
            SQL query string
        """
        return f"""
        SELECT
            finding_id,
            analysis_id,
            file_path,
            line_number,
            column_number,
            severity,
            analyzer,
            issue_type,
            description,
            recommendation,
            code_snippet,
            confidence,
            status,
            status_updated_at,
            status_updated_by,
            notes,
            created_at,
            updated_at
        FROM `{self.project_id}.{self.dataset_id}.findings`
        WHERE finding_id = '{finding_id}'
        LIMIT 1
        """

    def _transform_row_to_finding(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform BigQuery row to FindingSchema format.

        Args:
            row: BigQuery row as dictionary

        Returns:
            Finding in API format
        """
        return {
            "id": row["finding_id"],
            "file": row["file_path"],
            "line": row["line_number"],
            "column": row["column_number"] if row.get("column_number") else 1,
            "type": row["issue_type"],
            "severity": row["severity"],
            "message": row["description"],
            "function": row.get("function"),
            "suggestion": row.get("recommendation"),
            "code_snippet": row.get("code_snippet"),
            "metadata": {
                "analyzer": row["analyzer"],
                "confidence": row.get("confidence"),
                "status": row.get("status", "new"),
                "status_updated_at": (
                    row["status_updated_at"].isoformat() if row.get("status_updated_at") else None
                ),
                "status_updated_by": row.get("status_updated_by"),
                "notes": row.get("notes"),
                "created_at": (row["created_at"].isoformat() if row.get("created_at") else None),
                "updated_at": (row["updated_at"].isoformat() if row.get("updated_at") else None),
            },
        }

    def _transform_finding_to_bq(self, finding: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform FindingSchema to BigQuery row format.

        Args:
            finding: Finding in API format

        Returns:
            Row ready for BigQuery insertion
        """
        now = datetime.utcnow()

        return {
            "finding_id": finding["id"],
            "analysis_id": finding.get("analysis_id", ""),
            "file_path": finding["file"],
            "line_number": finding["line"],
            "column_number": finding.get("column", 1),
            "severity": finding["severity"],
            "analyzer": finding.get(
                "analyzer", finding.get("metadata", {}).get("analyzer", "unknown")
            ),
            "issue_type": finding["type"],
            "description": finding["message"],
            "recommendation": finding.get("suggestion"),
            "code_snippet": finding.get("code_snippet"),
            "confidence": finding.get("metadata", {}).get("confidence"),
            "status": "new",
            "status_updated_at": None,
            "status_updated_by": None,
            "notes": None,
            "created_at": now,
            "updated_at": now,
        }

    def _transform_analysis_to_bq(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform analysis summary to BigQuery analysis_runs format.

        Args:
            analysis: Analysis data from AnalysisResponse

        Returns:
            Row ready for BigQuery insertion
        """
        summary = analysis.get("summary", {})

        return {
            "analysis_id": analysis["analysis_id"],
            "timestamp": datetime.utcnow(),
            "path": analysis["path"],
            "analyzers": analysis.get("analyzers", []),
            "total_issues": summary.get("total_issues", 0),
            "critical_issues": summary.get("critical", 0),
            "high_issues": summary.get("high", 0),
            "medium_issues": summary.get("medium", 0),
            "low_issues": summary.get("low", 0),
            "execution_time_ms": int(summary.get("duration_seconds", 0) * 1000),
            "hefesto_version": analysis.get("hefesto_version", "4.0.1"),
            "metadata": {},
        }

    @retry.Retry(predicate=retry.if_transient_error)
    def list_findings(
        self, limit: int, offset: int, filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        List findings with pagination and filters.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip
            filters: Filter conditions (see _build_list_query)

        Returns:
            List of findings in API format
        """
        if not self.is_configured:
            logger.debug("BigQuery not configured, returning empty findings list")
            return []

        try:
            query = self._build_list_query(limit, offset, filters)
            query_job = self.client.query(query)
            results = query_job.result()

            findings = []
            for row in results:
                finding = self._transform_row_to_finding(dict(row))
                findings.append(finding)

            return findings

        except GoogleCloudError as e:
            logger.error(f"BigQuery error listing findings: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing findings: {e}")
            return []

    @retry.Retry(predicate=retry.if_transient_error)
    def get_finding_by_id(self, finding_id: str) -> Optional[Dict[str, Any]]:
        """
        Get single finding by ID.

        Args:
            finding_id: Finding identifier (fnd_*)

        Returns:
            Finding in API format, or None if not found
        """
        if not self.is_configured:
            logger.debug("BigQuery not configured, returning None for finding lookup")
            return None

        try:
            query = self._build_get_by_id_query(finding_id)
            query_job = self.client.query(query)
            results = list(query_job.result())

            if not results:
                return None

            return self._transform_row_to_finding(dict(results[0]))

        except GoogleCloudError as e:
            logger.error(f"BigQuery error getting finding {finding_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting finding {finding_id}: {e}")
            return None

    @retry.Retry(predicate=retry.if_transient_error)
    def update_finding_status(
        self,
        finding_id: str,
        new_status: str,
        updated_by: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> bool:
        """
        Update finding status and create history entry.

        Args:
            finding_id: Finding identifier (fnd_*)
            new_status: New status value
            updated_by: User who made the update
            notes: Optional notes about the update

        Returns:
            True if successful, False otherwise
        """
        if not self.is_configured:
            logger.debug("BigQuery not configured, cannot update finding status")
            return False

        try:
            now = datetime.utcnow()

            # First, get current status for history
            current_finding = self.get_finding_by_id(finding_id)
            previous_status = (
                current_finding.get("metadata", {}).get("status") if current_finding else None
            )

            # Update findings table
            update_query = f"""
            UPDATE `{self.project_id}.{self.dataset_id}.findings`
            SET
                status = '{new_status}',
                status_updated_at = TIMESTAMP('{now.isoformat()}'),
                status_updated_by = {f"'{updated_by}'" if updated_by else "NULL"},
                notes = {f"'{notes}'" if notes else "NULL"},
                updated_at = TIMESTAMP('{now.isoformat()}')
            WHERE finding_id = '{finding_id}'
            """

            query_job = self.client.query(update_query)
            query_job.result()

            # Insert into finding_history
            history_id = f"his_{finding_id}_{int(now.timestamp() * 1000)}"
            history_query = f"""
            INSERT INTO `{self.project_id}.{self.dataset_id}.finding_history`
            (history_id, finding_id, previous_status, new_status, changed_by, changed_at, notes)
            VALUES (
                '{history_id}',
                '{finding_id}',
                {f"'{previous_status}'" if previous_status else "NULL"},
                '{new_status}',
                {f"'{updated_by}'" if updated_by else "NULL"},
                TIMESTAMP('{now.isoformat()}'),
                {f"'{notes}'" if notes else "NULL"}
            )
            """

            history_job = self.client.query(history_query)
            history_job.result()

            logger.info(f"Updated finding {finding_id} status: {previous_status} -> {new_status}")
            return True

        except GoogleCloudError as e:
            logger.error(f"BigQuery error updating finding {finding_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error updating finding {finding_id}: {e}")
            return False

    def insert_findings(self, findings: List[Dict[str, Any]]) -> bool:
        """
        Batch insert findings into BigQuery.

        Args:
            findings: List of findings in API format

        Returns:
            True if successful, False otherwise
        """
        if not findings:
            return True  # Empty list is always successful (no-op)

        if not self.is_configured:
            logger.debug("BigQuery not configured, cannot insert findings")
            return False

        try:
            # Transform findings to BigQuery format
            rows = [self._transform_finding_to_bq(f) for f in findings]

            # Get table reference
            table_ref = self.client.dataset(self.dataset_id).table("findings")

            # Insert rows
            errors = self.client.insert_rows_json(table_ref, rows)

            if errors:
                logger.error(f"BigQuery insert errors: {errors}")
                return False

            logger.info(f"Inserted {len(findings)} findings into BigQuery")
            return True

        except GoogleCloudError as e:
            logger.error(f"BigQuery error inserting findings: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error inserting findings: {e}")
            return False

    def insert_analysis_run(self, analysis: Dict[str, Any]) -> bool:
        """
        Insert analysis run metadata into BigQuery.

        Args:
            analysis: Analysis data from AnalysisResponse

        Returns:
            True if successful, False otherwise
        """
        if not self.is_configured:
            logger.debug("BigQuery not configured, cannot insert analysis run")
            return False

        try:
            # Transform analysis to BigQuery format
            row = self._transform_analysis_to_bq(analysis)

            # Get table reference
            table_ref = self.client.dataset(self.dataset_id).table("analysis_runs")

            # Insert row
            errors = self.client.insert_rows_json(table_ref, [row])

            if errors:
                logger.error(f"BigQuery insert errors for analysis run: {errors}")
                return False

            logger.info(f"Inserted analysis run {analysis['analysis_id']} into BigQuery")
            return True

        except GoogleCloudError as e:
            logger.error(f"BigQuery error inserting analysis run: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error inserting analysis run: {e}")
            return False


# Singleton instance for application-wide use
_bigquery_client: Optional[BigQueryClient] = None


def get_bigquery_client() -> BigQueryClient:
    """
    Get singleton BigQuery client instance.

    Returns:
        BigQueryClient instance
    """
    global _bigquery_client
    if _bigquery_client is None:
        _bigquery_client = BigQueryClient()
    return _bigquery_client


__all__ = ["BigQueryClient", "get_bigquery_client"]
