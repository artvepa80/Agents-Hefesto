# 2026-10-09 — COBOL Fase 1: smoke tests y robustez

Plan: `plan-pruebas-cobol.md`, Fase 1 (aprobada por Arturo). Rama
`feat/cobol-phase1-robustness`, worktree desde `origin/main` (b07e144).

## Qué cambió

### Analizador (`hefesto/analyzers/devops/cobol_governance_analyzer.py`)
- **Formato libre sin directiva.** Antes, un archivo en formato libre sin
  `>>SOURCE FORMAT IS FREE` se leía como formato fijo y devolvía 0 hallazgos
  en silencio. Ahora:
  1. Una directiva en las primeras 50 líneas manda (`>>SOURCE FORMAT IS FREE`,
     `>>SOURCE FREE`, minúsculas, `$SET SOURCEFORMAT(FREE)` de Micro Focus;
     y también `FIXED`).
  2. Sin directiva, se infiere formato libre si un encabezado de DIVISION (o,
     en un copybook, una entrada de nivel 01/77) empieza antes de la columna 8.
     En formato fijo el Área A empieza en la columna 8, así que esa línea no
     sería válida. Los tabs se expanden a 8 columnas.
  3. Si no, formato fijo.
  El analizador expone `last_format_reason` (`directive-free`,
  `directive-fixed`, `inferred-free`, `default-fixed`) para pruebas y
  diagnóstico. OCCURS DEPENDING ON ahora también respeta el formato libre
  (antes siempre cortaba las columnas 1-6).
- **Agrupación de hallazgos idénticos** (bajo riesgo, hecho en esta fase):
  COBOL006 reporta una vez por par `PERFORM X THRU Y` y COBOL007 una vez por
  nombre de copybook, por archivo. El primer número de línea se mantiene; el
  mensaje añade "Occurs N times..." solo si N > 1, y `metadata` lleva
  `occurrences` y hasta 50 `lines`. Un archivo sintético con 20.000
  `PERFORM P00001 THRU P00009` pasa de 20.000 hallazgos a 1 (0,14 s).
- **COBOL006 en minúsculas:** el índice de párrafos está en mayúsculas y la
  búsqueda usaba el nombre tal cual, así que `perform a thru b` caía siempre
  en "partial detection". Ahora cuenta los párrafos.
- **Falsos positivos COBOL002:** se ignoran destinos cuyo nombre termina en
  `-FLAG`, `-FLG`, `-SW`, `-SWITCH`, `-IND`, `-INDICATOR`, `-OK`, `-VALID`,
  `-STATUS`, `-STAT`, `-LEN`, `-LENGTH`, `-MSG`, `-MESSAGE`, `-PROMPT`,
  `-LABEL`, `-LIT`, `-ERR`, `-ERROR` (ej. `WS-PASSWORD-OK-FLAG`).
- **Falsos positivos COBOL007:** se ignoran copybooks del proveedor: CICS
  `DFH*` (DFHAID, DFHBMSCA, ...) y DB2 `SQLCA`/`SQLDA`.

### Extensiones
- `hefesto/core/languages/specs.py`: se añaden `*.cobol`, `*.COBOL` y `*.PCO`.
  El descubrimiento de archivos usa `rglob` y distingue mayúsculas, por eso
  `X5.PCO` y `X3.cobol` no se escaneaban. `capabilities.yml` incluye `.cobol`.

### Pruebas (`tests/test_cobol_smoke.py`, fixtures en `tests/fixtures/cobol/smoke/`)
- Detectados: programa malo en formato fijo (5 hallazgos exactos con línea),
  formato libre con y sin directiva, fuente en minúsculas, programa limpio sin
  hallazgos, ACCEPT FROM CONSOLE.
- Formato: fijo con y sin números de secuencia, tabs, directiva FIXED,
  variantes de directiva FREE, copybook libre.
- Extensiones: detección y descubrimiento en directorio de `.cobol`, `.PCO`,
  `.COBOL`.
- Falsos positivos corregidos y un secreto real que sigue marcándose.
- Agrupación: 200 PERFORM THRU idénticos → 1; pares distintos no se agrupan;
  mensaje sin cambios con 1 ocurrencia; COPY repetido.
- 6 `xfail(strict=True)` para la Fase 3: secreto en cláusula VALUE, cadena de
  conexión `PASS=` en campo neutro, `EXEC SQL CONNECT ... USING 'literal'`,
  OPEN sin FILE STATUS, código después de STOP RUN, REDEFINES de PIC X.

### NIST COBOL85
- `scripts/cobol_nist_smoke.py` descarga `newcob.val` del espejo de GnuCOBOL
  (sourceforge; el sitio de NIST responde con un desafío de Cloudflare), lo
  separa en miembros y analiza cada uno. No se versiona el código de NIST.
- Resultado: 510 miembros (459 programas + 51 copybooks, 347.219 líneas),
  **0 excepciones**, ~3 s en total, el más lento NC250A con 59 ms. Los 510 se
  deciden como formato fijo (correcto: NIST usa números de secuencia).
- Hallazgos NIST antes → después: 6.150 → 6.034 (COBOL006 863 → 768,
  COBOL007 417 → 396 por agrupación). COBOL004 da 4.430: ruido que confirma
  la afinación pendiente de la Fase 3.

## Números antes → después (`hefesto analyze --severity low`, solo reglas COBOL)

| Corpus | Archivos COBOL | Antes | Después | Detalle |
|---|---|---|---|---|
| CardDemo | 106 | 421 | 339 | COBOL007 339 → 257 (−42 DFHAID/DFHBMSCA, −40 COPY repetidos de CSSETATY) |
| GenApp | 44 | 51 | 51 | sin cambios |
| zopeneditor-sample | 13 | 20 | 14 | COBOL007 20 → 14 (agrupación) |

Ningún archivo de los tres corpus cambió de formato (todos `default-fixed`).

## Pendiente (no hecho aquí)
- Fase 3: reglas nuevas para los 6 xfail, afinar COBOL004 (solo COMP-3/firmados)
  y revisar `GENERIC_COPYBOOKS`, que compara por subcadena (`ACCOUNT` coincide
  con `ACCOUNTX`).
- Fase 4: rendimiento a escala; la agrupación ya cubre el caso de 20k
  PERFORM THRU.
- No se emite aviso aparte cuando se infiere formato libre; el formato se
  detecta y se expone en `last_format_reason`, pero no llega al reporte.

## Verificación
- `hefesto analyze` (telemetría dogfood) sobre los archivos cambiados.
- black, isort, flake8.
- `pytest tests/test_cobol_smoke.py tests/test_cobol_governance.py
  tests/test_cobol_detection.py` y la suite completa.
