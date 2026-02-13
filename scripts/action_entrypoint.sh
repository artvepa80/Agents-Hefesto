#!/bin/bash
set -e

# Inputs provided by GitHub Actions (prefixed with INPUT_)
# Defaults are handled in action.yml, but safe fallbacks here are good practice.
TARGET="${INPUT_TARGET:-.}"
FAIL_ON="${INPUT_FAIL_ON:-CRITICAL}"
SEVERITY="${INPUT_MIN_SEVERITY:-LOW}"
FORMAT="${INPUT_FORMAT:-sarif}"
TELEMETRY="${INPUT_TELEMETRY:-0}"

# Telemetry Opt-in
export HEFESTO_TELEMETRY="${TELEMETRY}"

echo "::group::Hefesto Configuration"
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

# Construct command
CMD="hefesto analyze \"${TARGET}\" --severity \"${SEVERITY}\" --fail-on \"${FAIL_ON}\""

# Execute
eval "$CMD"
EXIT_CODE=$?

echo "::endgroup::"

# Set Outputs
echo "exit_code=${EXIT_CODE}" >> "$GITHUB_OUTPUT"

# Determine path for report if generated (placeholder logic if CLI supports file output)
# For now, we just pass the exit code.

# Exit with the code from hefesto to fail the workflow step if needed
exit $EXIT_CODE
