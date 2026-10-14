"""Git hook templates shipped with the package for ``hefesto install-hooks``.

These are the hooks for a user's own project. A clone of Agents-Hefesto keeps
its contributor hooks in ``scripts/git-hooks/``; ``install-hooks`` uses those
when that directory exists.
"""

PRE_COMMIT = """#!/usr/bin/env bash
# Installed by `hefesto install-hooks`. Bypass once: SKIP_HEFESTO_HOOKS=1 git commit
set -euo pipefail
if [[ "${SKIP_HEFESTO_HOOKS:-0}" == "1" ]]; then
  exit 0
fi
if ! command -v hefesto >/dev/null 2>&1; then
  echo "[hefesto] 'hefesto' not in PATH (pip install hefesto-ai); skipping." >&2
  exit 0
fi
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
FILES=()
while IFS= read -r -d '' f; do
  [[ -f "$f" ]] && FILES+=("$f")
done < <(git diff --cached --name-only --diff-filter=ACMR -z)
if [[ ${#FILES[@]} -eq 0 ]]; then
  exit 0
fi
echo "[hefesto] Analyzing ${#FILES[@]} staged file(s)..."
hefesto analyze "${FILES[@]}" --fail-on HIGH --allow-no-files
"""

PRE_PUSH = """#!/usr/bin/env bash
# Installed by `hefesto install-hooks`. Bypass once: SKIP_HEFESTO_HOOKS=1 git push
set -euo pipefail
if [[ "${SKIP_HEFESTO_HOOKS:-0}" == "1" ]]; then
  exit 0
fi
if ! command -v hefesto >/dev/null 2>&1; then
  echo "[hefesto] 'hefesto' not in PATH (pip install hefesto-ai); skipping." >&2
  exit 0
fi
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
echo "[hefesto] Analyzing the repository before push..."
hefesto analyze . --fail-on CRITICAL --allow-no-files
"""

TEMPLATES = {"pre-commit": PRE_COMMIT, "pre-push": PRE_PUSH}
