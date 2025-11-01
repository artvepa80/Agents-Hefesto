# BigQuery Setup Guide for Hefesto

## Overview

Hefesto stores analysis findings in **YOUR** BigQuery project. This architecture provides:

- **Full Data Ownership**: You control where your code quality data lives
- **No Vendor Lock-In**: Direct SQL access to your findings data
- **Custom Analytics**: Build dashboards and reports using your existing GCP tools
- **Cost Control**: Pay only for what you use in your own GCP account
- **Security**: Data never leaves your GCP project boundary

This guide walks you through setting up BigQuery for Hefesto findings persistence.

## Prerequisites

Before starting, ensure you have:

- **Google Cloud Platform account** with billing enabled
- **gcloud CLI** installed and configured ([Install Guide](https://cloud.google.com/sdk/docs/install))
- **GCP Project** with Owner or Editor role
- **BigQuery API** enabled (we'll do this in Step 1)
- **Service Account** creation permissions

## Step 1: Enable BigQuery API

Enable the BigQuery API in your GCP project:

```bash
# Set your project ID
export PROJECT_ID="your-gcp-project-id"
gcloud config set project $PROJECT_ID

# Enable BigQuery API
gcloud services enable bigquery.googleapis.com
```

Verify the API is enabled:

```bash
gcloud services list --enabled | grep bigquery
```

Expected output:
```
bigquery.googleapis.com          BigQuery API
```

## Step 2: Create BigQuery Dataset

Create a dataset to store Hefesto findings:

```bash
# Create dataset (change location if needed)
bq mk \
  --dataset \
  --location=US \
  --description="Hefesto code quality findings" \
  $PROJECT_ID:hefesto_findings
```

**Location Options:**
- `US` - United States (multi-region)
- `EU` - European Union (multi-region)
- `us-east1`, `europe-west1` - Single regions for lower latency

**Cost Consideration**: Multi-region storage costs ~$0.02/GB/month, single-region costs ~$0.01/GB/month.

Verify dataset creation:

```bash
bq ls --project_id=$PROJECT_ID
```

## Step 3: Create Tables

Run the SQL schema to create the three required tables:

```bash
# Download schema from repository
curl -O https://raw.githubusercontent.com/artvepa80/Agents-Hefesto/main/docs/BIGQUERY_SCHEMA.sql

# Replace {project_id} placeholder with your actual project ID
sed "s/{project_id}/$PROJECT_ID/g" BIGQUERY_SCHEMA.sql > schema_ready.sql

# Execute schema creation
bq query --use_legacy_sql=false < schema_ready.sql
```

Verify tables were created:

```bash
bq ls $PROJECT_ID:hefesto_findings
```

Expected output:
```
       tableId        Type
 -------------------- -------
  analysis_runs       TABLE
  findings            TABLE
  finding_history     TABLE
```

## Step 4: Create Service Account

Create a dedicated service account for Hefesto:

```bash
# Create service account
gcloud iam service-accounts create hefesto-api \
  --display-name="Hefesto API Service Account" \
  --description="Used by Hefesto API to write findings to BigQuery"

# Grant BigQuery Data Editor role (read + write)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:hefesto-api@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"

# Grant BigQuery Job User role (required to run queries)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:hefesto-api@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"
```

**Security Note**: The `bigquery.dataEditor` role allows read/write to datasets. For production, consider using custom roles with minimal permissions.

## Step 5: Generate Service Account Key

Create and download credentials for the service account:

```bash
# Generate JSON key file
gcloud iam service-accounts keys create ~/hefesto-bigquery-key.json \
  --iam-account=hefesto-api@$PROJECT_ID.iam.gserviceaccount.com

# Secure the key file (important!)
chmod 600 ~/hefesto-bigquery-key.json
```

**⚠️ SECURITY WARNING**: This JSON key provides full access to BigQuery with the granted permissions. Treat it like a password:
- Never commit to version control
- Store in secure location (e.g., secrets manager)
- Rotate regularly (every 90 days recommended)
- Use workload identity in production (see Advanced section)

## Step 6: Configure Hefesto

Set environment variables to connect Hefesto to your BigQuery project:

```bash
# Add to your ~/.bashrc or ~/.zshrc
export BIGQUERY_PROJECT_ID="your-gcp-project-id"
export BIGQUERY_DATASET_ID="hefesto_findings"
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/hefesto-bigquery-key.json"
```

Reload your shell:

```bash
source ~/.bashrc  # or source ~/.zshrc
```

## Step 7: Verify Configuration

Test the connection using Hefesto CLI:

```bash
# Run a test analysis (this will write to BigQuery if configured)
hefesto analyze /path/to/test/file.py

# Query findings via API
curl http://localhost:8000/api/v1/findings?limit=10

# Or use BigQuery directly
bq query --use_legacy_sql=false \
  "SELECT COUNT(*) as total_findings FROM \`$PROJECT_ID.hefesto_findings.findings\`"
```

If configured correctly, you should see findings data in BigQuery.

## Cost Estimation

### Storage Costs

**BigQuery Storage Pricing** (as of 2025):
- **Active storage**: $0.02 per GB/month (US multi-region)
- **Long-term storage**: $0.01 per GB/month (data not modified for 90 days)

**Example**: 1 million findings (~500 MB) = ~$0.01/month

### Query Costs

**BigQuery Query Pricing**:
- **On-demand**: $6.25 per TB scanned
- **Flat-rate**: $2,000/month for 100 slots (enterprise)

**Example Query Costs** (with partitioning/clustering optimized):
- List findings (1 day partition): ~10 MB scanned = $0.00006
- Get finding by ID (clustered): ~1 MB scanned = $0.000006
- Monthly analytics (30 days): ~300 MB scanned = $0.002

**Monthly Cost Estimate** (small team):
- Storage: $0.05
- Queries: $0.10
- **Total: ~$0.15/month**

### Free Tier

Google Cloud provides generous free tier:
- **Storage**: First 10 GB free
- **Queries**: First 1 TB scanned per month free

Most small teams will stay within free tier limits.

## Security Best Practices

### 1. Use Workload Identity (Production)

For production deployments on GKE or Cloud Run:

```bash
# Enable Workload Identity on GKE cluster
gcloud container clusters update CLUSTER_NAME \
  --workload-pool=$PROJECT_ID.svc.id.goog

# Bind service account to Kubernetes service account
gcloud iam service-accounts add-iam-policy-binding \
  hefesto-api@$PROJECT_ID.iam.gserviceaccount.com \
  --role roles/iam.workloadIdentityUser \
  --member "serviceAccount:$PROJECT_ID.svc.id.goog[NAMESPACE/KSA_NAME]"
```

This eliminates need for JSON key files.

### 2. Implement Least Privilege

Create custom IAM role with minimal permissions:

```bash
# Create custom role with only required permissions
gcloud iam roles create hefestoFindings \
  --project=$PROJECT_ID \
  --title="Hefesto Findings Writer" \
  --description="Minimal permissions for Hefesto findings storage" \
  --permissions="bigquery.tables.get,bigquery.tables.getData,bigquery.tables.updateData,bigquery.jobs.create"
```

### 3. Enable Audit Logging

Track all BigQuery access:

```bash
# Enable data access logs for BigQuery
gcloud logging sinks create hefesto-audit \
  bigquery.googleapis.com/projects/$PROJECT_ID/datasets/audit_logs \
  --log-filter='resource.type="bigquery_resource"'
```

### 4. Set Up VPC Service Controls

Restrict BigQuery access to specific networks (enterprise):

```bash
# Create access policy (requires organization-level permissions)
gcloud access-context-manager policies create \
  --organization=ORGANIZATION_ID \
  --title="Hefesto BigQuery Access"
```

### 5. Implement Data Retention Policies

Automatically delete old findings:

```bash
# Set table expiration (e.g., 365 days)
bq update --time_partitioning_expiration=31536000 \
  $PROJECT_ID:hefesto_findings.findings
```

## Troubleshooting

### Error: "Permission denied while globbing file pattern"

**Cause**: Service account lacks BigQuery Job User role.

**Solution**:
```bash
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:hefesto-api@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"
```

### Error: "Dataset not found"

**Cause**: Dataset doesn't exist or wrong project ID.

**Solution**:
```bash
# Verify dataset exists
bq ls --project_id=$PROJECT_ID

# Check environment variable
echo $BIGQUERY_PROJECT_ID
```

### Error: "Insufficient tokens for quota"

**Cause**: Exceeded BigQuery API rate limits.

**Solution**:
```bash
# Check quota usage
gcloud compute project-info describe --project=$PROJECT_ID

# Request quota increase (if needed)
# Go to: https://console.cloud.google.com/iam-admin/quotas
```

### Slow Query Performance

**Cause**: Missing clustering or querying across too many partitions.

**Solution**:
```sql
-- Add date_range filter to limit partition scanning
SELECT * FROM `project.hefesto_findings.findings`
WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  AND severity = 'HIGH'
```

### Connection Timeout

**Cause**: Network issues or firewall blocking googleapis.com.

**Solution**:
```bash
# Test connectivity
curl -I https://bigquery.googleapis.com

# Check firewall rules (allow egress to *.googleapis.com on port 443)
```

## Advanced: Custom SQL Queries

### Top 10 Files with Most Issues

```sql
SELECT
  file_path,
  COUNT(*) as issue_count,
  COUNTIF(severity = 'CRITICAL') as critical,
  COUNTIF(severity = 'HIGH') as high
FROM `{project_id}.hefesto_findings.findings`
WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY file_path
ORDER BY issue_count DESC
LIMIT 10;
```

### Issue Trend Over Time

```sql
SELECT
  DATE(created_at) as date,
  severity,
  COUNT(*) as count
FROM `{project_id}.hefesto_findings.findings`
WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
GROUP BY date, severity
ORDER BY date DESC;
```

### Analyzer Effectiveness

```sql
SELECT
  analyzer,
  COUNT(*) as findings_count,
  AVG(confidence) as avg_confidence,
  COUNTIF(status = 'resolved') as resolved_count,
  COUNTIF(status = 'resolved') / COUNT(*) as resolution_rate
FROM `{project_id}.hefesto_findings.findings`
WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY analyzer
ORDER BY findings_count DESC;
```

### Findings Resolution Time

```sql
WITH resolution_times AS (
  SELECT
    f.finding_id,
    f.severity,
    f.created_at,
    MIN(h.changed_at) as resolved_at
  FROM `{project_id}.hefesto_findings.findings` f
  JOIN `{project_id}.hefesto_findings.finding_history` h
    ON f.finding_id = h.finding_id
  WHERE h.new_status = 'resolved'
    AND f.created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
  GROUP BY f.finding_id, f.severity, f.created_at
)
SELECT
  severity,
  COUNT(*) as resolved_count,
  AVG(TIMESTAMP_DIFF(resolved_at, created_at, HOUR)) as avg_hours_to_resolve,
  APPROX_QUANTILES(TIMESTAMP_DIFF(resolved_at, created_at, HOUR), 100)[OFFSET(50)] as median_hours
FROM resolution_times
GROUP BY severity
ORDER BY avg_hours_to_resolve;
```

### Export to Google Sheets

```sql
-- Run this query and click "Save Results" > "Google Sheets"
SELECT
  file_path,
  line_number,
  severity,
  issue_type,
  description,
  status,
  created_at
FROM `{project_id}.hefesto_findings.findings`
WHERE status = 'new'
  AND severity IN ('CRITICAL', 'HIGH')
ORDER BY created_at DESC
LIMIT 1000;
```

## Integration with Data Studio

Create visualizations using Google Data Studio:

1. Go to [Google Data Studio](https://datastudio.google.com)
2. Create new report
3. Add data source > BigQuery
4. Select your project > `hefesto_findings` dataset
5. Choose tables to visualize

**Recommended Dashboards:**
- **Executive Summary**: Total issues by severity, trend over time
- **Team View**: Issues by file/module, resolution rate
- **Analyzer Performance**: Findings by analyzer, confidence distribution

## Integration with Cloud Monitoring

Set up alerts for critical findings:

```bash
# Create alert policy for critical findings
gcloud alpha monitoring policies create \
  --notification-channels=CHANNEL_ID \
  --display-name="Hefesto Critical Findings Alert" \
  --condition-display-name="New critical finding detected" \
  --condition-threshold-value=1 \
  --condition-threshold-duration=60s
```

## Next Steps

After completing setup:

1. **Run Analysis**: Execute `hefesto analyze` on your codebase
2. **Query Findings**: Use GET /api/v1/findings endpoint
3. **Build Dashboards**: Create custom analytics in Data Studio
4. **Set Up Alerts**: Configure monitoring for critical issues
5. **Enable IRIS Integration**: Connect to Omega Guardian (Phase 4)

## Support

For issues or questions:

- **GitHub Issues**: https://github.com/artvepa80/Agents-Hefesto/issues
- **Documentation**: https://github.com/artvepa80/Agents-Hefesto/blob/main/README.md
- **Email**: contact@narapallc.com

## License

Copyright (c) 2025 Narapa LLC, Miami, Florida

This setup guide is part of the Hefesto project under dual licensing:
- Open Source: Apache License 2.0
- Commercial: Contact contact@narapallc.com
