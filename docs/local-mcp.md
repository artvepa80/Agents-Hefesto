# Local MCP (stdio)

`hefesto-mcp` is a local, read-only [MCP](https://modelcontextprotocol.io) server over stdio. It is part of the MIT-licensed `hefesto-ai` package. It does not talk to a hosted service and it does not open network connections.

## Install

```bash
pip install "hefesto-ai[mcp]"
```

The extra installs `mcp` and the `hefesto-mcp` console script. The core package dependencies are unchanged. Without the extra, `hefesto analyze` works as before.

## Client config

Claude Desktop and Claude Code launch the server with stdio. `hefesto-mcp` must be on `PATH` (the same environment you installed the extra into).

```json
{
  "mcpServers": {
    "hefesto": {
      "command": "hefesto-mcp"
    }
  }
}
```

The working directory of that process is the directory the tools are allowed to read.

## Tools

| Tool | Arguments | Result |
|------|-----------|--------|
| `analyze_local` | `path` (string), `severity` (`LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`; default `MEDIUM`) | JSON report, same shape as `hefesto analyze --output json` |
| `version` | none | Engine version string |

`analyze_local` resolves `path` and rejects it when the result is outside the working directory. A symlink whose target resolves outside the working directory is rejected as well. The scan calls the local engine in-process. It does not read `.hefesto.yaml` and it does not send usage telemetry.

The CLI opt-out is unchanged: `HEFESTO_TELEMETRY=0`, `DO_NOT_TRACK=1`, or `hefesto telemetry disable`. This process does not send events and does not modify those settings.
