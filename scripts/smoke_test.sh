#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:8080}"

echo "[smoke] BASE_URL=${BASE_URL}"

echo "[smoke] GET /ping"
PING_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/ping")
if [[ "${PING_CODE}" != "200" ]]; then
  echo "[smoke][FAIL] /ping returned ${PING_CODE}"
  exit 1
fi
echo "[smoke][OK] /ping -> 200"

echo "[smoke] GET /docs"
DOCS_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/docs")
if [[ "${DOCS_CODE}" != "200" ]]; then
  echo "[smoke][WARN] /docs returned ${DOCS_CODE} (not fatal for MVP unless you want it strict)"
else
  echo "[smoke][OK] /docs -> 200"
fi

echo "[smoke] ✅ OK"
