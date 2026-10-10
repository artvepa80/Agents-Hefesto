# 2026-10-10 — COBOL Fase 3: pendientes antes de la Fase 4

## Qué se hizo

1. **Recall con issues sembrados.** Fixture `tests/fixtures/cobol/recall/` (7 programas, 3 copybooks: un `.cpy` copiado por 6 programas, un copybook sin extensión copiado por 5 y un DCLGEN `.dcl` traído con `EXEC SQL INCLUDE`) con 34 issues sembrados en `seeds.json`, al menos 2 por regla (COBOL008 ×4, COBOL002/COBOL009 ×3). `scripts/cobol_recall.py` imprime el recall por regla (`--json`, `--min-recall`); `scripts/cobol_recall_fixture.py` regenera el fixture. Un seed cuenta como encontrado si hay un hallazgo de la misma regla en el mismo archivo a ±2 líneas. Dos seeds están marcados `known_limit` (límites documentados); el test falla si alguno empieza a detectarse, para actualizar la documentación.
2. **COBOL004, idiom de byte view de CardDemo.** Un binario sin signo (`PIC 9(n)` BINARY/COMP/COMP-4/COMP-5) redefinido como bytes `PIC X` de exactamente su tamaño de almacenamiento (n≤4 → 2, ≤9 → 4, ≤18 → 8 bytes) ya no se reporta, en cualquiera de los dos sentidos. Un binario con signo, un tamaño distinto o un byte que no sea `PIC X` se siguen reportando (cubierto por tests y por el seed de RCL02). Al revisarlo apareció otro bug: las palabras de USAGE se detectaban dentro de nombres de datos (`REDEFINES TWO-BYTES-BINARY` volvía "binario" al grupo; `INDEXED BY STATIC-INDEX` se leía como `USAGE INDEX`). Ahora se exige que no estén pegadas a un guion o a otra letra.
3. **`EXEC SQL INCLUDE` y copybooks sin extensión.** El índice de COPY lee los INCLUDE dentro de `EXEC SQL ... END-EXEC` (también en varias líneas; ignora comentarios y literales). Los archivos `.dcl`, `.copy`, `.cbk` o sin extensión se indexan solo si algún programa escaneado los copia o incluye y su contenido tiene definiciones COBOL (niveles o `EXEC SQL DECLARE`); así los scripts sin extensión de CardDemo (`scripts/markers/`) no cuentan. Esos copybooks también se analizan (COBOL004/008/009/007). En formato fijo el nombre del COPY termina en la columna 72 (en NIST, `COPY KP001` seguido de `SM2064.2` en 73-80 se leía como `KP001SM2064`).
4. **`copybook_paths`.** Clave nueva en `.hefesto.yaml` (rutas relativas al archivo de configuración; error si no es un directorio) y flag `--copybook-path DIR` (repetible). Los nombres encontrados ahí resuelven COPY/INCLUDE para COBOL015; esos archivos no se analizan. Documentado en el README (sección COBOL, CLI y configuración).
5. **Aviso de formato libre inferido.** El reporte de texto muestra una sección **Notes** con los archivos leídos como formato libre por inferencia (máximo 10 y "... and N more"). En JSON va en `meta.cobol_format_notices` y por archivo en `metadata.cobol_source_format = "inferred-free"`.
6. **`hefesto.commit` del baseline.** `scripts/cobol_corpus_baseline.py` guarda `commit` (HEAD), `analyzer_tree` (hash del árbol `hefesto/`, que sobrevive al squash merge) y `dirty` (cambios sin commit en `hefesto/` o `pyproject.toml`, con aviso por stderr). Un test exige `dirty: false` en el baseline commiteado. El baseline se regeneró después de commitear el código (`8d58c55`).

Además: la continuación de un literal en formato fijo (indicador `-`) se une sin la comilla de apertura y sin incluir el propio guion; así un connection string partido en dos líneas se evalúa entero (COBOL009).

## Recall por regla (34 seeds)

| Regla | main (Fase 3) | Pendientes |
|---|---|---|
| COBOL001 | 2/2 | 2/2 |
| COBOL002 | 2/3 | 2/3 |
| COBOL003 | 2/2 | 2/2 |
| COBOL004 | 2/2 | 2/2 |
| COBOL005 | 2/2 | 2/2 |
| COBOL006 | 2/2 | 2/2 |
| COBOL007 | 1/2 | 2/2 |
| COBOL008 | 3/4 | 3/4 |
| COBOL009 | 1/3 | 3/3 |
| COBOL010 | 2/2 | 2/2 |
| COBOL011 | 2/2 | 2/2 |
| COBOL012 | 2/2 | 2/2 |
| COBOL013 | 2/2 | 2/2 |
| COBOL014 | 2/2 | 2/2 |
| COBOL015 | 1/2 | 2/2 |
| **Total** | **28/34 (82 %)** | **32/34 (94 %)** |

Fallos que quedan (límites conocidos): COBOL008 con un valor que contiene una palabra de credencial (`'secretAdmin2024'`, se omite a propósito para no marcar placeholders) y COBOL002 cuando el literal llega al campo de contraseña a través de otro campo (necesita data flow). Los seeds los escribimos nosotros con las definiciones de las reglas a la vista: mide que cada regla hace lo que dice, no el recall sobre código real desconocido.

## Deltas del baseline

| Corpus | Archivos | Hallazgos COBOL | Cambio |
|---|---|---|---|
| CardDemo | 115 → 118 | 56 → 48 | COBOL004 24 → 16 (los 8 byte views); 3 `.dcl` indexados y analizados, sin hallazgos |
| GenApp | 45 | 13 | sin cambios |
| zopeneditor-sample | 20 | 4 | sin cambios |
| NIST (fuera del baseline) | - | 7 308 → 7 307 | COBOL004 DB105A:337 eliminado |

Tiempo de análisis: CardDemo 0,59 s → 0,65 s, GenApp 0,16 s → 0,19 s (descubrimiento de copybooks extra y detección de formato en el índice). Queda para la Fase 4 (rendimiento).

## Precisión

| Regla | Después de Fase 3 | Pendientes |
|---|---|---|
| COBOL004 | 35/44 (80 %) | 35/35 (100 %) |
| resto | sin cambios | sin cambios |

Corrección: el hallazgo NIST DB105A:337 estaba etiquetado TP ("signed numeric") pero era FP (`INDEXED BY STATIC-INDEX` leído como `USAGE INDEX`; las dos vistas son `PIC X(25)`). La precisión "después" de COBOL004 publicada en la Fase 3 baja de 36/44 (82 %) a 35/44 (80 %); está corregida en `docs/cobol-corpus-baseline.md` y en el CHANGELOG. Las etiquetas tienen un tercer conjunto, `leftovers`; el test exige que las etiquetas `leftovers` de los corpus fijados coincidan exactamente con los hallazgos COBOL del baseline, y que la precisión no baje entre ejecuciones.

## Verificación

- Recall: `python scripts/cobol_recall.py` → 32/34.
- Precisión: `python scripts/cobol_label_precision.py`.
- `cobol_corpus_baseline.py compare` contra el baseline anterior: solo los −8 COBOL004 de CardDemo; tras regenerarlo, 0 cambios.
- Dogfood (`HEFESTO_TELEMETRY_ENV=dogfood`), black, isort, flake8, mypy (solo el error local conocido de `treesitter_parser.py:17`) y pytest (fallos locales conocidos: `test_version_drift` y `test_csharp_parses_with_cold_cache`).

## Pendiente / diferido

- COBOL008 con palabra de credencial dentro del valor y COBOL002 por data flow (límites documentados).
- `copybook_paths` recorre los directorios de forma recursiva y sin límite de tamaño total; con directorios enormes conviene acotarlo (Fase 4, rendimiento).
- El ligero aumento de tiempo por el índice (Fase 4).
