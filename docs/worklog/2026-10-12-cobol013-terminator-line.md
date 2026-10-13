# 2026-10-12 — COBOL013: citar la línea del terminador (B5)

## Problema

En `PAYROLL.cbl` (demo COBOL), `MAIN-PARA` tiene una sola oración de COBOL en las líneas
18-21 (`MOVE` / `ACCEPT` / `DISPLAY` / `STOP RUN.`). COBOL013 reportaba la línea 22 (bien)
con el mensaje "...STOP RUN/GOBACK/EXIT PROGRAM (line 18)": citaba el inicio de la oración,
no el `STOP RUN`. No tiene que ver con la expansión de COPY ni con los comentarios.

## Cambio

- `_Sentence` gana `line_starts` (default vacío): offset en `text` donde empieza cada línea
  unida, y `line_at(offset)`.
- `unconditional_end_offset()` devuelve el offset del terminador o `None`.
  `ends_unconditionally()` sigue devolviendo bool: `_ends_paragraph()` (COBOL014) lo usa
  dentro de `any(...)`, y un `STOP RUN` solo coincide en el offset 0, que es falsy.
- COBOL013 cita `sentence.line_at(offset)`.

## Tests (primero en rojo: 3 fallaban)

- PAYROLL tal cual: hallazgo en 22, mensaje "(line 21)".
- Oración larga: empieza en 137, `GOBACK` en 268, hallazgo en 269.
- Terminador en la primera línea de la oración, y literal con punto antes del `GOBACK`.
- COBOL014: un párrafo que termina en una oración que es solo `STOP RUN.` sigue cortando
  el fall-through.

## Verificación

- black, isort y flake8 limpios. pytest: 1241 passed, 8 skipped y 1 error local conocido
  (`test_csharp_parses_with_cold_cache`).
- `scripts/cobol_recall.py`: 39/41, sin cambios.
- CardDemo, GenApp y zopeneditor-sample: hallazgos idénticos a 4.16.0 (archivo, línea, regla
  y mensaje).
- Dogfood: 276 archivos, 389 hallazgos, igual que `main`.
