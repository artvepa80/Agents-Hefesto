"""
Iris Athena Health Monitor
Monitors Athena agent health and triggers alerts when issues detected

Part of OMEGA Apollo-Athena Integration - Phase 2: Iris Monitoring
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

# Optional Google Cloud imports
try:
    from google.cloud import bigquery

    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    GOOGLE_CLOUD_AVAILABLE = False
    bigquery = None

logger = logging.getLogger(__name__)


class AthenaHealthMonitor:
    """Monitors Athena agent health status via REST API"""

    def __init__(
        self,
        project_id: str = "eminent-carver-469323-q2",
        athena_api_base: str = "http://localhost:8080",  # Default to local, override for production
    ):
        """
        Initialize Athena health monitor

        Args:
            project_id: GCP project ID
            athena_api_base: Base URL for Athena API endpoints
        """
        self.project_id = project_id
        self.athena_api_base = athena_api_base
        self.bq_client = bigquery.Client(project=project_id)

        # Health check endpoints
        self.endpoints = {
            "health": f"{athena_api_base}/api/athena/health",
            "features": f"{athena_api_base}/api/athena/features/health",
        }

        logger.info(f"🏛️ Athena Health Monitor initialized")
        logger.info(f"   API Base: {athena_api_base}")

    def check_athena_health(self) -> Dict[str, Any]:
        """
        Query Athena health endpoint

        Returns:
            Health status dictionary with:
            - status: "healthy" | "degraded" | "error" | "unreachable"
            - agent_state: Current Athena state
            - response_time_ms: API response time
            - error: Error message if failed
        """
        start_time = datetime.utcnow()

        try:
            # Call Athena health endpoint
            response = requests.get(self.endpoints["health"], timeout=5)  # 5 second timeout

            response_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            if response.status_code == 200:
                data = response.json()

                # Extract key health metrics
                agent_info = data.get("agent_info", {})
                performance = data.get("performance", {})
                health = data.get("health", {})

                agent_state = agent_info.get("state", "unknown")
                avg_response_time = performance.get("avg_response_time_ms", 0)
                memory_within_limits = health.get("memory_within_limits", True)

                # Determine overall status
                if agent_state in ["HEALTHY", "MONITORING"]:
                    if memory_within_limits and avg_response_time < 100:
                        status = "healthy"
                    else:
                        status = "degraded"
                elif agent_state == "ERROR":
                    status = "error"
                else:
                    status = "degraded"

                return {
                    "status": status,
                    "agent_state": agent_state,
                    "response_time_ms": response_time_ms,
                    "avg_validation_time_ms": avg_response_time,
                    "memory_within_limits": memory_within_limits,
                    "uptime_hours": agent_info.get("uptime_hours", 0),
                    "decision_count": performance.get("decision_count", 0),
                    "error": None,
                    "raw_data": data,
                }

            else:
                return {
                    "status": "error",
                    "agent_state": "ERROR",
                    "response_time_ms": response_time_ms,
                    "error": f"HTTP {response.status_code}: {response.text[:100]}",
                    "raw_data": None,
                }

        except requests.exceptions.Timeout:
            return {
                "status": "unreachable",
                "agent_state": "UNREACHABLE",
                "response_time_ms": 5000,  # Timeout
                "error": "Athena health endpoint timed out (>5s)",
                "raw_data": None,
            }

        except requests.exceptions.ConnectionError:
            return {
                "status": "unreachable",
                "agent_state": "UNREACHABLE",
                "response_time_ms": 0,
                "error": "Cannot connect to Athena API (service down?)",
                "raw_data": None,
            }

        except Exception as e:
            return {
                "status": "error",
                "agent_state": "ERROR",
                "response_time_ms": 0,
                "error": f"Unexpected error: {str(e)}",
                "raw_data": None,
            }

    def check_feature_health(self) -> Dict[str, Any]:
        """
        Query Athena feature store health endpoint

        Returns:
            Feature health status dictionary
        """
        try:
            response = requests.get(self.endpoints["features"], timeout=5)

            if response.status_code == 200:
                data = response.json()
                freshness_pct = data.get("feature_freshness_pct", 0)
                status = data.get("health_status", "unknown")

                return {
                    "status": status,
                    "feature_freshness_pct": freshness_pct,
                    "is_healthy": freshness_pct > 0.8,  # >80% fresh
                    "error": None,
                }
            else:
                return {
                    "status": "error",
                    "feature_freshness_pct": 0,
                    "is_healthy": False,
                    "error": f"HTTP {response.status_code}",
                }

        except Exception as e:
            return {
                "status": "error",
                "feature_freshness_pct": 0,
                "is_healthy": False,
                "error": str(e),
            }

    def log_health_check_to_bigquery(self, health_data: Dict[str, Any]):
        """
        Log Athena health check result to BigQuery for audit trail

        Args:
            health_data: Health check result dictionary
        """
        table_id = f"{self.project_id}.omega_audit.athena_health_checks"

        row = {
            "check_id": f"iris-athena-{int(datetime.utcnow().timestamp())}",
            "checked_at": datetime.utcnow().isoformat(),
            "status": health_data.get("status"),
            "agent_state": health_data.get("agent_state"),
            "response_time_ms": health_data.get("response_time_ms"),
            "error_message": health_data.get("error"),
            "uptime_hours": health_data.get("uptime_hours", 0),
            "decision_count": health_data.get("decision_count", 0),
            "memory_within_limits": health_data.get("memory_within_limits", True),
        }

        try:
            errors = self.bq_client.insert_rows_json(table_id, [row])
            if not errors:
                logger.debug(f"✅ Logged health check to BigQuery: {health_data['status']}")
            else:
                logger.error(f"❌ BigQuery insert errors: {errors}")
        except Exception as e:
            # Table might not exist yet - log but don't fail
            logger.warning(f"⚠️ Could not log to BigQuery (table may not exist): {e}")

    def generate_alert_message(
        self, health_data: Dict[str, Any], feature_data: Dict[str, Any]
    ) -> Optional[str]:
        """
        Generate human-readable alert message for Hermes

        Args:
            health_data: Athena health check result
            feature_data: Feature store health result

        Returns:
            Alert message string if alert needed, None otherwise
        """
        status = health_data.get("status")

        # No alert if healthy
        if status == "healthy" and feature_data.get("is_healthy", False):
            return None

        # Generate alert based on issue type
        message = "🚨 ATHENA AGENT HEALTH ALERT\n\n"

        if status == "unreachable":
            message += "⚠️ CRITICAL: Athena agent is unreachable\n\n"
            message += f"Error: {health_data.get('error')}\n"
            message += "Impact: Apollo training validation is running in FAIL-OPEN mode\n"
            message += "       (Training jobs will proceed without Athena checks)\n\n"
            message += "ACTION REQUIRED:\n"
            message += "1. Check if Cloud Run service is running\n"
            message += "2. Check Athena agent logs for crashes\n"
            message += (
                "3. Restart service if needed: gcloud run services update omega-sports-commercial\n"
            )

        elif status == "error":
            message += "⚠️ HIGH: Athena agent is in ERROR state\n\n"
            message += f"Agent State: {health_data.get('agent_state')}\n"
            message += f"Error: {health_data.get('error')}\n"
            message += f"Response Time: {health_data.get('response_time_ms', 0):.1f}ms\n\n"
            message += "ACTION REQUIRED:\n"
            message += "1. Check Athena agent logs for errors\n"
            message += "2. Verify BigQuery connectivity\n"
            message += "3. Check memory usage (<2GB limit)\n"
            message += "4. Restart agent if needed\n"

        elif status == "degraded":
            message += "⚠️ MEDIUM: Athena agent performance degraded\n\n"
            message += f"Agent State: {health_data.get('agent_state')}\n"
            message += f"Avg Response Time: {health_data.get('avg_validation_time_ms', 0):.1f}ms (target: <100ms)\n"
            message += f"Memory Within Limits: {health_data.get('memory_within_limits', True)}\n\n"
            message += "ACTION REQUIRED:\n"
            message += "1. Monitor performance metrics\n"
            message += "2. Check for memory leaks\n"
            message += "3. Consider scaling if load is high\n"

        # Add feature health issues
        if not feature_data.get("is_healthy", False):
            freshness = feature_data.get("feature_freshness_pct", 0)
            message += f"\n⚠️ Feature Store Issue:\n"
            message += f"   Feature Freshness: {freshness:.1%} (target: >80%)\n"
            message += f"   Risk: Athena may block training jobs unnecessarily\n\n"

        message += f"\n📊 Monitoring Dashboard:\n"
        message += f"   Health Endpoint: {self.endpoints['health']}\n"
        message += f"   Features Endpoint: {self.endpoints['features']}\n"
        message += f"   Checked At: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"

        return message

    def run_monitoring_cycle(self) -> Dict[str, Any]:
        """
        Run complete Athena health monitoring cycle

        Returns:
            Monitoring result summary with alert status
        """
        logger.info("🏛️ Starting Athena health monitoring cycle...")

        # Check Athena health
        health_data = self.check_athena_health()

        # Check feature store health
        feature_data = self.check_feature_health()

        # Log to BigQuery
        self.log_health_check_to_bigquery(health_data)

        # Generate alert if needed
        alert_message = self.generate_alert_message(health_data, feature_data)

        result = {
            "athena_status": health_data.get("status"),
            "agent_state": health_data.get("agent_state"),
            "response_time_ms": health_data.get("response_time_ms", 0),
            "feature_freshness_pct": feature_data.get("feature_freshness_pct", 0),
            "should_alert": alert_message is not None,
            "alert_message": alert_message,
            "alert_severity": self._determine_severity(health_data),
            "checked_at": datetime.utcnow().isoformat(),
        }

        if result["should_alert"]:
            logger.warning(f"⚠️ Athena health issue detected: {result['athena_status']}")
        else:
            logger.info(f"✅ Athena is healthy: {result['athena_status']}")

        return result

    def _determine_severity(self, health_data: Dict[str, Any]) -> str:
        """Determine alert severity based on health status"""
        status = health_data.get("status")

        if status == "unreachable":
            return "CRITICAL"
        elif status == "error":
            return "HIGH"
        elif status == "degraded":
            return "MEDIUM"
        else:
            return "LOW"


def cli_check_athena_health():
    """CLI utility to check Athena health"""
    # For production, use actual Cloud Run URL
    api_base = "https://omega.narapa.app"  # Production

    monitor = AthenaHealthMonitor(athena_api_base=api_base)
    result = monitor.run_monitoring_cycle()

    print(f"\n{'='*80}")
    print("ATHENA HEALTH CHECK")
    print(f"{'='*80}\n")
    print(f"Status: {result['athena_status']}")
    print(f"Agent State: {result['agent_state']}")
    print(f"Response Time: {result['response_time_ms']:.1f}ms")
    print(f"Feature Freshness: {result['feature_freshness_pct']:.1%}")

    if result["should_alert"]:
        print(f"\n⚠️ ALERT SEVERITY: {result['alert_severity']}\n")
        print(result["alert_message"])
        return 1
    else:
        print("\n✅ Athena is healthy - No alerts")
        return 0


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    # Run monitor
    exit_code = cli_check_athena_health()
    exit(exit_code)
