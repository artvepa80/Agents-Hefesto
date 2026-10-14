# 2026-10-11 — Preparación de 4.16.0 (#85 + #91): diagnóstico, auditoría y borrador de notas

Hoy se hicieron solo los pasos 0–4 y 5A. #91 recibió código nuevo, así que no se mergea hoy
ni #91 ni #85, y 4.16.0 no se publica hoy.

## 0–1. Inicio de sesión y seguridad del repo

- Leídos `CLAUDE.md`, `docs/CLAUDE_HEFESTO.md`, `CHANGELOG.md` y `README.md`. `MEMORY.md`,
  `task.md` y `walkthrough.md` no existen en este repo; no se crearon.
- Repo: OSS (`Agents-Hefesto`). Archivos en alcance:
  - `hefesto/core/analyzer_engine.py`
  - `hefesto/reports/text_reporter.py`
  - `hefesto/reports/sarif_reporter.py`
  - `tests/test_default_exclude_vendored_js.py`
  - `CHANGELOG.md`, `README.md` y este worklog
- No se mueve código pago al OSS.

## 2. Diagnóstico (con evidencia)

a) Head de #91 antes de hoy: `b97107c`, con 16 check runs `success` en ese SHA.
   - Hay un commit `4b018d4` (11:06) que no estaba en el registro anterior. Hace que
     `multilang-smoke.yml` corra `tests/test_default_exclude_vendored_js.py` y salta los dos
     tests de CLI que cuentan JS analizado cuando falta `tree_sitter_language_pack`.
   - Motivo: en `lint-and-test` un `.js` sin gramática es `parser_unavailable` y no cuenta
     como analizado.

b) #85 (`9afa279`) ya no mergea limpio sobre `main` (`e92f60b`).
   - Hay un conflicto en `CHANGELOG.md`: `[Unreleased]` ganó la sección "GitHub Action"
     de #92.
   - Es trivial, pero hay que resolverlo al actualizar #85 (paso 5C).

c) `v4` → commit `579544f`. `v4.15.1` → objeto tag `639e675`, que desreferencia a `579544f`.
   Es el mismo commit.

d) Ruleset `24893027` ("Protect exact version tags"):
   - Target tag, `refs/tags/v[0-9]*.[0-9]*.[0-9]*`, reglas `update` y `deletion`, sin
     bypass.
   - Con fnmatch de Ruby y `FNM_PATHNAME` (la sintaxis que documenta GitHub), `v4` no
     matchea: después del dígito exige un `.` literal.

e) En #91 los archivos vendorizados se descartan en `_find_files`
   (`if not include_vendored and is_vendored_js(rel): return True`).
   - Antes de 5A no había ningún conteo en texto, JSON ni SARIF.
   - El JSON solo tenía `summary`, `files`, `timestamp` y un `meta` opcional; el SARIF tenía
     `invocations[0] = {"executionSuccessful": true}`.

f) `release.yml`:
   - Condición: `if [[ ! "$TAG" =~ ^v4\.[0-9]+\.[0-9]+$ ]]`.
   - Después calcula
     `LATEST=$(git ls-remote --tags --refs origin "refs/tags/${MAJOR}.*" | ... | sort -V | tail -n1)`
     y solo mueve si `[ "$LATEST" = "$TAG" ]`. Así solo la versión 4.x más alta mueve `v4`.
   - Simulado en un repo bare: v4.15.1 mueve; v4.14.1, `v4`, v5.0.0 y un RC no mueven.

## 3. Auditoría con tres lentes

### Socrática: supuestos de los que depende todo

1. *Los archivos excluidos son de terceros.* Verificado archivo por archivo en WebGoat (22) y
   NodeGoat (6): jQuery, jQuery UI, Ace, RequireJS, Backbone, Bootstrap, wysihtml5, Raphael,
   Morris, html5shiv, etc.
2. *Un `lib/` de primer nivel es código propio.* Verificado en express (`lib/`, 148 archivos
   sin cambio). No está verificado para todos los ecosistemas; es una regla de ruta y tiene
   opt-out.
3. *#91 solo puede bajar hallazgos, nunca poner un gate en rojo por sí solo.* Es cierto
   aislado, porque solo quita archivos. Combinado con #85, un repo con solo JS vendorizado
   pasa a cero archivos y su gate falla. Ver 4.1.
4. *El cambio de exit code de #85 solo afecta a quien usa `--fail-on`.* Verificado con el
   código de #85:
   - sin `--fail-on`: exit 0 y aviso;
   - con `--fail-on HIGH`: exit 1, "Gate failure: no files were analyzed";
   - 4.15.1: exit 0, "Gate passed".
   - La Action pone `fail_on: CRITICAL` por defecto, así que siempre lo afecta.
5. *Agregar `meta.vendored_skipped` no rompe consumidores.* `meta` ya es un dict de claves
   opcionales (`scope`, `multilang`, `parser_failures`, `cobol_format_notices`) y no hay un
   JSON Schema publicado de la salida JSON. No verificable: consumidores con validación
   estricta propia.
6. *Medir en 14 repos públicos representa a los usuarios.* No verificable. Es una muestra
   de conveniencia.

### Aristotélica: "0 FP en 14 repos; 11 hallazgos, todos reales"

- **Alcance**:
  - Solo la regla EVAL_USAGE, en 14 repos públicos clonados en el box: WebGoat `044948d`,
    NodeGoat `c5cb68a`, zod `284243f`, express `a419aa7`, flask `d086db8`, pygoat
    `19d17cc`, gson `845664b`, requests `611c616`, MediatR `916ef1b`, cobra `adbc881`,
    ripgrep `3fce3b5`, opensourcecobol4j `e71a282`, kubernetes-goat `723a0db`,
    terragoat `729f8da`.
  - Comando: `hefesto analyze <repo> --no-config --severity LOW --output json`.
- **Revisión**: completa, no muestreada. Se miraron los 11 hallazgos línea por línea, todos
  con una llamada real a `eval`/`exec`:
  - `Runtime.getRuntime().exec(...)`;
  - `eval(req.body.*)` ×3 en NodeGoat;
  - `exec(` de child_process en el Gruntfile;
  - `cy.exec`;
  - `eval(...)` en zod/bench;
  - `exec(compile(...))` y `eval(compile(...))` en flask;
  - `eval(...)` ×2 en pygoat.
  - "Real" significa que existe la llamada, no que sea explotable: `cy.exec` en un test o
    `compile` de un archivo de config son usos intencionales.
- **Quién juzgó**: una sola revisión, del agente que escribió el cambio. No hay revisión
  independiente.
- **Reproducibilidad**:
  - Hoy se reproduce en el box: corrida `vjs2` con el código de este PR, mismos 11
    hallazgos.
  - Pero los clones y los scripts (a local corpus of public repos) no están en este repo. Con n=11,
    un solo FP daría 8–9%; no se midió recall.
  - **Conclusión**: no entra en las notas de release en esa forma.
- **Plugin de jQuery que sigue analizado** (`static/js/jquery_form/jquery.form.js` en
  WebGoat):
  - Sí produce hallazgos: 31 (HIGH_COMPLEXITY 9, DEEP_NESTING 9, LONG_FUNCTION 7,
    VERY_HIGH_COMPLEXITY 5, INCOMPLETE_TODO 1).
  - Ninguno es EVAL_USAGE.
  - WebGoat conserva 84 hallazgos en 19 archivos JS.
  - Alcance preciso: el cambio quita las librerías en directorios de librería y los
    minificados; no todo JS de terceros.

### Platónica: contrato "qué miró esta corrida"

| Dimensión | Hoy | 4.16.0 | Después |
|---|---|---|---|
| Analizados | `summary.files_analyzed` | igual | — |
| Omitidos por vendorizados | nada | texto "N files skipped as vendored (use --include-vendored)", `meta.vendored_skipped {count, examples≤20}`, notificación SARIF `note` (5A) | — |
| Omitidos por exclusión (default o `--exclude`) | nada | nada | diferido: contar exige recorrer `node_modules/` y similares. Opción barata: contar directorios podados, no archivos |
| Sin parser / error de parseo | aviso en stderr + `meta.parser_failures` | igual | — |
| Scope gating (PRO) | `meta.scope` | igual | — |
| Cero archivos | "No issues found!", exit 0 | aviso + gate falla con `--fail-on` (#85) | — |

- **Criterio**: lo que cambia el resultado de un gate o lo que el usuario no puede deducir
  sale en 4.16.0. El conteo de exclusiones es información que el usuario ya pidió con sus
  patrones. Un objeto unificado `meta.coverage` sería una reforma del contrato; se puede
  agregar después de forma aditiva.
- **Pendiente para 5C**: si una corrida queda en cero archivos y hubo vendorizados omitidos,
  el aviso de #85 debe nombrar el conteo y `--include-vendored`. Hoy dice "(no supported
  source files, or every file was excluded)".

## 4. Decisiones

**4.1 Una minor o dos.**
- Conclusión: una sola (4.16.0), con una condición.
- #91 aislado nunca pone un gate en rojo: solo quita archivos y hallazgos. Las alertas de
  code scanning sobre vendorizados se cierran como resueltas.
- Todo rojo nuevo viene de #85. El único camino combinado (repo con solo JS vendorizado →
  cero archivos → rojo) se vuelve diagnosticable si el aviso de cero archivos nombra el
  conteo de vendorizados (pendiente de 5C).
- Separar en dos releases mueve `@v4` dos veces seguidas y no aísla mejor la causa: el
  mensaje de la salida ya la nombra.
- Condición: 5C agrega esa pista; sin ella, recomendaría dos releases.

**4.2 Avisar en 4.16.0 y aplicar en 5.0.0, o aplicar ya.**
- A favor de avisar primero:
  - un exit code es API para CI;
  - `@v4` lo entrega sin acción del usuario;
  - semver estricto lo trataría como breaking;
  - hay usos legítimos de rutas vacías (matrices de monorepo con paquetes sin fuentes
    soportadas).
- A favor de aplicar ya:
  - el comportamiento actual es un defecto del contrato central: el gate dice
    "Gate passed" sin haber mirado nada;
  - quien queda afectado es justo quien no mira su CI, así que un aviso en el log no le
    llega;
  - esperar a 5.0.0 deja a todos los usuarios de `@v4` con el falso verde
    indefinidamente, porque `@v4` nunca recibe 5.x;
  - sin `--fail-on` no cambia nada (exit 0).
- Conclusión: aplicar en 4.16.0, abriendo las notas con el cambio. Pregunta bloqueante 1
  (abajo): ¿una salida explícita para corridas vacías intencionales?

**4.3 JSON/SARIF.**
- Sí, ya implementado en 5A: `meta.vendored_skipped` y una notificación SARIF de nivel
  `note`.
- Agregar una clave opcional a `meta`, que ya es un dict de claves opcionales, es aditivo:
  compatible con minor (incluso patch) en semver. No hay schema JSON publicado.
- En SARIF, `toolExecutionNotifications` es parte del estándar OASIS. Nada se agrega si no
  hubo omisiones.

**4.4 Corrección vs. comportamiento nuevo.**
- #85 corrige un defecto (falso pase), pero cambia un exit code observable: mínimo minor,
  no patch.
- #91 agrega comportamiento: nueva exclusión por defecto, flag, clave de config y campo de
  salida. Es minor.
- Juntos: 4.16.0. No 4.15.2, porque un patch no debería cambiar qué se analiza ni un exit
  code. No 5.0.0, porque el cambio de exit code solo toca corridas que no analizaron nada y
  arregla una violación del contrato documentado del gate.

**Preguntas bloqueantes (máximo 2), ya respondidas por Arturo (16:05):**
1. ¿Se agrega en 4.16.0 una salida explícita para corridas vacías intencionales? Por
   ejemplo `--allow-no-files` o `allow_no_files: true`, que mantenga exit 0 con
   `--fail-on`. Recomendación: sí, pequeña y testeada.
   - Respuesta: sí, como flag de línea de comandos únicamente (`--allow-no-files`), más un
     input `allow_no_files` de la Action que solo pasa el flag; implementado en #85 (ver 5B).
     Refinamiento posterior de Arturo: sin clave en `.hefesto.yaml`.
2. ¿Se publican cifras de corpus en las notas? Requeriría agregar al repo un manifiesto
   (repos públicos + SHAs + comando + etiquetas de EVAL_USAGE), no el corpus.
   - Respuesta: no. Las notas no llevan cifras de corpus y no se agrega manifiesto.

## 5A. Implementado hoy (pusheado a #91)

- `AnalyzerEngine._vendored_skipped` cuenta cada archivo una vez, solo si ningún patrón de
  exclusión ya lo descarta (no cuenta `node_modules/x.min.js`).
- `meta.vendored_skipped = {"count", "examples"}`, con hasta 20 rutas ordenadas.
- Texto: `N files skipped as vendored (use --include-vendored)` (singular con 1) bajo
  "Files analyzed". Solo aparece si N > 0.
- SARIF: notificación de nivel `note` en `invocations[0].toolExecutionNotifications`;
  `executionSuccessful` sigue en true.
- Tests: 13 nuevos (61 en el archivo), primero en rojo (7 fallaban).
  - Cubren: conteo, deduplicación con el mismo path dos veces, exclusiones del usuario no
    contadas, sin entrada con 0 o con `--include-vendored`, tope de ejemplos, texto
    singular/plural, ausencia sin omisiones, campo JSON y notificación SARIF.
- `main` mergeado en #91 (conflicto de CHANGELOG resuelto conservando ambas entradas).
- Verificación local:
  - black, isort y flake8 limpios;
  - pytest: 1204 passed, 8 skipped, 1 error. El error es `test_csharp_parses_with_cold_cache`,
    del entorno local (versión del language pack); en CI pasa.
- Dogfood `hefesto analyze . --severity MEDIUM`: 276 archivos, 401 hallazgos, exit 0.
- WebGoat: "22 files skipped as vendored (use --include-vendored)". NodeGoat: 6. Los otros
  12 repos: 0, sin línea.

## 5B/5C. `--allow-no-files` y pista de vendorizados (pusheado a #85)

- `--allow-no-files`, solo como flag de CLI. Una clave `allow_no_files` en
  `.hefesto.yaml` se rechaza como desconocida (exit 2, "unknown key 'allow_no_files'"),
  no se ignora en silencio; hay test. Input `allow_no_files` de la Action (default
  `false`): con `true`, `1` o `yes` el entrypoint agrega `--allow-no-files` y el log
  muestra `Allow no files: yes (--allow-no-files)`.
- Casos de uso documentados: jobs que analizan solo archivos cambiados, PRs que solo tocan
  Markdown.
- Con `--fail-on` y cero archivos: exit 0 y "Gate skipped: no files were analyzed
  (--allow-no-files)". El reporte "No files were analyzed" y el aviso por stderr se
  imprimen igual (también con `--quiet` y `--output json`). No cambia nada si hubo
  archivos: los hallazgos siguen fallando el gate.
- Pista 5C: si una ruta termina con cero archivos y el motor omitió vendorizados en esa
  ruta, el aviso agrega "; N files skipped as vendored (use --include-vendored)".
  - #85 lee `meta.vendored_skipped.count` (el campo que agrega #91) antes y después de
    cada ruta, de forma defensiva: sin #91 el campo no existe y el aviso queda igual.
  - Tests unitarios con un motor falso (corren en #85 solo). Tests de integración con
    `skipif` mientras `is_vendored_js` no exista; se activan en cuanto ambos PR están en
    la misma rama.
- Verificado con un merge local de prueba de #85 en #91 (no pusheado): solo choca
  CHANGELOG.md; los tests de integración corren y pasan.

## 6. Borrador de notas de release 4.16.0 (sin cifras de corpus)

> **Breaking for CI gates that analyze nothing: a run with no analyzed files no longer passes `--fail-on`.**
> Until 4.15.1, when `hefesto analyze` found no files to analyze (empty or wrong path, only unsupported files, or everything excluded), it printed "No issues found!" and `--fail-on` reported "Gate passed" with exit code 0. From 4.16.0 it prints "No files were analyzed", writes a warning naming the path to stderr (also with `--quiet` and `--output json`, whose stdout stays valid JSON), and with `--fail-on` fails with "Gate failure: no files were analyzed" and **exit code 1**. Without `--fail-on` the exit code stays 0. With several paths, a path with no files only warns while another path was analyzed.
> **Intentionally empty runs:** for jobs that are empty on purpose (changed-files-only jobs, PRs that touch only Markdown), pass `--allow-no-files` (on the GitHub Action, `allow_no_files: 'true'` passes it). Only the exit code changes: the run keeps exit code 0 under `--fail-on` and prints "Gate skipped: no files were analyzed (--allow-no-files)", while "Files analyzed: 0", "No files were analyzed" and the stderr warning are still printed. It is a command-line flag only; `.hefesto.yaml` cannot set it. Findings still fail the gate as before.
> **GitHub Action:** `fail_on` defaults to `CRITICAL`, so a workflow whose `target` has no supported files now fails unless it sets `allow_no_files: 'true'`. `@v4` follows the whole 4.x line, minor releases included, so workflows on `@v4` get this change without editing anything. To stay on the old behaviour, pin an exact tag such as `@v4.15.1`.
>
> **Vendored and minified JavaScript is skipped by default.** `*.min.js` / `*-min.js`, JavaScript under `vendor/`, `vendors/`, `bower_components/`, `jspm_packages/`, and JavaScript under `lib/`, `libs/`, `plugins/`, `third_party/` or `thirdparty/` inside `static/`, `assets/`, `public/` or `wwwroot/` are no longer analyzed. On codebases that bundle libraries this way, the number of findings drops, and so do alerts on those files in code scanning. The summary says how many files were left out (`N files skipped as vendored (use --include-vendored)`; `meta.vendored_skipped` in JSON; a tool notification in SARIF). `--include-vendored` or `include_vendored: true` restores the old behaviour. If every candidate file of a path was vendored, the zero-files warning says how many were skipped and names `--include-vendored`. A top-level `lib/`, non-JavaScript files under `vendor/` and a single file given on the command line are still analyzed.

## 7. Orden de merge (mañana, no hoy)

1. Mergear #91 (squash) con CI verde.
2. Actualizar #85 desde `main` (merge, sin force-push). Conflicto esperado solo en
   CHANGELOG.md: en `[Unreleased]`, `### Changed` abre con la entrada de cero archivos,
   luego la de vendorizados; después `### Added` y `### GitHub Action`. Con push que
   incluya el token de workflows si el merge trae cambios en `.github/workflows`.
3. Verificar en el CI de #85 que `TestVendoredHintIntegration` ya no se salta y pasa.
4. Mergear #85 (squash) con CI verde.
5. Cortar 4.16.0 con las notas de la sección 6 (abren con el cambio de exit code).

El orden inverso también funciona (el código de la pista es defensivo y los tests de
integración se activarían en el CI de #91 al actualizarlo desde `main`), pero se prefiere
#91 primero para que el último CI antes del release sea el de #85, que valida la
combinación.
