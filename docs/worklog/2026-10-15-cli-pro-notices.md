# Avisos PRO dentro del CLI (2026-10-15)

## Hecho
- Una línea en stderr, después del resultado, en `hefesto/cli/growth.py`.
- No se muestra con `CI=true`, con proveedor ya clasificado en `environment_flags` (GitHub Actions, GitLab CI, `JENKINS_URL`, CircleCI), sin TTY en stdout, con `--output json`/`sarif` o `--quiet`, ni con `HEFESTO_TELEMETRY=0`, `DO_NOT_TRACK=1`, `HEFESTO_NO_UPSELL` (1/true/yes/on) o `hefesto telemetry disable`.
- Como máximo un aviso cada 7 días entre todos los tipos, y 3 veces por tipo. Estado en `~/.hefesto/upsell.json`. Archivo ilegible o corrupto: no se muestra nada y no se reescribe.
- `upgrade_cta_shown` lleva `source=hook|cli` y `cta=<tipo>`, solo si la telemetría puede enviar en ese proceso.
- Gating real: PRO = `serve` sin `HAS_API_HARDENING`, `--enrich` sin `HAS_ENRICHMENT`, flags de scope sin `HAS_SCOPE_GATING`. OMEGA = `_mount_iris_ingest` cuando `IRIS_BQ_PROJECT` está puesto y `iris` no importa. `hefesto info` imprime solo el aviso `gated_info` (API server, enrichment, scope gating en PRO $8/mo; IRIS en OMEGA $19/mo) y sale con 1. No repite `PRO_REQUIRED_MESSAGE`.
- Dato de swarm, sin inventar: `swarm/cli.py` del paquete PRO. La descripción del argparse es "HefestoAI Swarm — security analysis pipeline", la ayuda de `run` es "Run swarm analysis on a target repo", y `cmd_run` devuelve 1 cuando `result["verdict"] == "BLOCK"`.

## No hecho
- Sin merge, sin tag y sin PyPI.
