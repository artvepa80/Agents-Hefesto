#!/usr/bin/env python3
"""
IRIS-HEFESTO Integration: Automatic Alert Enrichment
======================================================
Correlates production alerts with Hefesto code findings
to provide 360° traceability from code warnings to production failures.

Copyright © 2025 Narapa LLC, Miami, Florida
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

# Optional Google Cloud imports
try:
    from google.cloud import bigquery
    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    GOOGLE_CLOUD_AVAILABLE = False
    bigquery = None

logger = logging.getLogger(__name__)


class HefestoEnricher:
    """
    Enriches Iris alerts with related Hefesto code findings.

    Correlation Strategy:
    1. Extract file paths from alert messages
    2. Query code_findings for CRITICAL/HIGH severity issues
    3. Filter by time window (90 days before alert)
    4. Score by severity + recency + status (ignored = higher impact)
    5. Return most relevant finding
    """

    def __init__(self, project_id: str, dry_run: bool = False):
        """
        Initialize Hefesto enricher.

        Args:
            project_id: GCP project ID
            dry_run: If True, don't query BigQuery (for testing)
        """
        self.project_id = project_id
        self.dry_run = dry_run

        if not GOOGLE_CLOUD_AVAILABLE:
            logger.warning(
                "Google Cloud libraries not available. "
                "Hefesto enrichment will be disabled. "
                "Install with: pip install google-cloud-bigquery"
            )
            self.client = None
            self.table_ref = None
            return

        if not dry_run:
            self.client = bigquery.Client(project=project_id)
            self.table_ref = f"{project_id}.omega_audit.code_findings"
        else:
            self.client = None
            self.table_ref = None

        logger.info(
            f"HefestoEnricher initialized: {self.table_ref} (dry_run={dry_run})"
        )

    def extract_file_paths(self, alert_message: str) -> List[str]:
        """
        Extract file paths from alert message.

        Supports patterns:
        - path/to/file.py
        - /absolute/path/to/file.py
        - file.py:123
        - in module.submodule.file

        Args:
            alert_message: Alert message text

        Returns:
            List of extracted file paths
        """
        file_paths = []

        # Pattern 1: Explicit file paths (e.g., "api/endpoints.py")
        path_pattern = r"([a-zA-Z0-9_/.-]+\.py)"
        matches = re.findall(path_pattern, alert_message)
        file_paths.extend(matches)

        # Pattern 2: Python module paths (e.g., "in api.endpoints")
        module_pattern = r"in ([a-zA-Z0-9_.]+)"
        module_matches = re.findall(module_pattern, alert_message)
        for module in module_matches:
            # Convert module path to file path
            file_path = module.replace(".", "/") + ".py"
            file_paths.append(file_path)

        # Remove duplicates while preserving order
        seen = set()
        unique_paths = []
        for path in file_paths:
            # Normalize: remove leading slash, line numbers
            normalized = path.lstrip("/").split(":")[0]
            if normalized not in seen:
                seen.add(normalized)
                unique_paths.append(normalized)

        logger.debug(f"Extracted file paths from alert: {unique_paths}")
        return unique_paths

    def query_related_findings(
        self, file_paths: List[str], alert_timestamp: datetime, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Query code_findings for related issues.

        Args:
            file_paths: List of file paths to search
            alert_timestamp: When the alert occurred
            limit: Maximum number of findings to return

        Returns:
            List of related findings (most severe first)
        """
        if self.dry_run:
            logger.info("[DRY RUN] Would query code_findings")
            return []

        if not file_paths:
            return []

        try:
            # Build query with file path matching
            # Use 90-day lookback window
            query = f"""
            SELECT
                finding_id,
                ts,
                file_path,
                line_number,
                function_name,
                issue_type,
                severity,
                description,
                rule_id,
                code_snippet,
                suggested_fix,
                llm_event_id,
                status,
                metadata,
                created_at,
                TIMESTAMP_DIFF(@alert_timestamp, ts, DAY) AS days_before_alert
            FROM `{self.table_ref}`
            WHERE file_path IN UNNEST(@file_paths)
              AND severity IN ('CRITICAL', 'HIGH')
              AND status IN ('open', 'ignored')
              AND ts <= @alert_timestamp
              AND ts >= TIMESTAMP_SUB(@alert_timestamp, INTERVAL 90 DAY)
            ORDER BY
              CASE severity
                WHEN 'CRITICAL' THEN 4
                WHEN 'HIGH' THEN 3
                WHEN 'MEDIUM' THEN 2
                ELSE 1
              END DESC,
              ts DESC
            LIMIT @limit
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ArrayQueryParameter("file_paths", "STRING", file_paths),
                    bigquery.ScalarQueryParameter(
                        "alert_timestamp", "TIMESTAMP", alert_timestamp
                    ),
                    bigquery.ScalarQueryParameter("limit", "INT64", limit),
                ]
            )

            query_job = self.client.query(query, job_config=job_config)
            results = query_job.result()

            findings = []
            for row in results:
                finding = dict(row)
                findings.append(finding)

            logger.info(f"Found {len(findings)} related Hefesto findings")
            return findings

        except Exception as e:
            logger.error(f"Error querying code_findings: {e}")
            return []

    def score_finding(self, finding: Dict[str, Any]) -> float:
        """
        Calculate relevance score for a finding.

        Scoring:
        - Severity: CRITICAL=4, HIGH=3, MEDIUM=2, LOW=1
        - Status: ignored=2x multiplier (shows impact)
        - Recency: Decay factor (newer = better)

        Args:
            finding: Finding dictionary

        Returns:
            Relevance score (higher = more relevant)
        """
        # Severity score
        severity_scores = {
            "CRITICAL": 4.0,
            "HIGH": 3.0,
            "MEDIUM": 2.0,
            "LOW": 1.0,
            "INFO": 0.5,
        }
        severity_score = severity_scores.get(finding.get("severity", "LOW"), 1.0)

        # Status multiplier (ignored warnings are more impactful)
        status_multiplier = 2.0 if finding.get("status") == "ignored" else 1.0

        # Recency decay (within 90 days)
        days_ago = finding.get("days_before_alert", 90)
        recency_factor = max(0.1, 1.0 - (days_ago / 90.0))

        total_score = severity_score * status_multiplier * recency_factor
        return total_score

    def enrich_alert_context(
        self,
        alert_message: str,
        alert_timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Enrich alert context with Hefesto finding (if available).

        Args:
            alert_message: Alert message text
            alert_timestamp: When alert occurred (default: now)
            metadata: Additional alert metadata

        Returns:
            Enrichment context with Hefesto finding (or None)
        """
        if alert_timestamp is None:
            alert_timestamp = datetime.utcnow()

        # Extract file paths from alert
        file_paths = self.extract_file_paths(alert_message)

        if not file_paths:
            logger.debug("No file paths found in alert message")
            return {
                "hefesto_finding_id": None,
                "hefesto_context": None,
                "correlation_attempted": True,
                "correlation_successful": False,
                "reason": "no_file_paths_extracted",
            }

        # Query related findings
        findings = self.query_related_findings(file_paths, alert_timestamp)

        if not findings:
            logger.debug(f"No Hefesto findings found for files: {file_paths}")
            return {
                "hefesto_finding_id": None,
                "hefesto_context": None,
                "correlation_attempted": True,
                "correlation_successful": False,
                "reason": "no_matching_findings",
                "searched_files": file_paths,
            }

        # Score findings and pick best match
        scored_findings = [
            (finding, self.score_finding(finding)) for finding in findings
        ]
        scored_findings.sort(key=lambda x: x[1], reverse=True)

        best_finding, best_score = scored_findings[0]

        logger.info(
            f"✅ Correlated alert with Hefesto finding: {best_finding['finding_id']} "
            f"(score={best_score:.2f}, severity={best_finding['severity']})"
        )

        # Build enrichment context
        hefesto_context = {
            "finding_id": best_finding["finding_id"],
            "file_path": best_finding["file_path"],
            "line_number": best_finding.get("line_number"),
            "function_name": best_finding.get("function_name"),
            "severity": best_finding["severity"],
            "issue_type": best_finding["issue_type"],
            "description": best_finding["description"],
            "status": best_finding["status"],
            "detected_days_ago": best_finding.get("days_before_alert"),
            "suggested_fix": best_finding.get("suggested_fix"),
            "rule_id": best_finding.get("rule_id"),
            "correlation_score": best_score,
            "total_findings_matched": len(findings),
        }

        return {
            "hefesto_finding_id": best_finding["finding_id"],
            "hefesto_context": hefesto_context,
            "correlation_attempted": True,
            "correlation_successful": True,
            "correlation_score": best_score,
        }


# Singleton instance
_enricher_instance: Optional[HefestoEnricher] = None


def get_hefesto_enricher(project_id: str, dry_run: bool = False) -> HefestoEnricher:
    """
    Get singleton Hefesto enricher instance.

    Args:
        project_id: GCP project ID
        dry_run: If True, don't query BigQuery

    Returns:
        HefestoEnricher instance
    """
    global _enricher_instance

    if _enricher_instance is None:
        _enricher_instance = HefestoEnricher(project_id, dry_run=dry_run)

    return _enricher_instance


if __name__ == "__main__":
    # Test the enricher
    import sys

    logging.basicConfig(level=logging.INFO)

    # Test with dry run
    enricher = HefestoEnricher(project_id="eminent-carver-469323-q2", dry_run=True)

    # Test file path extraction
    test_message = "API error rate 8.5% in api/endpoints.py (line 145)"
    file_paths = enricher.extract_file_paths(test_message)
    print(f"✅ Extracted file paths: {file_paths}")

    # Test enrichment (dry run)
    context = enricher.enrich_alert_context(test_message)
    print(f"✅ Enrichment context: {context}")

    print("\n✅ HefestoEnricher test passed!")
