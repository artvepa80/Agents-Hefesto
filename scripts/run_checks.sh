#!/usr/bin/env bash
set -euo pipefail

echo "--- 1) README Parity ---"
python3 scripts/verify_readme.py
echo

echo "--- 2) Capabilities Parity ---"
python3 scripts/verify_capabilities.py
echo

echo "--- 3) MCP server.json ---"
python3 scripts/verify_server_json.py
echo

echo "✅ All checks passed!"
