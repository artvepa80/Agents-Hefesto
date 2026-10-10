# 2026-10-10: Path Y, "release truth engine" en los archivos para máquinas (repo público)

## Contexto

Arturo aprobó el Path Y: el titular es "release truth engine", todo en inglés y solo con cifras verificadas. El README ya lo usaba, pero los archivos que leen agentes y registros todavía decían "AI-powered code quality guardian", "0.01s" y "17 languages".

## Cambios

- `.well-known/agent-card.json`:
  - `description` canónica: release truth engine, 22 formatos (7 de código y 15 DevOps/IaC), `hefesto analyze` corre 13.
  - El skill `analyze` ya no da a entender que `analyze` cubre los 22. El texto queda igual al de la card de la landing.
- `llms.txt`: el resumen y "What is HefestoAI?" dicen release truth engine; el tier FREE dice "22 format analyzers (13 run by `hefesto analyze`)".
- `pyproject.toml`, `description`, que es el resumen de PyPI: sin "Guardian" y sin "0.01s". Se publica en el próximo release.
- `CLAUDE.md`: nuevo H1.
- Test nuevo, `tests/test_positioning_cards.py`: fija la descripción canónica, controla que las cifras sean 22/13 y que no aparezcan los claims retirados en los 4 archivos, y que los H1 digan release truth engine.

## Paridad con el repo privado

La landing sirve su propia card (`landing-page/api/agent-card.js`). El PR privado de Path Y agrega `tests/landing_js/agent-card-parity.test.mjs`, que compara esa card completa con este archivo en `main`. Por eso este PR se mergea primero.

## Fuera de alcance

- "OMEGA Guardian" en `CLAUDE.md`, `requirements*.txt` y `docs/LICENSE_GATES.md` es el nombre viejo del tier. `hefesto/server.py`, `hefesto/__init__.py`, `html_reporter.py`, `action.yml` y `server.json` (registro MCP) todavía dicen "Guardian". Conviene cambiarlos en otro PR.
