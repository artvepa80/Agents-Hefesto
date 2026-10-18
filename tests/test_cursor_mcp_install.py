"""Root .mcp.json and the README "Add to Cursor" links point at the hosted MCP.

Formats: https://cursor.com/docs/context/mcp (remote server: ``url``) and
https://cursor.com/docs/mcp/install-links (``name`` plus base64 JSON config).
"""

import base64
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "https://hefestoai.narapallc.com/api/mcp-protocol"
READMES = ["README.md", "README.ja.md", "README.zh-CN.md"]
LINK = re.compile(r"(cursor://anysphere\.cursor-deeplink|https://cursor\.com/link)/mcp/install\?[^\s)`]+")


def test_root_mcp_json_is_the_hosted_remote_server():
    data = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
    assert data == {"mcpServers": {"hefestoai": {"url": ENDPOINT}}}


def test_root_and_cursor_project_configs_agree():
    root = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
    project = json.loads((ROOT / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
    assert root == project


@pytest.mark.parametrize("readme", READMES)
def test_readme_install_links_decode_to_the_server_config(readme):
    text = (ROOT / readme).read_text(encoding="utf-8")
    links = [m.group(0) for m in LINK.finditer(text)]
    assert {urlparse(link).scheme for link in links} == {"cursor", "https"}, links
    for link in links:
        query = parse_qs(urlparse(link).query)
        assert query["name"] == ["hefestoai"]
        config = json.loads(base64.b64decode(query["config"][0]))
        assert config == {"url": ENDPOINT}


@pytest.mark.parametrize("readme", READMES)
def test_readme_uses_the_official_button_image(readme):
    text = (ROOT / readme).read_text(encoding="utf-8")
    assert "](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/link/" in text
