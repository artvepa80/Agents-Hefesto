# README: Integración Hefesto & Iris

## Visión General: Un Circuito Cerrado de Calidad y Confiabilidad

Este documento describe la integración entre dos agentes clave del ecosistema OMEGA: **Hefesto** e **Iris**.

*   **Hefesto (Guardián de Código)**: Opera en **pre-producción**. Analiza el código fuente para detectar bugs, vulnerabilidades y deuda técnica *antes* de que llegue a producción. Sus hallazgos se registran en `omega_audit.code_findings`.

*   **Iris (Guardián de Producción)**: Opera en **producción**. Monitorea la ejecución del sistema en tiempo real (logs, métricas) para detectar anomalías operativas. Sus alertas se registran en `omega_audit.alerts_sent`.

Juntos, crean un **circuito de retroalimentación de 360°** que nos permite correlacionar las advertencias de calidad de código con las fallas reales en producción, proporcionando una trazabilidad completa y permitiendo la toma de decisiones basada en datos.

### Diagrama de Flujo Combinado: Hefesto (Pre-Producción) + Iris (Producción)

```mermaid
graph TD
    subgraph PRE-PRODUCCIÓN (Ciclo de Hefesto)
        A[Desarrollador escribe/modifica código] --> B{Hefesto analiza el código};
        B --> C[Hefesto detecta un issue];
        C --> D{¿Se corrige el código?};
        C -- Registra en --> E[`omega_audit.code_findings`];
        D -- Sí --> A;
        D -- No (Advertencia ignorada) --> F[Deploy a Producción];
    end

    subgraph PRODUCCIÓN (Ciclo de Iris)
        F --> G[Código con error se ejecuta];
        G --> H[Sistema genera anomalías<br/>(Logs, Métricas, Errores 500)];
        H --> I{Iris monitorea BigQuery};
        I --> J[Anomalía detectada];
        J -- Registra en --> K[`omega_audit.alerts_sent`];
        J --> L[Iris enriquece la alerta<br/>(Contexto de Argos, link a finding de Hefesto)];
        L --> M[Iris enruta la notificación<br/>(Apollo, Hermes, Artemis)];
        M --> N[Equipo de Operaciones/Desarrollo recibe alerta];
    end

    N --> A;

    style F fill:#f9f,stroke:#333,stroke-width:2px
    style G fill:#ff9999,stroke:#333,stroke-width:2px
```

## Correlación de Datos en BigQuery

La clave de esta integración reside en la capacidad de cruzar datos de las tablas `code_findings` (Hefesto) y `alerts_sent` (Iris). A continuación se muestran ejemplos de consultas para extraer insights valiosos.

### 1. Correlacionar un Finding Específico con Alertas de Producción

Esta consulta nos permite ver si un hallazgo de Hefesto ha "explotado" en producción, generando alertas.

```sql
-- Objetivo: Encontrar todas las alertas de producción relacionadas con un finding de código específico.
SELECT
    f.finding_id,
    f.file_path,
    f.description AS hefesto_finding_description,
    f.severity AS finding_severity,
    a.alert_id,
    a.ts AS alert_timestamp,
    a.message AS production_alert_message,
    a.channel AS notification_channel
FROM
    `omega_audit.code_findings` AS f
LEFT JOIN
    `omega_audit.alerts_sent` AS a
ON
    -- La correlación se hace buscando el path del fichero en el mensaje de la alerta.
    -- Esto asume que los mensajes de alerta de Iris incluyen el path del fichero que falla.
    CONTAINS_SUBSTR(a.message, f.file_path)
WHERE
    f.finding_id = 'HEF-SEC-00123' -- ID del finding de Hefesto que queremos investigar
ORDER BY
    a.ts DESC;
```

### 2. Cuantificar el Impacto de Ignorar Advertencias Críticas

Esta consulta mide cuántas alertas de producción fueron causadas por problemas que Hefesto ya había marcado como `CRITICAL` o `HIGH`. Es una métrica poderosa para demostrar el valor de la calidad del código.

```sql
-- Objetivo: Contar cuántas alertas en producción genera cada finding de alta severidad.
SELECT
    f.finding_id,
    f.file_path,
    f.description,
    f.severity,
    COUNT(a.alert_id) AS production_alert_count
FROM
    `omega_audit.code_findings` AS f
JOIN
    `omega_audit.alerts_sent` AS a ON CONTAINS_SUBSTR(a.message, f.file_path)
WHERE
    f.severity IN ('CRITICAL', 'HIGH')
    AND a.ts > f.ts -- Solo contar alertas posteriores al finding
GROUP BY
    f.finding_id, f.file_path, f.description, f.severity
HAVING
    production_alert_count > 0
ORDER BY
    production_alert_count DESC
LIMIT 50;
```

### 3. Identificar "Ficheros Problemáticos" (Top Offenders)

Esta consulta identifica qué ficheros han sido marcados repetidamente por Hefesto y, además, han generado el mayor número de alertas en producción. Esto ayuda a priorizar dónde enfocar los esfuerzos de refactorización.

```sql
-- Objetivo: Crear un ranking de los ficheros que más problemas causan.
SELECT
    f.file_path,
    COUNT(DISTINCT f.finding_id) AS hefesto_finding_count,
    COUNT(DISTINCT a.alert_id) AS production_alert_count
FROM
    `omega_audit.code_findings` AS f
LEFT JOIN
    `omega_audit.alerts_sent` AS a ON CONTAINS_SUBSTR(a.message, f.file_path)
WHERE
    DATE(f.ts) >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
GROUP BY
    f.file_path
ORDER BY
    production_alert_count DESC, hefesto_finding_count DESC
LIMIT 20;
```

## Beneficios de la Integración

*   **Trazabilidad Completa**: Conectamos una advertencia de calidad de código con su impacto real en la operación.
*   **Priorización Basada en Datos**: Podemos enfocar los recursos de desarrollo en arreglar los problemas que más "duelen" en producción.
*   **Feedback Loop para Desarrolladores**: Demuestra de manera tangible por qué las advertencias de Hefesto son importantes y no deben ser ignoradas.
