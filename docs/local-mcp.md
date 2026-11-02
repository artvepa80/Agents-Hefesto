# Local MCP (stdio)

`hefesto-mcp` is a local, read-only [MCP](https://modelcontextprotocol.io) server over stdio. It is part of the MIT-licensed `hefesto-ai` package. It does not talk to a hosted service and it does not open network connections.

This extra is not on PyPI yet. `uvx hefesto-mcp` becomes available once it is published on PyPI.

## Install

Python 3.11 or newer. That is the package `requires-python`; the `mcp` dependency requires `>=3.10`, which every supported Python meets, so the extra does not add an environment marker. The extra requires `mcp>=1.7,<2`.

```bash
pip install "hefesto-ai[mcp] @ git+https://github.com/artvepa80/Agents-Hefesto"
```

`HEFESTO_MCP_ROOT` is required for `uvx hefesto-mcp`. Set it to the project directory the tools may read. It must not be `/` or the home directory.

The `hefesto-mcp` distribution (`packaging/hefesto-mcp`) is metadata only: it depends on `hefesto-ai[mcp]==4.20.4` and installs the same console script. The core package dependencies are unchanged. Without the extra, `hefesto analyze` works as before.

## Sandbox root

The tools may read only inside one directory. The process chooses it in this order:

1. `--root` (command argument)
2. `HEFESTO_MCP_ROOT` (environment variable; required for `uvx hefesto-mcp`)
3. The working directory, if neither is set

The path is resolved with `Path.resolve()`. The process exits with status 2 when that directory is `/` or the home directory. The stderr message names `HEFESTO_MCP_ROOT` and `--root`. A relative request path is joined to that root, not to the process working directory, and then resolved the same way. It must be `is_relative_to()` that root. A symlink whose target resolves outside the root is rejected. The check does not use a string prefix.

## Client config

An MCP client launches the server with stdio.

```json
{
  "mcpServers": {
    "hefesto": {
      "command": "uvx",
      "args": ["hefesto-mcp"],
      "env": {
        "HEFESTO_MCP_ROOT": "/absolute/path/to/the/project"
      }
    }
  }
}
```

`--root` wins when both `--root` and `HEFESTO_MCP_ROOT` are set.

## Tools

| Tool | Arguments | Result |
|------|-----------|--------|
| `analyze_local` | `path` (string, inside the sandbox root), `severity` (`LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`; default `MEDIUM`) | JSON report, same shape as `hefesto analyze --output json`. Read-only, no network |
| `version` | none | Installed engine version string. Reads no files, no network |

`analyze_local` calls the local engine in-process. Text the engine prints is sent to stderr so stdout stays the MCP stream. That redirect is held under a lock: two overlapping calls cannot restore the real stdout while the other call is still printing. The scan does not read `.hefesto.yaml`.

Startup sets `HEFESTO_TELEMETRY=0` for this process. The tool path does not call the usage-event sender or the PyPI version check. The machine opt-out file used by `hefesto telemetry disable` is left unchanged.

## Container

`Dockerfile` at the repository root uses `python:3.12-slim`, installs `hefesto-ai[mcp]==4.20.4`, then runs `hefesto-mcp --help` so a pin that does not provide the command fails the build. It sets `HEFESTO_MCP_ROOT=/workspace` and `HEFESTO_TELEMETRY=0`, and runs `hefesto-mcp` as uid 10001. The image can be built from the next release, once that version is on PyPI.
