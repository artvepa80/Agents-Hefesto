# Local MCP (stdio) — unreleased

`hefesto-mcp` is a local, read-only [MCP](https://modelcontextprotocol.io) server over stdio. It is part of the MIT-licensed `hefesto-ai` package. It does not talk to a hosted service and it does not open network connections.

This extra is not on PyPI yet.

## Install

Python 3.10 or newer. That is the package `requires-python`, and the `mcp` dependency requires the same (`>=3.10`), so the extra does not add an environment marker.

```bash
pip install "hefesto-ai[mcp] @ git+https://github.com/artvepa80/Agents-Hefesto"
```

The extra installs `mcp` and the `hefesto-mcp` console script. The core package dependencies are unchanged. Without the extra, `hefesto analyze` works as before.

## Sandbox root

The tools may read only inside one directory. The process chooses it in this order:

1. `--root` (command argument)
2. `HEFESTO_MCP_ROOT` (environment variable)
3. The working directory, if neither is set

The path is resolved with `Path.resolve()`. The process exits with status 2 when that directory is `/` or the home directory. A request path is resolved the same way and must be `is_relative_to()` that root. A symlink whose target resolves outside the root is rejected. The check does not use a string prefix.

## Client config

Claude Desktop launches the server with stdio. `hefesto-mcp` must be on `PATH` (the same environment you installed the extra into).

```json
{
  "mcpServers": {
    "hefesto": {
      "command": "hefesto-mcp",
      "args": ["--root", "/absolute/path/to/the/project"]
    }
  }
}
```

The same directory can be passed as `HEFESTO_MCP_ROOT` instead of `--root`. `--root` wins when both are set.

## Tools

| Tool | Arguments | Result |
|------|-----------|--------|
| `analyze_local` | `path` (string), `severity` (`LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`; default `MEDIUM`) | JSON report, same shape as `hefesto analyze --output json` |
| `version` | none | Engine version string |

`analyze_local` calls the local engine in-process. Text the engine prints is sent to stderr so stdout stays the MCP stream. The scan does not read `.hefesto.yaml`.

Startup sets `HEFESTO_TELEMETRY=0` for this process. The tool path does not call the usage-event sender or the PyPI version check. The machine opt-out file used by `hefesto telemetry disable` is left unchanged.
