#!/usr/bin/env bash
set -euo pipefail

# capture_analysis.sh — Run hefesto analyze and capture evidence
# Usage: ./scripts/capture_analysis.sh [paths...] [--fail-on LEVEL]
#
# Saves JSON output, text output, and metadata to evidence directory.
# Prints a 1-line summary to stdout.

EVIDENCE_DIR="${HOME}/hefesto_tools/hermes/evidence"
mkdir -p "$EVIDENCE_DIR"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
SLUG=$(date -u +"%Y%m%d_%H%M%S")

JSON_FILE="${EVIDENCE_DIR}/${SLUG}_analysis.json"
TEXT_FILE="${EVIDENCE_DIR}/${SLUG}_analysis.txt"
META_FILE="${EVIDENCE_DIR}/${SLUG}_metadata.json"

# Run JSON output (stdout = pure JSON when --output json)
EXIT_CODE=0
hefesto analyze "$@" --output json --quiet > "$JSON_FILE" 2>/dev/null || EXIT_CODE=$?

# Run text output
hefesto analyze "$@" --quiet > "$TEXT_FILE" 2>/dev/null || true

# Parse JSON for metadata
if [ -s "$JSON_FILE" ]; then
    FILES=$(python3 -c "import json; d=json.load(open('$JSON_FILE')); print(d['summary']['files_analyzed'])" 2>/dev/null || echo 0)
    TOTAL=$(python3 -c "import json; d=json.load(open('$JSON_FILE')); print(d['summary']['total_issues'])" 2>/dev/null || echo 0)
    CRITICAL=$(python3 -c "import json; d=json.load(open('$JSON_FILE')); print(d['summary']['critical'])" 2>/dev/null || echo 0)
    HIGH=$(python3 -c "import json; d=json.load(open('$JSON_FILE')); print(d['summary']['high'])" 2>/dev/null || echo 0)
    MEDIUM=$(python3 -c "import json; d=json.load(open('$JSON_FILE')); print(d['summary']['medium'])" 2>/dev/null || echo 0)
    LOW=$(python3 -c "import json; d=json.load(open('$JSON_FILE')); print(d['summary']['low'])" 2>/dev/null || echo 0)
    DURATION=$(python3 -c "import json; d=json.load(open('$JSON_FILE')); print(round(d['summary']['duration_seconds'],2))" 2>/dev/null || echo 0)
else
    FILES=0; TOTAL=0; CRITICAL=0; HIGH=0; MEDIUM=0; LOW=0; DURATION=0
fi

# Determine status
if [ "$EXIT_CODE" -eq 1 ]; then
    STATUS="blocked"
elif [ "$TOTAL" -eq 0 ]; then
    STATUS="clean"
else
    STATUS="issues"
fi

# Write metadata
cat > "$META_FILE" << METAEOF
{
  "timestamp": "$TIMESTAMP",
  "files_analyzed": $FILES,
  "total_issues": $TOTAL,
  "critical": $CRITICAL,
  "high": $HIGH,
  "medium": $MEDIUM,
  "low": $LOW,
  "exit_code": $EXIT_CODE,
  "duration_seconds": $DURATION,
  "status": "$STATUS",
  "text_file": "$TEXT_FILE",
  "json_file": "$JSON_FILE"
}
METAEOF

# 1-line summary
echo "[hefesto] ${FILES} files, ${TOTAL} issues (${CRITICAL}C/${HIGH}H/${MEDIUM}M/${LOW}L) — ${STATUS} [${DURATION}s]"

exit $EXIT_CODE
