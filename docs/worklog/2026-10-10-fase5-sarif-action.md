# 2026-10-10 — Fase 5 (CI): salida SARIF y subida desde la GitHub Action

## Objetivo

Que los hallazgos de `hefesto analyze` (todos los analizadores, no solo
COBOL) puedan verse en **Security > Code scanning** de GitHub: salida SARIF
2.1.0 válida y aceptada por GitHub, y una opción en la Action para generarla
y subirla con `github/codeql-action/upload-sarif`.

## Qué se hizo

- Nuevo `hefesto/reports/sarif_reporter.py` (`SARIFReporter`, exportado en
  `hefesto.reports`):
  - Una regla (`reportingDescriptor`) por ID de regla (`COBOL004`,
    `DOCKER010`, `SC2086`...; si el analizador no da ID, el tipo de hallazgo,
    p. ej. `HARDCODED_SECRET`) con `name`, descripción corta y larga, `help`
    (texto y markdown, a partir de la sugerencia), `helpUri` y nivel por
    defecto (la severidad más alta de esa regla).
  - Severidad → `level`: CRITICAL/HIGH `error`, MEDIUM `warning`, LOW
    `note`; `problem.severity` igual. Las reglas de seguridad (secretos,
    inyección, comandos inseguros, privilegios...) llevan además
    `security-severity` 9.5/8.0/5.5/3.0, la etiqueta `security` y etiquetas
    CWE cuando el hallazgo trae `metadata.cwe`. `precision` sale de la
    confianza.
  - URIs relativas al repositorio con `uriBaseId: %SRCROOT%` (raíz = el
    nivel superior git del directorio actual; si no hay git,
    `$GITHUB_WORKSPACE` o el directorio actual); fuera de la raíz, URI
    `file://` absoluta. Solo línea de inicio (sin columnas).
  - `partialFingerprints["hefestoFingerprint/v1"]`: hash de regla + archivo
    + texto normalizado de la línea señalada (no su número) + número de
    ocurrencia; sin fuente legible, el mensaje sin dígitos. Para COBOL se
    añade el copybook y el texto de su línea. Mover código no reabre alertas.
  - Hallazgos COBOL que vienen de un copybook (`metadata.expanded_from`):
    `relatedLocations` con el archivo y la línea del copybook.
  - Límites de GitHub: máx. 25.000 resultados (se conservan los más
    severos), 1.000 ubicaciones relacionadas, 20 etiquetas por regla y log
    ≤ 10 MB comprimido con gzip; lo descartado se informa en
    `invocations[0].toolExecutionNotifications`.
- CLI: `--format` es alias de `--output`, nueva opción `sarif` (stdout = SARIF
  puro, el resto a stderr, igual que `json`) y `--sarif-file RUTA` para
  escribir el SARIF además de la salida normal. `output: sarif` también se
  acepta en `.hefesto.yaml`. `_print_report` usa una tabla de reporteros
  (evita el anidamiento que el dogfood marcaba como HIGH).
- GitHub Action:
  - `action.yml` pasa de Docker a **composite** (una acción Docker no puede
    llamar a `upload-sarif`): crea un venv en `$RUNNER_TEMP`, instala el
    paquete desde el checkout de la Action y ejecuta el mismo
    `scripts/action_entrypoint.sh`, con el venv en el `PATH` solo de ese
    paso (no se toca `GITHUB_PATH`).
  - Entradas nuevas `sarif` (false), `sarif_file` (hefesto.sarif),
    `upload_sarif` (true), `sarif_category` (hefesto); salida nueva
    `sarif_file`. `format` acepta `sarif`.
  - El paso de subida usa `github/codeql-action/upload-sarif@v4` (v3 queda
    obsoleta en diciembre de 2026) con `if: always()`, así que las alertas
    se suben aunque falle la puerta `fail_on`. Si el archivo no se escribió
    se emite un `::warning::` y no se sube nada.
  - `Dockerfile.action` se mantiene para usar el entrypoint con
    `docker run`, pero `action.yml` ya no lo construye.
- `jsonschema>=4.17,<5` añadido al extra `dev`; esquema oficial OASIS SARIF
  2.1.0 copiado en `tests/fixtures/sarif/sarif-schema-2.1.0.json`.
- Documentación: README (Action con SARIF, entradas/salidas, referencia CLI,
  sección "SARIF Output", ejemplo CI sin la Action, nota COBOL),
  nuevo `docs/github-action.md` (cómo funciona, permisos, forks, límites,
  cómo verificarlo en GitHub, repositorio de ejemplo), CHANGELOG.
- Repositorio de ejemplo preparado en local
  (`/workspace/hefesto-cobol-ci-example`, no creado en GitHub): programa
  `PAYROLL.cbl` con 6 problemas sembrados (COBOL008, COBOL004 vía
  `COPY ... REPLACING` con ubicación relacionada en el copybook, COBOL003,
  COBOL011, COBOL012, COBOL014), `CUSTRPT.cbl` limpio, `.hefesto.yaml`,
  workflow con `sarif: 'true'` y README.

## Pruebas

- `tests/test_sarif_reporter.py` (14): validación con el esquema OASIS
  (Draft 4) más las comprobaciones de GitHub en cada log; metadatos de
  reglas, niveles y `security-severity`; URIs relativas y escapadas; huellas
  estables al desplazar líneas y distintas al cambiar el código; ubicación
  relacionada del copybook; límite de resultados y de tamaño gzip; CLI de
  extremo a extremo con Python, YAML, Dockerfile y COBOL; stdout SARIF puro.
- `tests/scripts/test_action_entrypoint.py` (+7): SARIF apagado por
  defecto, valores verdaderos, ruta propia sin subida, subida aunque falle
  la puerta, archivo ausente → aviso, archivo viejo borrado antes de
  ejecutar, y `action.yml` composite con todas las entradas pasadas como
  `INPUT_*` y el paso `upload-sarif@v4`.
- Simulación local de la Action composite: instalación con `pip` desde el
  checkout en un venv nuevo y ejecución del entrypoint con el `hefesto` real
  sobre el repositorio de ejemplo → `exit_code=1` (CRITICAL sembrado),
  `sarif_file=hefesto.sarif`, `upload_sarif=true`, SARIF válido.

## Verificación

- black, isort, flake8, mypy (solo el error previo de tree-sitter del
  entorno local); `pytest -m "not integration and not slow"`: todo pasa.
- Dogfood: sin HIGH/CRITICAL en los archivos tocados. Quedan los MEDIUM de
  complejidad ya existentes de `cli/main.py` y dos LOW
  `SHELL_UNQUOTED_VARIABLE` en `rm -f "$VAR"` del entrypoint, que son falsos
  positivos (la variable está entre comillas; ya ocurría en main).

## Límites y pendientes

- No se reportan columnas (los analizadores no usan la misma base de
  columnas).
- El workflow `action-smoke.yml` no se tocó desde el box (sin permiso
  `workflow`); el YAML para añadir un caso SARIF va en el informe.
- La Action composite necesita `python3` >= 3.10 en el runner y solo se
  probó para runners Linux.
- Code scanning en repositorios privados requiere GitHub Advanced Security;
  las PR desde forks no pueden subir SARIF.
