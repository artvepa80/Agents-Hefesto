"""Local stdio adapter for the Hefesto engine.

Read-only. The sandbox root is ``--root``, then ``HEFESTO_MCP_ROOT``, then
the working directory. Startup sets ``HEFESTO_TELEMETRY=0``. Analysis does
not open network connections.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import sys
import threading
from collections.abc import Callable, Mapping
from pathlib import Path

from hefesto.__version__ import __version__

_LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
_ROOT: Path | None = None
# redirect_stdout replaces process-wide sys.stdout. Overlapping calls would
# restore the real stdout while the other call is still printing.
_ENGINE_STDOUT_LOCK = threading.Lock()


def _disable_telemetry() -> None:
    """Force the CLI opt-out so this process cannot send usage events."""
    os.environ["HEFESTO_TELEMETRY"] = "0"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hefesto-mcp")
    parser.add_argument("--root", default=None, help="Directory the tools may read")
    return parser


def _explicit_root(argv: list[str], env: Mapping[str, str]) -> str | None:
    chosen = _parser().parse_args(argv).root
    if isinstance(chosen, str) and chosen.strip():
        return chosen.strip()
    from_env = env.get("HEFESTO_MCP_ROOT", "").strip()
    return from_env or None


def _reject_broad_root(root: Path) -> None:
    hint = "set HEFESTO_MCP_ROOT or pass --root"
    if root == Path(root.anchor).resolve():
        raise ValueError(f"sandbox root cannot be the filesystem root; {hint}")
    if root == Path.home().resolve():
        raise ValueError(f"sandbox root cannot be the home directory; {hint}")


def resolve_sandbox_root(
    argv: list[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> Path:
    """Resolve the sandbox root. ``--root`` wins, then the env var, then cwd."""
    arguments = [] if argv is None else argv
    values = os.environ if env is None else env
    chosen = _explicit_root(arguments, values)
    root = Path.cwd().resolve() if chosen is None else Path(chosen).resolve()
    _reject_broad_root(root)
    return root


def prepare_startup(argv: list[str]) -> Path:
    """Disable telemetry and install the sandbox root. Does not serve."""
    global _ROOT
    _disable_telemetry()
    root = resolve_sandbox_root(argv)
    _ROOT = root
    return root


def current_root() -> Path:
    if _ROOT is not None:
        return _ROOT
    return resolve_sandbox_root([])


def _anchored(path: str, root: Path) -> Path:
    """Join a relative path to ``root``. Absolute paths stay absolute."""
    raw = Path(path)
    if raw.is_absolute():
        return raw
    return root / raw


def resolve_inside_root(path: str, root: Path | None = None) -> Path:
    """Resolve ``path`` against the sandbox root and reject anything outside it."""
    base = (root if root is not None else current_root()).resolve()
    resolved = _anchored(path, base).resolve()
    if not resolved.is_relative_to(base) or _symlink_escapes(path, base):
        raise ValueError(f"path is outside the sandbox root: {path}")
    return resolved


def _symlink_escapes(path: str, root: Path) -> bool:
    raw = Path(path)
    cursor = Path(raw.anchor) if raw.is_absolute() else root
    parts = raw.parts[1:] if raw.is_absolute() else raw.parts
    for part in parts:
        cursor = cursor / part
        if _linked_outside(cursor, root):
            return True
    return False


def _linked_outside(cursor: Path, root: Path) -> bool:
    return cursor.is_symlink() and not cursor.resolve().is_relative_to(root)


def _severity(severity: str | None) -> str:
    level = (severity or "MEDIUM").upper()
    if level not in _LEVELS:
        raise ValueError("severity must be LOW, MEDIUM, HIGH, or CRITICAL")
    return level


def _run_engine(target: Path, level: str) -> str:
    """Run the local engine. Its prints go to stderr so stdout stays MCP.

    The redirect is serialized. Two calls at once would otherwise restore
    the real stdout under the call that is still printing.
    """
    from hefesto.cli.main import (
        _apply_line_suppressions,
        _generate_report,
        _run_analysis_loop,
        _setup_analyzer_engine,
    )
    from hefesto.reports.json_reporter import JSONReporter

    # These helpers do not call telemetry or the PyPI version check.
    # Those run only from the CLI ``analyze`` command, which is not used here.
    with _ENGINE_STDOUT_LOCK, contextlib.redirect_stdout(sys.stderr):
        engine = _setup_analyzer_engine(level, quiet=True, json_mode=True)
        if engine is None:
            raise RuntimeError("analyzer engine failed to start")
        file_results, total_loc, total_duration, source_cache = _run_analysis_loop(
            engine, [str(target)], []
        )
        _apply_line_suppressions(file_results, source_cache)
        report = _generate_report(file_results, total_loc, total_duration, "json", None)
    return JSONReporter().generate(report)


def analyze_local(path: str, severity: str | None = None) -> str:
    """Analyze a file or directory with the local engine and return JSON.

    Runs the same local checks as ``hefesto analyze`` (security, complexity,
    and the formats that engine registers). ``path`` must resolve inside the
    sandbox root (``HEFESTO_MCP_ROOT`` or ``--root``). A relative path is
    joined to that root, not to the process working directory. ``severity``
    must be one of LOW, MEDIUM, HIGH, or CRITICAL (default MEDIUM). The
    result is the JSON report. Read-only: it writes no files.
    It uses no network.
    """
    _disable_telemetry()
    target = resolve_inside_root(path)
    return _run_engine(target, _severity(severity))


def version() -> str:
    """Return the installed engine version string.

    No args. Reads no files and uses no network.
    Use it to confirm which engine produced a result.
    """
    return __version__


async def _call_on_worker(fn: Callable[..., str], *args: object) -> str:
    """Run a sync tool off the stdio event loop.

    FastMCP calls a synchronous tool on the loop thread. A directory scan
    would block the session until it returned.
    """
    import anyio

    return await anyio.to_thread.run_sync(fn, *args)


async def _analyze_local_tool(path: str, severity: str | None = None) -> str:
    return await _call_on_worker(analyze_local, path, severity)


async def _version_tool() -> str:
    return await _call_on_worker(version)


_analyze_local_tool.__doc__ = analyze_local.__doc__
_version_tool.__doc__ = version.__doc__


def build_server():
    """FastMCP server with the two read-only tools. Requires the mcp extra."""
    from mcp.server.fastmcp import FastMCP
    from mcp.types import ToolAnnotations

    hints = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        openWorldHint=False,
    )
    server = FastMCP("hefesto")
    server.add_tool(_analyze_local_tool, name="analyze_local", annotations=hints)
    server.add_tool(_version_tool, name="version", annotations=hints)
    return server


def main(argv: list[str] | None = None) -> None:
    """Run the stdio server."""
    raw = sys.argv[1:] if argv is None else argv
    try:
        prepare_startup(raw)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
