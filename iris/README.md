# 👁️ Agente Iris - Gestor de Alertas Inteligentes

**Rol Principal**: Guardián de la Confiabilidad y el Rendimiento en Producción
**Estado**: v1.0 (Diseño Especializado)

---

## 🎯 Resumen Ejecutivo

**Iris** es el agente de **alertas inteligentes y enrutamiento de notificaciones** del ecosistema OMEGA. Su misión es ser el guardián de la **confiabilidad y el rendimiento** del sistema en producción.

Monitorea la ejecución en tiempo real (logs, métricas, estado de los jobs) para detectar anomalías operativas, degradación del rendimiento o fallos funcionales. Su objetivo es alertar de forma proactiva para minimizar el impacto y el tiempo de resolución de incidentes (MTTR).

---

## 🔺 El Rol de Iris en el Triángulo de Defensa

Con la especialización de los agentes, Iris ocupa un rol vital y claramente definido dentro del sistema de guardianes de OMEGA:

*   **Hefesto (Calidad de Código)**: Actúa en **pre-producción**, asegurando que el código sea de alta calidad antes de ser desplegado.
*   **Argos (Seguridad y Cumplimiento)**: Actúa en **todas las fases**, asegurando que la plataforma cumpla con los estándares de seguridad y las normativas legales.
*   **Iris (Confiabilidad en Producción)**: Actúa en **producción**, asegurando que el sistema funcione de manera correcta, eficiente y sin interrupciones.

---

## ⚙️ Funciones Principales

1.  **Monitoreo de Salud Operativa**:
    *   **Análisis de Logs de Ejecución**: Absorbiendo el rol original de Argos, Iris es ahora el principal consumidor de logs operativos para detectar errores de aplicación (`Exceptions`, `Tracebacks`), problemas de conexión (`TimeoutError`), errores de servidor (HTTP 5xx), etc.
    *   **Métricas de Rendimiento**: Vigila métricas clave como la latencia de las APIs, el uso de CPU/memoria de los servicios y el rendimiento de las consultas a la base de datos.
    *   **Estado de los Procesos**: Monitorea el estado de los jobs (ej. `jobs_runs` en BigQuery) y las colas de mensajes (ej. backlog en Pub/Sub).

2.  **Reglas de Alerta Inteligentes**:
    *   Utiliza umbrales (thresholds) que pueden ser dinámicos para adaptarse al contexto operativo.
    *   **Ejemplos**: `tasa de errores 5xx > 1% durante 5 min`, `latencia p95 de la API de predicción > 500ms`, `backlog de Pub/Sub > 10,000 mensajes`.

3.  **Enrutamiento y Escalada Multi-Canal**:
    *   Decide el canal más efectivo (Email, Slack, SMS) y los destinatarios correctos (equipo de guardia, desarrolladores, etc.) para cada alerta.
    *   Implementa una lógica de escalada si una alerta no es confirmada (`acknowledged`) en un tiempo definido.

4.  **Contexto Enriquecido para Incidentes**:
    *   Construye un "mini informe de incidencia" para cada alerta, incluyendo logs relevantes, métricas de rendimiento y enlaces a dashboards para acelerar el diagnóstico.

---

## 🌊 Flujo de Trabajo e Integraciones

```mermaid
graph TD
    subgraph Fuentes de Datos Operativas
        A[Logs de Aplicación (Errores, Warnings)]
        B[Métricas de Rendimiento (Latencia, CPU)]
        C[Estado de Jobs y Colas]
    end

    subgraph Agente Iris
        D{1. Monitoreo Continuo};
        E{2. Detección de Anomalías Operativas};
        F{3. Enriquecimiento de Contexto};
        G{4. Enrutamiento y Escalada};
    end

    subgraph Canales de Notificación
        H[Apollo (Slack/Chat)];
        I[Hermes (Email)];
        J[Artemis (SMS/WhatsApp)];
    end

    A --> D;
    B --> D;
    C --> D;
    D --> E;
    E -- Anomalía Detectada --> F;
    F --> G;
    G --> H & I & J;
    G -- Registra Alerta --> K[`omega_audit.alerts_sent`];

    style E fill:#FFC300,stroke:#333,stroke-width:2px
```

### Interacción con Otros Agentes:

*   **Consume de**: Las salidas de logs de todos los agentes y aplicaciones.
*   **Envía a**: **Hermes**, **Apollo**, **Artemis** para la entrega de notificaciones.
*   **Colabora con Argos**: Si Iris detecta una anomalía operativa (ej. un pico de errores de autenticación), puede consultar a **Argos** para determinar si el patrón corresponde a un evento de seguridad (ej. un ataque de fuerza bruta), enriqueciendo así la alerta.
*   **Activa a Apollo**: Si Iris detecta una degradación sostenida en el rendimiento de un modelo de ML, puede enviar una señal a **Apollo** para que este evalúe la necesidad de un reentrenamiento.
*   **Correlaciona con Hefesto**: Enriquecimiento automático de alertas con findings de código pre-detectados por Hefesto.

---

## 🔍 Integración Iris-Hefesto: Correlación Automática (v1.1)

**Estado**: ✅ Implementado (2025-10-12)

### Resumen

Iris ahora **correlaciona automáticamente** las alertas de producción con los findings de código detectados previamente por **Hefesto**, proporcionando trazabilidad 360° desde las advertencias de código hasta las fallas en producción.

### Valor de Negocio

- **Demuestra ROI de Calidad de Código**: Prueba cuantitativamente que ignorar advertencias de Hefesto resulta en incidentes de producción
- **Prioriza Correcciones**: Identifica qué issues de código realmente causan problemas operativos
- **Acelera RCA (Root Cause Analysis)**: Los emails de alerta incluyen el contexto del código problemático automáticamente
- **Feedback Loop**: Los desarrolladores ven el impacto tangible de ignorar warnings

### Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                   PRE-PRODUCCIÓN (Hefesto)                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    Código analizado
                              ↓
              Finding detectado (ej: SQL injection)
                              ↓
         Log a omega_audit.code_findings (BigQuery)
              ├─ finding_id: HEF-SEC-A1B2C3
              ├─ file_path: api/endpoints.py
              ├─ severity: CRITICAL
              └─ status: ignored ← Developer ignoró warning

┌─────────────────────────────────────────────────────────────────┐
│                      PRODUCCIÓN (Iris)                           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
            Anomalía detectada (500 errors spike)
                              ↓
                 Iris genera alerta
                              ↓
        Enriquecimiento automático con Hefesto
              ├─ Extrae file_path del mensaje
              ├─ Query: omega_audit.code_findings
              ├─ Filtra: severity IN (CRITICAL, HIGH)
              ├─ Lookback: 90 días antes de alerta
              └─ Score: severity × status × recency
                              ↓
         Correlación encontrada: HEF-SEC-A1B2C3
                              ↓
            Alert enriquecida con contexto
              ├─ hefesto_finding_id
              └─ hefesto_context (JSON completo)
                              ↓
         Almacena en omega_audit.alerts_sent
                              ↓
              Pub/Sub → Hermes → Email
                              ↓
        📧 Email muestra warning PREDICHO por Hefesto
```

### Componentes Implementados

#### 1. BigQuery Schema (`config/code_findings_schema.sql`)

**Tabla Principal**: `omega_audit.code_findings`
- Particionada por `DATE(ts)` (90 días retención)
- Clustering: `severity, issue_type, file_path`
- 18 columnas incluyendo: finding_id, file_path, severity, description, suggested_fix, status

**Modificación**: `omega_audit.alerts_sent`
- Nuevas columnas:
  - `hefesto_finding_id STRING`
  - `hefesto_context JSON`

**Vistas Analíticas**:
- `v_code_findings_recent` - Últimos 90 días
- `v_findings_to_alerts` - Correlación findings → alertas
- `v_ignored_critical_findings` - Warnings ignorados que causaron incidentes
- `v_problematic_files` - Top archivos con más findings + alertas

#### 2. Hefesto Logger (`Agentes/Hefesto/llm/code_findings_logger.py`)

**Propósito**: Log de code findings a BigQuery para correlación futura.

```python
from llm.code_findings_logger import get_code_findings_logger

logger = get_code_findings_logger(project_id='eminent-carver-469323-q2')

finding_id = logger.log_finding(
    file_path='api/endpoints.py',
    line_number=145,
    issue_type='security',
    severity='CRITICAL',
    description='SQL injection vulnerability',
    suggested_fix='Use parameterized queries',
    llm_event_id='abc-123'  # Link to llm_events
)
```

**Características**:
- Genera finding_id único: `HEF-{TYPE}-{HASH}`
- Máscara secrets en code snippets (usa `security.masking`)
- Singleton pattern para eficiencia
- Dry-run mode para testing

**Integración**: Llamado automáticamente en `Hefesto/api/health.py` endpoint `/suggest/refactor` (línea 367-398)

#### 3. Iris Enricher (`core/hefesto_enricher.py`)

**Propósito**: Correlaciona alertas de producción con findings de Hefesto.

```python
from core.hefesto_enricher import get_hefesto_enricher

enricher = get_hefesto_enricher(project_id='eminent-carver-469323-q2')

enrichment = enricher.enrich_alert_context(
    alert_message="API error rate 8.5% in api/endpoints.py",
    alert_timestamp=datetime.utcnow()
)

# Returns:
# {
#   "hefesto_finding_id": "HEF-SEC-A1B2C3",
#   "hefesto_context": {
#     "finding_id": "HEF-SEC-A1B2C3",
#     "file_path": "api/endpoints.py",
#     "severity": "CRITICAL",
#     "status": "ignored",
#     "detected_days_ago": 3,
#     ...
#   },
#   "correlation_successful": true
# }
```

**Algoritmo de Correlación**:
1. Extrae file paths del mensaje de alerta (regex patterns)
2. Query BigQuery: `code_findings` con filtros:
   - `file_path IN (extracted_paths)`
   - `severity IN ('CRITICAL', 'HIGH')`
   - `status IN ('open', 'ignored')`
   - `ts BETWEEN alert_time - 90 days AND alert_time`
3. Score findings: `severity × status_multiplier × recency_factor`
4. Retorna finding con score más alto

**Integración**: Llamado automáticamente en `core/iris_alert_manager.py` método `enrich_context()` (línea 116-156)

#### 4. Hermes Email Templates (`Agentes/Hermes/core/hermes_agent.py`)

**Modificación**: `_generate_iris_alert_html()` (línea 465-531)

Los emails de Iris ahora incluyen una **sección visual destacada** si existe correlación con Hefesto:

```html
🔍 HEFESTO Code Warning (Predicted This Alert!)

⚠️ IGNORED WARNING - Detected 3 days before this production alert

Finding ID: HEF-SEC-A1B2C3
File: api/endpoints.py
Line: 145
Severity: CRITICAL
Issue Type: security
Description: SQL injection vulnerability

💡 Suggested Fix: Use parameterized queries instead of string concatenation

Impact Analysis: This production alert was PREDICTED by Hefesto 3 days ago.
This warning was IGNORED during development.
```

**Colores visuales**:
- Status `ignored`: Rojo (#dc3545) - Máxima alerta
- Status `open`: Naranja (#fd7e14) - Alta prioridad
- Otros: Amarillo (#ffc107)

### Uso en Producción

**Flujo automático** (sin intervención manual):

1. Developer usa Hefesto API: `POST /suggest/refactor`
2. Hefesto detecta issue → Log a `code_findings`
3. Developer deploya código (ignorando warning)
4. Iris detecta anomalía en producción
5. Iris consulta `code_findings` automáticamente
6. Iris enriquece alerta con contexto de Hefesto
7. Hermes envía email con warning predicho por Hefesto

**Queries útiles**:

```sql
-- Alertas que fueron predichas por Hefesto
SELECT
    alert_id,
    severity,
    message,
    hefesto_finding_id,
    JSON_EXTRACT_SCALAR(hefesto_context, '$.detected_days_ago') AS days_warning_ignored
FROM `omega_audit.alerts_sent`
WHERE hefesto_finding_id IS NOT NULL
ORDER BY ts DESC;

-- Top archivos problemáticos
SELECT * FROM `omega_audit.v_problematic_files` LIMIT 10;

-- Warnings críticos ignorados que causaron alertas
SELECT * FROM `omega_audit.v_ignored_critical_findings`;
```

### Métricas de Éxito

**Targets (Q1 2025)**:
- ✅ Tasa de correlación: >10% de alertas correlacionadas con findings
- ✅ Precisión: >80% de correlaciones son relevantes
- ✅ Latencia: <100ms query performance (clustering optimization)
- ✅ Reducción warnings ignorados: -50% en 90 días

**Monitoreo**:
```sql
-- Correlation success rate
SELECT
    COUNT(*) AS total_alerts,
    COUNTIF(hefesto_finding_id IS NOT NULL) AS correlated_alerts,
    SAFE_DIVIDE(
        COUNTIF(hefesto_finding_id IS NOT NULL),
        COUNT(*)
    ) AS correlation_rate
FROM `omega_audit.alerts_sent`
WHERE ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY);
```

### Archivos Modificados

**Nuevos**:
- `Agentes/Iris/config/code_findings_schema.sql` - BigQuery schema
- `Agentes/Hefesto/llm/code_findings_logger.py` - Logging module
- `Agentes/Iris/core/hefesto_enricher.py` - Correlation engine

**Modificados**:
- `Agentes/Hefesto/api/health.py` - Línea 367-398 (logger integration)
- `Agentes/Iris/core/iris_alert_manager.py` - Línea 101-157 (enrichment), 242-244 (BigQuery logging)
- `Agentes/Hermes/core/hermes_agent.py` - Línea 465-531 (email template)

### Siguiente Fase

**v1.2 (Planificado)**:
- Machine Learning para predecir qué findings causarán alertas
- Auto-priorización de fixes basada en historical impact
- Dashboard Looker Studio con métricas de correlación
- Integración con JIRA para crear tickets automáticos

---