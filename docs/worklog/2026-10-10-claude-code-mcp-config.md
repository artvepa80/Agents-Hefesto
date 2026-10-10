# 2026-10-10 — Configuración MCP de Claude Code y feedback loop (rescate de rama)

## Contexto

La rama `claude/hefestoai-100-dollars-wrjgqq` (commit `9bc419f`, 2026-09-24) nunca tuvo PR. Corregía un error real de `skill/integration.md`: el ejemplo de configuración MCP manual usaba `~/.claude/mcp_servers.json` con `"type": "streamable-http"`, que Claude Code no lee. La rama estaba 21 commits atrás de `main`, y mergearla tal cual habría revertido dos filas de la tabla de inputs de la Action (`min_severity` y `telemetry`) que se corrigieron después.

## Qué se hizo

1. **Cherry-pick de `9bc419f` sobre `main`**, solo en `skill/integration.md`. Las filas `min_severity` ("INFO is treated as LOW") y `telemetry` ("only `1`/`true` sends the per-run ping") quedan como estaban en `main`. El CHANGELOG del commit original no se usó; la entrada se escribió de nuevo.
2. **Configuración MCP manual:** `claude mcp add --transport http hefestoai https://hefestoai.narapallc.com/api/mcp-protocol` o un `.mcp.json` de proyecto con `"mcpServers"` y `"type": "http"`. Para otros editores, la misma URL con su transporte streamable-HTTP.
3. **Sección "Claude Code Feedback Loop":** un hook `PostToolUse` que corre `hefesto analyze` sobre cada archivo editado y convierte el fallo del gate (exit 1) en exit 2 para que Claude lo corrija en la misma sesión, y el flujo "primero filtrar, después arreglar" (`--output json` → `claude -p`). Se ajustó una frase: en vez de "HefestoAI makes no LLM calls" dice "`hefesto analyze` makes no LLM calls", que es lo que se verificó.
4. **Test nuevo** `tests/test_skill_integration_docs.py` (4 casos): el ejemplo viejo no vuelve, el `.mcp.json` del documento es JSON válido con `type: http`, los flags que usa la guía (`--fail-on`, `--quiet`, `--severity`, `--output`) existen en `hefesto analyze` y existe `pr-review`, y las filas de la Action siguen al día.

## Verificación

- El hook, probado con un archivo con `eval` y una contraseña hardcodeada: `hefesto analyze --fail-on HIGH --quiet` sale con 1 y el hook con 2.
- `rg` sobre `hefesto/`: no hay llamadas a APIs de LLM en el análisis (solo patrones para detectar claves y un enum de modelos).
- `pytest tests/test_skill_integration_docs.py` → 4 passed. `black --check` y `hefesto analyze` sobre los archivos tocados, en verde.

## Después del merge

Borrar la rama `claude/hefestoai-100-dollars-wrjgqq` (último commit `9bc419ff39fac9ede33f4d3ae9d040b368e96785`).
