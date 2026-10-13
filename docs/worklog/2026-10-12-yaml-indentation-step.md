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
- 5 de los 12 revisados a mano, todos reales: Bank-of-Z `Setup.yml:21` (2 dentro de un
  archivo de 4), `deployment-method.yml:96` (1), `zapp.yaml:22` (4), opensourcecobol4j
  `push.yml:193` (3), requests `lock-issues.yml:18` (4).

## Verificación

- black, isort y flake8 limpios. pytest: 1250 passed, 8 skipped y 1 error local conocido.
- Dogfood: los mismos 389 hallazgos que `main`. La función se partió en `_IndentScanner`
  para no sumar HIGH_COMPLEXITY.
