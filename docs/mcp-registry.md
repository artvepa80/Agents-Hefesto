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
- The registry `version` tracks the deployed engine, not PyPI. It must equal all of:
  the production `initialize` `serverInfo.version`, the `engine.version` returned by
  a minimal `tools/call analyze` (the same check as the private
  `scripts/verify_hosted_engine.py`), and `changelog.json` `latest` on the landing
  page.
- A published registry version can never be changed
  ([versioning.mdx](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/versioning.mdx):
  "The version string MUST be unique for each publication"). The check uses the
  documented API
  ([openapi.yaml](https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/api/openapi.yaml)):
  `GET /v0.1/servers/{name}/versions/{version}?include_deleted=true` must return 404,
  and `GET /v0.1/servers/{name}/versions?include_deleted=true` lists every version,
  including deleted ones.
- No `packages` entry. A PyPI package entry needs the owner's decision and an
  `mcp-name: io.github.artvepa80/hefestoai` line in the README (registry
  ownership check for PyPI).

## How to run it

1. Actions → "MCP Registry (manual)" → Run workflow on `main`, with `version` set to
   the hosted engine version. Leave `publish` unchecked: this is the dry run. It
   fetches the canonical entry (cache-busted with `?t=$GITHUB_RUN_ID`, 3 retries),
   runs `scripts/check_mcp_registry_entry.py` (fields, the three hosted versions,
   already-published versions as a warning) and `mcp-publisher validate`. The job
   summary shows the version to publish, the hosted versions, and the registry's
   current latest version.
2. A real publish needs `publish` checked, the `main` branch, and a
   `mcp-registry` environment with a required reviewer and deployment branches set
   to "Selected branches" with only `main` (create it in Settings → Environments
   before the first publish). The `environment-gate` job fails when that
   environment is missing, has no reviewer, or allows any branch other than `main`,
   so GitHub never auto-creates it unprotected. In publish mode an
   already-published version is an error.
3. The `publish` job alone gets `id-token: write`. It checks that the entry is
   byte-for-byte the one validated, checks the registry again right before
   publishing (the version must still return 404, so two runs cannot both publish
   it), then runs `mcp-publisher login github-oidc` and `mcp-publisher publish`.

## Runbook

- **Who:** Hefesto MCP runs the workflow after each hosted engine deploy.
- **When:** only after the private `scripts/verify_hosted_engine.py` passes against
  production for that version.
- **How:** first a dry run (`publish` unchecked) with `version` set to the deployed
  version, and read its job summary. Then the same version with `publish=true`.
- **Approval:** the publish job waits on the `mcp-registry` environment. Arturo is
  its required reviewer and approves each deployment.
- **First publish:** 4.20.2, once the 4.20.2 hosted engine deploy (planned for
  2026-10-19) passes `verify_hosted_engine`.
- Registry state on 2026-10-18: 4.19.0 is latest (published 2026-10-16), with
  4.17.0, 4.13.1 and 4.9.3 before it. 4.20.1 was never published and is skipped.

`mcp-publisher` is pinned to `v1.8.1` and its tarball is checked against the
sha256 from that release's `registry_1.8.1_checksums.txt`. To upgrade, change
`MCP_PUBLISHER_VERSION` and `MCP_PUBLISHER_SHA256` together (the guide's
"invalid audience" error means the binary is too old).

`release.yml` is not involved: a PyPI release and a registry version are separate
events with separate versions.
