-- Hefesto Findings Storage Schema
-- Users run this in their own GCP project
-- Dataset: hefesto_findings (user configurable)
--
-- Copyright (c) 2025 Narapa LLC, Miami, Florida

-- Table 1: analysis_runs
-- Stores metadata about each analysis execution
CREATE TABLE IF NOT EXISTS `{project_id}.hefesto_findings.analysis_runs` (
  analysis_id STRING NOT NULL,
  timestamp TIMESTAMP NOT NULL,
  path STRING NOT NULL,
  analyzers ARRAY<STRING>,
  total_issues INT64 NOT NULL,
  critical_issues INT64 NOT NULL,
  high_issues INT64 NOT NULL,
  medium_issues INT64 NOT NULL,
  low_issues INT64 NOT NULL,
  execution_time_ms INT64 NOT NULL,
  hefesto_version STRING NOT NULL,
  metadata JSON
)
PARTITION BY DATE(timestamp)
CLUSTER BY analysis_id, path;

-- Table 2: findings
-- Stores individual code quality findings
CREATE TABLE IF NOT EXISTS `{project_id}.hefesto_findings.findings` (
  finding_id STRING NOT NULL,
  analysis_id STRING NOT NULL,
  file_path STRING NOT NULL,
  line_number INT64 NOT NULL,
  column_number INT64,
  severity STRING NOT NULL,
  analyzer STRING NOT NULL,
  issue_type STRING NOT NULL,
  description STRING NOT NULL,
  recommendation STRING,
  code_snippet STRING,
  confidence FLOAT64,
  status STRING DEFAULT 'new',
  status_updated_at TIMESTAMP,
  status_updated_by STRING,
  notes STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP
)
PARTITION BY DATE(created_at)
CLUSTER BY finding_id, analysis_id, file_path, severity;

-- Table 3: finding_history
-- Tracks status changes for audit trail
CREATE TABLE IF NOT EXISTS `{project_id}.hefesto_findings.finding_history` (
  history_id STRING NOT NULL,
  finding_id STRING NOT NULL,
  previous_status STRING,
  new_status STRING NOT NULL,
  changed_by STRING,
  changed_at TIMESTAMP NOT NULL,
  notes STRING
)
PARTITION BY DATE(changed_at)
CLUSTER BY finding_id;

-- Sample queries for validation
-- Find all HIGH severity findings in last 7 days
-- SELECT * FROM `{project_id}.hefesto_findings.findings`
-- WHERE severity = 'HIGH'
--   AND created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
-- ORDER BY created_at DESC
-- LIMIT 100;

-- Get analysis summary statistics
-- SELECT
--   DATE(timestamp) as analysis_date,
--   COUNT(*) as total_analyses,
--   SUM(total_issues) as total_issues,
--   AVG(execution_time_ms) as avg_execution_time
-- FROM `{project_id}.hefesto_findings.analysis_runs`
-- WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
-- GROUP BY analysis_date
-- ORDER BY analysis_date DESC;
