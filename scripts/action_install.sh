#!/bin/bash
# Install step of the GitHub Action (action.yml): installs HefestoAI from the
# Action's own checkout into a private virtualenv, so the job's Python is left
# untouched. With the opt-in input multilang: 'true' it installs the
# [multilang] extra too (tree-sitter grammars for TypeScript, JavaScript,
# Java, Go, Rust and C#). Default: base package only, as before.
set -e

# true/1/yes (any case, surrounding spaces ignored) -> 1, anything else -> 0
# (same rule as the boolean inputs in action_entrypoint.sh)
is_true() {
    local value="${1//[[:space:]]/}"
    case "${value,,}" in
        1|true|yes) echo 1 ;;
        *) echo 0 ;;
    esac
}

python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' || {
    echo "::error::HefestoAI needs python3 >= 3.11 on the runner (found $(python3 --version 2>&1)). Add actions/setup-python before this step."
    exit 1
}

PACKAGE="$GITHUB_ACTION_PATH"
if [ "$(is_true "${INPUT_MULTILANG:-false}")" = "1" ]; then
    PACKAGE="${GITHUB_ACTION_PATH}[multilang]"
    echo "Installing HefestoAI with the [multilang] extra (multilang: true)"
fi

python3 -m venv "$RUNNER_TEMP/hefesto-venv"
"$RUNNER_TEMP/hefesto-venv/bin/python" -m pip install --quiet --disable-pip-version-check "$PACKAGE"
