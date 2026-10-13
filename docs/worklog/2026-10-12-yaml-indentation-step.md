# 2026-10-12 — YAML_INDENTATION: paso entre niveles

## Problema

`_check_indentation` contaba los anchos de sangría distintos del archivo y marcaba si había
más de 3. Un workflow normal con anidación de 2 espacios (2/4/6/8/10) recibía "Inconsistent
indentation (5 levels)" en la línea 1: el mensaje decía "inconsistente" de un archivo
consistente. Ejemplo: `.github/workflows/hefesto.yml` de hefesto-cobol-ci-example.

## Cambio

- Se mide el paso entre una línea estructural y la siguiente más profunda. Si hay más de un
  paso distinto (por ejemplo 2 y 4), se marca la primera línea con el paso que no es el
  habitual, y el mensaje nombra los pasos: "nesting steps of 2 and 4 spaces; this line is 4
  spaces deeper than the previous one (usual step: 2)".
- Se saltan: contenido de block scalars (`|`, `>`, `|-`, `>+`, `|2`, también en `- run: |`),
  continuaciones de escalares multilínea (líneas más profundas bajo un `key: valor`) y, en
  `- key: v`, las líneas anidadas se miden desde el contenido después de `- `.

## Tests (primero en rojo: 4 fallaban)

- Workflow normal con `run: |`, continuaciones alineadas, heredoc, `>-` y `|2` → sin hallazgo.
- Archivo con pasos de 2 y 4 → un hallazgo en la línea 4, sin la palabra "levels".
- 4 espacios consistentes, anidación profunda, block scalars con cada indicador, escalares
  multilínea y listas compactas → sin hallazgo.

## Corpus de validación (34 repos públicos en /workspace/extval)

- YAML_INDENTATION (sin contar el chequeo de tabs, que no cambió: 2 antes y 2 después):
  142 antes (4.16.0) → 12 después. Ningún archivo nuevo marcado.
- Los 12 revisados uno por uno: **12 reales, 0 FP**. Todos son YAML válido (el parser los
  acepta); el hallazgo es de estilo (LOW): el archivo mezcla pasos de sangría.

| # | Archivo:línea | Paso | Veredicto | Por qué |
|---|---|---|---|---|
| 1 | Bank-of-Z `.github/workflows/Setup.yml:21` | +2 | Real | El archivo sangra de 4 en 4 (`jobs:` → `setup:` → `steps:`); el `- name:` bajo `steps:` entra solo 2. |
| 2 | Bank-of-Z `.setup/deploy/Development.yml:139` | +3 | Real | El archivo usa 2; el bloque `ims_acb_gen_default:` sangra sus claves con 3 espacios. |
| 3 | Bank-of-Z `.setup/deploy/deployment-method.yml:96` | +1 | Real | `- name: UPDATE` está 1 espacio más adentro que `steps:`; el resto de las listas del archivo entra 2. |
| 4 | Bank-of-Z `.setup/deploy/types_pattern_mapping.yml:80` | +1 | Real | Bajo `uss:` las claves entran 1 espacio (`directory:`), en un archivo de 2. |
| 5 | Bank-of-Z `.setup/zconfig/ims-region.yaml:31` | +4 | Real | `irlmnm:` entra 4 bajo `irlm:`; sus hermanos (`ims_lgmsg:` y demás) usan 2. |
| 6 | Bank-of-Z `dbb-app.yaml:29` | +4 | Real | La lista bajo `value:` entra 4; el archivo usa 2 (`variables:` → `- name:`). |
| 7 | Bank-of-Z `zapp.yaml:22` | +4 | Real | `libraries:` → `- name: syslib` entra 4; el bloque gemelo de arriba (`locations:` → `- '**'`) entra 2. |
| 8 | WebGoat `.github/workflows/release.yml:12` | +4 | Real | `contents: write` entra 4 bajo `permissions:`; `environment:` → `name:` justo debajo entra 2. |
| 9 | kubernetes-goat `docker-bench-security/deployment.yaml:120` | +4 | Real | `path:` entra 4 bajo `hostPath:`; los otros seis volúmenes del mismo manifiesto entran 2. |
| 10 | kubernetes-goat `hunger-check/deployment.yaml:34` | +4 | Real | `metadata:` del ServiceAccount sangra `name:` con 4; los otros documentos del archivo usan 2. |
| 11 | opensourcecobol4j `.github/workflows/push.yml:193` | +3 | Real | `matrix:` entra 3 bajo `strategy:` (y `test_name:` 2 más); el workflow usa 2. |
| 12 | requests `.github/workflows/lock-issues.yml:18` | +4 | Real | Las entradas de `with:` entran 4; el resto del workflow usa 2. |

## Verificación

- black, isort y flake8 limpios. pytest: 1250 passed, 8 skipped y 1 error local conocido.
- Dogfood: los mismos 389 hallazgos que `main`. La función se partió en `_IndentScanner`
  para no sumar HIGH_COMPLEXITY.
