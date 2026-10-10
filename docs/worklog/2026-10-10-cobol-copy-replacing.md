# 2026-10-10 — COBOL: expansión de COPY ... REPLACING

## Objetivo

Analizar cada programa con el texto de sus copybooks expandido (como lo ve el
compilador), aplicando `REPLACING`, para que las reglas que dependen de
definiciones de datos (COBOL004/005/008, FILE STATUS COBOL011/012, código
muerto COBOL013/014) vean el contenido de los copybooks en el contexto del
programa, con la línea correcta del programa y del copybook.

## Qué se hizo

- Nuevo módulo `hefesto/analyzers/devops/cobol_copy_expansion.py`:
  - Tokenizador de palabras de texto COBOL (palabras, literales, `==`,
    separadores; coma/punto y coma + espacio cuentan como espacio; `:` y
    paréntesis son palabras de texto aparte).
  - `parse_replacing`: `==pseudo-texto==` (también vacío), literales,
    palabras, identificadores (`A OF B`, `T(1)`), `LEADING`/`TRAILING`.
  - `apply_replacing`: comparación por palabras de texto (palabras sin
    distinguir mayúsculas, literales exactos), gana el primer par, el texto
    reemplazado no se vuelve a examinar, una coincidencia puede abarcar
    varias líneas (se conservan los saltos de línea para la atribución).
    Funcionan los modismos `==:TAG:==` (zopeneditor-sample) y
    `==(TESTVAR1)==` (CardDemo `CSSETATY`).
  - `CopyExpander`: sustituye `COPY ... .` y `EXEC SQL INCLUDE ... END-EXEC`
    (texto antes y después de la sentencia en la misma línea, sentencias en
    varias líneas). COPY anidado: el `REPLACING` exterior se aplica también
    al texto de los copybooks anidados (regla de IBM). Guardas: recursión
    (un copybook activo en la cadena no se expande otra vez), 16 niveles,
    250.000 líneas de copybook por programa; un COPY no expandido queda
    como está escrito.
  - Cada línea expandida guarda su origen (archivo, línea física, cadena de
    COPY). Las líneas propias del programa conservan su número (entero), así
    que un programa sin COPY no paga nada extra.
- `CobolProjectIndex`: archivos por nombre (`files_by_name`), `resolve()`
  elige el copybook más cercano al programa (copybook antes que programa,
  directorio común más largo), caché de líneas lógicas de copybooks
  (límite 64 M caracteres). `copybook_paths`: `library_copybook_files()`
  devuelve nombre → archivo, así esos copybooks también se expanden.
- Analizador: los programas se analizan expandidos; los copybooks se
  analizan tal como están. Atribución: un hallazgo en texto de copybook se
  reporta en la línea del COPY del programa, con
  `metadata.expanded_from` (copybook, archivo, línea, líneas COPY,
  `replaced`). Las líneas en mensajes y `metadata.lines` también se
  traducen. COBOL004/008/009 sobre una línea no modificada de un copybook
  escaneado no se repiten en cada programa (ya se reportan en el copybook);
  sí se reportan si `REPLACING` cambió la línea o si el copybook viene de
  `copybook_paths`.
- COBOL004: se omite un REDEFINES sobre un mapa simbólico de entrada BMS
  (todo campo binario es un `xxxL` con su `xxxI` en el mismo grupo).

## Corpus y precisión

- Expansión en los corpus: CardDemo 40 de 44 programas, 291 COPY (40 con
  REPLACING); GenApp 26 de 31, 35 COPY (5 copybooks no están en el repo);
  zopeneditor-sample 5 de 5, 22 COPY (11 con REPLACING).
- Hallazgos: ningún cambio (regla, archivo, línea) en CardDemo, GenApp,
  zopeneditor-sample ni NIST (7.307). Revisados:
  - CardDemo `COTRTLIC.cbl:434` COBOL004 aparecía al expandir el mapa BMS
    `COTRTLI` (`01 FILLER REDEFINES CTRTLIAI`, superposición de las 7 filas
    de la pantalla): sigue el layout generado, no es el riesgo de la regla →
    nueva exclusión de mapa de entrada BMS.
  - CardDemo `COACTUPC.cbl:973` COBOL001: mismo hallazgo, el mensaje pasa de
    51 a 66 GO TO por el copybook de procedimiento `CSUTLDPY` (15 GO TO).
- Precisión por etiquetas sin cambios (`scripts/cobol_label_precision.py`).
- Baseline regenerado (commit del analizador y tiempos).

## Recall

- 7 semillas nuevas en `RCL08.cbl` (marcadas `after_expansion`), una por
  regla COBOL004/005/008/011/012/013/014; solo se detectan con expansión
  (un test lo verifica desactivándola). Recall total 39/41 (las 2 fallas son
  los límites conocidos de siempre).

## Rendimiento (`scripts/cobol_perf_bench.py`)

| Escenario | main (s/Mloc) | expansión (s/Mloc) | RSS pico |
|---|---|---|---|
| project-1m | 7,4–8,1 | 7,9 | 60 → 61 MB |
| big-100k | 7,9–9,1 | 9,2 | 67 MB |
| big-500k | 8,5–8,9 | 8,7 | 245 MB |
| cli-1m | 8,2–8,3 | 8,8 | 80 MB |

Dentro del objetivo de < 10 s por millón de líneas. Una primera versión
costaba ~20 % más (objetos de origen por cada línea del programa y un
examen por línea); se corrigió con orígenes enteros para las líneas propias
y una búsqueda de candidatos sobre el texto unido. Test nuevo de
escalamiento lineal con el número de COPY.

## Límites

- No se soporta la sentencia `REPLACE`.
- `OF biblioteca` se lee pero no elige entre copybooks con el mismo nombre
  (gana el más cercano al programa).
- Con varios `REPLACING` en una misma cadena anidada (IBM lo rechaza) se
  aplican del más interno al más externo.
- Los copybooks se analizan solos tal como están (sin expandir sus COPY).

## Verificación

- black, isort, flake8, mypy; `pytest` (fallan solo `test_version_drift` y
  un test de tree-sitter por el entorno local, igual que en main).
- Dogfood (`HEFESTO_TELEMETRY_ENV=dogfood`): solo hallazgos MEDIUM de
  complejidad en el módulo nuevo (6–8), sin HIGH/CRITICAL.
