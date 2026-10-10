# 2026-10-09: COBOL, Fase 0 del plan de pruebas (docs honestas, 7 reglas gratis)

- **Contexto:** plan de pruebas COBOL (`/workspace/plan-pruebas-cobol.md`), Fase 0
  aprobada por Arturo: las 7 reglas COBOL quedan **FREE** y la documentación no
  debe prometer más de lo que hace el código.
- **Rama:** `docs/cobol-honesty`, desde `main` @ `9044fb1`. Sin cambio de versión ni tag.
- **PR relacionado (privado):** arreglo de la tool MCP `analyze` y de los textos
  de precios/idiomas en `landing-page/api/`.

## Qué se hizo

| Archivo | Cambio |
|---|---|
| `hefesto/analyzers/devops/cobol_governance_analyzer.py` | Se borra `_is_pro_tier_available()`, que siempre devolvía `True` (TODO del demo para inversionistas). Las 7 reglas se aplican igual que antes: **sin cambio de comportamiento**. El docstring dice "7 reglas FREE", que COBOL004 marca todo `REDEFINES` (COMP-3 no se verifica), que COBOL007 marca todo `COPY` y el requisito de `>>SOURCE FORMAT IS FREE` |
| `tests/test_cobol_governance.py` | Nueva clase `TestAllRulesFree`: las 7 reglas (COBOL001-007) salen sobre los fixtures sin licencia en el entorno, y el gate ya no existe |
| `README.md` | Fila COBOL: "7 free rules", con nota ³ sobre el formato fijo por defecto y free-format con `>>SOURCE FORMAT IS FREE`, REDEFINES, COPY y que **no hay SARIF todavía**. Resumen v4.12.0: "(3 FREE, 4 PRO)" → "7 free rules" |
| `CHANGELOG.md` | Entrada en Unreleased (Changed). La nota de 4.12.0 se corrige y queda marcado que antes decía "3 FREE, 4 PRO" |
| `docs/demo/cobol_investor_demo.sh` | Fuera "3 FREE + 4 PRO" y "zero false positives / low false positive rate". Se aclara que son 11 archivos sintéticos (10 programas + 1 copybook), BATCH-DB2 tiene 95 líneas (no 70), REDEFINES marca todos, y se agregan los límites (free-format, REDEFINES). SARIF figura como "no disponible todavía"; el GitHub Action ya corre estas reglas |

Hallazgos del demo verificados con 4.14.1: 3 CRITICAL en BATCH-DB2, 10 HIGH+ y
13 MEDIUM+ en `tests/fixtures/cobol/`, y 0 en CLEAN-PROG.

## Qué NO se hizo (fases siguientes del plan)
- Detección de free-format sin directiva, extensiones `.cobol`/`.PCO`, menos
  ruido en COBOL002/004/007, reglas nuevas (FILE STATUS, código muerto,
  copybook faltante), SARIF.

## Cómo verificar

```bash
CI=true PYTHONPATH=. HEFESTO_TELEMETRY=0 python -m pytest -q tests/test_cobol_detection.py tests/test_cobol_governance.py
python -m black --check hefesto tests
HEFESTO_TELEMETRY_ENV=dogfood hefesto analyze tests/fixtures/cobol/ --severity MEDIUM   # 13 hallazgos, igual que antes
```
