# 2026-10-10 — COBOL Fase 4: rendimiento

## Qué se hizo

1. **Benchmark sintético.** `scripts/cobol_perf_bench.py` genera un proyecto COBOL determinista y mide tiempo y memoria pico de cada escenario en un proceso nuevo: `project-1m` (1 000 programas de ~1 050 líneas + 60 copybooks, 1 053 200 líneas), `big-100k` y `big-500k` (un solo programa de 100 000 y 500 000 líneas) y `cli-1m` (`hefesto analyze --output json` sobre el proyecto). Los copybooks tienen 3 niveles: 20 `LEAF`, 20 `MID` que hacen `COPY LEAFnnn REPLACING ==:TAG:== BY ==MIDnnn==` y 20 `TOP` que copian un `MID`. Cada programa trae SELECT sin FILE STATUS, REDEFINES de COMP-3, OCCURS DEPENDING ON, `COPY TOPnnn`, `COPY LEAFnnn REPLACING`, GO TO, EXEC SQL y un párrafo sin usar. Flags: `--scenario`, `--json`, `--keep`, `--max-seconds-per-mloc`; subcomando `generate`.
2. **Hotspots (cProfile).** `mask_literals` y `_strip_comments` salen enseguida si la línea no tiene comillas o `*`; regex precompiladas; `split_program_units` una sola vez por archivo; los nombres de COPY que ya leyó el índice se reutilizan; `build_procedure` solo prueba las regex de cabecera si la línea tiene un punto; búsqueda de `THRU` empezando por la palabra clave; conjuntos de palabras perezosos; `_detect_fixed_format` filtra por "division" antes de la regex. COBOL014 ya no recorre la sección desde el principio para cada párrafo (prefijos acumulados): era O(n²) en una sección PERFORMada con miles de párrafos (20 000 líneas: 20,6 s en main, 0,08 s ahora).
3. **Memoria.** Se reutilizan las tuplas de líneas lógicas, el índice lee los archivos en streaming, COBOL009 solo mira líneas con comillas y las palabras del PROCEDURE se escanean por bloques. Archivo de 500 000 líneas: 356 → 245 MB.
4. **`copybook_paths` acotado.** La búsqueda recursiva para en 8 niveles y 50 000 archivos (con warning), ignora directorios ocultos y se hace una vez por motor (antes, una vez por ruta escaneada).
5. **COPY anidado.** COBOL007 cuenta los programas que llegan a un copybook a través de otros copybooks (cierre transitivo, seguro ante ciclos). COBOL015 también revisa los COPY de un copybook. `COPY ... REPLACING` se resuelve por nombre; el texto reemplazado no se expande dentro del programa (queda documentado como límite).
6. **Salida acotada.** Los hallazgos siguen agrupados: el archivo de 500 000 líneas da 4 hallazgos y el JSON del proyecto de 1M líneas pesa 3,2 MB.
7. **Test de regresión.** `tests/test_cobol_phase4_performance.py` compara el analizador consigo mismo: un input 4 veces más grande debe tardar menos de 10 veces más (lineal ≈ 4x, cuadrático ≈ 16x), con el mejor de 3 intentos. No depende de la velocidad de la máquina de CI. Verificado contra main: el caso de la sección da 15,1x en main (falla) y ~4x en esta rama. También cubre el límite de `copybook_paths`, la búsqueda única por motor, el cierre de COPY anidado con ciclo y COBOL015 dentro de un copybook.

## Antes / después

Medido con `python scripts/cobol_perf_bench.py` (VM Linux de 8 vCPU, Python 3.13; el análisis usa un solo hilo).

| Escenario | Líneas | main | Fase 4 | s/Mlínea | Memoria pico |
|---|---|---|---|---|---|
| project-1m | 1 053 200 | 18,49 s | 8,01 s | 17,55 → 7,61 | 59,6 → 60,2 MB |
| big-100k | 100 000 | 1,93 s | 0,86 s | 19,34 → 8,63 | 89,2 → 67,4 MB |
| big-500k | 500 000 | 10,50 s | 4,41 s | 20,99 → 8,81 | 355,6 → 245,1 MB |
| cli-1m (JSON) | 1 053 200 | 20,02 s | 9,10 s | 19,01 → 8,64 | 79,2 → 79,1 MB |

Objetivo del plan: menos de 10 s por millón de líneas. Se cumple en los cuatro escenarios en esta máquina; en un runner de CI más lento puede no cumplirse, por eso el test de CI mide escalado y no tiempo absoluto.

Hallazgos del proyecto sintético: 4 040 → 4 060 (COBOL007 40 → 60: los 20 copybooks `LEAF` ahora cuentan los programas que los usan a través de `MID`/`TOP`).

## Corpus

Sin cambios de hallazgos en CardDemo, GenApp, zopeneditor-sample ni NIST (7 307). Las etiquetas no cambian. El baseline se regeneró después de commitear el analizador (`b67242a`): solo cambian `commit`, `analyzer_tree` y los tiempos (CardDemo 0,65 → 0,42 s, GenApp 0,19 → 0,10 s, zopeneditor-sample 0,12 → 0,11 s).

## Pendiente / diferido

- Expandir el texto de `COPY ... REPLACING` dentro del programa (las reglas de procedimiento verían el código de los copybooks). Necesita mapear líneas al copybook de origen; queda para otra fase.
- `_find_files` recorre el árbol una vez por glob soportado (33). En los proyectos medidos tarda unos 40 ms; en árboles con muchos directorios se podría hacer un solo recorrido.
- El índice de COPY no se cachea entre ejecuciones (por ejemplo, por mtime): cada `hefesto analyze` lo reconstruye.
- La memoria de un solo archivo enorme sigue siendo ~0,5 KB por línea (500 000 líneas → 245 MB).

## Verificación

- `python scripts/cobol_perf_bench.py` (tabla de arriba).
- Recall: `python scripts/cobol_recall.py` → 32/34 (sin cambios).
- `python scripts/cobol_corpus_baseline.py compare --workdir ...` → sin cambios de hallazgos.
- Dogfood (`HEFESTO_TELEMETRY_ENV=dogfood`, 49 HIGH en `hefesto/`, igual que main), black, isort, flake8, mypy (solo el error local conocido de `treesitter_parser.py:17`) y pytest (fallos locales conocidos: `test_version_drift` y `test_csharp_parses_with_cold_cache`).
