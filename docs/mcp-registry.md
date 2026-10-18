# Publishing to the official MCP Registry

Entry: `io.github.artvepa80/hefestoai` on https://registry.modelcontextprotocol.io.
Workflow: `.github/workflows/mcp-registry.yml`, built from the registry's guide
[How to Automate Publishing with GitHub Actions](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/github-actions.mdx)
(GitHub OIDC authentication).

## What is published

- The canonical entry is the one deployed with the landing page at
  `https://hefestoai.narapallc.com/server.json`: a remote (`streamable-http`,
  `https://hefestoai.narapallc.com/api/mcp-protocol`), description
  "HefestoAI checks AI-generated code before you ship it.", and `repository.url`
  on this public repository.
- This repository's `server.json` is never published. It tracks the PyPI version
  and has a different description; `scripts/verify_server_json.py` keeps checking
  it in CI.
- The registry `version` tracks the hosted engine (`changelog.json` `latest` on the
  landing page), not PyPI. A published registry version can never be changed.
- No `packages` entry. A PyPI package entry needs the owner's decision and an
  `mcp-name: io.github.artvepa80/hefestoai` line in the README (registry
  ownership check for PyPI).

## How to run it

1. Actions → "MCP Registry (manual)" → Run workflow on `main`, with `version` set to
   the hosted engine version. Leave `publish` unchecked: this is the dry run. It
   fetches the canonical entry, runs `scripts/check_mcp_registry_entry.py`
   (fields, hosted version, already-published versions as a warning) and
   `mcp-publisher validate`.
2. A real publish needs `publish` checked, the `main` branch, and a
   `mcp-registry` environment with a required reviewer (create it in
   Settings → Environments before the first publish). The `environment-gate` job
   fails when that environment is missing or has no reviewer, so GitHub never
   auto-creates it unprotected. In publish mode an already-published version is
   an error.
3. The `publish` job alone gets `id-token: write`. It checks that the entry is
   byte-for-byte the one validated, then runs `mcp-publisher login github-oidc`
   and `mcp-publisher publish`.

`mcp-publisher` is pinned to `v1.8.1` and its tarball is checked against the
sha256 from that release's `registry_1.8.1_checksums.txt`. To upgrade, change
`MCP_PUBLISHER_VERSION` and `MCP_PUBLISHER_SHA256` together (the guide's
"invalid audience" error means the binary is too old).

`release.yml` is not involved: a PyPI release and a registry version are separate
events with separate versions.
