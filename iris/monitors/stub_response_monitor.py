"""
Iris Stub Response Monitor
Monitors Cloud Run logs for stub responses in production

Part of OMEGA Agent Optimization - Closes gap in Iris monitoring
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

# Optional Google Cloud imports
try:
    from google.cloud import bigquery
    from google.cloud import logging as cloud_logging

    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    GOOGLE_CLOUD_AVAILABLE = False
    cloud_logging = None
    bigquery = None


logger = logging.getLogger(__name__)


class StubResponseMonitor:
    """Monitors production API responses for stub messages"""

    STUB_PATTERNS = [
        "to be integrated",
        "to be implemented",
        "pending integration",
        "pendiente integración",
        "fixtures query routed to smart_router_helpers",
        "standings query routed",
    ]

    def __init__(self, project_id: str = "eminent-carver-469323-q2"):
        self.project_id = project_id
        self.logging_client = cloud_logging.Client(project=project_id)
        self.bq_client = bigquery.Client(project=project_id)

    def check_stub_responses(self, hours: int = 1) -> List[Dict[str, Any]]:
        """
        Query Cloud Run logs for stub responses in the last N hours

        Args:
            hours: How many hours back to check (default: 1)

        Returns:
            List of log entries containing stub messages
        """
        # Calculate time filter
        time_ago = datetime.utcnow() - timedelta(hours=hours)
        time_filter = time_ago.isoformat() + "Z"

        # Build filter for Cloud Run logs
        filter_str = f"""
        resource.type="cloud_run_revision"
        resource.labels.service_name="omega-sports-commercial"
        timestamp>="{time_filter}"
        (
            jsonPayload.response=~"to be integrated" OR
            jsonPayload.response=~"to be implemented" OR
            jsonPayload.response=~"pending integration" OR
            jsonPayload.response=~"pendiente" OR
            textPayload=~"to be integrated" OR
            textPayload=~"to be implemented"
        )
        """

        logger.info(f"Querying Cloud Run logs (last {hours} hour(s))...")

        stub_entries = []

        try:
            # Query logs
            for entry in self.logging_client.list_entries(filter_=filter_str, page_size=100):
                # Extract relevant information
                stub_entry = {
                    "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                    "severity": entry.severity,
                    "trace": entry.trace,
                    "log_name": entry.log_name,
                }

                # Extract response text
                if hasattr(entry, "json_payload") and entry.json_payload:
                    stub_entry["response"] = entry.json_payload.get("response", "")
                    stub_entry["message"] = entry.json_payload.get("message", "")
                    stub_entry["user_id"] = entry.json_payload.get("user_id", "unknown")
                elif hasattr(entry, "text_payload"):
                    stub_entry["response"] = entry.text_payload

                stub_entries.append(stub_entry)

                # Log warning for each stub found
                logger.warning(f"Stub response detected: {stub_entry['response'][:100]}")

        except Exception as e:
            logger.error(f"Error querying Cloud Run logs: {e}")

        return stub_entries

    def log_stub_alert_to_bigquery(self, stub_entries: List[Dict[str, Any]]):
        """
        Log stub detection alert to BigQuery for audit trail

        Args:
            stub_entries: List of stub log entries found
        """
        if not stub_entries:
            return

        table_id = f"{self.project_id}.omega_audit.stub_detections"

        rows_to_insert = []
        for entry in stub_entries:
            row = {
                "detection_id": f"iris-stub-{datetime.utcnow().timestamp()}",
                "detected_at": datetime.utcnow().isoformat(),
                "log_timestamp": entry.get("timestamp"),
                "severity": "HIGH",
                "stub_response": entry.get("response", "")[:500],  # Limit to 500 chars
                "user_id": entry.get("user_id", "unknown"),
                "trace_id": entry.get("trace"),
                "service_name": "omega-sports-commercial",
                "action_required": "Fix stub code and redeploy",
            }
            rows_to_insert.append(row)

        try:
            errors = self.bq_client.insert_rows_json(table_id, rows_to_insert)
            if not errors:
                logger.info(f"✅ Logged {len(rows_to_insert)} stub detections to BigQuery")
            else:
                logger.error(f"❌ BigQuery insert errors: {errors}")
        except Exception as e:
            logger.error(f"❌ Error logging to BigQuery: {e}")

    def generate_alert_message(self, stub_entries: List[Dict[str, Any]]) -> str:
        """
        Generate human-readable alert message for Hermes

        Args:
            stub_entries: List of stub log entries

        Returns:
            Formatted alert message
        """
        if not stub_entries:
            return "✅ No stub responses detected in production"

        count = len(stub_entries)
        message = f"🚨 STUB RESPONSES DETECTED IN PRODUCTION\n\n"
        message += f"Found {count} stub response(s) in the last hour:\n\n"

        for i, entry in enumerate(stub_entries[:5], 1):  # Show first 5
            timestamp = entry.get("timestamp", "unknown")
            response = entry.get("response", "unknown")[:100]
            user_id = entry.get("user_id", "unknown")

            message += f"{i}. Time: {timestamp}\n"
            message += f"   User: {user_id}\n"
            message += f"   Response: {response}\n\n"

        if count > 5:
            message += f"... and {count - 5} more\n\n"

        message += "ACTION REQUIRED:\n"
        message += "1. Check smart_router.py for stub implementations\n"
        message += "2. Implement real backend logic\n"
        message += "3. Run Hefesto stub_detector before deploying\n"
        message += "4. Redeploy to fix\n"

        return message

    def run_monitoring_cycle(self, hours: int = 1) -> Dict[str, Any]:
        """
        Run complete stub response monitoring cycle

        Args:
            hours: How many hours back to check

        Returns:
            Monitoring result summary
        """
        logger.info("🔍 Starting stub response monitoring cycle...")

        # Check for stubs
        stub_entries = self.check_stub_responses(hours=hours)

        # Log to BigQuery
        self.log_stub_alert_to_bigquery(stub_entries)

        # Generate alert
        alert_message = self.generate_alert_message(stub_entries)

        result = {
            "stub_count": len(stub_entries),
            "alert_message": alert_message,
            "should_alert": len(stub_entries) > 0,
            "checked_hours": hours,
            "checked_at": datetime.utcnow().isoformat(),
        }

        if result["should_alert"]:
            logger.warning(f"⚠️ {len(stub_entries)} stub responses detected!")
        else:
            logger.info("✅ No stub responses found")

        return result


def cli_check_stubs():
    """CLI utility to check for stub responses"""
    monitor = StubResponseMonitor()
    result = monitor.run_monitoring_cycle(hours=1)

    print(result["alert_message"])

    return 1 if result["should_alert"] else 0


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    # Run monitor
    exit_code = cli_check_stubs()
    exit(exit_code)
