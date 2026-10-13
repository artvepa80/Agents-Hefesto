# 2026-10-13 — COBOL016: REDEFINES dependientes de la plataforma (PR B)

Apilado sobre el PR A (#102, BINARY-xxx como binario) y con #101 (COMP-5 en COBOL004)
mergeado dentro, porque mueve los hallazgos de COMP-5 de COBOL004 a COBOL016.

## Patrones (MEDIUM, cada uno con su mensaje y sugerencia)

1. **Vista de bytes nativa**: PIC X del mismo tamaño sobre COMP-5 o BINARY-SHORT/LONG/
   LONG-LONG/DOUBLE. BINARY-CHAR (1 byte) no tiene orden de bytes: limpio.
   - COMP-5: mensaje z/OS big-endian vs x86 (GnuCOBOL, Micro Focus) little-endian;
     sugerencia de #101 (truncamiento con TRUNC(STD) usando los dígitos reales, TRUNC(BIN) /
     -fnotrunc, "COMP-5 uses the full binary capacity of the field", nota C/SQL/SQLCA).
   - BINARY-xxx: "native byte order (platform-dependent)" (no son tipos de IBM Enterprise
     COBOL, así que no se habla de z/OS); sugerencia: PIC 9(n) BINARY si el layout debe ser
     portable (ojo al truncamiento), o calcular los bytes (DIVIDE por 256); nota C/SQL.
2. **BINARY sobre POINTER**: BINARY/COMP/COMP-4 sin signo de 4 u 8 bytes sobre un POINTER.
   El puntero está en orden nativo y BINARY es big-endian siempre: en x86 el número es la
   dirección con los bytes invertidos. Aquí COMP-5 es la vista portable y BINARY la
   peligrosa. Si la vista es de 4 bytes, el mensaje añade los tamaños de POINTER.
3. **Vista de 4 bytes de un POINTER**: PIC X(4), COMP-5 de 4 bytes o BINARY-LONG. POINTER
   ocupa 4 bytes en z/OS con 31 bits y 8 en plataformas de 64 bits.
   Limpias: PIC X(8), PIC 9(18) COMP-5, BINARY-LONG-LONG UNSIGNED.

COBOL004 sigue con las reinterpretaciones reales (tamaño distinto, vista de dígitos,
vista con signo de un puntero). `_is_intended_overlay()` vuelve a eximir todas las vistas
de bytes del mismo tamaño (la exclusión de COMP-5 de #101 ya no hace falta: COBOL016 se
evalúa antes). `check_redefines()` delega en `_redefines_issue()` (COBOL016 → COBOL004 →
nada) para no subir la complejidad. Nuevo `AnalysisIssueType.COBOL_PLATFORM_DEPENDENT_LAYOUT`;
COBOL016 está en `_COPYBOOK_RULES` (corre en copybooks como COBOL004).

## Tests (primero en rojo: 22 de 31)

`tests/test_cobol016_platform_layout.py`: COMP-5 (9(4), S9(4), 9(9)); BINARY-SHORT/LONG/
LONG-LONG/DOUBLE × ""/SIGNED/UNSIGNED; BINARY-CHAR limpio; BINARY/COMP/COMP-4 limpios;
desajuste de tamaño COMP-5 sigue en COBOL004; BINARY/COMP/COMP-4 sobre POINTER; fixture
INQACC.cbl:164-166 (una sola alerta, COBOL016 en la línea de 166, con "big-endian",
"4 bytes" y "8 bytes"; la vista X(8) de 165 limpia); vistas de 4 bytes; vistas de 8 bytes
nativas limpias; vista con signo sigue en COBOL004. Los tests de COMP-5 de #101 en
`test_cobol_phase3_leftovers.py` pasan a esperar COBOL016 (y ningún COBOL004).

## Corpus (contra 4.16.0)

COBOL004 sin cambios en CardDemo (16), GenApp (0), zopeneditor (0) y los 20 repos COBOL de
extval. COBOL016: 4 lugares (6 hallazgos contando la copia zapp-copy), todos BINARY sobre
POINTER, todos reales como patrón; en la práctica es código solo para z/OS:

| Archivo:línea | Vista | Nota |
|---|---|---|
| Bank-of-Z `src/base/cics/cobol/INQACC.cbl:166` | `PIC 9(8) BINARY` | fixture; 4 bytes |
| Bank-of-Z `src/base/cics/cobol/INQCUST.cbl:158` | `PIC 9(8) BINARY` | mismo idioma que INQACC |
| dbb-zappbuild `samples/MortgageApplication/cobol/epscsmrd.cbl:1257` | `PIC 9(9) COMP` | generado por CICS (web services) |
| dbb-zappbuild `.../epscsmrd.cbl:3243` | `PIC 9(9) COMP` | ídem; también en zapp-copy (copia) |

CobolCraft: 0 hallazgos. 2,319 líneas de código con BINARY-xxx (2,328 contando 9 líneas en
comentarios `*>`), ningún COMP-5. Recall 39/41. Dogfood 389 hallazgos, igual que main.

## Docs

README: COBOL001-COBOL016 (16 reglas gratis), copybooks reciben COBOL016, párrafo de
COBOL016 y nota de BINARY-xxx en COBOL004. Docstring del analizador y
`docs/demo/cobol_investor_demo.sh` (15 → 16 reglas). La landing privada también dice
15 reglas: queda para un PR en el repo privado cuando se publique.

## Orden de merge

1. **#101** (mañana; regla: no release hasta que entre COBOL016).
2. **PR A (#102)**: actualizar desde main con merge; conflicto esperado en
   `cobol_program_rules.py` (ambos insertan regex antes de `_USAGE_OTHER`; quedan los dos)
   y CHANGELOG.
3. **PR B (este)**: actualizar desde A/main; ya contiene la resolución A+#101, así que el
   diff restante es solo COBOL016.
4. Release después de B: así code scanning nunca ve el cambio de rule-id COBOL004 →
   COBOL016 para las vistas de COMP-5.
