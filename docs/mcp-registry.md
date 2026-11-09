# Publishing to the official MCP Registry

Entry: `io.github.artvepa80/hefestoai` on https://registry.modelcontextprotocol.io.
Workflow: `.github/workflows/mcp-registry.yml`, built from the registry's guide
[How to Automate Publishing with GitHub Actions](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/github-actions.mdx)
(GitHub OIDC authentication).

## What is published

- The file the workflow downloads is
  `https://hefestoai.narapallc.com/server.json`. That file is not in this
  repository. It is served with the hosted landing page.
- `scripts/check_mcp_registry_entry.py` requires the downloaded file to match
  this repository's `server.json` description, one PyPI package
  (`hefesto-mcp`, `uvx`, transport `stdio`, package version equal to the
  document version, `HEFESTO_MCP_ROOT` required), and the existing remote
  (`streamable-http`, `https://hefestoai.narapallc.com/api/mcp-protocol`).
  `repository.url` stays on this public repository.
- The registry `version` is tied to the PyPI package version. It must equal all of:
  the production `initialize` `serverInfo.version`, the `engine.version` returned by
  a minimal `tools/call analyze` (the same check as the private
  `scripts/verify_hosted_engine.py`), `changelog.json` `latest` on the landing
  page, and a `hefesto-mcp` release already on PyPI
  (`https://pypi.org/pypi/hefesto-mcp/<version>/json` returns 200). A hotfix that
  exists only on the hosted server cannot be published to the registry unless
  that same version is also published as the package.
- A published registry version can never be changed
  ([versioning.mdx](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/versioning.mdx):
  "The version string MUST be unique for each publication"). The check uses the
  documented API
  ([openapi.yaml](https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/api/openapi.yaml)):
  `GET /v0.1/servers/{name}/versions/{version}?include_deleted=true` must return 404,
  and `GET /v0.1/servers/{name}/versions?include_deleted=true` lists every version,
  including deleted ones.
- This repository's `server.json` is still not the file the workflow uploads.
  The workflow downloads the hosted URL, and the checker now rejects that
  download until it has the package entry and the description from this
  repository's `server.json`. The README and the wrapper README each contain
  `mcp-name: io.github.artvepa80/hefestoai` for the PyPI ownership check.
- `release.yml` builds the `hefesto-mcp` wheel in the `build` job (tag check,
  `twine check`, wheel metadata, and an install smoke from the local wheels)
  and uploads it as `hefesto-mcp-distributions`. `publish-hefesto-mcp` only
  downloads that artifact and publishes it after `hefesto-ai`, using the same
  GitHub environment `pypi` and trusted publishing. The pending publisher for
  project `hefesto-mcp` is a separate PyPI record.

## How to run it

1. Actions → "MCP Registry (manual)" → Run workflow on `main`, with `version` set to
   the hosted engine version. Leave `publish` unchecked: this is the dry run. It
   fetches the canonical entry (cache-busted with `?t=$GITHUB_RUN_ID`, 3 retries),
   runs `scripts/check_mcp_registry_entry.py` (fields, the three hosted versions,
   already-published versions as a warning) and `mcp-publisher validate`. The job
   summary shows the version to publish, the hosted versions, and the registry's
   current latest version.
2. A real publish needs `publish` checked, the `main` branch, and a
   `mcp-registry` environment that Arturo creates himself in Settings →
   Environments, with himself as required reviewer and deployment branches set
   to "Selected branches" with only `main`. The `environment-gate` job fails when
   that environment is missing, has no reviewer, or allows any branch other than
   `main`, so GitHub never auto-creates it unprotected. In publish mode an
   already-published version is an error.
3. The `publish` job alone gets `id-token: write`. It checks that the entry is
   byte-for-byte the one validated, checks the registry again right before
   publishing (the version must still return 404, so two runs cannot both publish
   it), then runs `mcp-publisher login github-oidc` and `mcp-publisher publish`.

## Runbook

- **Who:** the maintainer runs the workflow after each hosted engine deploy, once
  production is verified.
- **When:** only after a hosted-engine check passes against production for that
  version.
- **How:** first a dry run (`publish` unchecked) with `version` set to the deployed
  version, and read its job summary. Then the same version with `publish=true`.
- **Approval:** Arturo creates the `mcp-registry` environment himself (required
  reviewer: himself; `main` only). The publish job waits on that environment, and
  he approves each deployment.
- **Wrapper upload failed:** if `publish-hefesto-mcp` in `release.yml` fails
  (for example the pending publisher for `hefesto-mcp` is not in place), fix
  that publisher and choose only "Re-run failed jobs" on the same workflow run.
  Never choose "Re-run all jobs": that runs the engine publish again, and PyPI
  rejects a second upload of the same release. Do not set `skip-existing`.
  The wheel is already in the `hefesto-mcp-distributions` artifact, so the
  rerun publishes that wheel and does not build it again.
- Registry state on 2026-10-24: 4.20.3 is latest (published 2026-10-24), with
  4.20.2, 4.19.0, 4.17.0, 4.13.1 and 4.9.3 before it. 4.20.1 was never
  published.

`mcp-publisher` is pinned to `v1.8.1` and its tarball is checked against the
sha256 from that release's `registry_1.8.1_checksums.txt`. To upgrade, change
`MCP_PUBLISHER_VERSION` and `MCP_PUBLISHER_SHA256` together (the guide's
"invalid audience" error means the binary is too old).

`release.yml` publishes `hefesto-mcp`. The registry check refuses a version
that is not already that PyPI release, so the registry version and the
package version are the same string.
