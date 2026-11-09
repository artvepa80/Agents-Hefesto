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
# Analyzes the staged (index) content of the staged files, not the working tree.
set -euo pipefail
if [[ "${SKIP_HEFESTO_HOOKS:-0}" == "1" ]]; then
  exit 0
fi
"""
    + _RESOLVE
    + """ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
NAMES=()
while IFS= read -r -d '' f; do
  NAMES+=("$f")
done < <(git diff --cached --name-only --diff-filter=ACMR --ignore-submodules=all -z)
if [[ ${#NAMES[@]} -eq 0 ]]; then
  exit 0
fi
# Analyze the staged (index) content, not the working tree: export the staged
# files to a temporary copy with their repository-relative paths, so path-based
# rules (test paths, excludes) still apply, and report the real paths.
STAGED="$(mktemp -d "${TMPDIR:-/tmp}/hefesto-staged.XXXXXX")"
trap 'rm -rf "$STAGED"' EXIT
STAGED="$(cd "$STAGED" && pwd -P)"  # resolved, as hefesto prints it
mkdir "$STAGED/.git"  # config lookup stops at the copy's root
git ls-files -z -- ':(glob)**/.hefesto.yaml' ':(glob)**/.hefesto.yml' |
  git checkout-index --stdin -z --prefix="$STAGED/"
for cfg in .hefesto.yaml .hefesto.yml; do
  if [[ ! -e "$STAGED/$cfg" && -f "$ROOT/$cfg" ]]; then
    cp "$ROOT/$cfg" "$STAGED/$cfg"
  fi
done
if [[ ${#NAMES[@]} -gt 0 ]]; then
  printf '%s\\0' "${NAMES[@]}" | git checkout-index --stdin -z --prefix="$STAGED/"
fi
FILES=()
for f in "${NAMES[@]+"${NAMES[@]}"}"; do
  [[ -f "$STAGED/$f" ]] && FILES+=("$STAGED/$f")
done
if [[ ${#FILES[@]} -eq 0 ]]; then
  exit 0
fi
echo "[hefesto] Analyzing ${#FILES[@]} staged file(s)..."
export HEFESTO_SOURCE=hook
set +e
"${RUN[@]}" analyze "${FILES[@]}" --fail-on HIGH --allow-no-files 2>&1 | sed "s|$STAGED/||g"
STATUS=${PIPESTATUS[0]}
set -e
exit "$STATUS"
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
export HEFESTO_SOURCE=hook
"${RUN[@]}" analyze . --fail-on CRITICAL --allow-no-files
"""
)

TEMPLATES = {"pre-commit": PRE_COMMIT, "pre-push": PRE_PUSH}


def render(hook_name: str, python: str) -> str:
    """Return the hook text with the interpreter path filled in."""
    return TEMPLATES[hook_name].replace("__HEFESTO_PYTHON__", shlex.quote(python))
