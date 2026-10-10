# 2026-10-10: correcciones de precisión y de exclusiones (PRs #84-#88)

Cinco PRs abiertos contra `main`. **Ninguno está mergeado**: por la regla de no mergear el mismo día los cambios de código con riesgo de regresión, el merge queda para otra jornada, después de revisarlos. Tampoco hay tags ni publicación en PyPI.

| PR | Rama | Qué arregla | Semver |
|---|---|---|---|
| #84 | `fix/exclude-path-components` | Exclusiones por componente de ruta, relativas a la ruta analizada | patch (4.15.1) |
| #85 | `feat/zero-files-invariant` | Un análisis sin archivos ya no pasa como éxito (`--fail-on` sale con 1) | minor |
| #86 | `fix/yaml-multidoc-helm` | YAML_SYNTAX_ERROR: multi-documento y plantillas Helm | patch |
| #87 | `fix/cobol004-intended-redefines` | COBOL004: cuatro idiomas de REDEFINES que no reinterpretan valores | patch |
| #88 | `fix/eval-usage-ast` | EVAL_USAGE en JS/TS/Java a partir del árbol de tree-sitter | patch |

## #84: exclusiones por componente

- **Defecto:** `DEFAULT_EXCLUDES` y `--exclude` se comparaban como subcadenas de la ruta absoluta.
  - `hefesto analyze app-build`, `cd app-build && hefesto analyze .` o un proyecto bajo `~/venv/` analizaban 0 archivos y decían "No issues found!".
  - `rebuild/` también se excluía.
- **Call sites corregidos:**
  - `AnalyzerEngine._find_files` (`analyzer_engine.py:391-393`).
  - `_extra_copybook_candidates` (`:178` y `:182-183`).
  - `ImportsVsDepsAnalyzer._iter_python_files`: `EXCLUDED_DIRS` sobre `path.parts` absoluto. Este no estaba en la descripción de la tarea.
- **Nuevo helper:** `path_is_excluded(rel_parts, patterns, is_dir=False)`.
- **Test actualizado:** `test_cobol_phase3_precision.py::test_prepared_index_uses_engine_discovery`, que afirmaba el defecto.
- **Antes/después:**
  - `IBM/dbb-zappbuild`: 0 → 16 archivos, 0 → 9 hallazgos.
  - Dogfood sin cambios, salvo el fixture nuevo.
- **Cambio visible:** `--exclude test` ya no excluye `tests/` ni `latest.py`. Está documentado en CHANGELOG, sección *Changed*.
- **MEMORY.md:** la nota de que el invariante de cero archivos queda pendiente para la próxima minor va en `CHANGELOG.md` [Unreleased] (primer commit de #84). No va en `MEMORY.md` porque este repo público ya no tiene ese archivo: se quitó en `1d93a7d` (los trackers internos no van en el repo OSS).

## #85: invariante de cero archivos

- **Comportamiento:** footer "No files were analyzed" (sin ✅), aviso en stderr por cada ruta sin archivos (también con `--quiet` y `--output json`), y con `--fail-on` "Gate failure: no files were analyzed" y exit 1.
- Sin `--fail-on`, el exit sigue en 0.
- **Por qué es minor:** la GitHub Action tiene `fail_on: CRITICAL` por defecto, así que un workflow cuya `path` no contiene archivos soportados pasa de verde a rojo. Hay que anunciarlo en las notas de la release.
- **Merge:** es independiente de #84. El que se mergee segundo tiene que quitar la nota *Pending* de #84 del CHANGELOG.

## #86: YAML multi-documento y Helm

- **Fix:** `safe_load_all` y, para las plantillas de un chart (directorio `templates/` junto a `Chart.yaml`) que contienen `{{`, no se hace el chequeo de sintaxis. Las demás reglas YAML siguen corriendo.
- **Antes/después en `kubernetes-goat`:** YAML_SYNTAX_ERROR 15 → 0 (10 multi-documento, 5 Helm). Total 84 → 69. Ninguna otra regla cambia.

## #87: COBOL004

- **Idiomas exentos:**
  1. Split de un zoned con signo, con el signo en el último grupo.
  2. Puntero contra una vista de 4 u 8 bytes (`PIC X(n)` o binario sin signo).
  3. Mismo layout de almacenamiento al expandir `OCCURS` fijos (tablas de constantes).
  4. Vista de bytes de un binario con signo.
- **Muestra de 19 repos COBOL públicos:** 61 → 10 hallazgos. Los 10 TP revisados a mano se mantienen, así que la precisión pasa de 16 % a 100 %.
- **Corpus etiquetado:**
  - `cobol_corpus_baseline.py compare`: sin cambios en los hallazgos (CardDemo, GenApp, zopeneditor).
  - NIST: 77 → 76. Los 19 TP etiquetados se mantienen; el que sale es una tabla de constantes (`NC125A.CBL:64`).
- **Tests y fixtures actualizados (afirmaban la vista de bytes con signo como hallazgo):**
  - `test_byte_view_idiom`.
  - Una fila de `test_sensitive_overlay_flagged`.
  - El seed de recall `RCL02.cbl:20`, regenerado con `scripts/cobol_recall_fixture.py`: ahora es un byte más un dígito, que sigue siendo hallazgo.

## #88: EVAL_USAGE por AST

- **Nuevo módulo:** `hefesto/analyzers/eval_calls.py`.
  - JS/TS: `eval`, `window/globalThis/self.eval`, `exec` de `child_process` (require/import, alias y desestructuración incluidos) y `cy.exec`.
  - Java: `Runtime.exec`, `ScriptEngine.eval`.
  - Go/Rust/C#: nada.
- **Misma muestra (14 repos, 128 hallazgos revisados):** 128 → 12. TP 11 → 11, FP 117 → 1, precisión 8,6 % → 91,7 %.
- **Meta de < 5 % de FP:** no se cumple (1/12 = 8,3 %). El FP que queda es un `eval(text)` real dentro de `require.min.js` vendorizado (WebGoat). Excluir el JS vendorizado o minificado quedó fuera de hoy. Con esa exclusión serían 0/11. La muestra es chica.
- **CI:** el job multilang ahora corre `tests/test_eval_usage_ast.py`, porque `lint-and-test` no instala las gramáticas y se lo saltea. El cambio de workflow se pusheó con el token con scope `workflow`.

## Comprobaciones antes de cada PR

`black --check`, `isort --check-only`, `flake8`, `pytest -m "not integration and not slow"`, `guard_public_repo.py`, `verify_capabilities.py`, `verify_readme.py`, dogfood (`HEFESTO_TELEMETRY_ENV=dogfood hefesto analyze . --severity MEDIUM`) y la reproducción de cada PR. El `mypy` local marca 1 error en `treesitter_parser.py:17`. Es igual en `main` y solo aparece con `tree-sitter-language-pack` instalado, que CI no instala.

## GitHub Action

`action.yml` instala con `pip install "$GITHUB_ACTION_PATH"`, desde su propio checkout y no desde PyPI. Los arreglos llegan a quien use `@main` (después del merge) o el tag nuevo. Los workflows fijados a `@v4.15.0` (los ejemplos del README y de `docs/github-action.md`) siguen con el defecto hasta que suban de versión. En la release hay que actualizar esos ejemplos al tag nuevo.

## Pendiente

- Revisar y mergear #84-#88 otro día (squash). Orden sugerido: #84, #86, #87, #88 en un patch 4.15.1, y #85 en la minor siguiente.
- Excluir JS vendorizado o minificado (deja EVAL_USAGE bajo 5 % en esta muestra y saca el ruido de WebGoat).
- Releases: actualizar los ejemplos `@v4.15.0` de la Action. Opcional: tag móvil `v4` (requiere aprobación).
