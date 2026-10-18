"""The MCP Registry entry check accepts only the canonical hosted entry.

No network: the hosted version and the registry versions are passed in or
monkeypatched. Nothing here publishes.
"""

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "check_mcp_registry_entry.py"

CANONICAL = {
    "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
    "name": "io.github.artvepa80/hefestoai",
    "title": "HefestoAI",
    "description": "HefestoAI checks AI-generated code before you ship it.",
    "version": "4.20.1",
    "websiteUrl": "https://hefestoai.narapallc.com",
    "repository": {
        "url": "https://github.com/artvepa80/Agents-Hefesto",
        "source": "github",
        "id": "1079896229",
    },
    "remotes": [
        {"type": "streamable-http", "url": "https://hefestoai.narapallc.com/api/mcp-protocol"}
    ],
}


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("check_mcp_registry_entry", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_mcp_registry_entry"] = module
    spec.loader.exec_module(module)
    return module


def test_canonical_entry_passes(mod):
    assert mod.check_document(CANONICAL, "4.20.1") == []


def test_public_server_json_is_rejected(mod):
    public = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
    errors = mod.check_document(public, public["version"])
    assert any("description" in error for error in errors)


@pytest.mark.parametrize(
    "mutate, needle",
    [
        (lambda d: d.update(description="Release-truth gate."), "description"),
        (lambda d: d["repository"].update(url="https://github.com/x/private"), "repository.url"),
        (lambda d: d.update(packages=[{"registryType": "pypi"}]), "packages"),
        (lambda d: d["remotes"][0].update(type="sse"), "remotes[0]"),
        (lambda d: d["remotes"][0].update(url="https://example.com/mcp"), "remotes[0]"),
        (lambda d: d["remotes"].append(dict(d["remotes"][0])), "exactly one"),
        (lambda d: d.update(name="io.github.artvepa80/other"), "name"),
        (lambda d: d.update(version="4.20.2"), "version"),
    ],
)
def test_each_constraint_is_enforced(mod, mutate, needle):
    document = copy.deepcopy(CANONICAL)
    mutate(document)
    errors = mod.check_document(document, "4.20.1")
    assert any(needle in error for error in errors), errors


def test_version_must_match_hosted_engine(mod):
    assert mod.check_hosted_version(CANONICAL, "4.20.1") == []
    assert mod.check_hosted_version(CANONICAL, "4.20.2")


def test_published_version_is_never_republished(mod):
    assert mod.check_not_published("4.20.1", ["4.19.0", "4.17.0"]) == []
    assert "immutable" in mod.check_not_published("4.19.0", ["4.19.0"])[0]


def _run(mod, tmp_path, monkeypatch, *, published, hosted="4.20.1", mode="dry-run"):
    path = tmp_path / "server.json"
    path.write_text(json.dumps(CANONICAL), encoding="utf-8")
    monkeypatch.setattr(mod, "fetch_hosted_latest", lambda: hosted)
    monkeypatch.setattr(mod, "fetch_published_versions", lambda: published)
    return mod.main([str(path), "--expected-version", "4.20.1", "--mode", mode])


def test_dry_run_only_warns_on_an_existing_version(mod, tmp_path, monkeypatch, capsys):
    assert _run(mod, tmp_path, monkeypatch, published=["4.20.1"]) == 0
    assert "WARNING" in capsys.readouterr().out


def test_publish_mode_fails_on_an_existing_version(mod, tmp_path, monkeypatch):
    assert _run(mod, tmp_path, monkeypatch, published=["4.20.1"], mode="publish") == 1


def test_publish_mode_passes_for_a_new_hosted_version(mod, tmp_path, monkeypatch):
    assert _run(mod, tmp_path, monkeypatch, published=["4.19.0"], mode="publish") == 0


def test_hosted_engine_mismatch_fails(mod, tmp_path, monkeypatch):
    assert _run(mod, tmp_path, monkeypatch, published=[], hosted="4.20.2") == 1
