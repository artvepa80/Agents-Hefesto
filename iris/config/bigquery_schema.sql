-- BigQuery Schema for Iris Alert Manager Audit Table
-- Table: omega_audit.alerts_sent
-- Purpose: Audit trail of all alerts sent by Iris agent

-- Create dataset if not exists
CREATE SCHEMA IF NOT EXISTS omega_audit
OPTIONS (
  location='US',
  description='OMEGA Sports Analytics audit and compliance dataset'
);

-- Create alerts_sent table
CREATE TABLE IF NOT EXISTS `eminent-carver-469323-q2.omega_audit.alerts_sent` (
  -- Alert Identification
  alert_id STRING NOT NULL OPTIONS(description='Unique identifier for alert (iris-{timestamp})'),
  ts TIMESTAMP NOT NULL OPTIONS(description='Timestamp when alert was generated'),

  -- Alert Classification
  severity STRING NOT NULL OPTIONS(description='Alert severity: LOW, MEDIUM, HIGH, CRITICAL'),
  source STRING NOT NULL OPTIONS(description='Rule name that triggered the alert'),
  alert_type STRING OPTIONS(description='Type of alert: OPERATIONAL, SECURITY, PERFORMANCE, SPORTS'),

  -- Alert Content
  message STRING NOT NULL OPTIONS(description='Alert message sent to users'),
  details JSON OPTIONS(description='Additional context and metadata for the alert'),

  -- Routing Information
  channel STRING NOT NULL OPTIONS(description='Notification channel: Email_*, Slack_*, SMS_*'),
  recipients ARRAY<STRING> OPTIONS(description='List of recipient emails/phone numbers'),
  pubsub_topic STRING OPTIONS(description='Pub/Sub topic used for routing (hermes/apollo/artemis)'),
  pubsub_message_id STRING OPTIONS(description='Pub/Sub message ID for tracking'),

  -- Delivery Status
  status STRING NOT NULL OPTIONS(description='Delivery status: SENT, FAILED, PENDING, ACKNOWLEDGED'),
  delivery_attempts INT64 OPTIONS(description='Number of delivery attempts'),
  acknowledged_at TIMESTAMP OPTIONS(description='When alert was acknowledged by recipient'),
  acknowledged_by STRING OPTIONS(description='User who acknowledged the alert'),

  -- Performance Metrics
  latency_ms INT64 OPTIONS(description='Time from detection to notification (milliseconds)'),

  -- Audit Trail
  created_at TIMESTAMP NOT NULL OPTIONS(description='Record creation timestamp'),
  updated_at TIMESTAMP OPTIONS(description='Last update timestamp')
)
PARTITION BY DATE(ts)
CLUSTER BY severity, source, channel
OPTIONS(
  description='Audit trail of all alerts sent by Iris alert manager',
  labels=[("agent", "iris"), ("purpose", "audit"), ("tier", "production")]
);

-- Create view for recent critical alerts
CREATE OR REPLACE VIEW `eminent-carver-469323-q2.omega_audit.v_critical_alerts_24h` AS
SELECT
  alert_id,
  ts,
  severity,
  source,
  message,
  channel,
  status,
  latency_ms
FROM `eminent-carver-469323-q2.omega_audit.alerts_sent`
WHERE
  ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
  AND severity IN ('CRITICAL', 'HIGH')
ORDER BY ts DESC;

-- Create view for alert statistics by severity
CREATE OR REPLACE VIEW `eminent-carver-469323-q2.omega_audit.v_alert_stats_daily` AS
SELECT
  DATE(ts) AS alert_date,
  severity,
  source,
  channel,
  COUNT(*) AS alert_count,
  COUNTIF(status = 'SENT') AS sent_count,
  COUNTIF(status = 'FAILED') AS failed_count,
  AVG(latency_ms) AS avg_latency_ms,
  MAX(latency_ms) AS max_latency_ms
FROM `eminent-carver-469323-q2.omega_audit.alerts_sent`
WHERE ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY alert_date, severity, source, channel
ORDER BY alert_date DESC, alert_count DESC;

-- Create view for unacknowledged critical alerts
CREATE OR REPLACE VIEW `eminent-carver-469323-q2.omega_audit.v_unacknowledged_critical` AS
SELECT
  alert_id,
  ts,
  severity,
  source,
  message,
  channel,
  TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), ts, MINUTE) AS age_minutes
FROM `eminent-carver-469323-q2.omega_audit.alerts_sent`
WHERE
  severity IN ('CRITICAL', 'HIGH')
  AND acknowledged_at IS NULL
  AND status = 'SENT'
  AND ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
ORDER BY ts ASC;

-- Grant permissions to Iris service account (will be created separately)
-- GRANT `roles/bigquery.dataEditor` ON TABLE `eminent-carver-469323-q2.omega_audit.alerts_sent` TO "serviceAccount:iris-agent-sa@eminent-carver-469323-q2.iam.gserviceaccount.com";

-- Success message
SELECT 'BigQuery schema for Iris Alert Manager created successfully' AS status;
