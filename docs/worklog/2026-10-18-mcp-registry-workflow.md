# 2026-10-18 — Manual MCP Registry workflow (draft PR, not merged)

## Request
Arturo's OK (relayed by Hefesto Growth, 08:34 Lima) to open a draft PR that publishes `io.github.artvepa80/hefestoai` to the official MCP Registry. Not to merge it, not to publish.

## Source
- Guide: https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/github-actions.mdx (read 2026-10-18): OIDC needs `id-token: write`; `mcp-publisher login github-oidc`; protect publishing with an environment that has a required reviewer, and note that `environment:` alone auto-creates an unprotected environment.
- `mcp-publisher` latest release v1.8.1 (2026-08-06). `mcp-publisher_linux_amd64.tar.gz` sha256 `a06c9096dcb9727c13555b6be26c7effa707b01f06a4c561ba7a3635443cf2cc` from `registry_1.8.1_checksums.txt`; checked locally with `sha256sum -c`.

## Constraints (Hefesto MCP)
- Canonical entry: the hosted landing's `server.json` (`https://hefestoai.narapallc.com/server.json`), remote streamable-http. This repository's `server.json` is never published.
- Registry version tracks the hosted engine, not PyPI; registry versions are immutable.
- No `packages` (PyPI) entry without the owner's decision and an `mcp-name:` README line.
- Description "HefestoAI checks AI-generated code before you ship it."; `repository.url` stays on this repository.

## State on 2026-10-18
- Registry versions: 4.19.0 (latest), 4.17.0, 4.13.1, 4.9.3 (`GET /v0/servers/io.github.artvepa80%2Fhefestoai/versions`).
- Canonical entry live: version 4.20.1, `changelog.json` latest 4.20.1.
- Local dry run: `python scripts/check_mcp_registry_entry.py <canonical> --expected-version 4.20.1` → OK; `mcp-publisher validate <canonical>` → valid. The public `server.json` is rejected (description, version 4.20.2 ≠ hosted 4.20.1).
- Environment `mcp-registry` does not exist (404); the gate job fails until Arturo creates it with himself as required reviewer.

## Why a separate workflow
`release.yml` runs on version tags for PyPI. A registry version follows the hosted engine, which is deployed from another repository at another time, so tying it to the PyPI tag would publish the wrong version or the wrong document.

## Open questions
- PyPI `packages` entry (needs Arturo; also `mcp-name: io.github.artvepa80/hefestoai` in the README).
- Who triggers the registry publish after a hosted-engine deploy (Hefesto MCP or PYTHIA), and whether the canonical file should move to a stable public artifact.
