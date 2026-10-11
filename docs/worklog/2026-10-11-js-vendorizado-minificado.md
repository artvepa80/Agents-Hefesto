# 2026-10-11 — JavaScript vendorizado y minificado excluido por defecto

## Diagnóstico

Sobre 4.15.1 (exclusiones por componente de ruta, #84), una muestra de 14 repos públicos
(WebGoat, NodeGoat, zod, express, flask, pygoat, gson, requests, MediatR, cobra, ripgrep,
opensourcecobol4j, kubernetes-goat, terragoat) analizada con
`hefesto analyze <repo> --no-config --severity LOW --output json`:

- **WebGoat**: 589 archivos, 1,943 hallazgos. 1,769 (91%) venían de 22 librerías copiadas
  al repo: jQuery, jQuery UI, Ace, RequireJS, Backbone, Bootstrap, wysihtml5, etc., bajo
  `static/js/libs/`, `static/plugins/` y archivos `*.min.js`.
- **NodeGoat**: 308 hallazgos; 253 de 6 archivos en `app/assets/vendor/`.
- **EVAL_USAGE**: 12 hallazgos, 11 verdaderos positivos y 1 falso positivo
  (`static/js/libs/require.min.js:5`, el `eval` propio de RequireJS): 8.3% de FP.

Ningún otro repo de la muestra tiene JS vendorizado; sus resultados no cambian.

## Cambio

`hefesto.core.analyzer_engine.is_vendored_js(rel_parts)`, aplicado en `_find_files` antes
de los default excludes. Solo archivos `.js`, `.mjs`, `.cjs`; rutas relativas al path
analizado; sin distinguir mayúsculas:

1. Nombre minificado: `*.min.js`, `*-min.js`.
2. Dentro de `vendor/`, `vendors/`, `bower_components/` o `jspm_packages/`, a cualquier
   profundidad.
3. Dentro de `lib/`, `libs/`, `plugins/`, `third_party/` o `thirdparty/` que esté a su vez
   bajo `static/`, `assets/`, `public/` o `wwwroot/`.

Conservador a propósito: un `lib/` de primer nivel (código propio de express) sigue,
igual que Go/PHP bajo `vendor/`, TypeScript minificado y un archivo pasado directamente en
la línea de comandos. Opt-out: `--include-vendored` o `include_vendored: true` en
`.hefesto.yaml`.

## Tests (primero en rojo)

`tests/test_default_exclude_vendored_js.py` (48 casos): rutas vendorizadas y propias,
raíz dentro de un directorio vendor, archivo único, `--include-vendored`, clave de config,
excludes del usuario que siguen aplicando. Ajustes: `test_project_config` (nueva clave) y
`test_pro_wiring` (el fixture de scope gating usaba `vendor/*.js`, que ahora no llega al
filtro PRO; pasa a `vendor/*.py`).

## Medición (mismo binario, con y sin `--include-vendored`)

| Repo | Archivos | Hallazgos |
|---|---|---|
| WebGoat | 589 → 567 | 1,943 → 174 (−1,769, −91%) |
| NodeGoat | 55 → 49 | 308 → 55 (−253) |
| Los otros 12 | sin cambio | sin cambio |

EVAL_USAGE en los 14 repos: 12 (11 TP, 1 FP, 8.3%) → 11 (11 TP, 0 FP, 0%), por debajo del
objetivo de 5%. Los 28 archivos excluidos son todos librerías de terceros (revisados uno
por uno). Dogfood en este repo: 276 archivos y 400 hallazgos con o sin la opción.

## Límites conocidos

- WebGoat `static/js/jquery_form/jquery.form.js` (31 hallazgos) sigue: es jQuery Form, pero
  su directorio no es `lib`/`libs`/`plugins`; no se adivina por nombre de archivo.
- Un `public/js/lib/` con código propio queda excluido; se recupera con
  `--include-vendored`.
- Sin heurística de contenido (líneas largas): las reglas son solo de ruta y deterministas.

## CI (seguimiento)

- `lint-and-test` instala `.[dev,lint]` sin las gramáticas tree-sitter, así que un `.js` sale
  como `parser_unavailable` y no cuenta como analizado. Los dos tests de CLI que cuentan
  archivos JS analizados (`test_flag_includes_vendored`, `test_config_key_includes_vendored`)
  ahora se saltan sin `tree_sitter_language_pack`, y `multilang-smoke.yml` corre este archivo
  de tests junto a `test_eval_usage_ast.py`, donde sí están las gramáticas.
- Local: 70 passed con gramáticas; 46 passed + 2 skipped sin gramáticas; Black limpio.
