"""server.json is a truthful official-registry entry for the hosted MCP server.

``repository`` stays on this public repo (the hefesto-ai engine ``analyze``
runs). The description states that the hosted MCP server is closed-source and
operated by Narapa LLC. The schema check downloads the official 2025-12-11
schema named by ``$schema``; nothing here publishes to the registry.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "verify_server_json.py"
HOSTED_SENTENCE = "The hosted MCP server is closed-source and operated by Narapa LLC."


def _load_module():
    spec = importlib.util.spec_from_file_location("verify_server_json", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["verify_server_json"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod():
    return _load_module()


@pytest.fixture(scope="module")
def committed(mod):
    return mod.load_server_json(ROOT / "server.json")


@pytest.fixture(scope="module")
def official_schema(mod):
    schema = mod.fetch_schema(mod.OFFICIAL_SCHEMA_URL)
    assert schema["$id"] == mod.OFFICIAL_SCHEMA_URL
    assert schema["$schema"] == mod.SCHEMA_DRAFT
    return schema


def test_description_fits_the_schema_limit(mod):
    assert len(mod.DESCRIPTION) <= mod.DESCRIPTION_MAX_LENGTH
    assert "closed-source" in mod.DESCRIPTION
    assert "Narapa LLC" in mod.DESCRIPTION


def test_committed_document_names_the_public_repo_and_the_closed_server(mod, committed):
    version = mod.read_package_version(ROOT / "pyproject.toml")
    assert version == "4.17.0"
    assert mod.check_document(committed, version) == []
    assert committed["version"] == "4.17.0"
    assert committed["repository"]["url"] == mod.PUBLIC_REPOSITORY_URL
    assert committed["repository"]["id"] == "1079896229"
    assert isinstance(committed["repository"]["id"], str)


def test_public_docs_state_the_hosted_server_is_closed_source():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    discovery = (ROOT / "docs" / "ai-discovery.md").read_text(encoding="utf-8")
    integration = (ROOT / "skill" / "integration.md").read_text(encoding="utf-8")
    for text in (readme, discovery, integration):
        assert HOSTED_SENTENCE in text
    assert "keeps `repository` on this public repository" in readme
    assert "hefesto-ai" in readme


def test_check_document_rejects_a_private_repository(mod, committed):
    document = json.loads(json.dumps(committed))
    document["repository"]["url"] = "https://github.com/artvepa80/Agents-Hefesto-Pro-Private"
    errors = mod.check_document(document, "4.17.0")
    assert any("repository.url" in error for error in errors)


def test_check_document_rejects_a_numeric_repository_id(mod, committed):
    document = json.loads(json.dumps(committed))
    document["repository"]["id"] = 1079896229
    errors = mod.check_document(document, "4.17.0")
    assert any("repository.id" in error for error in errors)


def test_check_document_rejects_a_version_bump(mod, committed):
    errors = mod.check_document(committed, "4.17.1")
    assert any("pyproject.toml" in error for error in errors)


def test_committed_document_validates_against_official_schema(mod, committed, official_schema):
    assert mod.schema_errors(committed, official_schema) == []


def test_schema_rejects_an_overlong_description(mod, committed, official_schema):
    document = json.loads(json.dumps(committed))
    document["description"] = "x" * (mod.DESCRIPTION_MAX_LENGTH + 1)
    errors = mod.schema_errors(document, official_schema)
    assert errors


def test_schema_rejects_a_numeric_repository_id(mod, committed, official_schema):
    document = json.loads(json.dumps(committed))
    document["repository"]["id"] = 1079896229
    errors = mod.schema_errors(document, official_schema)
    assert any("1079896229 is not of type 'string'" in error for error in errors)


def test_repository_url_is_anonymously_cloneable(mod):
    assert mod.anonymous_clone_error(mod.PUBLIC_REPOSITORY_URL) is None
