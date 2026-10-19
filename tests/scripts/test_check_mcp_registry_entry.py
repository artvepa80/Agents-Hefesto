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


HOSTED_OK = {
    "initialize serverInfo.version": "4.20.1",
    "analyze engine.version": "4.20.1",
    "changelog.json latest": "4.20.1",
}


def test_version_must_match_every_hosted_source(mod):
    assert mod.check_hosted_version(CANONICAL, HOSTED_OK) == []
    for source in HOSTED_OK:
        hosted = dict(HOSTED_OK, **{source: "4.20.2"})
        errors = mod.check_hosted_version(CANONICAL, hosted)
        assert len(errors) == 1 and source in errors[0]


def test_published_version_is_never_republished(mod):
    assert mod.check_not_published("4.20.1", ["4.19.0", "4.17.0"]) == []
    assert "immutable" in mod.check_not_published("4.19.0", ["4.19.0"])[0]


ANALYZE_JSON = {"analyzed": True, "engine": {"name": "hefesto-ai", "version": "4.20.1"}}


def test_engine_version_from_structured_content(mod):
    assert mod.engine_version_from_analyze({"structuredContent": ANALYZE_JSON}) == "4.20.1"


def test_engine_version_from_text_content(mod):
    text = "hefesto-ai 4.20.1 analyzed 1 of 1 file(s).\n\n" + json.dumps(ANALYZE_JSON) + "\ntail"
    result = {"structuredContent": {}, "content": [{"type": "text", "text": text}]}
    assert mod.engine_version_from_analyze(result) == "4.20.1"


def test_engine_version_missing_is_none(mod):
    assert mod.engine_version_from_analyze({"content": [{"type": "text", "text": "x"}]}) is None


def _entry(version, latest):
    meta = {"io.modelcontextprotocol.registry/official": {"isLatest": latest}}
    return {"server": {"version": version}, "_meta": meta}


def test_latest_registry_version(mod):
    assert (
        mod.latest_registry_version([_entry("4.19.0", True), _entry("4.17.0", False)]) == "4.19.0"
    )
    assert mod.latest_registry_version([]) is None


def test_registry_urls_follow_the_v0_1_api(mod, monkeypatch):
    seen = []

    def fake_get_json(url):
        seen.append(url)
        return {"servers": [_entry("4.19.0", True)]}

    monkeypatch.setattr(mod, "_get_json", fake_get_json)
    assert mod.is_published("4.20.2") is True
    assert [e["server"]["version"] for e in mod.fetch_registry_versions()] == ["4.19.0"]
    base = "https://registry.modelcontextprotocol.io/v0.1/servers/io.github.artvepa80%2Fhefestoai"
    assert seen == [
        f"{base}/versions/4.20.2?include_deleted=true",
        f"{base}/versions?include_deleted=true",
    ]


def test_registry_404_means_not_published(mod, monkeypatch):
    def not_found(url):
        raise mod.urllib.error.HTTPError(url, 404, "Not Found", None, None)

    monkeypatch.setattr(mod, "_get_json", not_found)
    assert mod.is_published("4.20.2") is False
    assert mod.fetch_registry_versions() == []


def test_registry_other_errors_propagate(mod, monkeypatch):
    def server_error(url):
        raise mod.urllib.error.HTTPError(url, 503, "Unavailable", None, None)

    monkeypatch.setattr(mod, "_get_json", server_error)
    with pytest.raises(mod.urllib.error.HTTPError):
        mod.is_published("4.20.2")


def _run(mod, tmp_path, monkeypatch, *, published, hosted=None, mode="dry-run", summary=None):
    path = tmp_path / "server.json"
    path.write_text(json.dumps(CANONICAL), encoding="utf-8")
    monkeypatch.setattr(mod, "fetch_hosted_versions", lambda: dict(hosted or HOSTED_OK))
    entries = [_entry(v, i == 0) for i, v in enumerate(published)]
    monkeypatch.setattr(mod, "fetch_registry_versions", lambda: entries)
    monkeypatch.setattr(mod, "is_published", lambda version: version in published)
    argv = [str(path), "--expected-version", "4.20.1", "--mode", mode]
    if summary:
        argv += ["--summary", str(summary)]
    return mod.main(argv)


def test_dry_run_only_warns_on_an_existing_version(mod, tmp_path, monkeypatch, capsys):
    assert _run(mod, tmp_path, monkeypatch, published=["4.20.1"]) == 0
    assert "WARNING" in capsys.readouterr().out


def test_publish_mode_fails_on_an_existing_version(mod, tmp_path, monkeypatch):
    assert _run(mod, tmp_path, monkeypatch, published=["4.20.1"], mode="publish") == 1


def test_publish_mode_passes_for_a_new_hosted_version(mod, tmp_path, monkeypatch):
    assert _run(mod, tmp_path, monkeypatch, published=["4.19.0"], mode="publish") == 0


def test_hosted_engine_mismatch_fails(mod, tmp_path, monkeypatch):
    hosted = dict(HOSTED_OK, **{"analyze engine.version": "4.20.0"})
    assert _run(mod, tmp_path, monkeypatch, published=[], hosted=hosted) == 1


def test_summary_lists_the_version_and_registry_latest(mod, tmp_path, monkeypatch):
    summary = tmp_path / "summary.md"
    assert _run(mod, tmp_path, monkeypatch, published=["4.19.0"], summary=summary) == 0
    text = summary.read_text(encoding="utf-8")
    assert "| to publish | `4.20.1` |" in text
    assert "| registry latest | `4.19.0` |" in text


def test_docstring_example_is_generic(mod):
    assert "--expected-version X.Y.Z" in mod.__doc__
