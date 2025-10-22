# README: Integración Iris & Hefesto

**Asunto**: Conectando la Calidad del Código con la Confiabilidad en Producción

---

## 🎯 Visión General

Esta integración representa un bucle de retroalimentación fundamental en el ecosistema OMEGA, conectando los hallazgos de **Hefesto** (el guardián de la calidad del código en pre-producción) con las alertas de **Iris** (el guardián de la confiabilidad en producción).

El objetivo es simple pero poderoso: **correlacionar los problemas teóricos de calidad de código con los fallos operativos reales**, permitiendo un diagnóstico más rápido y una priorización de la deuda técnica basada en datos.

*   **Hefesto sabe** qué partes del código son frágiles o tienen mala calidad.
*   **Iris sabe** qué partes del sistema están fallando en tiempo real.

Juntos, pueden responder a la pregunta: *"¿Qué porcentaje de nuestros incidentes en producción fueron causados por problemas de calidad que ya conocíamos?"*

---

## 🌊 Diagrama de Flujo de la Integración

Este diagrama ilustra cómo Iris enriquece sus alertas utilizando la información previamente generada por Hefesto.

```mermaid
graph TD
    subgraph PRE-PRODUCCIÓN (Hefesto)
        A[Hefesto analiza el código] --> B[Detecta un "code smell" o bug potencial];
        B -- Registra en --> C[`omega_audit.code_findings`];
    end

    subgraph PRODUCCIÓN (Iris)
        D[Código desplegado se ejecuta] --> E[Se produce un error en `main.py:50`];
        E --> F[Iris detecta un pico de errores en los logs];
        F --> G{Paso de Enriquecimiento de Contexto};
        G -- Consulta a --> C;
        C -- Devuelve finding HEF-123 --> G;
        G --> H[Iris construye una alerta enriquecida];
        H --> I[Señal enviada a Hermes];
    end

    I --> J[📧 Notificación al desarrollador];

    style G fill:#87CEEB,stroke:#333,stroke-width:2px
```

---

## ⚙️ Mecanismo de Integración

La integración no requiere una comunicación directa entre los agentes, sino que se realiza de forma asíncrona a través de **BigQuery** como fuente de verdad compartida.

1.  **Hefesto**: Durante sus análisis de código estático, registra cada hallazgo (un bug, una vulnerabilidad, una pieza de código complejo) en la tabla `omega_audit.code_findings`. Cada registro incluye el `file_path`, el `line_number` y una descripción del problema.

2.  **Iris**: Cuando una de sus reglas detecta una anomalía en producción (ej. un error recurrente en los logs), su función `enrich_context` se activa.

3.  **Enriquecimiento**: Dentro de esta función, Iris extrae el `file_path` y `line_number` del log de error y ejecuta una consulta contra la tabla `omega_audit.code_findings` para ver si existe algún hallazgo de calidad de código reportado por Hefesto para esa misma ubicación.

4.  **Alerta Enriquecida**: Si se encuentra una correlación, Iris añade esta información a la alerta antes de enviarla. 

    **Ejemplo de mensaje de alerta enriquecida:**
    > **Asunto**: 🔴 ALERTA: Pico de `NullPointerException` en `predictor.py`
    >
    > **Detalles**: Se han detectado 150 errores en los últimos 10 minutos en `predictor.py`, línea 85.
    >
    > **💡 Contexto de Hefesto**: Este fichero tiene un hallazgo de calidad abierto (HEF-451) por "Alta Complejidad Ciclomática" reportado hace 2 semanas. Es posible que el error esté relacionado.

---

## 💡 Beneficios Clave

*   **Diagnóstico Acelerado**: El desarrollador que recibe la alerta no empieza de cero. Inmediatamente sabe que la causa probable es un problema de calidad de código ya conocido, reduciendo el tiempo de investigación.
*   **Priorización Inteligente de Deuda Técnica**: Permite al equipo de desarrollo priorizar la corrección de aquellos `findings` de Hefesto que están causando problemas reales y medibles en producción.
*   **Demostración de Valor**: Provee evidencia concreta del impacto negativo de la deuda técnica, justificando la inversión de tiempo en refactorización y mejoras de calidad.
*   **Cierre del Bucle DevOps**: Conecta el ciclo de desarrollo (calidad de código) con el de operaciones (confiabilidad), creando un verdadero bucle de mejora continua.

---

## 쿼리 Ejemplo de Consulta de Enriquecimiento (SQL)

Esta es una consulta de ejemplo que la función `enrich_context` de Iris podría ejecutar para encontrar hallazgos de Hefesto relacionados con un error específico.

```sql
-- Parámetros que Iris extraería del log de error:
DECLARE error_file_path STRING DEFAULT 'modules/predictor.py';
DECLARE error_line_number INT64 DEFAULT 85;

-- Consulta para encontrar findings de Hefesto relevantes
SELECT
    finding_id,
    description,
    severity,
    ts AS finding_timestamp
FROM
    `omega_audit.code_findings`
WHERE
    -- El finding corresponde al mismo fichero
    file_path = error_file_path
    -- Y está en un rango de +/- 10 líneas del error, para dar contexto
    AND line_number BETWEEN (error_line_number - 10) AND (error_line_number + 10)
    -- Y el finding sigue abierto
    AND status = 'OPEN'
ORDER BY
    severity DESC, -- Los más severos primero
    ts DESC
LIMIT 5; -- Limitar a los 5 más relevantes
```
