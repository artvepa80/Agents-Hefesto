#!/usr/bin/env python3
"""Check the canonical MCP Registry entry before validate or publish.

Used by ``.github/workflows/mcp-registry.yml``. It never publishes.

The workflow downloads ``https://hefestoai.narapallc.com/server.json`` and
passes that file here. This repository's ``server.json`` is not uploaded.
Its ``description`` is the source of truth: the downloaded document must use
that same description, and ``packages`` must be exactly one PyPI entry for
``hefesto-mcp`` (stdio, ``uvx``, version equal to the document version,
``HEFESTO_MCP_ROOT`` required). ``remotes`` stays the single hosted
streamable-http URL. The downloaded file is not stored in this repository.

The registry version is the hosted engine version and the PyPI package
version. The entry's version must equal all of: the hosted ``initialize``
``serverInfo.version``, the ``engine.version`` returned by a minimal
``tools/call analyze`` (as the private ``scripts/verify_hosted_engine.py``
does), ``changelog.json`` ``latest`` on the landing page, and a release
already on PyPI (``https://pypi.org/pypi/hefesto-mcp/<version>/json``
returns 200). ``URLError`` and a timeout on that request fail the check
with a message. A hosted-only hotfix cannot be registered without publishing
the package too.

A published registry version can never be changed
(``docs/modelcontextprotocol-io/versioning.mdx``), so a version that is
already in the registry, deleted ones included, is an error in publish mode
and a warning in a dry run. The lookup is
``GET /v0.1/servers/{name}/versions/{version}?include_deleted=true``
(404 means free) plus ``GET /v0.1/servers/{name}/versions?include_deleted=true``
(``docs/reference/api/openapi.yaml``).

``--offline`` skips the hosted engine, the registry, and the PyPI request.

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
PACKAGE_ID = "hefesto-mcp"
ROOT_ENV = "HEFESTO_MCP_ROOT"
PUBLIC_REPOSITORY_URL = "https://github.com/artvepa80/Agents-Hefesto"
REMOTE_TYPE = "streamable-http"
REMOTE_URL = "https://hefestoai.narapallc.com/api/mcp-protocol"
CANONICAL_URL = "https://hefestoai.narapallc.com/server.json"
HOSTED_CHANGELOG_URL = "https://hefestoai.narapallc.com/changelog.json"
REGISTRY_BASE = "https://registry.modelcontextprotocol.io"
PYPI_JSON_URL = "https://pypi.org/pypi/{package}/{version}/json"
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
_REPO_SERVER = Path(__file__).resolve().parent.parent / "server.json"


def _repo_description() -> str:
    """Description in this repository's server.json."""
    document = json.loads(_REPO_SERVER.read_text(encoding="utf-8"))
    description = document.get("description")
    if not isinstance(description, str) or not description:
        raise RuntimeError("repo server.json description is missing")
    return description


DESCRIPTION = _repo_description()


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
    errors.extend(_package_errors(document))
    return errors + _remote_errors(document.get("remotes"))


def _package_identity_errors(package: dict, version: str) -> List[str]:
    errors: List[str] = []
    if package.get("registryType") != "pypi" or package.get("identifier") != PACKAGE_ID:
        errors.append("packages[0] must be the pypi package hefesto-mcp")
    if package.get("version") != version:
        errors.append("packages[0].version must equal the document version")
    if package.get("runtimeHint") != "uvx":
        errors.append("packages[0].runtimeHint must be uvx")
    return errors


def _stdio_transport(package: dict) -> bool:
    transport = package.get("transport")
    return isinstance(transport, dict) and transport.get("type") == "stdio"


def _root_env_required(variables: object) -> bool:
    if not isinstance(variables, list):
        return False
    for item in variables:
        if not isinstance(item, dict):
            continue
        if item.get("name") == ROOT_ENV and item.get("isRequired") is True:
            return True
    return False


def _one_package(document: dict) -> Optional[dict]:
    version = document.get("version")
    packages = document.get("packages")
    if not isinstance(version, str) or not isinstance(packages, list) or len(packages) != 1:
        return None
    package = packages[0]
    if not isinstance(package, dict):
        return None
    return package


def _package_errors(document: dict) -> List[str]:
    package = _one_package(document)
    if package is None:
        return ["packages must hold exactly one hefesto-mcp entry"]
    version = str(document.get("version"))
    errors = _package_identity_errors(package, version)
    if not _stdio_transport(package):
        errors.append("packages[0].transport must be stdio")
    if not _root_env_required(package.get("environmentVariables")):
        errors.append("packages[0] must require HEFESTO_MCP_ROOT")
    return errors


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


def pypi_json_url(version: str, package: str = PACKAGE_ID) -> str:
    quoted = urllib.parse.quote(version, safe="")
    return PYPI_JSON_URL.format(package=package, version=quoted)


class PypiLookupError(Exception):
    """PyPI JSON could not be read. The check fails closed."""


def pypi_release_status(version: str) -> int:
    """HTTP status of the PyPI JSON for this package version.

    An HTTP error returns its status code. A transport error or a timeout
    raises ``PypiLookupError``.
    """
    url = pypi_json_url(version)
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # nosec B310
            return int(response.status)
    except urllib.error.HTTPError as exc:
        # HTTPError is a URLError. Handle it first so a 404 stays a status.
        return int(exc.code)
    except urllib.error.URLError as exc:
        raise PypiLookupError(f"{url} could not be reached: {exc.reason}") from exc
    except TimeoutError as exc:
        raise PypiLookupError(f"{url} timed out after {TIMEOUT_SECONDS}s") from exc


def check_pypi_release(version: str) -> List[str]:
    """The registry version must already be the published hefesto-mcp release."""
    url = pypi_json_url(version)
    try:
        status = pypi_release_status(version)
    except PypiLookupError as exc:
        return [str(exc)]
    if status == 200:
        return []
    return [f"{url} returned {status}, expected 200"]


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
    errors.extend(check_pypi_release(version))
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
