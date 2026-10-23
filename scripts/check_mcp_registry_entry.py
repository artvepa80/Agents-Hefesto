#!/usr/bin/env python3
"""Check the canonical MCP Registry entry before validate or publish.

Used by ``.github/workflows/mcp-registry.yml``. It never publishes.

The canonical ``server.json`` is deployed with the hosted landing page and served at
``https://hefestoai.narapallc.com/server.json``. This public repository's
``server.json`` is never sent to the registry: its description and version
(PyPI) differ from the hosted entry.

The registry version tracks the deployed engine, not PyPI. The entry's
version must equal all of: the hosted ``initialize`` ``serverInfo.version``,
the ``engine.version`` returned by a minimal ``tools/call analyze`` (as the
private ``scripts/verify_hosted_engine.py`` does), and ``changelog.json``
``latest`` on the landing page.

A published registry version can never be changed
(``docs/modelcontextprotocol-io/versioning.mdx``), so a version that is
already in the registry, deleted ones included, is an error in publish mode
and a warning in a dry run. The lookup is
``GET /v0.1/servers/{name}/versions/{version}?include_deleted=true``
(404 means free) plus ``GET /v0.1/servers/{name}/versions?include_deleted=true``
(``docs/reference/api/openapi.yaml``).

There is no ``packages`` entry: a PyPI package entry needs a decision from
the owner and an ``mcp-name:`` line in the README. Until then the entry is a
remote (streamable-http) only.

Usage::

    python scripts/check_mcp_registry_entry.py server.json \
        --expected-version X.Y.Z --mode dry-run --summary "$GITHUB_STEP_SUMMARY"
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

SCHEMA_URL = "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json"
SERVER_NAME = "io.github.artvepa80/hefestoai"
DESCRIPTION = "HefestoAI checks AI-generated code before you ship it."
PUBLIC_REPOSITORY_URL = "https://github.com/artvepa80/Agents-Hefesto"
REMOTE_TYPE = "streamable-http"
REMOTE_URL = "https://hefestoai.narapallc.com/api/mcp-protocol"
CANONICAL_URL = "https://hefestoai.narapallc.com/server.json"
HOSTED_CHANGELOG_URL = "https://hefestoai.narapallc.com/changelog.json"
REGISTRY_BASE = "https://registry.modelcontextprotocol.io"
OFFICIAL_META = "io.modelcontextprotocol.registry/official"
INITIALIZE_PARAMS = {
    "protocolVersion": "2025-06-18",
    "capabilities": {},
    "clientInfo": {"name": "hefesto-mcp-registry-check", "version": "1.0"},
}
# Minimal analyze call: one tiny file, read-only, nothing stored.
ANALYZE_PARAMS = {
    "name": "analyze",
    "arguments": {"files": [{"path": "registry_probe.py", "content": "VALUE = 1\n"}]},
}
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


def check_hosted_version(document: dict, hosted: Dict[str, str]) -> List[str]:
    """The registry version must equal every version the hosted engine reports."""
    version = document.get("version")
    return [
        f"version {version!r} does not match {source} {found!r}"
        for source, found in hosted.items()
        if found != version
    ]


def check_not_published(version: str, published: Iterable[str]) -> List[str]:
    """Registry versions are immutable: never try to publish one twice."""
    if version in set(published):
        return [f"version {version} is already in the MCP Registry (versions are immutable)"]
    return []


def _open(request: urllib.request.Request) -> str:
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # nosec B310
        return str(response.read().decode("utf-8"))


def _get_json(url: str) -> dict:
    payload = json.loads(_open(urllib.request.Request(url, headers={"Accept": "application/json"})))
    if not isinstance(payload, dict):
        raise ValueError(f"{url} did not return a JSON object")
    return payload


def _rpc(method: str, params: dict, rid: int, url: str = REMOTE_URL) -> dict:
    """One JSON-RPC call to the hosted MCP server (JSON or SSE response)."""
    body = json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
    request = urllib.request.Request(
        url,
        data=body.encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "hefesto-mcp-registry-check/1.0",
        },
    )
    raw = _open(request)
    if "data: " in raw:
        raw = raw.rsplit("data: ", 1)[1].strip()
    payload = json.loads(raw, strict=False)
    result = payload.get("result") if isinstance(payload, dict) else None
    if not isinstance(result, dict):
        raise ValueError(f"{method} returned no result: {raw[:300]}")
    return result


def engine_version_from_analyze(result: dict) -> Optional[str]:
    """``engine.version`` from a tools/call analyze result.

    Same parsing as the private ``scripts/verify_hosted_engine.py``: prefer
    ``structuredContent``; otherwise the text content is a summary sentence
    followed by the JSON body.
    """
    data = result.get("structuredContent")
    if not isinstance(data, dict) or "engine" not in data:
        text = "".join(
            c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"
        )
        try:
            data, _ = json.JSONDecoder(strict=False).raw_decode(text[text.index("{") :])
        except ValueError:
            return None
    engine = data.get("engine") if isinstance(data, dict) else None
    version = engine.get("version") if isinstance(engine, dict) else None
    return None if version is None else str(version)


def fetch_hosted_versions() -> Dict[str, str]:
    """Versions reported by the deployed engine, plus the landing changelog."""
    init = _rpc("initialize", INITIALIZE_PARAMS, 1)
    analyze = _rpc("tools/call", ANALYZE_PARAMS, 2)
    changelog = _get_json(HOSTED_CHANGELOG_URL)
    return {
        "initialize serverInfo.version": str(init.get("serverInfo", {}).get("version")),
        "analyze engine.version": str(engine_version_from_analyze(analyze)),
        "changelog.json latest": str(changelog.get("latest")),
    }


def _server_path(name: str) -> str:
    return f"/v0.1/servers/{urllib.parse.quote(name, safe='')}/versions"


def is_published(version: str, name: str = SERVER_NAME, base: str = REGISTRY_BASE) -> bool:
    """GET /v0.1/servers/{name}/versions/{version}?include_deleted=true: 404 means free."""
    url = f"{base}{_server_path(name)}/{urllib.parse.quote(version, safe='')}?include_deleted=true"
    try:
        _get_json(url)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        raise
    return True


def fetch_registry_versions(name: str = SERVER_NAME, base: str = REGISTRY_BASE) -> List[dict]:
    """All versions of ``name``, deleted ones included (empty when it has none)."""
    url = f"{base}{_server_path(name)}?include_deleted=true"
    try:
        page = _get_json(url)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return []
        raise
    return [item for item in page.get("servers", []) if isinstance(item, dict)]


def latest_registry_version(entries: Iterable[dict]) -> Optional[str]:
    """The version the registry marks ``isLatest`` (None when there is none)."""
    for entry in entries:
        official = entry.get("_meta", {}).get(OFFICIAL_META, {})
        if official.get("isLatest"):
            return str(entry.get("server", {}).get("version"))
    return None


def network_findings(version: str, mode: str) -> Tuple[List[str], List[str], Dict[str, str]]:
    """(errors, warnings, facts) from the hosted engine and the registry."""
    hosted = fetch_hosted_versions()
    errors = check_hosted_version({"version": version}, hosted)
    entries = fetch_registry_versions()
    listed = [str(e.get("server", {}).get("version")) for e in entries]
    already = check_not_published(version, listed + ([version] if is_published(version) else []))
    facts = dict(hosted)
    facts["registry latest"] = str(latest_registry_version(entries))
    if mode == "publish":
        return errors + already, [], facts
    return errors, already, facts


def write_summary(path: Path, version: str, mode: str, facts: Dict[str, str]) -> None:
    """Append a Markdown table to the GitHub job summary."""
    rows = [("to publish", version), ("mode", mode)] + list(facts.items())
    lines = ["### MCP Registry entry", "", "| | version |", "|---|---|"]
    lines += [f"| {label} | `{value}` |" for label, value in rows]
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("server_json", type=Path)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--mode", choices=("dry-run", "publish"), default="dry-run")
    parser.add_argument("--offline", action="store_true", help="skip the network checks")
    parser.add_argument("--summary", type=Path, help="append a Markdown summary to this file")
    return parser


def _report(facts: Dict[str, str], warnings: List[str], errors: List[str]) -> None:
    lines = [f"{k}: {v}" for k, v in facts.items()]
    lines += [f"WARNING: {w}" for w in warnings] + [f"ERROR: {e}" for e in errors]
    for line in lines:
        print(line)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    document = json.loads(args.server_json.read_text(encoding="utf-8"))
    version = str(document.get("version"))
    errors = check_document(document, args.expected_version)
    warnings: List[str] = []
    facts: Dict[str, str] = {}
    if not args.offline:
        more_errors, warnings, facts = network_findings(version, args.mode)
        errors += more_errors
    if args.summary:
        write_summary(args.summary, version, args.mode, facts)
    _report(facts, warnings, errors)
    if errors:
        return 1
    print(f"OK: {SERVER_NAME} {args.expected_version} ({args.mode})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
