# 2026-10-10 — COBOL Fase 6: docs públicos del `analyze` hosted

Estado: aprobado por Arturo. Depende de Pro-Private #122 (el endpoint `/api/analyze` y la
tool MCP `analyze` que corre el motor), mergeado como `14f62e5` y probado en producción
(Python, COBOL, SARIF, TS/JS/Java/Go/Rust/C#, rechazo de path traversal, MCP `tools/call`).

- README (tabla de endpoints + párrafo), `docs/ai-discovery.md`, `skill/integration.md`:
  describen `/api/analyze` y sus límites (20 archivos, 100 KB c/u, 256 KB total, 20 s,
  TS/JS/Java/Go/Rust/C# incluidos vía `multilang`, sin `.hefesto.yaml`, nada se guarda).
- No hay cambios de código en el paquete; el motor es hefesto-ai 4.15.0 sin cambios.
- `server.json` no cambia (la URL del MCP es la misma; la descripción no menciona la tool).
