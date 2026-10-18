#!/usr/bin/env python3
"""Check the canonical MCP Registry entry before validate or publish.

Used by ``.github/workflows/mcp-registry.yml``. It never publishes.

The canonical ``server.json`` is the private repository's
``landing-page/server.json``, deployed with the landing page and served at
``https://hefestoai.narapallc.com/server.json``. This public repository's
``server.json`` is never sent to the registry: its description and version
(PyPI) differ from the hosted entry. The registry version tracks the hosted
engine (``changelog.json`` ``latest`` on the landing page), not PyPI, and a
published registry version can never be changed, so a version that is
already in the registry is an error in publish mode.

There is no ``packages`` entry: a PyPI package entry needs a decision from
the owner and an ``mcp-name:`` line in the README. Until then the entry is a
remote (streamable-http) only.

Usage::

    python scripts/check_mcp_registry_entry.py server.json \
        --expected-version 4.20.1 --mode dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

SCHEMA_URL = "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json"
SERVER_NAME = "io.github.artvepa80/hefestoai"
DESCRIPTION = "HefestoAI checks AI-generated code before you ship it."
PUBLIC_REPOSITORY_URL = "https://github.com/artvepa80/Agents-Hefesto"
REMOTE_TYPE = "streamable-http"
REMOTE_URL = "https://hefestoai.narapallc.com/api/mcp-protocol"
CANONICAL_URL = "https://hefestoai.narapallc.com/server.json"
HOSTED_CHANGELOG_URL = "https://hefestoai.narapallc.com/changelog.json"
REGISTRY_BASE = "https://registry.modelcontextprotocol.io"
TIMEOUT_SECONDS = 90


def _expected_fields(expected_version: str) -> List[Tuple[str, Tuple[str, ...], str]]:
    """(label, key path, expected value) for the exact-match fields."""
    return [
        ("$schema", ("$schema",), SCHEMA_URL),
        ("name", ("name",), SERVER_NAME),
        ("description", ("description",), DESCRIPTION),
        ("repository.url", ("repository", "url"), PUBLIC_REPOSITORY_URL),
        ("version", ("version",), expected_version),
    ]


def _lookup(document: dict, path: Tuple[str, ...]) -> object:
    value: object = document
    for key in path:
        value = value.get(key) if isinstance(value, dict) else None
    return value


def _remote_errors(remotes: object) -> List[str]:
    if not isinstance(remotes, list) or len(remotes) != 1:
        return ["remotes must hold exactly one entry"]
    first = remotes[0] if isinstance(remotes[0], dict) else {}
    if (first.get("type"), first.get("url")) != (REMOTE_TYPE, REMOTE_URL):
        return [f"remotes[0] must be {REMOTE_TYPE} at {REMOTE_URL}"]
    return []


def check_document(document: dict, expected_version: str) -> List[str]:
    """Field checks without network access."""
    errors = [
        f"{label} is {_lookup(document, path)!r}, expected {expected!r}"
        for label, path, expected in _expected_fields(expected_version)
        if _lookup(document, path) != expected
    ]
    if "packages" in document:
        errors.append("packages is not allowed (PyPI entry needs the owner's decision)")
    return errors + _remote_errors(document.get("remotes"))


def check_hosted_version(document: dict, hosted_latest: str) -> List[str]:
    """The registry version must equal the hosted engine version."""
    version = document.get("version")
    if version != hosted_latest:
        return [f"version {version!r} does not match the hosted engine {hosted_latest!r}"]
    return []


def check_not_published(version: str, published: Iterable[str]) -> List[str]:
    """Registry versions are immutable: never try to publish one twice."""
    if version in set(published):
        return [f"version {version} is already in the MCP Registry (versions are immutable)"]
    return []


def _get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # nosec B310
        return json.loads(response.read().decode("utf-8"))


def fetch_hosted_latest(url: str = HOSTED_CHANGELOG_URL) -> str:
    return str(_get_json(url)["latest"])


def fetch_published_versions(name: str = SERVER_NAME, base: str = REGISTRY_BASE) -> List[str]:
    """Versions of ``name`` already in the registry (empty when it has none)."""
    url = f"{base}/v0/servers/{urllib.parse.quote(name, safe='')}/versions"
    try:
        page = _get_json(url)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return []
        raise
    return [str(item.get("server", {}).get("version")) for item in page.get("servers", [])]


def network_findings(version: str, mode: str) -> Tuple[List[str], List[str]]:
    """(errors, warnings) from the hosted engine and the registry."""
    document_version = {"version": version}
    errors = check_hosted_version(document_version, fetch_hosted_latest())
    already = check_not_published(version, fetch_published_versions())
    if mode == "publish":
        return errors + already, []
    return errors, already


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("server_json", type=Path)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--mode", choices=("dry-run", "publish"), default="dry-run")
    parser.add_argument("--offline", action="store_true", help="skip the network checks")
    args = parser.parse_args(argv)

    document = json.loads(args.server_json.read_text(encoding="utf-8"))
    errors = check_document(document, args.expected_version)
    warnings: List[str] = []
    if not args.offline:
        more_errors, warnings = network_findings(str(document.get("version")), args.mode)
        errors += more_errors
    for line in [f"WARNING: {w}" for w in warnings] + [f"ERROR: {e}" for e in errors]:
        print(line)
    if errors:
        return 1
    print(f"OK: {SERVER_NAME} {args.expected_version} ({args.mode})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
