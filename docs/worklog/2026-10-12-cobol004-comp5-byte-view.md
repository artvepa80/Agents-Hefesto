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

## Mensaje propio (2026-10-13)

La vista de bytes de COMP-5 recibía el mensaje genérico ("a different layout over binary
(COMP) data ... can corrupt values"), que es incorrecto: mismo tamaño, mismos bytes, es
COMP-5 y no COMP, y el riesgo es leer bytes distintos en z/OS y en x86, no corrupción en
la misma plataforma.

- `_is_native_byte_view()` detecta el caso; `_redefines_text()` elige mensaje y sugerencia.
  Severidad y regla sin cambios (COBOL004, HIGH).
- Mensaje: "'X' REDEFINES 'Y' as PIC X bytes of a COMP-5 field. COMP-5 uses the platform's
  native byte order: big-endian on z/OS, little-endian on x86 (GnuCOBOL, Micro Focus), so
  the byte view reads the same value as different bytes on each platform."
- Sugerencia: "Declare the field BINARY (or COMP) if its byte layout must be portable, or
  drop the byte view and work with the numeric value."
- Tests primero (2 en rojo): el mensaje cita byte order, COMP-5, z/OS, x86 y big-endian,
  en ambas direcciones; BINARY con tamaño distinto o vista de dígitos, y COMP-5 que no es
  vista de bytes del mismo tamaño, conservan el mensaje genérico.
- CardDemo, cics-genapp, zopeneditor-sample y los 7 repos de extval con COMP-5: hallazgos
  COBOL (línea, regla, mensaje) idénticos a 4.16.0. Recall 39/41.
