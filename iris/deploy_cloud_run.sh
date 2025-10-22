#!/bin/bash
# deploy_cloud_run.sh
# Deploy Iris Alert Manager to Cloud Run without local Docker
# Uses Cloud Build to build the image in GCP

set -e  # Exit on error

PROJECT_ID="${GCP_PROJECT_ID:-eminent-carver-469323-q2}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="iris-alert-manager-job"
SERVICE_ACCOUNT="iris-agent-sa@${PROJECT_ID}.iam.gserviceaccount.com"
IMAGE_NAME="iris-alert-agent"
IMAGE_TAG="${IMAGE_TAG:-v1.0.0}"
IMAGE_URL="gcr.io/${PROJECT_ID}/${IMAGE_NAME}:${IMAGE_TAG}"

echo "🚀 Deploying Iris Alert Manager to Cloud Run"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo "Image: ${IMAGE_URL}"
echo ""

# Step 1: Build image using Cloud Build (no local Docker needed)
echo "📦 Step 1: Building Docker image using Cloud Build..."
gcloud builds submit \
  --tag "${IMAGE_URL}" \
  --project "${PROJECT_ID}" \
  --timeout=10m \
  .

echo "✅ Image built successfully: ${IMAGE_URL}"
echo ""

# Step 2: Deploy or update Cloud Run Job
echo "☁️  Step 2: Deploying to Cloud Run Job..."

# Check if job exists
if gcloud run jobs describe "${SERVICE_NAME}" \
   --region "${REGION}" \
   --project "${PROJECT_ID}" &>/dev/null; then

  echo "Updating existing job: ${SERVICE_NAME}"
  gcloud run jobs update "${SERVICE_NAME}" \
    --image "${IMAGE_URL}" \
    --region "${REGION}" \
    --project "${PROJECT_ID}" \
    --service-account "${SERVICE_ACCOUNT}" \
    --set-env-vars="GCP_PROJECT_ID=${PROJECT_ID}" \
    --set-env-vars="DRY_RUN=false" \
    --cpu=1 \
    --memory=512Mi \
    --max-retries=3 \
    --task-timeout=600

else
  echo "Creating new job: ${SERVICE_NAME}"
  gcloud run jobs create "${SERVICE_NAME}" \
    --image "${IMAGE_URL}" \
    --region "${REGION}" \
    --project "${PROJECT_ID}" \
    --service-account "${SERVICE_ACCOUNT}" \
    --set-env-vars="GCP_PROJECT_ID=${PROJECT_ID}" \
    --set-env-vars="DRY_RUN=false" \
    --cpu=1 \
    --memory=512Mi \
    --max-retries=3 \
    --task-timeout=600
fi

echo "✅ Cloud Run Job deployed successfully"
echo ""

# Step 3: Create/Update Cloud Scheduler
SCHEDULER_NAME="iris-monitoring-schedule"
SCHEDULE="${SCHEDULE:-*/15 * * * *}"  # Every 15 minutes

echo "⏰ Step 3: Configuring Cloud Scheduler..."

# Get job URI
JOB_URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${SERVICE_NAME}:run"

# Check if scheduler job exists
if gcloud scheduler jobs describe "${SCHEDULER_NAME}" \
   --location "${REGION}" \
   --project "${PROJECT_ID}" &>/dev/null; then

  echo "Updating existing scheduler: ${SCHEDULER_NAME}"
  gcloud scheduler jobs update http "${SCHEDULER_NAME}" \
    --location "${REGION}" \
    --project "${PROJECT_ID}" \
    --schedule="${SCHEDULE}" \
    --http-method=POST \
    --uri="${JOB_URI}" \
    --oauth-service-account-email="${SERVICE_ACCOUNT}"

else
  echo "Creating new scheduler: ${SCHEDULER_NAME}"
  gcloud scheduler jobs create http "${SCHEDULER_NAME}" \
    --location "${REGION}" \
    --project "${PROJECT_ID}" \
    --schedule="${SCHEDULE}" \
    --http-method=POST \
    --uri="${JOB_URI}" \
    --oauth-service-account-email="${SERVICE_ACCOUNT}" \
    --description="Executes Iris Alert Manager every 15 minutes"
fi

echo "✅ Cloud Scheduler configured: ${SCHEDULE}"
echo ""

# Step 4: Verify deployment
echo "🔍 Step 4: Verifying deployment..."

# Check job status
echo "Cloud Run Job status:"
gcloud run jobs describe "${SERVICE_NAME}" \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --format="value(status.conditions)"

echo ""

# Step 5: Test execution (optional)
echo "▶️  Step 5: Test execution"
read -p "Do you want to run a test execution now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  echo "Executing job manually..."
  gcloud run jobs execute "${SERVICE_NAME}" \
    --region "${REGION}" \
    --project "${PROJECT_ID}" \
    --wait

  echo "✅ Test execution completed"

  # Show logs
  echo "📋 Recent logs:"
  gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=${SERVICE_NAME}" \
    --project "${PROJECT_ID}" \
    --limit=20 \
    --format="table(timestamp,severity,textPayload)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 Deployment Complete!"
echo ""
echo "Service: ${SERVICE_NAME}"
echo "Image: ${IMAGE_URL}"
echo "Schedule: ${SCHEDULE}"
echo "Region: ${REGION}"
echo ""
echo "📚 Useful commands:"
echo "  # View logs"
echo "  gcloud logging read 'resource.labels.job_name=${SERVICE_NAME}' --limit=50"
echo ""
echo "  # Execute manually"
echo "  gcloud run jobs execute ${SERVICE_NAME} --region ${REGION}"
echo ""
echo "  # Pause scheduler"
echo "  gcloud scheduler jobs pause ${SCHEDULER_NAME} --location ${REGION}"
echo ""
echo "  # View job status"
echo "  gcloud run jobs describe ${SERVICE_NAME} --region ${REGION}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
