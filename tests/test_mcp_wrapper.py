"""Metadata-only ``hefesto-mcp`` wrapper and its wheel."""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "packaging" / "hefesto-mcp"
MCP_NAME_LINE = "<!-- mcp-name: io.github.artvepa80/hefestoai -->"


def _load_toml(path: Path) -> dict:
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib
    with path.open("rb") as handle:
        return tomllib.load(handle)


def test_wrapper_metadata_matches_the_engine_release():
    engine = _load_toml(ROOT / "pyproject.toml")
    wrapper = _load_toml(WRAPPER / "pyproject.toml")
    version = engine["project"]["version"]
    project = wrapper["project"]
    assert project["name"] == "hefesto-mcp"
    assert project["version"] == "4.20.5"
    assert project["version"] == version
    assert project["requires-python"] == ">=3.10"
    assert project["license"] == "MIT"
    assert project["readme"] == "README.md"
    assert project["dependencies"] == [f"hefesto-ai[mcp]=={version}"]
    assert project["scripts"] == {"hefesto-mcp": "hefesto.mcp_server:main"}
    assert wrapper["build-system"]["build-backend"] == "hatchling.build"
    assert wrapper["tool"]["hatch"]["build"]["targets"]["wheel"]["bypass-selection"] is True


def test_wrapper_readme_has_the_mcp_name_line():
    lines = (WRAPPER / "README.md").read_text(encoding="utf-8").splitlines()
    assert MCP_NAME_LINE in lines


def test_root_readme_has_the_mcp_name_line():
    lines = (ROOT / "README.md").read_text(encoding="utf-8").splitlines()
    assert MCP_NAME_LINE in lines


def test_wrapper_wheel_has_the_script_and_no_python_modules(tmp_path):
    pytest.importorskip("build")
    out = tmp_path / "dist"
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(out), str(WRAPPER)],
        check=True,
        cwd=tmp_path,
        timeout=180,
    )
    wheels = list(out.glob("*.whl"))
    assert len(wheels) == 1
    with zipfile.ZipFile(wheels[0]) as archive:
        names = archive.namelist()
        python_modules = [
            name for name in names if name.endswith(".py") and ".dist-info/" not in name
        ]
        assert python_modules == []
        entries = [name for name in names if name.endswith(".dist-info/entry_points.txt")]
        assert len(entries) == 1
        text = archive.read(entries[0]).decode("utf-8")
        assert "hefesto-mcp = hefesto.mcp_server:main" in text
        metadata = archive.read(
            next(name for name in names if name.endswith(".dist-info/METADATA"))
        ).decode("utf-8")
    assert "Requires-Dist: hefesto-ai[mcp]==4.20.5" in metadata
    assert "Requires-Python: >=3.10" in metadata
