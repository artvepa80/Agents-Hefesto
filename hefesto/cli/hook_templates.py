"""Git hook templates shipped with the package for ``hefesto install-hooks``.

These are the hooks for a user's own project. A clone of Agents-Hefesto
(root ``pyproject.toml`` with ``name = "hefesto-ai"``) gets the contributor
hooks in ``scripts/git-hooks/`` instead.

``__HEFESTO_PYTHON__`` is replaced at install time with the shell-quoted path
of the interpreter that ran ``hefesto install-hooks``.
"""

import shlex

_RESOLVE = """PY=__HEFESTO_PYTHON__
if [[ -x "$PY" ]]; then
  RUN=("$PY" -m hefesto)
elif command -v hefesto >/dev/null 2>&1; then
  RUN=(hefesto)
else
  echo "[hefesto] HefestoAI not found ($PY is gone and 'hefesto' is not in PATH)." >&2
  echo "[hefesto] Reinstall the hooks (hefesto install-hooks --force)" \
    "or set SKIP_HEFESTO_HOOKS=1." >&2
  exit 1
fi
"""

PRE_COMMIT = (
    """#!/usr/bin/env bash
# Installed by `hefesto install-hooks`. Bypass once: SKIP_HEFESTO_HOOKS=1 git commit
# Note: analyzes the working-tree copy of the staged files, not the staged (index) content.
set -euo pipefail
if [[ "${SKIP_HEFESTO_HOOKS:-0}" == "1" ]]; then
  exit 0
fi
"""
    + _RESOLVE
    + """ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
FILES=()
while IFS= read -r -d '' f; do
  [[ -f "$f" ]] && FILES+=("$f")
done < <(git diff --cached --name-only --diff-filter=ACMR -z)
if [[ ${#FILES[@]} -eq 0 ]]; then
  exit 0
fi
echo "[hefesto] Analyzing ${#FILES[@]} staged file(s)..."
"${RUN[@]}" analyze "${FILES[@]}" --fail-on HIGH --allow-no-files
"""
)

PRE_PUSH = (
    """#!/usr/bin/env bash
# Installed by `hefesto install-hooks`. Bypass once: SKIP_HEFESTO_HOOKS=1 git push
set -euo pipefail
if [[ "${SKIP_HEFESTO_HOOKS:-0}" == "1" ]]; then
  exit 0
fi
"""
    + _RESOLVE
    + """ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
echo "[hefesto] Analyzing the repository before push..."
"${RUN[@]}" analyze . --fail-on CRITICAL --allow-no-files
"""
)

TEMPLATES = {"pre-commit": PRE_COMMIT, "pre-push": PRE_PUSH}


def render(hook_name: str, python: str) -> str:
    """Return the hook text with the interpreter path filled in."""
    return TEMPLATES[hook_name].replace("__HEFESTO_PYTHON__", shlex.quote(python))
