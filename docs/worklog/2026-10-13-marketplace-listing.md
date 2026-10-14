# 2026-10-13 — Listing del Marketplace (hefesto-code-guardian)

Auditoría de Hefesto Growth (documento interno de auditoría), verificada punto por punto.

## Verificado y aplicado

1. **action.yml**: el Action instala `pip install "$GITHUB_ACTION_PATH"` sin extras.
   Medido con una venv limpia sin extras sobre un directorio con un archivo por formato:
   analiza `.py`, `.yml`, `.tf`, `.sh`, `Dockerfile`, `.sql`, `.cbl`; salta Go, Java,
   JavaScript y TypeScript ("parser unavailable ... pip install hefesto-ai[multilang]").
   Descripción nueva (113 caracteres, límite 125): "Deterministic pass/fail check for
   agent-written code: declared-vs-real drift, secrets, IaC and COBOL, with SARIF."
   Branding `check-circle` verde. Nombre sin cambios (la URL del listing depende de él).
2. **README, Quick start arriba**: workflow con `@v4`, `fail_on: HIGH`, `sarif: 'true'` y
   permisos; nota de fijar `@v4.16.0` o SHA (4.16.0 cambió el caso sin archivos); qué
   formatos cubre el Action; enlace a `#pricing` (PRO $8, OMEGA $19; sin "no credit card",
   sin cupones).
3. **Tabla "What Hefesto Catches"**: `rg PATH_TRAVERSAL|UNSAFE_DESERIALIZATION hefesto/` no
   encuentra nada: ningún analizador los emite. PATH_TRAVERSAL se quita. En lugar de
   UNSAFE_DESERIALIZATION se lista PICKLE_USAGE (HIGH, `security.py`, imports de
   pickle/cPickle), que sí se emite; `yaml.unsafe_load` no se detecta, se quita de la fila.
4. **Copy**: `/api/analyze` alojado se mantiene (existe en producción desde la Fase 6) y ya
   describe sus límites (20 archivos, 100 KB c/u, 256 KB, 20 s, nada se guarda). "39 of 41"
   se mantiene (reproducible con `scripts/cobol_recall.py`), ahora en `docs/cobol.md`.
   "about 9 s" ya estaba tras #100. "SQL_INJECTION FP rate 43%→0%": el "después" es
   reproducible (`tests/fixtures/sqli_safe_patterns/`: 0 FP en los 4 fixtures seguros, 3/3
   TP), el "antes" no (necesita el código viejo) y la cifra no cuadra (4 FP / 7 = 57 %).
   Estaba en el changelog del README, que se reemplazó por un enlace a CHANGELOG.md; la
   entrada histórica de CHANGELOG.md no se toca.
5. **Mover a docs/**: REST API (PRO) → `docs/rest-api.md`, OMEGA/IRIS + contrato de
   telemetría IRIS → `docs/omega-iris.md`, Telemetry → `docs/telemetry.md`, detalle COBOL
   → `docs/cobol.md`, changelog del README → enlace. Enlaces relativos corregidos.
   README 916 → 716 líneas. README Parity (`scripts/verify_readme.py`) y Capabilities
   Parity pasan. No se llegó a ~150 líneas: README Parity exige en el README las tablas
   de lenguajes (Code / DevOps / Cloud), el badge `languages-22-green` y el encabezado
   `CLI Reference (vX.Y.Z)`; mover más (CLI reference, CI/CD, configuración) es posible
   pero cambia el script de paridad o rompe enlaces externos: queda como propuesta.
6. **`.pre-commit-hooks.yaml`**: descripción "Deterministic security and complexity checks
   on staged Python files (hefesto analyze)" (`types: [python]`; no se promete drift: en una
   prueba con archivos sueltos no aparecieron hallazgos OT) y `hefesto-ai>=4.16.0`.

## No aplicado (propuestas en el cuerpo del PR)

- Descripción y topics del repo (ajuste de repo; Arturo quiere revisarlo).
- Inputs `multilang` / `format_check` del Action y verified creator (org de GitHub +
  dominio verificado).
- Captura real de code scanning / anotación de PR: no se puede producir desde aquí sin una
  corrida con subida SARIF y sesión en GitHub; queda TODO.
- Badge del Marketplace: no añadido (el badge `languages-22` se mantiene por README Parity).

## Verificación

pytest 1255 passed, 8 skipped (1 error local conocido); dogfood 279 archivos / 389
hallazgos, igual que main; README Parity y Capabilities Parity OK.

## Correcciones (2026-10-13, revisión de Arturo)

- **Telemetría (bloqueante)**: el README decía "Off by default; opt-in only", falso.
  `hefesto/telemetry/client.py::remote_ping_enabled()` devuelve True salvo
  `HEFESTO_TELEMETRY` en 0/false/no/off (opt-out); el Action tiene `telemetry: '0'` por
  defecto; `docs/telemetry.md` ya decía "collects anonymous usage data by default". Frase
  nueva en el README: "The CLI sends one anonymous usage ping per run by default (no code,
  file paths or PII); turn it off with HEFESTO_TELEMETRY=0. The GitHub Action sends nothing
  unless you set telemetry: 1." `tests/test_readme_telemetry_claim.py` ata la frase a
  `remote_ping_enabled()` (por defecto True, False con 0) y al default `'0'` del input.
- **Quick start**: "Public repositories work as shown; private repositories without GitHub
  Code Security set `upload_sarif: 'false'` (the SARIF file is still written)". El input se
  llama `upload_sarif` en `action.yml` (verificado).
- **Pin**: `artvepa80/Agents-Hefesto@v4.16.0`; `scripts/verify_readme.py` (ACTION_REF
  `Agents-Hefesto@v(\d+(?:\.\d+\.\d+)?)`) acepta solo la versión de `pyproject.toml` o `4`,
  así que el pin se valida en cada release.
- **action.yml**: "Deterministic pass/fail gate for Python, IaC, SQL and COBOL:
  declared-vs-real drift, secrets and risky code, with SARIF." (120 caracteres).
- Enlaces del README a docs/ y CHANGELOG con URL absoluta de GitHub (el README es la página
  de PyPI y del Marketplace, donde los relativos no resuelven).
- Worklogs públicos: "a local corpus of N public repos" en lugar de la ruta local.

## 2026-10-14: actualizado desde main tras #103

- Merge de `origin/main` (56258e0, #103 COBOL016) en la rama, sin force-push.
- Conflictos: README (se conserva la versión corta de #104; nota ³ pasa a "16 rules" y COBOL016 en la lista de reglas de copybooks) y CHANGELOG (se conservan las dos entradas).
- `docs/cobol.md`: el párrafo COBOL004 lleva el texto de COBOL016 tal como quedó mergeado (byte views COMP-5 y BINARY-xxx, vistas de POINTER, MEDIUM) y cómo excluirlo con `exclude_types: [COBOL_PLATFORM_DEPENDENT_LAYOUT]`.
- Comprobación: `grep -rn COBOL016 README.md docs/cobol.md`.
- La entrada COBOL016 del CHANGELOG aún cita "20 public COBOL repositories" y Bank-of-Z/MortgageApplication; se corrige en el PR de la release 4.17.0.
- Sin merge: requiere los 15 checks y el OK de Arturo.
- Tras el merge, `lint-and-test` falló: `test_own_test_suite_has_no_contradictions` (#107) leía como contradicción las dos llamadas sin argumentos a `remote_ping_enabled()` en dos tests distintos (resultado distinto por el entorno). Se unieron en un solo test (`test_cli_ping_default_and_opt_out`) que comprueba los dos estados; no se toca el validador ni se oculta nada.
- `docs/rest-api.md`: tabla de endpoints reducida a lo que existe (`GET /health`, `POST /analyze` en `hefesto/server.py`; `/v1/ingest/*` solo con IRIS, `_mount_iris_ingest`); `HEFESTO_EXPOSE_DOCS=1` (el valor `true` no hace nada).
- `docs/omega-iris.md`: quitado el bloque Setup (`python -m hefesto.omega.iris_agent`, `hefesto omega status`, `iris_config.yaml`), que no existen. Se mantiene el contrato de telemetría IRIS.
