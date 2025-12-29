#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK_SRC="$ROOT/scripts/git-hooks/pre-push"
HOOK_DST="$ROOT/.git/hooks/pre-push"

chmod +x "$HOOK_SRC"
cp "$HOOK_SRC" "$HOOK_DST"
chmod +x "$HOOK_DST"

echo "Installed pre-push hook -> .git/hooks/pre-push"
echo "To skip once: SKIP_HEFESTO_HOOKS=1 git push"
