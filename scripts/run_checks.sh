#!/usr/bin/env bash
set -euo pipefail

echo "--- 1) README Parity ---"
python3 scripts/verify_readme.py
echo

echo "--- 2) Capabilities Parity ---"
python3 scripts/verify_capabilities.py
echo

echo "✅ All checks passed!"
