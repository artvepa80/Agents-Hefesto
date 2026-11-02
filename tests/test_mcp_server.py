"""Local stdio adapter: imports, sandbox root, version, and one local scan."""

from __future__ import annotations

import ast
import asyncio
import json
import os
import shutil
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "hefesto" / "mcp_server.py"
FORBIDDEN = ("hefesto.api", "hefesto.llm", "hefesto.licensing", "hefesto.omega")


@pytest.fixture(autouse=True)
def _reset_sandbox(monkeypatch):
    import hefesto.mcp_server as mcp_server

    monkeypatch.setattr(mcp_server, "_ROOT", None)
    monkeypatch.delenv("HEFESTO_MCP_ROOT", raising=False)
    monkeypatch.delenv("HEFESTO_TELEMETRY", raising=False)


def _imported_modules(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_mcp_server_imports_no_forbidden_modules():
    source = SOURCE.read_text(encoding="utf-8")
    assert "startswith" not in source
    tree = ast.parse(source)
    for name in _imported_modules(tree):
        for banned in FORBIDDEN:
            assert name != banned
            assert not name.startswith(banned + ".")


def test_root_from_flag(tmp_path, monkeypatch):
    from hefesto.mcp_server import resolve_sandbox_root

    proj = tmp_path / "proj"
    proj.mkdir()
    monkeypatch.chdir(tmp_path)
    assert resolve_sandbox_root(["--root", "proj"]) == proj.resolve()


def test_root_from_env(tmp_path, monkeypatch):
    from hefesto.mcp_server import resolve_sandbox_root

    proj = tmp_path / "proj"
    proj.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HEFESTO_MCP_ROOT", str(proj))
    assert resolve_sandbox_root([]) == proj.resolve()


def test_flag_overrides_env(tmp_path, monkeypatch):
    from hefesto.mcp_server import resolve_sandbox_root

    chosen = tmp_path / "chosen"
    other = tmp_path / "other"
    chosen.mkdir()
    other.mkdir()
    monkeypatch.setenv("HEFESTO_MCP_ROOT", str(other))
    assert resolve_sandbox_root(["--root", str(chosen)]) == chosen.resolve()


def test_root_falls_back_to_cwd(tmp_path, monkeypatch):
    from hefesto.mcp_server import resolve_sandbox_root

    monkeypatch.chdir(tmp_path)
    assert resolve_sandbox_root([]) == tmp_path.resolve()


def test_refuses_filesystem_root(capsys):
    from hefesto.mcp_server import main, resolve_sandbox_root

    with pytest.raises(ValueError, match="filesystem root"):
        resolve_sandbox_root(["--root", "/"])
    with pytest.raises(SystemExit) as caught:
        main(["--root", "/"])
    assert caught.value.code == 2
    err = capsys.readouterr().err
    assert "filesystem root" in err
    assert "HEFESTO_MCP_ROOT" in err
    assert "--root" in err


def test_refuses_home_directory(capsys, monkeypatch):
    from hefesto.mcp_server import main, resolve_sandbox_root

    home = str(Path.home())
    with pytest.raises(ValueError, match="home directory"):
        resolve_sandbox_root(["--root", home])
    monkeypatch.setenv("HEFESTO_MCP_ROOT", home)
    with pytest.raises(SystemExit) as caught:
        main([])
    assert caught.value.code == 2
    err = capsys.readouterr().err
    assert "home directory" in err
    assert "HEFESTO_MCP_ROOT" in err
    assert "--root" in err


def test_path_outside_root_is_rejected(tmp_path, monkeypatch):
    from hefesto.mcp_server import resolve_inside_root

    work = tmp_path / "work"
    work.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("x = 1\n", encoding="utf-8")
    sibling = tmp_path / "work-evil"
    sibling.mkdir()
    sibling_file = sibling / "x.py"
    sibling_file.write_text("x = 1\n", encoding="utf-8")
    monkeypatch.chdir(work)

    with pytest.raises(ValueError):
        resolve_inside_root(str(outside), root=work)
    with pytest.raises(ValueError):
        resolve_inside_root("../outside.py", root=work)
    with pytest.raises(ValueError):
        resolve_inside_root(str(sibling_file), root=work)

    link = work / "escape.py"
    link.symlink_to(outside)
    with pytest.raises(ValueError):
        resolve_inside_root("escape.py", root=work)

    inside = work / "ok.py"
    inside.write_text("x = 1\n", encoding="utf-8")
    assert resolve_inside_root("ok.py", root=work) == inside.resolve()


def test_relative_path_joins_the_sandbox_root_not_cwd(tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    app = proj / "src" / "app.py"
    app.parent.mkdir(parents=True)
    app.write_text("x = 1\n", encoding="utf-8")
    outside = tmp_path / "outside.py"
    outside.write_text("x = 1\n", encoding="utf-8")
    link = proj / "escape.py"
    link.symlink_to(outside)
    monkeypatch.chdir("/")
    monkeypatch.setenv("HEFESTO_MCP_ROOT", str(proj))

    from hefesto.mcp_server import analyze_local, prepare_startup, resolve_inside_root

    assert prepare_startup([]) == proj.resolve()
    assert resolve_inside_root("src/app.py") == app.resolve()
    payload = json.loads(analyze_local("src/app.py", severity="LOW"))
    assert payload["summary"]["files_analyzed"] == 1
    with pytest.raises(ValueError):
        resolve_inside_root("/etc/passwd")
    with pytest.raises(ValueError):
        resolve_inside_root("../etc/passwd")
    with pytest.raises(ValueError):
        resolve_inside_root("escape.py")


def test_sync_tools_run_off_the_event_loop(monkeypatch):
    pytest.importorskip("anyio")
    import contextlib

    import hefesto.mcp_server as mcp_server

    saw = {"thread": None, "ticks": 0, "result": None, "loop": None}

    def slow(_path, _severity=None):
        import time

        saw["thread"] = threading.get_ident()
        time.sleep(0.2)
        return "ok"

    monkeypatch.setattr(mcp_server, "analyze_local", slow)

    async def _run():
        saw["loop"] = threading.get_ident()

        async def _tick():
            while True:
                await asyncio.sleep(0.02)
                saw["ticks"] += 1

        ticker = asyncio.create_task(_tick())
        try:
            saw["result"] = await mcp_server._analyze_local_tool("src/app.py")
        finally:
            ticker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await ticker

    asyncio.run(_run())
    assert saw["result"] == "ok"
    assert saw["thread"] not in (None, saw["loop"])
    assert saw["ticks"] >= 2


def test_version_matches_package():
    from hefesto.__version__ import __version__
    from hefesto.mcp_server import version

    assert version() == __version__
    assert version()
    text = version.__doc__ or ""
    assert "installed engine version string" in text
    assert "No args" in text
    assert "Reads no files" in text
    assert "no network" in text
    assert "which engine produced a result" in text


def test_analyze_local_docstring_states_the_contract():
    from hefesto.mcp_server import analyze_local

    text = analyze_local.__doc__ or ""
    assert "HEFESTO_MCP_ROOT" in text
    assert "--root" in text
    for level in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
        assert level in text
    assert "JSON" in text
    assert "Read-only" in text
    assert "no network" in text


def test_startup_forces_telemetry_off(tmp_path, monkeypatch):
    from hefesto.mcp_server import prepare_startup

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HEFESTO_TELEMETRY", "1")
    assert prepare_startup([]) == tmp_path.resolve()
    assert os.environ["HEFESTO_TELEMETRY"] == "0"


def test_analyze_local_does_not_use_network(tmp_path, monkeypatch):
    import urllib.request

    import hefesto.telemetry.client as telemetry

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HEFESTO_TELEMETRY", "1")
    sample = tmp_path / "sample.py"
    sample.write_text("def add(left, right):\n    return left + right\n", encoding="utf-8")

    def _blocked(*_args, **_kwargs):
        raise AssertionError("network call")

    monkeypatch.setattr(urllib.request, "urlopen", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(telemetry, "capture", _blocked)
    monkeypatch.setattr(telemetry, "refresh_latest_version", _blocked)

    from hefesto.mcp_server import analyze_local

    payload = json.loads(analyze_local("sample.py", severity="LOW"))
    assert payload["summary"]["files_analyzed"] == 1
    assert os.environ["HEFESTO_TELEMETRY"] == "0"


def _read_fd(fd: int) -> bytes:
    os.set_blocking(fd, False)
    chunks: list[bytes] = []
    while True:
        try:
            chunk = os.read(fd, 4096)
        except BlockingIOError:
            return b"".join(chunks)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def test_concurrent_engine_prints_do_not_reach_fd_1(monkeypatch):
    """Two overlapping scans must not write engine text to the real stdout fd."""
    import hefesto.cli.main as cli
    from hefesto.mcp_server import _run_engine
    from hefesto.reports.json_reporter import JSONReporter

    def _printing_setup(*_args, **_kwargs):
        print("engine-text")
        time.sleep(0.05)
        print("engine-text")
        return object()

    def _printing_loop(*_args, **_kwargs):
        print("engine-text")
        return [], 0, 0.0, {}

    def _printing(*_args, **_kwargs):
        print("engine-text")

    monkeypatch.setattr(cli, "_setup_analyzer_engine", _printing_setup)
    monkeypatch.setattr(cli, "_run_analysis_loop", _printing_loop)
    monkeypatch.setattr(cli, "_apply_line_suppressions", _printing)
    monkeypatch.setattr(cli, "_generate_report", _printing)
    monkeypatch.setattr(JSONReporter, "generate", lambda self, report: "{}")

    read_fd, write_fd = os.pipe()
    saved = os.dup(1)
    os.dup2(write_fd, 1)
    os.close(write_fd)
    errors: list[BaseException] = []

    def _call() -> None:
        try:
            assert _run_engine(Path("."), "MEDIUM") == "{}"
        except BaseException as exc:
            errors.append(exc)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(_call) for _ in range(2)]
            for future in futures:
                future.result(timeout=5)
        assert errors == []
        assert _read_fd(read_fd) == b""
    finally:
        os.dup2(saved, 1)
        os.close(saved)
        os.close(read_fd)


def _hefesto_mcp_executable() -> str:
    pytest.importorskip("mcp")
    local_bin = str(Path.home() / ".local" / "bin")
    search = os.pathsep.join([local_bin, os.environ.get("PATH", "")])
    found = shutil.which("hefesto-mcp", path=search)
    if found is None:
        pytest.skip("hefesto-mcp is not installed")
    return found


def test_stdio_analyze_local(tmp_path):
    command = _hefesto_mcp_executable()
    sample = tmp_path / "sample.py"
    sample.write_text("def add(left, right):\n    return left + right\n", encoding="utf-8")
    text = asyncio.run(_stdio_analyze(command, tmp_path))
    payload = json.loads(text)
    assert payload["summary"]["files_analyzed"] == 1


async def _stdio_analyze(command: str, root: Path) -> str:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    env = os.environ.copy()
    env["HEFESTO_TELEMETRY"] = "1"
    env.pop("HEFESTO_MCP_ROOT", None)
    params = StdioServerParameters(
        command=command,
        args=["--root", str(root)],
        cwd=root,
        env=env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            names = sorted(tool.name for tool in listed.tools)
            assert names == ["analyze_local", "version"]
            result = await session.call_tool(
                "analyze_local",
                {"path": "sample.py", "severity": "LOW"},
            )
    assert result.isError is False
    assert result.content
    return result.content[0].text
