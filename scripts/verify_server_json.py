#!/usr/bin/env python3
"""Validate server.json against the official MCP registry schema.

The schema URL is the registry's current released schema (not the in-repo
draft). Confirmed 2026-10-15:

- ``CurrentSchemaVersion`` in ``modelcontextprotocol/registry``
  ``pkg/model/constants.go`` is ``2025-12-11``.
- The newest directory under ``modelcontextprotocol/static`` ``schemas/``
  is ``2025-12-11``.

This script does not publish to the registry. ``version`` must keep matching
``pyproject.toml`` (4.17.1 at the time of writing). The live registry entry
is updated only by a separate publish, which this check never performs.

``repository`` stays on this public repository because it contains the
``hefesto-ai`` engine that the hosted ``analyze`` tool runs. The hosted MCP
server itself is closed-source and operated by Narapa LLC; that fact is in
``description`` (schema maxLength 100). ``repository.subfolder`` is omitted:
the schema uses it for a server that lives in a monorepo path, and the MCP
server is not in this repository.
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from jsonschema import Draft7Validator, FormatChecker

# Official released schema. Do not point $schema at the registry repo's draft.
OFFICIAL_SCHEMA_URL = "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json"
SCHEMA_DRAFT = "http://json-schema.org/draft-07/schema#"

SERVER_NAME = "io.github.artvepa80/hefestoai"
# 90 characters. server.schema.json ServerDetail.description maxLength is 100.
DESCRIPTION = (
    "Release-truth gate for AI-generated code. Hosted MCP server is closed-source (Narapa LLC)."
)
PUBLIC_REPOSITORY_URL = "https://github.com/artvepa80/Agents-Hefesto"
# GitHub database id from `gh api repos/artvepa80/Agents-Hefesto --jq .id`.
# The schema types `repository.id` as a string; a JSON number is invalid.
REPOSITORY_ID = "1079896229"
REMOTE_URL = "https://hefestoai.narapallc.com/api/mcp-protocol"
DESCRIPTION_MAX_LENGTH = 100


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def read_package_version(pyproject_path: Path) -> str:
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]
    with pyproject_path.open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def load_server_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check_document(document: dict, package_version: str) -> list[str]:
    """Field checks that do not use the network.

    The JSON Schema pass is separate so a unit test can reject a dishonest
    document without downloading the schema.
    """
    errors: list[str] = []
    if document.get("$schema") != OFFICIAL_SCHEMA_URL:
        errors.append(f"$schema must be {OFFICIAL_SCHEMA_URL}")
    if document.get("name") != SERVER_NAME:
        errors.append(f"name must be {SERVER_NAME}")
    if document.get("description") != DESCRIPTION:
        errors.append("description must state that the hosted MCP server is closed-source (Narapa)")
    description = document.get("description")
    if isinstance(description, str) and len(description) > DESCRIPTION_MAX_LENGTH:
        errors.append(
            f"description length {len(description)} exceeds schema maxLength {DESCRIPTION_MAX_LENGTH}"
        )
    if document.get("version") != package_version:
        errors.append(
            f"version {document.get('version')!r} must match pyproject.toml {package_version!r}"
        )
    repository = document.get("repository")
    if not isinstance(repository, dict):
        errors.append("repository must be an object")
    else:
        if repository.get("url") != PUBLIC_REPOSITORY_URL:
            errors.append(f"repository.url must be {PUBLIC_REPOSITORY_URL}")
        if repository.get("source") != "github":
            errors.append("repository.source must be github")
        repo_id = repository.get("id")
        if repo_id != REPOSITORY_ID or not isinstance(repo_id, str):
            errors.append(f"repository.id must be the string {REPOSITORY_ID!r}")
        if "subfolder" in repository:
            errors.append(
                "repository.subfolder must be omitted; the MCP server is not in this repository"
            )
    remotes = document.get("remotes")
    expected_remote = {"type": "streamable-http", "url": REMOTE_URL}
    if remotes != [expected_remote]:
        errors.append(f"remotes must be [{expected_remote}]")
    if "packages" in document:
        errors.append("packages must be omitted; hefesto-ai is the engine, not the MCP server")
    return errors


def fetch_schema(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "hefesto-verify-server-json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read()
    except urllib.error.URLError as exc:
        raise RuntimeError(f"failed to fetch {url}: {exc}") from exc
    schema = json.loads(payload)
    if not isinstance(schema, dict):
        raise RuntimeError(f"{url} did not return a JSON object")
    return schema


def schema_errors(document: dict, schema: dict) -> list[str]:
    validator = Draft7Validator(schema, format_checker=FormatChecker())
    found = sorted(validator.iter_errors(document), key=lambda err: list(err.absolute_path))
    messages = []
    for err in found:
        location = "/".join(str(part) for part in err.absolute_path) or "(root)"
        messages.append(f"{location}: {err.message}")
    return messages


def anonymous_clone_error(url: str) -> str | None:
    """``git ls-remote`` with no config and no credential helper.

    A stored token must not make a private repository look public.
    """
    env = {
        "PATH": os.environ.get("PATH", ""),
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "HOME": os.environ.get("HOME", ""),
    }
    try:
        result = subprocess.run(
            ["git", "-c", "credential.helper=", "ls-remote", url, "HEAD"],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"git ls-remote failed for {url}: {exc}"
    if result.returncode != 0 or not result.stdout.strip():
        detail = (result.stderr or result.stdout or "").strip()
        return f"repository.url is not anonymously cloneable ({url}): {detail}"
    return None


def verify(root: Path) -> list[str]:
    document = load_server_json(root / "server.json")
    package_version = read_package_version(root / "pyproject.toml")
    errors = check_document(document, package_version)
    schema = fetch_schema(OFFICIAL_SCHEMA_URL)
    schema_id = schema.get("$id")
    if schema_id != OFFICIAL_SCHEMA_URL:
        errors.append(f"schema $id {schema_id!r} != {OFFICIAL_SCHEMA_URL}")
    if schema.get("$schema") != SCHEMA_DRAFT:
        errors.append(f"schema $schema {schema.get('$schema')!r} != {SCHEMA_DRAFT}")
    errors.extend(schema_errors(document, schema))
    clone_error = anonymous_clone_error(PUBLIC_REPOSITORY_URL)
    if clone_error:
        errors.append(clone_error)
    return errors


def main() -> int:
    root = repo_root()
    print(f"Official MCP registry schema: {OFFICIAL_SCHEMA_URL}")
    print(f"JSON Schema draft: {SCHEMA_DRAFT}")
    print(f"description length: {len(DESCRIPTION)}/{DESCRIPTION_MAX_LENGTH}")
    try:
        errors = verify(root)
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"Verification: FAILED\n  - {exc}")
        return 1
    if errors:
        print("Verification: FAILED")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("Verification: PASSED")
    print(f"  repository: {PUBLIC_REPOSITORY_URL} (id {REPOSITORY_ID})")
    print(f"  remote: {REMOTE_URL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
