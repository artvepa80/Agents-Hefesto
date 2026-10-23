# 2026-10-18 — Root .mcp.json and "Add to Cursor" button (draft PR, not merged)

Approved by Arturo 2026-10-18 09:28 Lima.

## Sources opened
- Cursor MCP docs: https://cursor.com/docs/context/mcp — remote server entry is `{"mcpServers":{"name":{"url":"…"}}}` (optional `headers`, `auth`); `type` is listed as required only for STDIO servers.
- Cursor MCP install links: https://cursor.com/docs/mcp/install-links — `cursor://anysphere.cursor-deeplink/mcp/install?name=$NAME&config=$BASE64_ENCODED_CONFIG`, config is the single server's JSON (`JSON.stringify` then base64); the docs' example base64 decodes to the inner object. Button images: `https://cursor.com/deeplink/mcp-install-dark.{svg,png}` and `-light`.
- Cursor deeplinks reference: https://cursor.com/docs/reference/deeplinks — "Links can also be opened via cursor.com. Append the path and url params", i.e. `https://cursor.com/link/mcp/install?…`.
- cursor.directory submit page: https://cursor.directory/plugins/new ("We follow the Open Plugins standard"). Its parser (`cursor/community-plugins`, `apps/cursor/src/lib/github-plugin/parse.ts`) reads `.mcp.json` or `mcp.json` at the root and uses `mcpServers ?? <object>`; no `type` needed. The README of that repo lists MCP servers at `.mcp.json`.
- Open Plugins spec: https://open-plugins.com/plugin-builders/specification — its `mcp.json` (inside a plugin with `plugin.json`) requires `$schema` and `type` (`streamable-http`). Not used: we are not shipping a plugin, and Cursor's native format has no `type` for remote servers.

## Checks
- base64 `eyJ1cmwiOiJodHRwczovL2hlZmVzdG9haS5uYXJhcGFsbGMuY29tL2FwaS9tY3AtcHJvdG9jb2wifQ==` decodes to `{"url":"https://hefestoai.narapallc.com/api/mcp-protocol"}`; re-encoding the compact JSON gives the same string.
- GitHub markdown render (`POST /markdown`): a `cursor://` href is dropped; the `https://cursor.com/link/...` href survives. Hence the button links to cursor.com and the raw deeplink is shown as code.
- `https://cursor.com/link/mcp/install?...` → 200 ("Open in Cursor"). Button SVG/PNG → 200.
- Endpoint (read-only): `initialize` POST → 200, protocolVersion 2025-06-18, serverInfo hefestoai 4.20.1, "No API key"; `tools/list` → pricing, install, compare, analyze, all `readOnlyHint: true`.
- No version strings changed (README Parity unaffected).
