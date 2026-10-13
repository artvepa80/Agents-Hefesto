# 2026-10-12 — Demo COBOL sin "SARIF not available" y cifra de rendimiento

## SARIF

`docs/demo/cobol_investor_demo.sh` listaba en "Next Steps" "SARIF output (not available
yet; ...)". SARIF 2.1.0 existe desde 4.15.0; se quitó la línea. (La línea siguiente,
"Phase 4: performance on large codebases", también está cumplida; no se tocó porque no
estaba en el alcance.)

## Rendimiento

`python scripts/cobol_perf_bench.py --scenario project-1m`, hefesto-ai 4.16.0 de PyPI:

| Corrida | s | s/Mloc | MB | Hallazgos |
|---|---|---|---|---|
| 1 | 9.30 | 8.83 | 59.0 | 4060 |
| 2 | 9.29 | 8.82 | 58.7 | 4060 |
| 3 | 9.17 | 8.71 | 58.7 | 4060 |

Mediana: 8.82 s por millón de líneas (1,053,200 líneas, 1,060 archivos). Máquina: 8 vCPU
(`nproc` = 8, Intel Xeon), Linux, Python 3.13.5: coincide con lo que documenta el README
("8-vCPU Linux VM with Python 3.13"). Como la mediana supera 8.5, "about 8 s" pasa a
"about 9 s" en el README y en `docs/cobol-corpus-baseline.md` (que cita al README). La nota
histórica de esa misma doc ("stays under 8 s", medición de la fase de REPLACING) queda como
registro de entonces.
