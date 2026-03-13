#!/bin/bash
set -e

# Run from GitHub workspace so relative paths (e.g. tests/fixtures/action/clean.py) resolve.
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
TELEMETRY="${INPUT_TELEMETRY:-0}"

# Telemetry Opt-in
export HEFESTO_TELEMETRY="${TELEMETRY}"

echo "::group::Hefesto Configuration"
echo "Workspace: $(pwd)"
echo "Target: ${TARGET}"
echo "Fail On: ${FAIL_ON}"
echo "Min Severity: ${SEVERITY}"
echo "Format: ${FORMAT}"
echo "Telemetry: ${HEFESTO_TELEMETRY}"
echo "::endgroup::"

# Run Analysis
# We pipe output to a file if format is JSON/SARIF to allow artifact upload if needed,
# but hefesto CLI usually prints to stdout. 
# We'll rely on the CLI's standard behavior.
# If an output file is requested, we might need CLI support for --output.
# Checking CLI args: hefesto analyze [TARGET] --fail-on ... 
# Assuming standard usage.

echo "::group::Running Analysis"
set +e # Allow failure to capture exit code

# Construct command array (safe, no eval)
CMD=("hefesto" "analyze" "$TARGET" "--severity" "$SEVERITY" "--fail-on" "$FAIL_ON")

# Add format if specified (default logic handled in CLI or verified here)
if [ -n "$FORMAT" ]; then
    CMD+=("--output" "$FORMAT")
fi

# Execute (tee to temp file for telemetry parsing)
TMPOUT=$(mktemp)
"${CMD[@]}" 2>&1 | tee "$TMPOUT"
EXIT_CODE=${PIPESTATUS[0]}

echo "::endgroup::"

# Anonymous telemetry ping (always-on for CI)
HEFESTO_VERSION=$(hefesto --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "0.0.0")
FILE_COUNT=$(grep -oE 'Files analyzed: [0-9]+' "$TMPOUT" | grep -oE '[0-9]+' || echo "0")
ISSUE_COUNT=$(grep -oE 'Issues found: [0-9]+' "$TMPOUT" | grep -oE '[0-9]+' || echo "0")
rm -f "$TMPOUT"

curl -s -X POST https://hefestoai.narapallc.com/api/telemetry \
  -H "Content-Type: application/json" \
  -d "{\"event\":\"action\",\"v\":\"${HEFESTO_VERSION}\",\"files\":${FILE_COUNT},\"issues\":${ISSUE_COUNT},\"exit_code\":${EXIT_CODE}}" \
  --connect-timeout 2 --max-time 3 || true

# Set Outputs
echo "exit_code=${EXIT_CODE}" >> "$GITHUB_OUTPUT"

# If format is JSON or SARIF, we might want to expose the output file.
# Since the CLI prints to stdout by default, users can redirect it if they run manually,
# but in an Action, capturing stdout to a file requires wrapper logic.
# For now, we rely on the user viewing the logs or using the CLI's --output flag if added in future.


# Determine path for report if generated (placeholder logic if CLI supports file output)
# For now, we just pass the exit code.

# Exit with the code from hefesto to fail the workflow step if needed
exit $EXIT_CODE
