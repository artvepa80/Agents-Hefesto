"""The Claude Code integration guide must match what Claude Code and the CLI accept.

``skill/integration.md`` used to tell users to put a ``streamable-http`` server in
``~/.claude/mcp_servers.json``, which Claude Code does not read. These checks keep
the corrected MCP config, and make sure every CLI flag the guide relies on exists.
"""

import json
import re
from pathlib import Path

from hefesto.cli.main import cli

DOC = Path(__file__).resolve().parent.parent / "skill" / "integration.md"


def _text() -> str:
    return DOC.read_text(encoding="utf-8")


def test_manual_mcp_config_uses_claude_code_shapes():
    text = _text()
    assert "mcp_servers.json" not in text
    assert '"type": "streamable-http"' not in text
    assert "claude mcp add --transport http hefestoai " in text


def test_project_mcp_json_example_is_valid():
    blocks = re.findall(r"```json\n(.*?)```", _text(), re.S)
    configs = [json.loads(b) for b in blocks if '"mcpServers"' in b]
    assert configs, "missing .mcp.json example"
    server = configs[0]["mcpServers"]["hefestoai"]
    assert server["type"] == "http"
    assert server["url"].endswith("/api/mcp-protocol")


def test_flags_used_in_the_guide_exist():
    analyze = cli.commands["analyze"]
    opts = {o for p in analyze.params for o in getattr(p, "opts", [])}
    for flag in ("--fail-on", "--quiet", "--severity", "--output"):
        assert flag in opts, flag
    assert "pr-review" in cli.commands


def test_action_input_rows_kept():
    text = _text()
    assert "INFO is treated as LOW" in text
    assert "only `1`/`true` sends the per-run ping" in text
