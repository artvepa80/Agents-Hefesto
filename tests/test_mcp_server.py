"""Local stdio adapter: imports, sandbox root, version, and one local scan."""

from __future__ import annotations

import ast
import asyncio
import json
import os
import shutil
import socket
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
    assert "filesystem root" in capsys.readouterr().err


def test_refuses_home_directory(capsys, monkeypatch):
    from hefesto.mcp_server import main, resolve_sandbox_root

    home = str(Path.home())
    with pytest.raises(ValueError, match="home directory"):
        resolve_sandbox_root(["--root", home])
    monkeypatch.setenv("HEFESTO_MCP_ROOT", home)
    with pytest.raises(SystemExit) as caught:
        main([])
    assert caught.value.code == 2
    assert "home directory" in capsys.readouterr().err


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


def test_version_matches_package():
    from hefesto.__version__ import __version__
    from hefesto.mcp_server import version

    assert version() == __version__
    assert version()


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
