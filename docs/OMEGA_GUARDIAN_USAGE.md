# 🛡️ OMEGA Guardian - Guía de Uso Completa

**OMEGA Guardian** = Hefesto + Iris + ML Enhancement

Esta es la suite completa de herramientas de Narapa LLC para análisis de código, monitoring en producción y enriquecimiento con Machine Learning.

---

## 📋 Tabla de Contenidos

1. [Arquitectura OMEGA Guardian](#arquitectura)
2. [Comandos de Hefesto](#hefesto-comandos)
3. [Comandos de Iris](#iris-comandos)
4. [Workflows Integrados](#workflows-integrados)
5. [Configuración Avanzada](#configuración)

---

## 🏗️ Arquitectura OMEGA Guardian {#arquitectura}

```
┌─────────────────────────────────────────────────────────────┐
│                    OMEGA GUARDIAN                            │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │   HEFESTO    │───▶│  BigQuery    │◀───│     IRIS     │ │
│  │              │    │              │    │              │ │
│  │ Static Code  │    │ omega_audit. │    │  Production  │ │
│  │  Analysis    │    │code_findings │    │  Monitoring  │ │
│  └──────────────┘    └──────────────┘    └──────────────┘ │
│         │                    ▲                    │         │
│         │                    │                    │         │
│         └────────────── ML Enhancement ───────────┘         │
│                     (Professional Tier)                     │
└─────────────────────────────────────────────────────────────┘
```

### Flujo de Trabajo:

1. **Pre-Producción**: Hefesto analiza código → detecta issues → guarda en BigQuery
2. **Producción**: Iris monitorea aplicaciones → detecta errores → consulta BigQuery
3. **Enriquecimiento**: Iris correlaciona errores de producción con findings de Hefesto
4. **Alerta**: Desarrollador recibe alerta enriquecida con contexto completo

---

## 🔨 HEFESTO - Comandos {#hefesto-comandos}

### 1. Información de Licencia

```bash
# Ver estado de tu licencia OMEGA Guardian
hefesto info

# Debería mostrar:
# License: HFST-6F06-4D54-6402-B3B1-CF72
# Tier: Professional (Omega Guardian)
# Status: ACTIVE
# ML Enhancement: ✅ Enabled
```

### 2. Análisis de Código

```bash
# Análisis básico (directorio actual)
hefesto analyze .

# Análisis con severidad específica
hefesto analyze . --severity HIGH

# Análisis con exclusiones
hefesto analyze . --exclude "tests/,docs/,private/"

# Análisis con salida JSON
hefesto analyze . --output json

# Análisis con reporte HTML
hefesto analyze . --output html --save-html report.html

# Análisis de archivo específico
hefesto analyze src/main.py
```

### 3. Validación de Código

```bash
# Validar un archivo específico
hefesto validate src/utils.py

# Validar con límites de licencia
hefesto validate . --check-limits
```

### 4. Activación de Licencia

```bash
# Activar licencia (solo necesario una vez)
hefesto activate HFST-XXXX-XXXX-XXXX-XXXX-XXXX

# Verificar activación
hefesto info
```

### 5. Exportar Findings a BigQuery

```bash
# Si tienes BigQuery configurado (tier Professional)
hefesto analyze . --output json > findings.json

# Luego usar script de carga:
python scripts/load_findings_to_bq.py findings.json
```

---

## 👁️ IRIS - Comandos {#iris-comandos}

### 1. Iniciar Monitoring

```bash
# Iniciar Iris en modo daemon
cd /path/to/Agents-Hefesto-Pro-Private/iris
python -m iris.cli start

# Ver estado de Iris
python -m iris.cli status

# Detener Iris
python -m iris.cli stop
```

### 2. Configurar Monitores

```bash
# Ver configuración actual
python -m iris.cli config show

# Añadir monitor de salud de Athena
python -m iris.cli monitor add \
  --type athena_health \
  --interval 300 \
  --threshold 0.95

# Añadir monitor de respuestas stub
python -m iris.cli monitor add \
  --type stub_response \
  --interval 60 \
  --max_stubs 100
```

### 3. Ver Alertas

```bash
# Ver alertas activas
python -m iris.cli alerts list

# Ver historial de alertas
python -m iris.cli alerts history --days 7

# Detalles de alerta específica
python -m iris.cli alerts show IRIS-2024-001
```

### 4. Testing de Monitores

```bash
# Test de monitor específico
python -m iris.cli test athena_health

# Test de correlación con Hefesto
python -m iris.cli test hefesto_correlation
```

---

## 🔄 Workflows Integrados {#workflows-integrados}

### Workflow 1: Análisis Pre-Deploy

```bash
#!/bin/bash
# Pre-deployment quality check

echo "🔍 Running OMEGA Guardian Pre-Deploy Analysis..."

# 1. Análisis de Hefesto
hefesto analyze . \
  --severity MEDIUM \
  --exclude "tests/,docs/" \
  --output json > pre_deploy_findings.json

# 2. Verificar límites de licencia
hefesto validate . --check-limits

# 3. Si hay CRITICAL issues, bloquear deploy
CRITICAL_COUNT=$(jq '[.findings[] | select(.severity=="CRITICAL")] | length' pre_deploy_findings.json)

if [ "$CRITICAL_COUNT" -gt 0 ]; then
  echo "❌ Deploy bloqueado: $CRITICAL_COUNT issues CRITICAL encontrados"
  exit 1
fi

echo "✅ Pre-deploy check pasado"
```

### Workflow 2: Correlación Post-Incident

```bash
#!/bin/bash
# Correlacionar incidente de producción con findings de Hefesto

FILE_PATH="$1"
LINE_NUMBER="$2"

echo "🔎 Buscando findings de Hefesto para $FILE_PATH:$LINE_NUMBER..."

# Buscar findings locales de último análisis
jq ".findings[] | select(.file_path==\"$FILE_PATH\" and .line_number>=$LINE_NUMBER-10 and .line_number<=$LINE_NUMBER+10)" \
  pre_deploy_findings.json

# O consultar BigQuery directamente si está configurado
bq query --use_legacy_sql=false \
"SELECT finding_id, description, severity, ts
FROM omega_audit.code_findings
WHERE file_path = '$FILE_PATH'
  AND line_number BETWEEN $LINE_NUMBER-10 AND $LINE_NUMBER+10
  AND status = 'OPEN'
ORDER BY severity DESC, ts DESC
LIMIT 5"
```

### Workflow 3: Dashboard Completo

```bash
#!/bin/bash
# Generar dashboard completo de OMEGA Guardian

echo "📊 Generando Dashboard OMEGA Guardian..."

# 1. Estadísticas de Hefesto
echo "=== HEFESTO STATS ==="
hefesto analyze . --output json | jq '{
  total_files: .total_files,
  total_findings: .total_findings,
  by_severity: .summary
}'

# 2. Estado de Iris
echo "=== IRIS STATUS ==="
python -m iris.cli status

# 3. Alertas activas
echo "=== ACTIVE ALERTS ==="
python -m iris.cli alerts list

# 4. Correlación de incidentes
echo "=== INCIDENT CORRELATION ==="
python -m iris.cli stats correlation --days 30
```

---

## ⚙️ Configuración Avanzada {#configuración}

### 1. Configurar BigQuery para OMEGA Guardian

```bash
# 1. Crear proyecto en GCP
gcloud projects create omega-guardian-prod

# 2. Habilitar BigQuery API
gcloud services enable bigquery.googleapis.com

# 3. Crear dataset
bq mk --dataset --location=US omega_audit

# 4. Crear tabla de findings
bq mk --table omega_audit.code_findings \
  finding_id:STRING,file_path:STRING,line_number:INTEGER,\
  description:STRING,severity:STRING,status:STRING,ts:TIMESTAMP

# 5. Configurar credenciales
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

### 2. Auto-load de Licencia

```bash
# Añadir a ~/.zshrc o ~/.bashrc
echo 'source /path/to/Agents-Hefesto-Pro-Private/config/.env.omega' >> ~/.zshrc

# O usar variables de entorno directamente
echo 'export HEFESTO_LICENSE_KEY="HFST-6F06-4D54-6402-B3B1-CF72"' >> ~/.zshrc
echo 'export HEFESTO_TIER="professional"' >> ~/.zshrc
```

### 3. Integración con CI/CD

#### GitHub Actions

```yaml
# .github/workflows/omega-guardian.yml
name: OMEGA Guardian Analysis

on: [push, pull_request]

jobs:
  code-quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Install Hefesto
        run: pip install hefesto-ai

      - name: Activate License
        env:
          HEFESTO_LICENSE_KEY: ${{ secrets.HEFESTO_LICENSE_KEY }}
        run: hefesto activate $HEFESTO_LICENSE_KEY

      - name: Run Analysis
        run: |
          hefesto analyze . \
            --severity MEDIUM \
            --output json > findings.json

      - name: Check Critical Issues
        run: |
          CRITICAL=$(jq '[.findings[] | select(.severity=="CRITICAL")] | length' findings.json)
          if [ "$CRITICAL" -gt 0 ]; then
            echo "❌ $CRITICAL critical issues found"
            exit 1
          fi
```

#### GitLab CI

```yaml
# .gitlab-ci.yml
omega-guardian:
  stage: test
  script:
    - pip install hefesto-ai
    - hefesto activate $HEFESTO_LICENSE_KEY
    - hefesto analyze . --severity MEDIUM --output json > findings.json
    - |
      CRITICAL=$(jq '[.findings[] | select(.severity=="CRITICAL")] | length' findings.json)
      if [ "$CRITICAL" -gt 0 ]; then
        echo "❌ $CRITICAL critical issues found"
        exit 1
      fi
  artifacts:
    paths:
      - findings.json
    expire_in: 1 week
```

---

## 📊 Ejemplos de Output

### Hefesto Analysis Output

```
🔍 Analyzing: src/
📊 Minimum severity: MEDIUM
🚫 Excluding: tests/, docs/

🔨 HEFESTO ANALYSIS PIPELINE
==================================================
License: PROFESSIONAL (Omega Guardian)
ML Enhancement: ✅ Enabled
==================================================

📁 Found 45 Python file(s)

🔍 Step 1/3: Running static analyzers...
   Found 23 potential issue(s)

✅ Step 2/3: Validation layer...
   23 issue(s) validated

🤖 Step 3/3: ML enhancement...
   Enhanced with semantic analysis
   5 false positives filtered
   3 new patterns detected

✅ Analysis complete!
   Duration: 45.2s

📊 Summary:
   Files analyzed: 45
   Issues found: 18
   Critical: 2
   High: 5
   Medium: 11
```

### Iris Alert (Enriched)

```
🔴 ALERT: High error rate detected

📄 Service: athena-api
📍 Location: src/predictor.py:85
⏰ Time: 2025-10-31 17:30:00
📈 Errors: 150 in last 10 minutes

💡 HEFESTO CONTEXT:
─────────────────────────────────────────
Finding: HEF-451
Severity: HIGH
Issue: High Cyclomatic Complexity (score: 15)
Detected: 2 weeks ago
Status: OPEN

Suggestion: Refactor this function to reduce complexity.
Consider extracting helper methods.
─────────────────────────────────────────

🔗 Related Findings:
  • HEF-449: Missing error handling in same file
  • HEF-432: Potential null pointer in predictor.py:92

📊 Impact:
  • 2,500 failed requests
  • $450 estimated cost
  • 15 affected customers
```

---

## 🎯 Casos de Uso Recomendados

### Caso 1: Quality Gate en CI/CD

```bash
# Bloquear merge si hay issues CRITICAL
hefesto analyze . --severity CRITICAL --output json | \
  jq -e '.total_findings == 0' || exit 1
```

### Caso 2: Weekly Quality Report

```bash
# Generar reporte semanal
hefesto analyze . --output html --save-html weekly_report_$(date +%Y%m%d).html
# Enviar por email a equipo
```

### Caso 3: Incident Response

```bash
# Cuando hay incidente en producción
# 1. Ver alerta de Iris
python -m iris.cli alerts show IRIS-2024-123

# 2. Ver correlación con Hefesto
hefesto validate affected_file.py

# 3. Revisar historial de findings
jq ".findings[] | select(.file_path==\"affected_file.py\")" findings.json
```

---

## 🆘 Troubleshooting

### Licencia no reconocida

```bash
# Verificar variables de entorno
echo $HEFESTO_LICENSE_KEY

# Reactivar licencia
hefesto activate HFST-6F06-4D54-6402-B3B1-CF72

# Verificar activación
hefesto info
```

### ML Enhancement no funciona

```bash
# Verificar tier
hefesto info | grep "ML Enhancement"

# Si dice "Disabled", verificar licencia es Professional
# ML solo disponible en tier Professional
```

### Iris no inicia

```bash
# Ver logs de Iris
tail -f /var/log/iris/iris.log

# Verificar configuración BigQuery
python -m iris.cli config validate

# Test de conexión
python -m iris.cli test connection
```

---

## 📚 Recursos Adicionales

- **Documentación completa**: Ver `REPOSITORY_SUMMARY.md` en repo privado
- **Integración Iris-Hefesto**: Ver `iris/README_IRIS_HEFESTO_INTEGRATION.md`
- **Manual de fulfillment**: Ver `docs/MANUAL_FULFILLMENT.md`
- **Security model**: Ver `SECURITY_MODEL.md`

---

## 📞 Soporte

**Internal Team (Narapa LLC):**
- Technical: contact@narapallc.com
- License issues: support@narapallc.com

**For Customers:**
- Support: support@narapallc.com
- Sales: sales@narapallc.com
- Documentation: https://docs.hefesto.ai (coming soon)

---

**© 2025 Narapa LLC - OMEGA Guardian Suite**
**License: HFST-6F06-4D54-6402-B3B1-CF72 (Internal Development)**
