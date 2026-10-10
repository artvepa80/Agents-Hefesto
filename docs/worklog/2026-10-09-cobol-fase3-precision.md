# 2026-10-09 — COBOL Fase 3: ajuste de precisión

## Qué se hizo

- **Índice de COPY del proyecto** (`hefesto/analyzers/devops/cobol_project_index.py`): por cada `analyze_path` (o sobre todas las rutas del CLI con `engine.prepare_cobol_index`) se indexan los copybooks disponibles (`.cpy`) y qué programas copian cada uno. Los nombres de COPY ignoran comentarios y literales.
- **COBOL007** ya no se reporta en cada COPY de cada programa: se reporta una vez, en la línea 1 del copybook, cuando 5 o más programas escaneados lo copian (MEDIUM; HIGH con 15+ o con nombre genérico). Los nombres genéricos (COMMON, UTILS, UTIL, SHARED, CUSTOMER, ACCOUNT) se comparan por token completo, no por subcadena. Se omiten DFH*, CMQ* (IBM MQ), SQLCA y SQLDA.
- **COBOL015 COPYBOOK_NOT_FOUND (nueva, LOW)**: COPY cuyo copybook no está en el árbol escaneado, agrupado por nombre. Solo se activa si algún COPY del escaneo resuelve (un archivo suelto no genera ruido).
- **COBOL004** pasó a `cobol_program_rules` y corre también en copybooks: solo marca un REDEFINES cuando un lado tiene datos packed/binarios/float/pointer/numéricos con signo y los layouts difieren. Se omiten los mapas BMS (`xxxO REDEFINES xxxI`) y los REDEFINES cuyo original no está en el archivo. El xfail de `PIC X` ahora pasa.
- **COBOL005** se evalúa por entrada de datos: línea correcta, sin duplicados ni cruces entre entradas, sin GO TO DEPENDING ni RECORD VARYING, y omite el idiom CICS `DEPENDING ON EIBCALEN`.
- **COBOL011** queda en LOW y agrupado: un hallazgo por programa en el primer SELECT, con `metadata.files`, `lines` y `occurrences`.
- **Etiquetado**: 440 hallazgos etiquetados (TP/FP con motivo) en `tests/fixtures/cobol/labels/phase3_labels.json`; `scripts/cobol_label_precision.py` calcula la precisión por regla y valida el formato. Tests en `tests/scripts/test_cobol_label_precision.py` (incluye que cada etiqueta "after" exista en el baseline).
- Baseline regenerado (`benchmark/cobol/baseline.json`), README, docstrings, demo y `docs/cobol-corpus-baseline.md` actualizados.
- YAML del job de CI listo para pegar desde la UI de GitHub: `docs/cobol-corpus-baseline-ci.md`.

## Hallazgos COBOL por corpus (antes → después)

| Corpus | Antes | Después | Cambios principales |
|---|---|---|---|
| CardDemo | 341 | 56 | COBOL007 257 → 15, COBOL004 44 → 24 (−35 / +15), COBOL005 24 → 2, COBOL011 2 → 1 |
| GenApp | 52 | 13 | COBOL007 29 → 2, COBOL004 17 → 0, COBOL015 +5 (SSMAP) |
| zopeneditor-sample | 14 | 4 | COBOL007 14 → 4 |
| NIST COBOL85 (fuera del baseline) | 12 385 | 7 308 | COBOL004 4 430 → 78, COBOL007 396 → 0, COBOL011 747 → 432, COBOL005 26 → 12 |

COBOL007 pasa de 257 de 313 hallazgos HIGH+ en CardDemo (82 %) a 4 de 40 (10 %), por debajo de la meta del 20 %.

`compare` contra el baseline anterior mostró exactamente esos deltas; tras regenerarlo, `compare` da 0 cambios. El tiempo de análisis no cambió (CardDemo ~0,6 s).

## Precisión por regla (muestra etiquetada)

| Regla | Antes | Después |
|---|---|---|
| COBOL001 | 22/22 | 22/22 |
| COBOL003 | 12/12 | 12/12 |
| COBOL004 | 1/81 (1 %) | 36/44 (82 %) |
| COBOL005 | 12/50 (24 %) | 14/14 |
| COBOL006 | 15/15 | 15/15 |
| COBOL007 | 80/123 (65 %) | 21/21 |
| COBOL008 | 1/1 | 1/1 |
| COBOL011 | 22/22 | 21/21 |
| COBOL015 | — | 5/5 |

Notas:

- Las etiquetas aplican criterios por regla (guardados en el fixture) con un script auxiliar; cada categoría se revisó a mano por muestreo. No es una revisión humana línea por línea.
- El criterio de COBOL007 es la propia definición (5+ programas), así que el 100 % confirma el conteo, no que cada copybook compartido sea un riesgo.
- Los 8 FP restantes de COBOL004 son el idiom de CardDemo que parte un file status binario de 2 bytes en dos `PIC X`.
- COBOL004 ganó 15 TP que el matcher anterior (una sola línea) no veía: `PIC X(12)` sobre `PIC S9(10)V99` en COACTUPC y CVEXPORT.cpy.

## CodeQL

- El primer push dio 1 alerta alta `py/path-injection` en `prepare_cobol_index` (nuevo índice multi-ruta). La fuente es `request.paths` del servidor API (`hefesto/server.py`), que ya pasaba por `resolve_under_root`, pero CodeQL no reconoce `Path.resolve()` + `relative_to()` como sanitizador (por eso había alertas descartadas en `server.py` y `path_sandbox.py`).
- Arreglo: `resolve_under_root` usa `os.path.realpath` + verificación de prefijo (patrón que CodeQL sí reconoce), y además rechaza hermanos con el mismo prefijo (`/work/app-evil`) y symlinks que salen de la raíz. Tests nuevos en `tests/test_path_sandbox.py`.
- CodeQL 2.27.2 local (suite `python-code-scanning`): 0 alertas.

## Verificación

- black, isort, flake8 y mypy (solo el error conocido de `treesitter_parser.py:17`, que pasa en CI).
- Tests: suite completa en verde salvo los 2 fallos conocidos de entorno local (`test_version_drift`, `test_csharp_parses_with_cold_cache`).
- Dogfood: `HEFESTO_TELEMETRY_ENV=dogfood hefesto analyze` sobre los archivos tocados.

## Pendiente / diferido

- Idiom TWO-BYTES (file status binario) sigue como FP de COBOL004.
- Recall con ~30 inyecciones conocidas (plan, sección 5) no se midió en esta fase.
- `EXEC SQL INCLUDE` y copybooks sin extensión no se indexan todavía.
- COBOL007 solo se reporta si el copybook está dentro del escaneo; en zopeneditor los dos árboles (COBOL/ y multiroot/) cuentan juntos.
- COBOL001/006/014 sin cambios en esta fase; rendimiento en Fase 4.
- Job de CI del baseline: lo agrega Arturo desde la UI con el YAML de `docs/cobol-corpus-baseline-ci.md`.
