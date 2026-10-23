# 2026-10-18 — Manual MCP Registry workflow (draft PR, not merged)

## Request
Arturo's OK (08:34 Lima) to open a draft PR that publishes `io.github.artvepa80/hefestoai` to the official MCP Registry. Not to merge it, not to publish.

## Source
- Guide: https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/github-actions.mdx (read 2026-10-18): OIDC needs `id-token: write`; `mcp-publisher login github-oidc`; protect publishing with an environment that has a required reviewer, and note that `environment:` alone auto-creates an unprotected environment.
- `mcp-publisher` latest release v1.8.1 (2026-08-06). `mcp-publisher_linux_amd64.tar.gz` sha256 `a06c9096dcb9727c13555b6be26c7effa707b01f06a4c561ba7a3635443cf2cc` from `registry_1.8.1_checksums.txt`; checked locally with `sha256sum -c`.

## Constraints (hosted engine)
- Canonical entry: the hosted landing's `server.json` (`https://hefestoai.narapallc.com/server.json`), remote streamable-http. This repository's `server.json` is never published.
- Registry version tracks the hosted engine, not PyPI; registry versions are immutable.
- No `packages` (PyPI) entry until a local MCP server exists (Arturo, 2026-10-18). An `mcp-name:` README line is required only if that changes.
- Description "HefestoAI checks AI-generated code before you ship it."; `repository.url` stays on this repository.

## State on 2026-10-18
- Registry versions: 4.19.0 (latest), 4.17.0, 4.13.1, 4.9.3 (`GET /v0/servers/io.github.artvepa80%2Fhefestoai/versions`).
- Canonical entry live: version 4.20.1, `changelog.json` latest 4.20.1.
- Local dry run: `python scripts/check_mcp_registry_entry.py <canonical> --expected-version 4.20.1` → OK; `mcp-publisher validate <canonical>` → valid. The public `server.json` is rejected (description, version 4.20.2 ≠ hosted 4.20.1).
- Environment `mcp-registry` does not exist (404); the gate job fails until Arturo creates it with himself as required reviewer.

## Why a separate workflow
`release.yml` runs on version tags for PyPI. A registry version follows the hosted engine, which is deployed from another repository at another time, so tying it to the PyPI tag would publish the wrong version or the wrong document.

## Decisions (Arturo, 2026-10-18 10:26 Lima)
- No PyPI `packages` entry until a local MCP server exists.
- Arturo creates the `mcp-registry` environment himself, with himself as required reviewer (`main` only).
- The maintainer runs the workflow after each hosted engine deploy, once production is verified.
- First publish: after the 4.20.2 hosted deploy.

## Update: hosted engine review (2026-10-18)

- Hosted version comes from the deployed engine: `initialize` `serverInfo.version`
  == `engine.version` from a minimal `tools/call analyze` (same parsing as the
  hosted-engine check; the live response has no `engine` in
  `structuredContent`, so the text JSON is parsed) == `changelog.json` `latest`
  == `server.json` `version`.
- Registry lookups moved to the documented v0.1 API (openapi.yaml):
  `/versions/{version}?include_deleted=true` (404 = free) and
  `/versions?include_deleted=true`. Live: 4.19.0 → 200, 4.20.2 → 404.
- TOCTOU: the publish job checks the registry again in the step right before
  `mcp-publisher publish`. A first draft built the URL with `jq -r ... | jq -sRr @uri`,
  which encoded the trailing newline (`%0A`) and returned 404 even for the
  published 4.19.0. It now encodes inside jq (`.name | @uri`), and a test pins this.
- Nice-to-have: `?t=$GITHUB_RUN_ID` cache-bust with `--retry 3`; the gate requires
  `deployment_branch_policy` = custom with exactly `branch:main`; the job summary
  lists the version to publish and the registry latest; the docstring example uses
  `X.Y.Z`.
- Side finding: the existing `pypi` environment has `deployment_branch_policy: null`
  (any branch). Not changed here.

## Update: Arturo decisions (2026-10-18 10:26 Lima)

Docs and PR body updated to record the three decisions above. No workflow change.
