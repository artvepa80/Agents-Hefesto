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
from typing import Iterable, List, Optional

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


def check_document(document: dict, expected_version: str) -> List[str]:
    """Field checks without network access."""
    errors: List[str] = []
    if document.get("$schema") != SCHEMA_URL:
        errors.append(f"$schema must be {SCHEMA_URL}")
    if document.get("name") != SERVER_NAME:
        errors.append(f"name must be {SERVER_NAME}")
    if document.get("description") != DESCRIPTION:
        errors.append(f"description must be exactly {DESCRIPTION!r}")
    repository = document.get("repository") or {}
    if repository.get("url") != PUBLIC_REPOSITORY_URL:
        errors.append(f"repository.url must be {PUBLIC_REPOSITORY_URL}")
    if "packages" in document:
        errors.append("packages is not allowed (PyPI entry needs the owner's decision)")
    remotes = document.get("remotes")
    expected_remote = {"type": REMOTE_TYPE, "url": REMOTE_URL}
    if not isinstance(remotes, list) or len(remotes) != 1:
        errors.append("remotes must hold exactly one entry")
    elif {k: remotes[0].get(k) for k in ("type", "url")} != expected_remote:
        errors.append(f"remotes[0] must be {REMOTE_TYPE} at {REMOTE_URL}")
    version = document.get("version")
    if version != expected_version:
        errors.append(f"version is {version!r}, expected {expected_version!r}")
    return errors


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
        errors += check_hosted_version(document, fetch_hosted_latest())
        already = check_not_published(args.expected_version, fetch_published_versions())
        if args.mode == "publish":
            errors += already
        else:
            warnings += already
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        return 1
    print(f"OK: {SERVER_NAME} {args.expected_version} ({args.mode})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
