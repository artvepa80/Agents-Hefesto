"""``--experimental`` and ``experimental:`` in .hefesto.yaml."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from hefesto.cli.main import cli
from hefesto.core import experimental
from hefesto.core.experimental import ExperimentalError, parse

_C_FILES = {
    "src/a.c": "int add(int a, int b) { return a + b; }\n",
    "src/a.h": "int add(int a, int b);\n",
    "src/b.cpp": "namespace n {\nint f(int a) { return a; }\n}\n",
    "src/b.hpp": "namespace n { int f(int a); }\n",
}
_PY = {"app.py": "def run(x):\n    return eval(x)\n"}


def _tree(root: Path, files: dict) -> Path:
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    return root


def _run(path: Path, *args: str, cwd: Path | None = None):
    # .hefesto.yaml is found from the analyzed path, so ``cwd`` is informational.
    runner = CliRunner(mix_stderr=False) if _mix_ok() else CliRunner()
    return runner.invoke(cli, ["analyze", str(path), *args], catch_exceptions=False)


def _mix_ok() -> bool:
    import inspect

    return "mix_stderr" in inspect.signature(CliRunner.__init__).parameters


def _stable(text: str) -> str:
    data = json.loads(text)
    blob = json.dumps(data, sort_keys=True)
    blob = re.sub(
        r'"(duration[a-z_]*|timestamp|analysis_time[a-z_]*|[a-z_]*_ms)": [^,}]+', "", blob
    )
    return blob.replace(str(Path.cwd()), "<cwd>")


def test_parse_accepts_comma_string_and_list() -> None:
    assert parse("c-cpp")[0] == {"c-cpp"}
    assert parse([" C-CPP "])[0] == {"c-cpp"}
    assert parse(None) == (frozenset(), [])


def test_parse_rejects_unknown_names() -> None:
    with pytest.raises(ExperimentalError, match="unknown experimental feature"):
        parse("c-cpp,nope")


def test_graduated_name_warns(monkeypatch) -> None:
    monkeypatch.setitem(experimental.GRADUATED, "old", "9.9.9")
    enabled, warnings = parse("old")
    assert enabled == frozenset()
    assert warnings and "no longer experimental" in warnings[0]


def test_off_by_default_output_is_unchanged(tmp_path: Path) -> None:
    """Without the option, C and C++ files are not found: the report of a tree
    with them equals the report of the same tree without them."""
    with_c = _tree(tmp_path / "with", {**_PY, **_C_FILES})
    without = _tree(tmp_path / "without", dict(_PY))
    a = _run(with_c, "--output", "json", "--quiet")
    b = _run(without, "--output", "json", "--quiet")
    assert a.exit_code == b.exit_code
    assert _stable(a.stdout.replace(str(with_c), "<p>")) == _stable(
        b.stdout.replace(str(without), "<p>")
    )
    assert '"experimental"' not in a.stdout
    sarif = _run(with_c, "--output", "sarif", "--quiet")
    assert '"experimental"' not in sarif.stdout and "a.c" not in sarif.stdout


def test_on_reports_meta_and_sarif_property(tmp_path: Path) -> None:
    pytest.importorskip("tree_sitter_language_pack")
    root = _tree(tmp_path, {**_PY, **_C_FILES})
    out = _run(root, "--experimental", "c-cpp", "--output", "json", "--quiet")
    data = json.loads(out.stdout)
    assert data["meta"]["experimental"] == ["c-cpp"]
    langs = {f["language"] for f in data["files"]}
    assert {"c", "cpp", "python"} <= langs
    sarif = json.loads(_run(root, "--experimental", "c-cpp", "--output", "sarif").stdout)
    assert sarif["runs"][0]["properties"] == {"experimental": ["c-cpp"]}


def test_unknown_cli_name_exits_2(tmp_path: Path) -> None:
    root = _tree(tmp_path, _PY)
    result = _run(root, "--experimental", "c-cpp,bogus")
    assert result.exit_code == 2
    assert "unknown experimental feature(s): bogus" in (result.stderr or result.output)


def test_unknown_config_name_exits_2(tmp_path: Path) -> None:
    root = _tree(tmp_path, _PY)
    (root / ".hefesto.yaml").write_text("experimental: [bogus]\n")
    result = _run(root, cwd=root)
    assert result.exit_code == 2


def test_config_list_turns_features_on(tmp_path: Path) -> None:
    pytest.importorskip("tree_sitter_language_pack")
    root = _tree(tmp_path, {**_PY, **_C_FILES})
    (root / ".hefesto.yaml").write_text("experimental:\n  - c-cpp\n")
    data = json.loads(_run(root, "--output", "json", "--quiet", cwd=root).stdout)
    assert data["meta"]["experimental"] == ["c-cpp"]


def test_cli_list_replaces_config_list(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setitem(experimental.FEATURES, "other", "test only")
    root = _tree(tmp_path, {**_PY, **_C_FILES})
    (root / ".hefesto.yaml").write_text("experimental: [c-cpp]\n")
    data = json.loads(
        _run(root, "--experimental", "other", "--output", "json", "--quiet", cwd=root).stdout
    )
    assert data["meta"]["experimental"] == ["other"]
    assert not {"c", "cpp"} & {f["language"] for f in data["files"]}


def test_mcp_and_library_engine_are_off() -> None:
    from hefesto.core.analyzer_engine import AnalyzerEngine

    assert AnalyzerEngine(severity_threshold="LOW", quiet=True).experimental == frozenset()
