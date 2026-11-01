"""Local stdio adapter: imports, path sandbox, version, and one local scan."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "hefesto" / "mcp_server.py"
FORBIDDEN = ("hefesto.api", "hefesto.llm", "hefesto.licensing", "hefesto.omega")


def _imported_modules(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_mcp_server_imports_no_forbidden_modules():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    for name in _imported_modules(tree):
        for banned in FORBIDDEN:
            assert name != banned
            assert not name.startswith(banned + ".")


def test_path_outside_cwd_is_rejected(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("x = 1\n", encoding="utf-8")
    monkeypatch.chdir(work)

    from hefesto.mcp_server import resolve_inside_cwd

    with pytest.raises(ValueError):
        resolve_inside_cwd(str(outside))
    with pytest.raises(ValueError):
        resolve_inside_cwd("../outside.py")

    link = work / "escape.py"
    link.symlink_to(outside)
    with pytest.raises(ValueError):
        resolve_inside_cwd("escape.py")

    inside = work / "ok.py"
    inside.write_text("x = 1\n", encoding="utf-8")
    assert resolve_inside_cwd("ok.py") == inside.resolve()


def test_version_matches_package():
    from hefesto.__version__ import __version__
    from hefesto.mcp_server import version

    assert version() == __version__
    assert version()


def test_analyze_local_on_temp_file(tmp_path, monkeypatch):
    pytest.importorskip("mcp")
    monkeypatch.chdir(tmp_path)
    sample = tmp_path / "sample.py"
    sample.write_text("def add(left, right):\n    return left + right\n", encoding="utf-8")

    def _no_network(*_args, **_kwargs):
        raise AssertionError("network call")

    monkeypatch.setattr("urllib.request.urlopen", _no_network)

    from hefesto.mcp_server import analyze_local, build_server

    payload = json.loads(analyze_local("sample.py", severity="LOW"))
    assert payload["summary"]["files_analyzed"] == 1

    tools = build_server()._tool_manager.list_tools()
    assert sorted(tool.name for tool in tools) == ["analyze_local", "version"]
    for tool in tools:
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.openWorldHint is False
