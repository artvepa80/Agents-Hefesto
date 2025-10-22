-- ============================================================================
-- IRIS-HEFESTO INTEGRATION: Code Findings Schema
-- ============================================================================
-- Purpose: Log code issues detected by Hefesto for correlation with Iris alerts
-- Dataset: omega_audit
-- Table: code_findings
-- Created: 2025-10-12
-- Copyright © 2025 Narapa LLC, Miami, Florida
-- ============================================================================

-- ============================================================================
-- TABLE: code_findings
-- Purpose: Comprehensive log of all code issues detected by Hefesto
-- Partitioned by: DATE(ts) for query performance (90-day retention)
-- Clustering: severity, issue_type, file_path for correlation queries
-- ============================================================================

CREATE TABLE IF NOT EXISTS `eminent-carver-469323-q2.omega_audit.code_findings` (
  -- Identification
  finding_id STRING NOT NULL OPTIONS(description='Unique finding ID (HEF-{TYPE}-{TIMESTAMP})'),
  ts TIMESTAMP NOT NULL OPTIONS(description='When the issue was detected'),

  -- Code Location
  file_path STRING NOT NULL OPTIONS(description='Relative path to file (e.g., api/endpoints.py)'),
  line_number INT64 OPTIONS(description='Line number where issue was found'),
  function_name STRING OPTIONS(description='Function/method name containing the issue'),

  -- Issue Classification
  issue_type STRING NOT NULL OPTIONS(description='Type: security, performance, maintainability, style'),
  severity STRING NOT NULL OPTIONS(description='Severity: CRITICAL, HIGH, MEDIUM, LOW, INFO'),
  description STRING NOT NULL OPTIONS(description='Human-readable description of the issue'),

  -- Detection Context
  rule_id STRING OPTIONS(description='Rule/pattern that detected the issue (e.g., sql-injection-001)'),
  detected_by STRING OPTIONS(description='Agent that detected it (default: hefesto)'),

  -- Code Snippet
  code_snippet STRING OPTIONS(description='Actual problematic code (max 500 chars, masked)'),

  -- Fix Suggestion
  suggested_fix STRING OPTIONS(description='Refactoring recommendation from Hefesto'),
  llm_event_id STRING OPTIONS(description='Link to omega_agent.llm_events for LLM details'),

  -- Lifecycle Tracking
  status STRING OPTIONS(description='Status: open, acknowledged, fixed, ignored, wont_fix'),
  fixed_at TIMESTAMP OPTIONS(description='When the issue was resolved'),
  fixed_by STRING OPTIONS(description='User/agent who fixed it'),

  -- Metadata
  metadata JSON OPTIONS(description='Additional context: {repo, branch, commit_hash, etc.}'),

  -- Audit Trail
  created_at TIMESTAMP NOT NULL OPTIONS(description='Record creation timestamp'),
  updated_at TIMESTAMP OPTIONS(description='Last update timestamp')
)
PARTITION BY DATE(ts)
CLUSTER BY severity, issue_type, file_path
OPTIONS(
  description='Code issues detected by Hefesto for correlation with Iris production alerts',
  labels=[("agent", "hefesto"), ("purpose", "code_quality"), ("tier", "audit")],
  partition_expiration_days=90  -- 90-day retention for correlation analysis
);

-- ============================================================================
-- ALTER TABLE: Add Hefesto correlation to alerts_sent
-- ============================================================================

-- Add columns to existing alerts_sent table for Hefesto enrichment
ALTER TABLE `eminent-carver-469323-q2.omega_audit.alerts_sent`
ADD COLUMN IF NOT EXISTS hefesto_finding_id STRING OPTIONS(description='Related Hefesto finding ID'),
ADD COLUMN IF NOT EXISTS hefesto_context JSON OPTIONS(description='Full Hefesto finding details for display');

-- ============================================================================
-- VIEW 1: Recent Code Findings (Last 90 Days)
-- ============================================================================

CREATE OR REPLACE VIEW `eminent-carver-469323-q2.omega_audit.v_code_findings_recent` AS
SELECT
  finding_id,
  ts,
  file_path,
  line_number,
  severity,
  issue_type,
  description,
  status,
  suggested_fix,
  TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), ts, DAY) AS days_ago
FROM `eminent-carver-469323-q2.omega_audit.code_findings`
WHERE ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
ORDER BY ts DESC;

-- ============================================================================
-- VIEW 2: Findings-to-Alerts Correlation
-- ============================================================================

CREATE OR REPLACE VIEW `eminent-carver-469323-q2.omega_audit.v_findings_to_alerts` AS
SELECT
  f.finding_id,
  f.file_path,
  f.severity AS finding_severity,
  f.description AS finding_description,
  f.ts AS finding_timestamp,
  f.status AS finding_status,
  COUNT(DISTINCT a.alert_id) AS related_alerts_count,
  MIN(a.ts) AS first_alert_timestamp,
  MAX(a.ts) AS last_alert_timestamp,
  TIMESTAMP_DIFF(MIN(a.ts), f.ts, DAY) AS days_until_first_alert
FROM `eminent-carver-469323-q2.omega_audit.code_findings` AS f
LEFT JOIN `eminent-carver-469323-q2.omega_audit.alerts_sent` AS a
  ON a.hefesto_finding_id = f.finding_id
WHERE f.ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
GROUP BY f.finding_id, f.file_path, f.severity, f.description, f.ts, f.status
ORDER BY related_alerts_count DESC, f.ts DESC;

-- ============================================================================
-- VIEW 3: Ignored Critical Findings (Warnings That Became Incidents)
-- ============================================================================

CREATE OR REPLACE VIEW `eminent-carver-469323-q2.omega_audit.v_ignored_critical_findings` AS
SELECT
  f.finding_id,
  f.file_path,
  f.line_number,
  f.severity,
  f.description,
  f.ts AS warning_timestamp,
  f.status,
  COUNT(a.alert_id) AS production_alerts_triggered,
  MIN(a.ts) AS first_production_failure,
  TIMESTAMP_DIFF(MIN(a.ts), f.ts, DAY) AS days_warning_ignored
FROM `eminent-carver-469323-q2.omega_audit.code_findings` AS f
INNER JOIN `eminent-carver-469323-q2.omega_audit.alerts_sent` AS a
  ON a.hefesto_finding_id = f.finding_id
WHERE f.severity IN ('CRITICAL', 'HIGH')
  AND f.status IN ('ignored', 'open')
  AND f.ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
GROUP BY f.finding_id, f.file_path, f.line_number, f.severity, f.description, f.ts, f.status
ORDER BY production_alerts_triggered DESC, f.severity DESC;

-- ============================================================================
-- VIEW 4: Top Problematic Files
-- ============================================================================

CREATE OR REPLACE VIEW `eminent-carver-469323-q2.omega_audit.v_problematic_files` AS
SELECT
  f.file_path,
  COUNT(DISTINCT f.finding_id) AS hefesto_findings_count,
  COUNTIF(f.severity = 'CRITICAL') AS critical_findings,
  COUNTIF(f.severity = 'HIGH') AS high_findings,
  COUNT(DISTINCT a.alert_id) AS production_alerts_count,
  COUNTIF(f.status = 'ignored') AS ignored_warnings,
  MAX(f.ts) AS last_finding_timestamp,
  MAX(a.ts) AS last_alert_timestamp
FROM `eminent-carver-469323-q2.omega_audit.code_findings` AS f
LEFT JOIN `eminent-carver-469323-q2.omega_audit.alerts_sent` AS a
  ON a.hefesto_finding_id = f.finding_id
WHERE f.ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
GROUP BY f.file_path
HAVING hefesto_findings_count > 0
ORDER BY production_alerts_count DESC, critical_findings DESC, high_findings DESC
LIMIT 50;

-- ============================================================================
-- VALIDATION QUERY: Verify schema deployment
-- ============================================================================

SELECT
  'code_findings' AS table_name,
  COUNT(*) AS row_count,
  MIN(ts) AS earliest_finding,
  MAX(ts) AS latest_finding,
  COUNTIF(severity = 'CRITICAL') AS critical_count,
  COUNTIF(status = 'open') AS open_count
FROM `eminent-carver-469323-q2.omega_audit.code_findings`;

-- Expected: Empty table initially, schema should exist

-- ============================================================================
-- SAMPLE CORRELATION QUERY: How to use in Iris
-- ============================================================================
/*
-- Query used by Iris to find related Hefesto findings
SELECT
  finding_id,
  file_path,
  line_number,
  severity,
  description,
  suggested_fix,
  status,
  ts,
  TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), ts, DAY) AS days_ago
FROM `omega_audit.code_findings`
WHERE file_path = @file_path_from_alert
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
LIMIT 1;
*/

-- ============================================================================
-- SUCCESS MESSAGE
-- ============================================================================

SELECT
  'code_findings schema deployed successfully' AS status,
  '4 analytical views created' AS views,
  'alerts_sent table updated with Hefesto columns' AS enrichment,
  'Ready for Iris-Hefesto integration' AS next_step;

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
