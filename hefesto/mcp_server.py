"""Local stdio adapter for the Hefesto engine.

Read-only. Analysis runs in-process on the working directory and does not
open network connections. CLI telemetry settings are left unchanged; this
process does not send usage events.
"""

from __future__ import annotations

from pathlib import Path

from hefesto.__version__ import __version__

_LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


def resolve_inside_cwd(path: str) -> Path:
    """Resolve ``path`` and reject anything outside the working directory."""
    cwd = Path.cwd().resolve()
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(cwd) or _symlink_escapes(path, cwd):
        raise ValueError(f"path is outside the current working directory: {path}")
    return resolved


def _symlink_escapes(path: str, cwd: Path) -> bool:
    raw = Path(path)
    absolute = raw.is_absolute()
    cursor = Path(raw.anchor) if absolute else cwd
    parts = raw.parts[1:] if absolute else raw.parts
    for part in parts:
        cursor = cursor / part
        if _linked_outside(cursor, cwd):
            return True
    return False


def _linked_outside(cursor: Path, cwd: Path) -> bool:
    return cursor.is_symlink() and not cursor.resolve().is_relative_to(cwd)


def _severity(severity: str | None) -> str:
    level = (severity or "MEDIUM").upper()
    if level not in _LEVELS:
        raise ValueError("severity must be LOW, MEDIUM, HIGH, or CRITICAL")
    return level


def analyze_local(path: str, severity: str | None = None) -> str:
    """Analyze a path inside the working directory. Returns JSON. Read-only."""
    target = resolve_inside_cwd(path)
    level = _severity(severity)
    from hefesto.cli.main import (
        _apply_line_suppressions,
        _generate_report,
        _run_analysis_loop,
        _setup_analyzer_engine,
    )
    from hefesto.reports.json_reporter import JSONReporter

    engine = _setup_analyzer_engine(level, quiet=True, json_mode=True)
    if engine is None:
        raise RuntimeError("analyzer engine failed to start")
    file_results, total_loc, total_duration, source_cache = _run_analysis_loop(
        engine, [str(target)], []
    )
    _apply_line_suppressions(file_results, source_cache)
    report = _generate_report(file_results, total_loc, total_duration, "json", None)
    return JSONReporter().generate(report)


def version() -> str:
    """Return the engine version."""
    return __version__


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
    server.add_tool(analyze_local, annotations=hints)
    server.add_tool(version, annotations=hints)
    return server


def main() -> None:
    """Run the stdio server."""
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
