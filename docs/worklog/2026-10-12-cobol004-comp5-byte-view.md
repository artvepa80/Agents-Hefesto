# 2026-10-12 — COBOL004: las vistas de bytes de COMP-5 ya no se eximen

## Problema

`_is_byte_view()` exime de COBOL004 un entero binario redefinido como bytes PIC X del
mismo tamaño (idioma de CardDemo para leer el file status). La clase de uso venía de
`_USAGE_BINARY`, que agrupa COMP/BINARY/COMP-4/COMP-5. COMP-5 es binario nativo: el
orden de bytes depende de la plataforma (big-endian en z/OS, little-endian en x86), así
que la misma vista PIC X lee bytes distintos en cada una. Eso sí es un riesgo de
portabilidad y debe reportarse.

## Cambio

- Nuevo regex `_USAGE_NATIVE_BINARY` (`COMP-5` / `COMPUTATIONAL-5`).
- `_is_intended_overlay()` calcula las cláusulas de los miembros de ambos lados antes del
  chequeo de vista de bytes; si alguna declara COMP-5 (en el ítem o en su grupo), no
  aplica la exención. `_is_byte_view()` no cambia de firma.
- COMP, COMPUTATIONAL, BINARY y COMP-4 (big-endian en todas partes) mantienen la exención.

## Tests (primero en rojo: 14 fallaban)

`tests/test_cobol_phase3_leftovers.py`:
- `test_comp5_byte_view_is_flagged`: COMP-5 / COMPUTATIONAL-5 / USAGE COMP-5 ×
  9(4), S9(4), 9(9), S9(18) → reportado (con y sin signo).
- `test_portable_binary_byte_view_still_skipped`: BINARY, COMP, COMP-4, COMPUTATIONAL,
  USAGE BINARY × 9(4), S9(4) → no reportado.
- `test_comp5_group_usage_is_flagged` (uso heredado del grupo) y
  `test_comp5_reverse_direction_is_flagged` (PIC X redefinido como COMP-5).

## Validación

- Suite completa verde; recall 39/41 sin cambios.
- CardDemo, cics-genapp, zopeneditor-sample: salida de `hefesto analyze --severity LOW`
  idéntica antes y después (diff vacío).
- extval: 7 repos con COMP-5 (Bank-of-Z, COBOL-Examples, cobol-on-wheelchair,
  dbb-zappbuild, gcblunit, gnucobol, zapp-copy): COBOL004 idéntico antes y después.

Riesgo de regresión: nuevos hallazgos COBOL004 en código con vistas de bytes de COMP-5.
No se mergea el mismo día.
