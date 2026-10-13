# 2026-10-13 — corpus-baseline en cada PR y en push a main

## Problema (verificado)

- `main` 067ec70: `python scripts/cobol_corpus_baseline.py compare` sale con exit 1:
  zopeneditor-sample `YAML_INDENTATION: +0 -2` (`multiroot/sam/zapp.yaml:1`, `zapp.yaml:1`),
  CardDemo y GenApp sin cambios. Lo causó el fix de YAML_INDENTATION (#99), que no tocó
  archivos del filtro `paths` del workflow, así que el check no corrió.
- #101 sobre main actual (merge local): el mismo exit 1 y la misma diferencia. Además
  #101 tiene conflicto de CHANGELOG con main (el código mergea limpio).

## Cambio

- `benchmark/cobol/baseline.json`: solo el archivo del commit 14ae97b (#102): se quitan las
  2 entradas YAML_INDENTATION de zopeneditor-sample (9 → 7 hallazgos, LOW 2 → 0).
- `.github/workflows/cobol-corpus-baseline.yml`: sin filtro `paths`; corre en todo PR a
  main, en push a main, semanal y manual.
- Local con este branch: `compare` exit 0, sin cambios en los 3 corpus.

## Check requerido

Lectura de reglas (`gh api repos/.../rules/branches/main`): el ruleset activo
"main branch protection" exige solo `multilang-smoke (3.10..3.13)`. `corpus-baseline` no es
un check requerido (no hay branch protection clásica: 404). Hacerlo requerido es un
cambio de ajustes del repo y queda a decisión de Arturo.
