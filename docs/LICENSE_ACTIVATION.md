# 🔑 HEFESTO Professional - Guía de Activación de Licencia

**Para clientes de OMEGA Guardian / Hefesto Professional**

Después de comprar tu licencia, puedes activarla de **2 formas diferentes**. Elige la que prefieras:

---

## 📋 Opción 1: Comando Interactivo (Recomendado ⭐)

**Más fácil - Para todos los usuarios**

### Paso 1: Ejecutar el comando de activación

```bash
hefesto activate
```

### Paso 2: Introducir tu información

El sistema te preguntará:

```
🔑 HEFESTO Professional - License Activation
═══════════════════════════════════════════════

Enter your license key: HFST-XXXX-XXXX-XXXX-XXXX-XXXX
Enter your email: tu@email.com

✅ License activated successfully!
✅ Tier: Professional (Omega Guardian)
✅ ML Enhancement: Enabled

License saved to: ~/.hefesto/license

You're all set! Run 'hefesto info' to verify.
```

### Paso 3: Verificar activación

```bash
hefesto info
```

Deberías ver:

```
🔨 HEFESTO v4.0.0

📜 License:
   Tier: PROFESSIONAL
   ML Enhancement: ✅ Enabled
   Pro Features: ✅ Enabled
```

### ¿Dónde se guarda?

Tu licencia se guarda en:
- **macOS/Linux:** `~/.hefesto/license`
- **Windows:** `C:\Users\TuUsuario\.hefesto\license`

Este archivo es seguro y solo tú puedes leerlo.

---

## ⚙️ Opción 2: Variables de Entorno (Para Usuarios Avanzados)

**Más flexible - Para configuraciones personalizadas**

### Método A: Temporal (Solo para esta sesión)

```bash
export HEFESTO_LICENSE_KEY="HFST-XXXX-XXXX-XXXX-XXXX-XXXX"
export HEFESTO_TIER="professional"

# Verificar
hefesto info
```

### Método B: Permanente (Recomendado para uso diario)

#### En macOS/Linux (bash):

Añade al final de `~/.bashrc`:

```bash
# HEFESTO Professional License
export HEFESTO_LICENSE_KEY="HFST-XXXX-XXXX-XXXX-XXXX-XXXX"
export HEFESTO_TIER="professional"
export ML_SEMANTIC_ANALYSIS=true
export BIGQUERY_ANALYTICS=true
```

Luego ejecuta:

```bash
source ~/.bashrc
hefesto info
```

#### En macOS/Linux (zsh):

Añade al final de `~/.zshrc`:

```bash
# HEFESTO Professional License
export HEFESTO_LICENSE_KEY="HFST-XXXX-XXXX-XXXX-XXXX-XXXX"
export HEFESTO_TIER="professional"
export ML_SEMANTIC_ANALYSIS=true
export BIGQUERY_ANALYTICS=true
```

Luego ejecuta:

```bash
source ~/.zshrc
hefesto info
```

#### En Windows (PowerShell):

```powershell
# Agregar permanentemente
[System.Environment]::SetEnvironmentVariable("HEFESTO_LICENSE_KEY", "HFST-XXXX-XXXX-XXXX-XXXX-XXXX", "User")
[System.Environment]::SetEnvironmentVariable("HEFESTO_TIER", "professional", "User")

# Verificar
hefesto info
```

#### En Windows (CMD):

```cmd
setx HEFESTO_LICENSE_KEY "HFST-XXXX-XXXX-XXXX-XXXX-XXXX"
setx HEFESTO_TIER "professional"
```

---

## 🔄 Orden de Prioridad

Hefesto busca tu licencia en este orden:

1. **Variables de entorno** (`HEFESTO_LICENSE_KEY`)
2. **Archivo de configuración** (`~/.hefesto/license`)
3. **Archivo .env.omega** (solo para desarrollo)

Puedes usar cualquiera de los métodos, Hefesto los detecta automáticamente.

---

## 🧪 Verificar que la Licencia Funciona

### Test 1: Información básica

```bash
hefesto info
```

Debe mostrar:
- ✅ Tier: PROFESSIONAL
- ✅ ML Enhancement: Enabled
- ✅ Pro Features: Enabled

### Test 2: Análisis con ML

```bash
hefesto analyze . --severity MEDIUM
```

Debe mostrar en el pipeline:
```
🔨 HEFESTO ANALYSIS PIPELINE
==================================================
License: PROFESSIONAL
ML Enhancement: ✅ Enabled
==================================================
```

### Test 3: Validación de licencia

```bash
hefesto validate --check-limits
```

---

## ❓ Problemas Comunes

### "License: FREE" aparece en el análisis

**Causa:** La licencia no se está cargando

**Solución:**

```bash
# Opción 1: Re-activar con comando
hefesto activate HFST-XXXX-XXXX-XXXX-XXXX-XXXX

# Opción 2: Verificar variables de entorno
echo $HEFESTO_LICENSE_KEY
# Si está vacío, añádelo a tu .bashrc o .zshrc

# Opción 3: Verificar archivo de licencia
cat ~/.hefesto/license
# Si no existe, usa 'hefesto activate'
```

### "ML Enhancement: ❌ Disabled"

**Causa:** Tier no se reconoce como Professional

**Solución:**

```bash
# Asegúrate de que ambas variables estén configuradas
export HEFESTO_LICENSE_KEY="HFST-XXXX-XXXX-XXXX-XXXX-XXXX"
export HEFESTO_TIER="professional"

# O re-activa con el comando
hefesto activate HFST-XXXX-XXXX-XXXX-XXXX-XXXX
```

### La licencia desaparece después de reiniciar

**Causa:** Variables de entorno no persistentes

**Solución:**

Añade las variables a tu shell profile:

```bash
# Para bash
echo 'export HEFESTO_LICENSE_KEY="TU-KEY"' >> ~/.bashrc
echo 'export HEFESTO_TIER="professional"' >> ~/.bashrc

# Para zsh (macOS default)
echo 'export HEFESTO_LICENSE_KEY="TU-KEY"' >> ~/.zshrc
echo 'export HEFESTO_TIER="professional"' >> ~/.zshrc

# Recargar
source ~/.bashrc  # o ~/.zshrc
```

---

## 🔐 Seguridad

### ¿Es seguro guardar la licencia en un archivo?

✅ Sí, el archivo `~/.hefesto/license` tiene permisos restrictivos (600) - solo tú puedes leerlo.

### ¿Puedo compartir mi licencia?

❌ No, las licencias son individuales/por equipo y están vinculadas a tu email.

### ¿Qué pasa si pierdo mi licencia?

📧 Contáctanos en support@narapallc.com con tu email de compra y te la reenviamos.

---

## 🚀 Configuración para CI/CD

### GitHub Actions

```yaml
name: Code Analysis

on: [push, pull_request]

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Install Hefesto
        run: pip install hefesto-ai

      - name: Activate License
        env:
          HEFESTO_LICENSE_KEY: ${{ secrets.HEFESTO_LICENSE_KEY }}
          HEFESTO_TIER: professional
        run: hefesto analyze . --severity MEDIUM
```

**Importante:** Añade `HEFESTO_LICENSE_KEY` en:
- Settings → Secrets → Actions → New repository secret

### GitLab CI

```yaml
hefesto-analysis:
  stage: test
  script:
    - pip install hefesto-ai
    - export HEFESTO_LICENSE_KEY=$HEFESTO_LICENSE_KEY
    - export HEFESTO_TIER=professional
    - hefesto analyze . --severity MEDIUM
  variables:
    HEFESTO_LICENSE_KEY: $HEFESTO_LICENSE_KEY
```

**Importante:** Añade `HEFESTO_LICENSE_KEY` en:
- Settings → CI/CD → Variables

---

## 📊 Features Disponibles con Professional

Una vez activada tu licencia Professional, tendrás acceso a:

### ML Enhancement
- ✅ Semantic code analysis
- ✅ Duplicate detection con embeddings
- ✅ Context-aware suggestions
- ✅ False positive filtering

### Advanced Analytics
- ✅ BigQuery integration
- ✅ Historical trend analysis
- ✅ Team dashboards
- ✅ Custom metrics

### OMEGA Guardian (Si aplicable)
- ✅ Iris production monitoring
- ✅ Code-to-incident correlation
- ✅ ML-powered root cause analysis
- ✅ Automated alerting

### Enterprise Features
- ✅ API access
- ✅ Batch processing
- ✅ Custom rules
- ✅ Priority support

---

## 📞 Soporte

¿Problemas activando tu licencia?

**Email:** support@narapallc.com
**Subject:** License Activation Issue
**Incluye:**
- Tu license key
- Email de compra
- Output de `hefesto info`
- Sistema operativo

**Tiempo de respuesta:**
- Clientes Professional: < 24 horas
- Founding Members: < 4 horas

---

## 🎉 ¡Listo!

Una vez activada tu licencia, puedes empezar a usar todas las features Professional:

```bash
# Análisis completo con ML
hefesto analyze . --severity MEDIUM

# Generar reporte HTML
hefesto analyze . --output html --save-html report.html

# Integrar con BigQuery
hefesto analyze . --output json > findings.json
python -m hefesto.bigquery.loader findings.json

# Usar OMEGA Guardian (si aplicable)
iris start
```

---

**© 2025 Narapa LLC**
**OMEGA Guardian Suite**

¿Preguntas? → contact@narapallc.com
