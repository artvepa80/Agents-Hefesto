# IRIS Alert Manager - Production Deployment Guide

**Version**: v1.2.0
**Last Updated**: 2025-10-12
**Status**: ✅ **PRODUCTION-READY**

---

## 📋 Overview

IRIS Alert Manager runs as a **Cloud Run Job** that executes on a schedule to evaluate monitoring rules and send alerts via Pub/Sub to HERMES.

---

## ☁️ Cloud Run Deployment

### Job Configuration

**Job Name**: `iris-alert-manager-job`
**Region**: `us-central1`
**Project**: `eminent-carver-469323-q2`
**Image**: `gcr.io/eminent-carver-469323-q2/iris-alert-agent:v1.0.0`

### Resources

- **Memory**: 1Gi
- **CPU**: 2
- **Timeout**: 300s (5 minutes)
- **Max Retries**: 1
- **Parallelism**: 1

### Environment Variables

\`\`\`bash
GCP_PROJECT_ID=eminent-carver-469323-q2
IRIS_CONFIG_PATH=/app/config/rules.yaml
DRY_RUN=false
\`\`\`

### Service Account

**Name**: `iris-agent-sa@eminent-carver-469323-q2.iam.gserviceaccount.com`

**Permissions Required**:
- `roles/bigquery.dataViewer` - Read monitoring data
- `roles/bigquery.jobUser` - Execute BigQuery queries
- `roles/pubsub.publisher` - Publish alerts to Pub/Sub
- `roles/logging.logWriter` - Write execution logs

---

## 📅 Scheduler Configuration

### Cloud Scheduler Job

**Name**: `iris-monitoring-schedule`
**Schedule**: `0 * * * *` (Every hour at :00)
**Timezone**: `Etc/UTC`
**Target**: Cloud Run Job (`iris-alert-manager-job`)

**Previous Schedule** (deprecated):
- ~~`*/15 * * * *`~~ (Every 15 minutes) - Changed to hourly to reduce noise

---

## 🔍 Monitoring Rules

### Current Rules (v1.2.0)

IRIS evaluates **7 production monitoring rules** (plus 1 test rule, currently commented):

#### 1. Code Quality Rules

**[CRITICAL] Nuevos Code Findings Críticos de Hefesto**
- **Query**: `omega_audit.code_findings` (last 4 hours)
- **Threshold**: > 0 critical findings (status=open)
- **Channel**: Email via HERMES
- **Severity**: CRITICAL

**[HIGH] Code Findings CRITICAL Ignorados**
- **Query**: `omega_audit.code_findings` (last 24 hours)
- **Threshold**: > 2 critical findings (status=ignored)
- **Channel**: Email
- **Severity**: HIGH

#### 2. Email System Rules

**[HIGH] Alta Tasa de Fallos en Envío de Emails**
- **Query**: `omega_audit.mails_sent` (last 2 hours)
- **Threshold**: Failure rate > 10%
- **Channel**: Email
- **Severity**: HIGH

**[MEDIUM] Ningún Email Enviado en Última Hora**
- **Query**: `omega_audit.mails_sent` (last 1 hour)
- **Threshold**: < 1 email sent
- **Channel**: Email
- **Severity**: MEDIUM

#### 3. LLM Performance Rules

**[MEDIUM] Alto Rate de Errores en LLM**
- **Query**: `omega_agent.llm_events` (last 2 hours)
- **Threshold**: Error rate > 5%
- **Channel**: Email
- **Severity**: MEDIUM

**[LOW] Latencia Alta en Responses de LLM**
- **Query**: `omega_agent.llm_events` (last 2 hours)
- **Threshold**: Average latency > 10 seconds
- **Channel**: Email
- **Severity**: LOW

#### 4. System Health Rules

**[MEDIUM] Alto Volumen de Errores en Logs**
- **Query**: `omega_audit.log_events` (last 1 hour)
- **Threshold**: > 50 ERROR level events
- **Channel**: Email
- **Severity**: MEDIUM

#### 5. Test Rule (Commented)

**[INFO] Test: Sistema Iris Operacional**
- **Status**: ⚠️ COMMENTED OUT (to reduce email noise)
- **Purpose**: Validates IRIS-HERMES pipeline
- **Threshold**: Always triggers (1 > 0)
- **Usage**: Uncomment in `rules.yaml` for testing

---

## 🚀 Deployment Commands

### Deploy IRIS Job

\`\`\`bash
cd /opt/omega-pro-ai/SPORTS_ANALYTICS_FOUNDATION/Agentes/Iris
bash deploy_cloud_run.sh
\`\`\`

---

**Status**: ✅ **PRODUCTION-READY**
**Version**: v1.2.0
**Last Deploy**: 2025-10-12
