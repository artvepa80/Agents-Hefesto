# iris_alert_manager.py
# Agente Iris: Gestor de Alertas Inteligentes para el Ecosistema OMEGA

import os
import json
import yaml
import logging
from datetime import datetime
from typing import Optional

# Optional Google Cloud imports
try:
    from google.cloud import bigquery, pubsub_v1
    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    GOOGLE_CLOUD_AVAILABLE = False
    # Mock objects para evitar errores de import
    bigquery = None
    pubsub_v1 = None

# Configuración del logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class IrisAgent:
    """Agente de alertas inteligentes y enrutamiento de notificaciones."""

    def __init__(self, config_path: str, project_id: str, dry_run: bool = False):
        """Inicializa el agente Iris.

        Args:
            config_path: Path al fichero de configuración YAML.
            project_id: ID del proyecto de Google Cloud.
            dry_run: Si es True, no enviará notificaciones reales.
        """
        self.project_id = project_id
        self.dry_run = dry_run
        self.config = self._load_config(config_path)
        
        if not GOOGLE_CLOUD_AVAILABLE:
            logging.warning(
                "Google Cloud libraries not available. "
                "Some features will be disabled. "
                "Install with: pip install google-cloud-bigquery google-cloud-pubsub"
            )
            self.bq_client = None
            self.pubsub_client = None
            return
            
        self.bq_client = bigquery.Client(project=self.project_id)

        # Initialize Pub/Sub client for inter-agent communication
        self.pubsub_client: Optional[pubsub_v1.PublisherClient] = None
        if not self.dry_run:
            self.pubsub_client = pubsub_v1.PublisherClient()
            logging.info("Pub/Sub client initialized for production notifications")

        logging.info(f"Agente Iris inicializado. Dry run: {self.dry_run}")

    def _load_config(self, path: str) -> dict:
        """Carga la configuración de reglas desde un archivo YAML."""
        logging.info(f"Cargando configuración desde: {path}")
        with open(path, 'r') as f:
            return yaml.safe_load(f)

    def run_monitor_cycle(self):
        """Ejecuta un ciclo completo de monitoreo y alerta."""
        logging.info("Iniciando nuevo ciclo de monitoreo...")
        for rule in self.config.get('rules', []):
            try:
                self.evaluate_rule(rule)
            except Exception as e:
                logging.error(f"Error al evaluar la regla '{rule.get('name')}': {e}")
        logging.info("Ciclo de monitoreo completado.")

    def evaluate_rule(self, rule: dict):
        """Evalúa una regla de alerta específica consultando BigQuery."""
        if not GOOGLE_CLOUD_AVAILABLE or self.bq_client is None:
            logging.warning(f"BigQuery not available, skipping rule: {rule.get('name')}")
            return
            
        rule_name = rule.get('name')
        query = rule.get('query')
        threshold = rule.get('threshold')
        severity = rule.get('severity')
        channel = rule.get('channel')

        if not all([rule_name, query, threshold, severity, channel]):
            logging.warning(f"La regla {rule_name or 'sin nombre'} está mal configurada. Saltando...")
            return

        logging.info(f"Evaluando regla: {rule_name}")
        
        # Ejecutar la consulta en BigQuery
        query_job = self.bq_client.query(query)
        results = query_job.result()
        
        for row in results:
            metric_value = row[0] # Asumimos que el valor a evaluar está en la primera columna
            if self._check_threshold(metric_value, threshold):
                logging.warning(f"¡ANOMALÍA DETECTADA! Regla: {rule_name}, Valor: {metric_value}, Umbral: {threshold}")
                self.trigger_alert(rule, row)
            else:
                logging.info(f"Regla '{rule_name}' evaluada. Valor: {metric_value}. Todo OK.")

    def _check_threshold(self, value, threshold_config) -> bool:
        """Comprueba si un valor supera un umbral configurado."""
        op = threshold_config.get('operator', '>')
        limit = threshold_config.get('value')

        if op == '>': return value > limit
        if op == '>=': return value >= limit
        if op == '<': return value < limit
        if op == '<=': return value <= limit
        if op == '==': return value == limit
        if op == '!=': return value != limit

        logging.error(f"Operador de umbral no soportado: {op}")
        return False

    def trigger_alert(self, rule: dict, data_row: bigquery.Row):
        """Construye y envía una alerta a los canales apropiados."""
        context = self.enrich_context(rule, data_row)
        self.route_notification(context)

    def enrich_context(self, rule: dict, data_row: bigquery.Row) -> dict:
        """Enriquece la alerta con información de contexto adicional."""
        logging.info(f"Enriqueciendo contexto para la regla '{rule.get('name')}'...")

        # Base context
        message = rule.get('message_template', 'Alerta genérica').format(**dict(data_row.items()))
        context = {
            'rule_name': rule.get('name'),
            'severity': rule.get('severity'),
            'channel': rule.get('channel'),
            'message': message,
            'details': dict(data_row.items()),
            'timestamp': datetime.utcnow().isoformat()
        }

        # Enrich with Hefesto code findings (if available)
        try:
            from core.hefesto_enricher import get_hefesto_enricher

            enricher = get_hefesto_enricher(
                project_id=self.project_id,
                dry_run=self.dry_run
            )

            hefesto_enrichment = enricher.enrich_alert_context(
                alert_message=message,
                alert_timestamp=datetime.utcnow(),
                metadata=context
            )

            # Add Hefesto context to alert
            context['hefesto_finding_id'] = hefesto_enrichment.get('hefesto_finding_id')
            context['hefesto_context'] = hefesto_enrichment.get('hefesto_context')
            context['hefesto_correlation'] = {
                'attempted': hefesto_enrichment.get('correlation_attempted', False),
                'successful': hefesto_enrichment.get('correlation_successful', False),
                'score': hefesto_enrichment.get('correlation_score')
            }

            if hefesto_enrichment.get('correlation_successful'):
                logging.info(
                    f"✅ Alert enriched with Hefesto finding: "
                    f"{hefesto_enrichment['hefesto_finding_id']}"
                )
            else:
                logging.debug(
                    f"ℹ️ No Hefesto correlation found "
                    f"(reason: {hefesto_enrichment.get('reason', 'unknown')})"
                )

        except Exception as e:
            logging.warning(f"Failed to enrich with Hefesto: {e}")
            # Continue without Hefesto enrichment
            context['hefesto_finding_id'] = None
            context['hefesto_context'] = None

        return context

    def route_notification(self, context: dict):
        """Envía la notificación al agente de comunicación apropiado vía Pub/Sub."""
        channel = context.get('channel')
        logging.info(f"Enrutando notificación para '{context['rule_name']}' vía canal '{channel}'.")

        if self.dry_run:
            logging.warning(f"[DRY RUN] No se enviará la notificación: {context['message']}")
            return

        # Determine target topic based on channel
        topic_name = self._get_topic_for_channel(channel)

        if not topic_name:
            logging.error(f"No se pudo determinar el topic para el canal '{channel}'")
            return

        # Publish message to Pub/Sub
        try:
            topic_path = self.pubsub_client.topic_path(self.project_id, topic_name)
            message_data = json.dumps(context).encode('utf-8')

            # Publish with attributes for routing
            future = self.pubsub_client.publish(
                topic_path,
                message_data,
                channel=channel,
                severity=context.get('severity', 'UNKNOWN'),
                rule_name=context.get('rule_name', 'UNKNOWN')
            )

            message_id = future.result(timeout=10.0)
            logging.info(f"Notificación publicada a '{topic_name}' con message_id: {message_id}")

        except Exception as e:
            logging.error(f"Error publicando a Pub/Sub: {e}")
            # Continue to log even if publish fails

        # Registrar en BigQuery (audit trail)
        self._log_alert_to_bq(context)

    def _get_topic_for_channel(self, channel: str) -> Optional[str]:
        """Determina el topic de Pub/Sub apropiado basado en el canal.

        Mapping de canales a topics:
        - Email_* → hermes_notifications (Hermes agent handles email)
        - Slack_* → apollo_notifications (Apollo can send to Slack)
        - SMS_* → artemis_notifications (Artemis handles SMS/WhatsApp)

        Args:
            channel: Canal de notificación (ej. 'Email_DevOps', 'Slack_OnCall')

        Returns:
            Nombre del topic de Pub/Sub o None si no se reconoce el canal
        """
        if not channel:
            return None

        channel_lower = channel.lower()

        if 'email' in channel_lower:
            return 'iris_notifications_hermes'  # Email via Hermes
        elif 'slack' in channel_lower:
            return 'iris_notifications_apollo'  # Slack via Apollo
        elif 'sms' in channel_lower or 'whatsapp' in channel_lower:
            return 'iris_notifications_artemis'  # SMS/WhatsApp via Artemis
        else:
            # Default to Hermes for unknown channels
            logging.warning(f"Canal desconocido '{channel}', usando Hermes por defecto")
            return 'iris_notifications_hermes'

    def _log_alert_to_bq(self, context: dict):
        """Registra la alerta enviada en la tabla de auditoría de BigQuery."""
        table_id = self.config.get('audit', {}).get('table_id', 'omega_audit.alerts_sent')
        row_to_insert = {
            "alert_id": f"iris-{datetime.utcnow().timestamp()}",
            "ts": context['timestamp'],
            "severity": context['severity'],
            "source": context['rule_name'],
            "message": context['message'],
            "channel": context['channel'],
            "recipients": [], # Placeholder
            "status": "SENT",
            "details": context['details'],
            # Hefesto integration columns
            "hefesto_finding_id": context.get('hefesto_finding_id'),
            "hefesto_context": context.get('hefesto_context')
        }
        
        errors = self.bq_client.insert_rows_json(table_id, [row_to_insert])
        if not errors:
            logging.info(f"Alerta '{context['rule_name']}' registrada en BigQuery.")
        else:
            logging.error(f"Error al registrar alerta en BigQuery: {errors}")

def main():
    """Punto de entrada principal para ejecutar el agente Iris."""
    project_id = os.environ.get('GCP_PROJECT_ID')
    config_path = os.environ.get('IRIS_CONFIG_PATH', 'config/rules.yaml')
    dry_run = os.environ.get('DRY_RUN', 'false').lower() == 'true'

    if not project_id:
        logging.critical("La variable de entorno GCP_PROJECT_ID no está definida.")
        return

    if not os.path.exists(config_path):
        logging.critical(f"El archivo de configuración no se encuentra en: {config_path}")
        return

    agent = IrisAgent(config_path=config_path, project_id=project_id, dry_run=dry_run)
    agent.run_monitor_cycle()

if __name__ == '__main__':
    main()
