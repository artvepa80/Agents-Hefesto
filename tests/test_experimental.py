"""``--experimental`` and ``experimental:`` in .hefesto.yaml."""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from hefesto.cli.main import cli
from hefesto.core import experimental
from hefesto.core.experimental import ExperimentalError, parse

# Findings only the C#/Go/Rust rules report (a generic check reports none of them).
_RULE_FILES = {
    "src/Load.cs": (
        "using System.Runtime.Serialization.Formatters.Binary;\n"
        "class Load {\n"
        "  object Run(System.IO.Stream s) {\n"
        "    var f = new BinaryFormatter();\n"
        "    return f.Deserialize(s);\n"
        "  }\n"
        "}\n"
    ),
    "src/MyApp.Tests/LoadTests.cs": (
        "using System.Runtime.Serialization.Formatters.Binary;\n"
        "class LoadTests { object R(System.IO.Stream s) {"
        " return new BinaryFormatter().Deserialize(s); } }\n"
    ),
    "cmd/hash.go": (
        'package main\n\nimport "crypto/md5"\n\n'
        "func H(b []byte) [16]byte {\n\treturn md5.Sum(b)\n}\n"
    ),
}
_PY = {"app.py": "def run(x):\n    return eval(x)\n"}
_RULE_TYPES = {"INSECURE_DESERIALIZATION", "INSECURE_CRYPTOGRAPHY", "UNSAFE_CODE"}


def _tree(root: Path, files: dict) -> Path:
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    return root


def _run(path: Path, *args: str):
    # .hefesto.yaml is found from the analyzed path.
    mix = "mix_stderr" in inspect.signature(CliRunner.__init__).parameters
    runner = CliRunner(mix_stderr=False) if mix else CliRunner()
    return runner.invoke(cli, ["analyze", str(path), *args], catch_exceptions=False)


def _types(stdout: str) -> set:
    data = json.loads(stdout)
    return {i["type"] for f in data["files"] for i in f["issues"]}


def test_parse_accepts_comma_string_and_list() -> None:
    assert parse("lang-security")[0] == {"lang-security"}
    assert parse([" LANG-SECURITY "])[0] == {"lang-security"}
    assert parse(None) == (frozenset(), [])


def test_parse_rejects_unknown_names() -> None:
    with pytest.raises(ExperimentalError, match="unknown experimental feature"):
        parse("lang-security,nope")


def test_graduated_name_warns(monkeypatch) -> None:
    monkeypatch.setitem(experimental.GRADUATED, "old", "9.9.9")
    enabled, warnings = parse("old")
    assert enabled == frozenset()
    assert warnings and "no longer experimental" in warnings[0]


def test_off_by_default_rules_do_not_run(tmp_path: Path) -> None:
    pytest.importorskip("tree_sitter_language_pack")
    root = _tree(tmp_path, {**_PY, **_RULE_FILES})
    out = _run(root, "--output", "json", "--quiet", "--severity", "LOW")
    assert not _types(out.stdout) & _RULE_TYPES
    assert '"experimental"' not in out.stdout
    sarif = _run(root, "--output", "sarif", "--quiet", "--severity", "LOW")
    assert '"experimental"' not in sarif.stdout


def test_on_runs_rules_and_reports_meta_and_sarif(tmp_path: Path) -> None:
    pytest.importorskip("tree_sitter_language_pack")
    root = _tree(tmp_path, {**_PY, **_RULE_FILES})
    args = ("--experimental", "lang-security", "--severity", "LOW", "--quiet")
    out = _run(root, *args, "--output", "json")
    data = json.loads(out.stdout)
    assert data["meta"]["experimental"] == ["lang-security"]
    assert {"INSECURE_DESERIALIZATION", "INSECURE_CRYPTOGRAPHY"} <= _types(out.stdout)
    # .NET test projects are skipped by the rules.
    rule_files = {f["file"] for f in data["files"] for i in f["issues"] if i["type"] in _RULE_TYPES}
    assert not any("Tests" in name for name in rule_files)
    sarif = json.loads(_run(root, *args, "--output", "sarif").stdout)
    assert sarif["runs"][0]["properties"] == {"experimental": ["lang-security"]}


def test_unknown_cli_name_exits_2(tmp_path: Path) -> None:
    root = _tree(tmp_path, _PY)
    result = _run(root, "--experimental", "lang-security,bogus")
    assert result.exit_code == 2
    assert "unknown experimental feature(s): bogus" in (result.stderr or result.output)


def test_unknown_config_name_exits_2(tmp_path: Path) -> None:
    root = _tree(tmp_path, _PY)
    (root / ".hefesto.yaml").write_text("experimental: [bogus]\n")
    assert _run(root).exit_code == 2


def test_config_list_turns_features_on(tmp_path: Path) -> None:
    pytest.importorskip("tree_sitter_language_pack")
    root = _tree(tmp_path, {**_PY, **_RULE_FILES})
    (root / ".hefesto.yaml").write_text("experimental:\n  - lang-security\n")
    out = _run(root, "--output", "json", "--quiet", "--severity", "LOW")
    assert json.loads(out.stdout)["meta"]["experimental"] == ["lang-security"]
    assert _types(out.stdout) & _RULE_TYPES


def test_cli_list_replaces_config_list(tmp_path: Path, monkeypatch) -> None:
    pytest.importorskip("tree_sitter_language_pack")
    monkeypatch.setitem(experimental.FEATURES, "other", "test only")
    root = _tree(tmp_path, {**_PY, **_RULE_FILES})
    (root / ".hefesto.yaml").write_text("experimental: [lang-security]\n")
    out = _run(root, "--experimental", "other", "--output", "json", "--quiet", "--severity", "LOW")
    assert json.loads(out.stdout)["meta"]["experimental"] == ["other"]
    assert not _types(out.stdout) & _RULE_TYPES


def test_mcp_and_library_engine_are_off() -> None:
    from hefesto.analyzers.security import SecurityAnalyzer
    from hefesto.core.analyzer_engine import AnalyzerEngine

    engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
    engine.register_analyzer(SecurityAnalyzer())
    assert engine.experimental == frozenset()
    assert engine.analyzers[-1].lang_rules is False
    engine.experimental = {"lang-security"}
    assert engine.analyzers[-1].lang_rules is True


def _stable(text: str) -> str:
    blob = json.dumps(json.loads(text), sort_keys=True)
    return re.sub(r'"(duration[a-z_]*|timestamp|[a-z_]*_ms)": [^,}]+', "", blob)
