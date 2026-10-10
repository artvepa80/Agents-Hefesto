#!/bin/bash
set -e

# Run from GitHub workspace so relative paths (e.g. .github/action-smoke/clean.py) resolve.
# Docker image WORKDIR is /app; the repo is mounted at GITHUB_WORKSPACE.
if [ -n "${GITHUB_WORKSPACE:-}" ] && [ -d "$GITHUB_WORKSPACE" ]; then
    cd "$GITHUB_WORKSPACE"
fi

# Inputs provided by GitHub Actions (prefixed with INPUT_)
# Defaults are handled in action.yml, but safe fallbacks here are good practice.
TARGET="${INPUT_TARGET:-.}"
FAIL_ON="${INPUT_FAIL_ON:-CRITICAL}"
FAIL_ON="${FAIL_ON^^}" # Force uppercase
SEVERITY="${INPUT_MIN_SEVERITY:-LOW}"
SEVERITY="${SEVERITY^^}" # Force uppercase
FORMAT="${INPUT_FORMAT:-text}"
TELEMETRY_INPUT="${INPUT_TELEMETRY:-0}"
SARIF_FILE="${INPUT_SARIF_FILE:-hefesto.sarif}"
SARIF_CATEGORY="${INPUT_SARIF_CATEGORY:-hefesto}"

# true/1/yes (any case, surrounding spaces ignored) -> 1, anything else -> 0
is_true() {
    local value="${1//[[:space:]]/}"
    case "${value,,}" in
        1|true|yes) echo 1 ;;
        *) echo 0 ;;
    esac
}
SARIF_ENABLED=$(is_true "${INPUT_SARIF:-false}")
UPLOAD_SARIF=$(is_true "${INPUT_UPLOAD_SARIF:-true}")
if [ "$SARIF_ENABLED" != "1" ]; then
    UPLOAD_SARIF=0
fi

# The CLI has no INFO level (its --severity accepts LOW..CRITICAL), so INFO
# used to make the Action exit 2. Treat it as LOW, the lowest level (BUG-13).
if [ "$SEVERITY" = "INFO" ]; then
    echo "::warning::min_severity INFO is not supported; using LOW (the lowest level)."
    SEVERITY="LOW"
fi

# Telemetry is opt-in (SEC-06). Only the values 1 or true (any case) enable it.
# Anything else, including the default 0, disables both the Action ping below
# and the CLI's own ping (the CLI treats HEFESTO_TELEMETRY=0 as off).
TELEMETRY_NORMALIZED="${TELEMETRY_INPUT//[[:space:]]/}"
case "${TELEMETRY_NORMALIZED,,}" in
    1|true) TELEMETRY_ENABLED=1 ;;
    *) TELEMETRY_ENABLED=0 ;;
esac
export HEFESTO_TELEMETRY="${TELEMETRY_ENABLED}"

echo "::group::Hefesto Configuration"
echo "Workspace: $(pwd)"
echo "Target: ${TARGET}"
echo "Fail On: ${FAIL_ON}"
echo "Min Severity: ${SEVERITY}"
echo "Format: ${FORMAT}"
echo "Telemetry: ${HEFESTO_TELEMETRY}"
if [ "$SARIF_ENABLED" = "1" ]; then
    echo "SARIF file: ${SARIF_FILE} (upload: $([ "$UPLOAD_SARIF" = "1" ] && echo yes || echo no), category: ${SARIF_CATEGORY})"
else
    echo "SARIF file: off"
fi
echo "::endgroup::"

# Run Analysis: the report goes to the log in FORMAT; with `sarif: true` a
# SARIF 2.1.0 file is written too (--sarif-file) for upload-sarif.

echo "::group::Running Analysis"
set +e # Allow failure to capture exit code

# Construct command array (safe, no eval)
CMD=("hefesto" "analyze" "$TARGET" "--severity" "$SEVERITY" "--fail-on" "$FAIL_ON")

# Add format if specified (default logic handled in CLI or verified here)
if [ -n "$FORMAT" ]; then
    CMD+=("--output" "$FORMAT")
fi
if [ "$SARIF_ENABLED" = "1" ]; then
    rm -f "$SARIF_FILE"
    CMD+=("--sarif-file" "$SARIF_FILE")
fi

# Execute (tee to temp file for telemetry parsing)
TMPOUT=$(mktemp)
"${CMD[@]}" 2>&1 | tee "$TMPOUT"
EXIT_CODE=${PIPESTATUS[0]}

echo "::endgroup::"

# Anonymous Action ping: sent ONLY when the `telemetry` input is enabled
# (1/true). With the default `telemetry: 0` nothing leaves the runner (SEC-06).
if [ "$TELEMETRY_ENABLED" = "1" ]; then
    HEFESTO_VERSION=$(hefesto --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "0.0.0")
    FILE_COUNT=$(grep -oE 'Files analyzed: [0-9]+' "$TMPOUT" | grep -oE '[0-9]+' || echo "0")
    ISSUE_COUNT=$(grep -oE 'Issues found: [0-9]+' "$TMPOUT" | grep -oE '[0-9]+' || echo "0")

    curl -s -X POST https://hefestoai.narapallc.com/api/telemetry \
      -H "Content-Type: application/json" \
      -d "{\"event\":\"action\",\"v\":\"${HEFESTO_VERSION}\",\"files\":${FILE_COUNT},\"issues\":${ISSUE_COUNT},\"exit_code\":${EXIT_CODE}}" \
      --connect-timeout 2 --max-time 3 || true
fi
rm -f "$TMPOUT"

# Set Outputs
echo "exit_code=${EXIT_CODE}" >> "$GITHUB_OUTPUT"
if [ "$SARIF_ENABLED" = "1" ]; then
    if [ -s "$SARIF_FILE" ]; then
        echo "sarif_file=${SARIF_FILE}" >> "$GITHUB_OUTPUT"
        echo "upload_sarif=$([ "$UPLOAD_SARIF" = "1" ] && echo true || echo false)" >> "$GITHUB_OUTPUT"
    else
        echo "::warning::sarif is enabled but ${SARIF_FILE} was not written (hefesto exit code ${EXIT_CODE}); nothing to upload."
    fi
fi

# Exit with the code from hefesto to fail the workflow step if needed
exit $EXIT_CODE
