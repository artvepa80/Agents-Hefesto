#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-hefesto-api-staging}"
REPO="${REPO:-hefesto}"                  # Artifact Registry repo name
IMAGE_NAME="${IMAGE_NAME:-hefesto-api}"  # image name inside repo

if [[ -z "${PROJECT_ID}" ]]; then
  echo "ERROR: PROJECT_ID is required"
  exit 1
fi

echo "[deploy] project=${PROJECT_ID} region=${REGION} service=${SERVICE}"

# Ensure Artifact Registry repository exists (idempotent)
if ! gcloud artifacts repositories describe "${REPO}" --location="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "[deploy] creating Artifact Registry repo: ${REPO}"
  gcloud artifacts repositories create "${REPO}" \
    --repository-format=docker \
    --location="${REGION}" \
    --project="${PROJECT_ID}"
fi

GIT_SHA="$(git rev-parse --short HEAD)"
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE_NAME}:${GIT_SHA}"

echo "[deploy] build image: ${IMAGE_URI}"
gcloud builds submit --tag "${IMAGE_URI}" --project "${PROJECT_ID}"

echo "[deploy] deploying to Cloud Run..."
gcloud run deploy "${SERVICE}" \
  --image "${IMAGE_URI}" \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --platform managed \
  --allow-unauthenticated \
  --port 8080

SERVICE_URL="$(gcloud run services describe "${SERVICE}" --region "${REGION}" --project "${PROJECT_ID}" --format='value(status.url)')"
echo "[deploy] service url: ${SERVICE_URL}"

echo "[deploy] smoke test..."
bash scripts/smoke_test.sh "${SERVICE_URL}"

echo "[deploy] ✅ done"
