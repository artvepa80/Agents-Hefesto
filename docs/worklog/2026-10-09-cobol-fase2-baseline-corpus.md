# 2026-10-09 — COBOL Fase 2: baseline de corpus

## Qué se hizo

- Nuevo script `scripts/cobol_corpus_baseline.py`:
  - `run`: clona (shallow, por SHA) CardDemo, GenApp y zopeneditor-sample en commits fijos, ejecuta `hefesto analyze --severity low --output json` y guarda `benchmark/cobol/baseline.json` con conteos por regla, severidad y archivo, cada hallazgo como `[regla, ruta relativa, línea]` y tiempos.
  - `compare`: corre de nuevo (o usa `--current` con una corrida guardada) y reporta por corpus y regla los hallazgos nuevos y eliminados. Sale con 1 si hay cambios; el tiempo se muestra pero no falla.
  - La versión de HefestoAI se toma de `pyproject.toml` (la metadata instalada puede estar desactualizada) junto con el commit.
- Solo se commitean los resultados (~40 KB), nunca el código de los corpus.
- Tests offline en `tests/scripts/test_cobol_corpus_baseline.py` (resumen, diff, `main compare`, coherencia del baseline con los pins y un checkout contra un repo git local).
- Documentación: `docs/cobol-corpus-baseline.md`; CHANGELOG (Unreleased → Added).

## Pins

| Corpus | Commit | Licencia |
|---|---|---|
| CardDemo (aws-samples) | 59cc6c2fd7eb | Apache-2.0 |
| GenApp (cicsdev) | f6f3f4b2580d | EPL-2.0 |
| zopeneditor-sample (IBM) | 8f9835308de6 | Apache-2.0 |

## Baseline (HefestoAI 4.14.1, main 39186db)

| Corpus | Archivos | LOC | Hallazgos | COBOL | Por severidad | analyze / pared |
|---|---|---|---|---|---|---|
| CardDemo | 115 | 38 409 | 352 | 341 | HIGH 313, MEDIUM 39 | ~0,6 s / ~1-3 s |
| GenApp | 45 | 8 509 | 53 | 52 | CRITICAL 1, HIGH 51, MEDIUM 1 | ~0,2 s / ~1 s |
| zopeneditor-sample | 20 | 2 217 | 19 | 14 | HIGH 14, MEDIUM 3, LOW 2 | ~0,1 s / ~0,8 s |

Por regla COBOL: CardDemo COBOL001 7, COBOL003 2, COBOL004 44, COBOL005 24, COBOL006 5, COBOL007 257, COBOL011 2; GenApp COBOL001 5, COBOL004 17, COBOL007 29, COBOL008 1; zopeneditor COBOL007 14. El resto son hallazgos de shell/YAML en esos repos.

Una segunda corrida con `compare` dio 0 cambios en los tres corpus.

## Pendiente

- Job de CI (manual o nocturno): no se agregó porque el push desde el box no tiene scope `workflow`. Hay que crearlo desde la UI de GitHub o con un token con ese scope.
- El ruido de COBOL011 queda para la Fase 3.
- El emparejamiento es por (regla, archivo, línea): si una regla cambia de línea reportada aparece como eliminado + nuevo.
