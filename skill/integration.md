# HefestoAI Integration Guide

## Install

```bash
pip install hefesto-ai
```

Requires Python >= 3.10. Installs the `hefesto` CLI.

## Pre-Commit Hook

### Automatic Installation

```bash
hefesto install-hooks         # install to .git/hooks/
hefesto install-hooks --force # overwrite existing hooks
```

Installs both pre-commit and pre-push hooks from `scripts/git-hooks/`.

### What the Hook Does

The pre-commit hook runs:
```bash
hefesto analyze . --severity HIGH --exclude tests/ --exclude docs/   --exclude build/ --exclude dist/ --exclude .git/ --exclude htmlcov/
```

Blocks commit if CRITICAL or HIGH issues are found.

### Bypass

```bash
SKIP_HEFESTO_HOOKS=1 git commit -m "emergency fix"
```

### Manual Hook

Add to `.git/hooks/pre-commit` (or `.pre-commit-config.yaml`):
```bash
#!/usr/bin/env bash
set -euo pipefail
hefesto analyze . --fail-on HIGH --exclude tests/
```

## GitHub Actions

### As a Docker Action

```yaml
name: Code Quality
on: [push, pull_request]
jobs:
  hefesto:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: artvepa80/Agents-Hefesto@main
        with:
          target: '.'
          fail_on: 'CRITICAL'
          min_severity: 'LOW'
          format: 'text'
```

### Action Inputs

| Input | Default | Description |
|-------|---------|-------------|
| target | . | Path to analyze |
| fail_on | CRITICAL | Gate severity threshold |
| min_severity | LOW | Minimum severity to report (CRITICAL, HIGH, MEDIUM, LOW; INFO is treated as LOW) |
| format | text | Output format: text, json, html |
| telemetry | 0 | Opt-in anonymous telemetry: only `1`/`true` sends the per-run ping; anything else sends nothing |

### As a pip Install Step

```yaml
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install hefesto-ai
      - run: hefesto analyze . --fail-on HIGH --output json
```

## MCP Server (Claude Code / Cursor)

HefestoAI is registered as an MCP server for AI code editors.

### Install via Smithery

```bash
npx @smithery/cli@latest mcp add artvepa80/hefestoai
```

### Manual Configuration

Claude Code:

```bash
claude mcp add --transport http hefestoai https://hefestoai.narapallc.com/api/mcp-protocol
```

Or commit a project-scoped `.mcp.json` at the repo root:

```json
{
  "mcpServers": {
    "hefestoai": {
      "type": "http",
      "url": "https://hefestoai.narapallc.com/api/mcp-protocol"
    }
  }
}
```

Other editors: use the same URL with their streamable-HTTP transport.

### Available MCP Endpoints

| Endpoint | Protocol | Purpose |
|----------|----------|---------|
| /api/mcp-protocol | JSON-RPC 2.0 | MCP tool calls |
| /api/mcp | HTTP GET/POST | REST discovery |
| /api/openapi.json | OpenAPI 3.0 | API specification |
| /api/ask | HTTP POST | Natural language Q&A |
| /.well-known/agent.json | A2A | Agent descriptor |

### Registry IDs

- Official MCP Registry: `io.github.artvepa80/hefestoai`
- Smithery: `artvepa80/hefestoai`

## Claude Code Feedback Loop

`hefesto analyze` makes no LLM calls: analysis is deterministic and runs
locally, so it consumes no Claude API credit. Pair it with Claude Code so the
credit is spent on fixing findings, not on finding them.

### PostToolUse Hook

Add to `.claude/settings.json` (requires `jq`):

```json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Edit|Write",
      "hooks": [{
        "type": "command",
        "command": "f=$(jq -r '.tool_input.file_path'); hefesto analyze \"$f\" --fail-on HIGH --quiet >&2 || exit 2"
      }]
    }]
  }
}
```

`hefesto analyze` exits 1 on a gate failure; the hook maps that to exit 2,
which Claude Code feeds back to Claude so it fixes the finding in the same
session.

### Filter First, Then Fix

Hand Claude only the findings instead of the whole repository:

```bash
hefesto analyze . --severity HIGH --output json > findings.json
claude -p "Fix the findings in findings.json"
```

For pull requests, `hefesto pr-review` emits the same JSON scoped to the diff.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| HEFESTO_TIER | (none) | License tier: professional, omega |
| SKIP_HEFESTO_HOOKS | 0 | Set to 1 to bypass git hooks |
| IRIS_BQ_PROJECT | (none) | GCP project for IRIS telemetry |
| IRIS_BQ_DATASET | omega_audit | BigQuery dataset for IRIS |

## Default Excludes

The analyzer always excludes these directories:
`.venv/`, `venv/`, `.tox/`, `node_modules/`, `.git/`, `__pycache__/`,
`dist/`, `build/`, `.mypy_cache/`, `.pytest_cache/`, `.eggs/`, `.egg-info/`

Additional excludes via `--exclude` flag.
