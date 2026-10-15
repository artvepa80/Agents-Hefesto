# 2026-10-15 — server.json del registro MCP: repo público, servidor alojado cerrado

## Qué se pidió

Dejar `server.json` (entrada `io.github.artvepa80/hefestoai`, remoto `https://hefestoai.narapallc.com/api/mcp-protocol`) apuntando a este repo público, y decir en la descripción que el servidor MCP alojado es de código cerrado y lo opera Narapa. Validar contra el esquema oficial vigente. No publicar en el registro.

## Esquema

El esquema oficial vigente es **2025-12-11**, draft-07:

`https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json`

Comprobado el 2026-10-15:

- `CurrentSchemaVersion` en `modelcontextprotocol/registry` `pkg/model/constants.go` es `2025-12-11`.
- El directorio más nuevo en `modelcontextprotocol/static` `schemas/` es `2025-12-11` (hay 2025-07-09, 2025-08-26, 2025-09-16, 2025-09-29, 2025-10-11, 2025-10-17 y 2025-12-11). No hay esquema 2026 publicado.
- `$schema` del archivo ya era esa URL. No había que cambiarla.
- El documento anterior ya validaba. El esquema exige `name`, `description` y `version`. `repository` es opcional; si está, exige `url` y `source`. `description` tiene `maxLength` 100. `repository.id` es `string`.

## Qué cambió en server.json

- `repository.url` sigue en `https://github.com/artvepa80/Agents-Hefesto` y `source` sigue en `github`. Este repo es público y contiene el motor `hefesto-ai` que ejecuta `analyze`. No se apunta al repo privado: no se puede clonar ni navegar sin credenciales, y el campo existe para que se pueda inspeccionar el código.
- `repository.id` es `"1079896229"` (el `id` numérico de GitHub, `gh api repos/artvepa80/Agents-Hefesto --jq .id`). Va entre comillas: el esquema pide string, y un número no valida.
- No hay `repository.subfolder`. Ese campo es la ruta del servidor dentro de un monorepo. El servidor MCP no está en este repo. El paquete `hefesto/` es el motor, no una subcarpeta del servidor.
- No hay `packages`. Un paquete PyPI haría pensar que el servidor MCP se instala con `hefesto-ai`. El paquete es el motor.
- `description` (90 caracteres): `Release-truth gate for AI-generated code. Hosted MCP server is closed-source (Narapa LLC).`
- `version` se queda en `4.17.0`, igual que `pyproject.toml`. No se publica. La entrada viva del registro sigue siendo `4.13.1` (la otra versión publicada es `4.9.3`); el registro no permite cambiar una versión ya publicada, así que esta descripción sale en un publish futuro, que este PR no hace.
- El remoto no cambia: `streamable-http` en `https://hefestoai.narapallc.com/api/mcp-protocol`.

La misma frase ("The hosted MCP server is closed-source and operated by Narapa LLC.") está en el README, `docs/ai-discovery.md` y `skill/integration.md`. El README y la guía de integración dicen además que `repository` se queda en este repo porque aquí está el motor.

## Verificación

`scripts/verify_server_json.py` (paso `Verify MCP server.json` de `lint-and-test`, también en `scripts/run_checks.sh` y en el comando de `CLAUDE.md`):

- Comprueba los campos de arriba, incluida la versión contra `pyproject.toml`.
- Descarga el esquema de la URL de `$schema` y valida con `jsonschema` (`Draft7Validator` + `FormatChecker`). El repo ya depende de `jsonschema` en el extra `dev` (SARIF); no se añadió ajv.
- `git ls-remote` de `repository.url` sin `credential.helper` y sin la config global/sistema, para que un token guardado no haga pasar un repo privado.

Tests: `tests/scripts/test_verify_server_json.py`.

## No hecho

- No se publicó en `registry.modelcontextprotocol.io`.
- No se movió `repository` al repo privado.
- Smithery (`configSchema`, server card) queda fuera: es el repo privado y hace falta la API key.
