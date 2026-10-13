# 2026-10-13 — BINARY-CHAR/SHORT/LONG/LONG-LONG/DOUBLE como binario (PR A)

## Problema

`_USAGE_BINARY` es `(?<![\w-])(?:COMP(?:UTATIONAL)?(?:-[45])?|BINARY)(?![\w-])`: el
lookahead falla en el guion de `BINARY-SHORT`, así que `_usage_class()` devolvía `None`
y, sin PIC, `_elementary_class(None, None)` los clasificaba "alphanumeric". COBOL004 no
veía ninguna REDEFINES sobre ellos (ni una reinterpretación real como `BINARY-LONG`
redefinido como `PIC 9(4)`).

## Cambio (solo el clasificador; el orden de bytes va en el PR B / COBOL016)

- `_FIXED_BINARY` + `_FIXED_BINARY_BYTES` = {CHAR: 1, SHORT: 2, LONG: 4, LONG-LONG: 8,
  DOUBLE: 8}. Tabla fija, no `_binary_bytes()` (que deriva el tamaño de los dígitos del
  PIC con reglas IBM). Tamaños medidos con GnuCOBOL 3.2 x86_64 (`FUNCTION BYTE-LENGTH`).
- `_usage_class()` los devuelve como "binary" (con o sin USAGE [IS], SIGNED/UNSIGNED).
- `_pic_text()`: sin PIC, el nombre del tipo hace de PIC en el layout (`BINARY-LONG`), así
  los layouts se comparan y se miden; SIGNED/UNSIGNED se ignora (mismos bytes).
- `_binary_size()`: tabla fija para BINARY-xxx, dígitos del PIC para el resto. Lo usan
  `_is_byte_view()` y `_is_pointer_view()` (que sigue exigiendo binario sin signo).
- BINARY-C-LONG queda fuera: su tamaño depende de la plataforma (4 u 8).

## Tests (primero en rojo: 55 fallaban)

`tests/test_cobol_binary_native_usages.py`: clasificación (5 tipos × SIGNED/UNSIGNED ×
USAGE/USAGE IS), tabla de tamaños, reinterpretaciones reportadas (BINARY-LONG → 9(4),
9(4) → BINARY-SHORT, COMP-3 → BINARY-LONG, vistas de bytes de tamaño distinto), vistas de
bytes del mismo tamaño no reportadas por COBOL004, POINTER como BINARY-LONG-LONG UNSIGNED
no reportado, y los controles de CobolCraft: `chunk-io.cob:35/:764/:925` (BINARY-LONG-LONG
UNSIGNED + REDEFINES BINARY-LONG-LONG) y `encode.cob:139` / `decode.cob:141` (BINARY-LONG +
REDEFINES BINARY-LONG UNSIGNED) siguen limpios. Los nombres de chunk-io se acortaron en el
test para caber en la columna 72 del programa de prueba (CobolCraft es formato libre).

## Delta de COBOL004 (solo este PR, contra 4.16.0)

CardDemo 16 → 16, GenApp 0 → 0, zopeneditor 0 → 0 y 20 repos COBOL de un corpus local de 34 repos públicos (Bank-of-Z 6,
COBOL-Examples 1, cobol-programming-course 1, opensourcecobol4j 77, el resto 0, CobolCraft
incluido): **delta 0, ningún hallazgo nuevo ni perdido**. CobolCraft (272 archivos) solo
tiene REDEFINES BINARY-xxx de la misma especie con y sin signo. Recall 39/41.

## Relación con #101

#101 toca `_is_intended_overlay()` y COBOL004 (mensaje COMP-5); este PR toca el
clasificador, `_is_byte_view()` y `_is_pointer_view()`. Ver el PR B para el orden.

## corpus-baseline (CI)

El check `corpus-baseline` falló en este PR por un cambio que ya está en main: #99
(YAML_INDENTATION) quitó los 2 hallazgos `zapp.yaml:1` y `multiroot/sam/zapp.yaml:1` de
zopeneditor-sample ("Inconsistent indentation (N levels)", el falso positivo que corrigió),
y `benchmark/cobol/baseline.json` no se actualizó (el check solo corre cuando cambian
archivos COBOL). Se quitan esas 2 entradas del baseline (9 → 7 hallazgos, LOW 2 → 0);
CardDemo y GenApp sin cambios.
