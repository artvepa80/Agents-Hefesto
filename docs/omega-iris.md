# OMEGA Guardian and IRIS

Moved from the README.

## OMEGA Guardian

Production monitoring that correlates code issues with production failures.

### Features

- **IRIS Agent**: Real-time production monitoring
- **Auto-Correlation**: Links code changes to incidents
- **Real-Time Alerts**: Pub/Sub notifications
- **BigQuery Analytics**: Track correlations over time

### Setup

```yaml
# iris_config.yaml
project_id: your-gcp-project
dataset: omega_production
pubsub_topic: hefesto-alerts

alert_rules:
  - name: error_rate_spike
    threshold: 10
  - name: latency_increase
    threshold: 1000
```

```bash
# Run IRIS Agent
python -m hefesto.omega.iris_agent --config iris_config.yaml

# Check status
hefesto omega status
```

---

## IRIS Telemetry Contract (OMEGA)

IRIS labels deployments as GREEN/YELLOW/RED using post-deploy telemetry. The input format is an open contract — any observability stack can produce it:

| Resource | Path | Description |
|----------|------|-------------|
| **Aggregates Contract v1** | [`docs/telemetry/AGGREGATES_CONTRACT.md`](telemetry/AGGREGATES_CONTRACT.md) | Row schema, units, validation checklist |
| **JSONL Validator** | [`scripts/validate_aggregates_jsonl.py`](../scripts/validate_aggregates_jsonl.py) | Stdlib-only validator (no deps) |

```bash
# Validate your telemetry file
python scripts/validate_aggregates_jsonl.py aggregates.jsonl

# Feed to IRIS (OMEGA tier)
export IRIS_TELEMETRY_SOURCE=file
export IRIS_TELEMETRY_FILE=aggregates.jsonl
iris label-outcomes --repo org/repo --commit abc123 --env production --window both --json
```

Enterprise collectors (Prometheus, Datadog, CloudWatch) and integration runbooks are available in the PRO distribution.
