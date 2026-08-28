#!/usr/bin/env bash
set -Eeuo pipefail

project="${GCP_PROJECT_ID:?GCP_PROJECT_ID is required}"
region="${GCP_REGION:-us-central1}"

echo '--- Cloud Run services ---'
gcloud run services list --project="${project}" --region="${region}"
echo '--- Cloud Run jobs ---'
gcloud run jobs list --project="${project}" --region="${region}"
echo '--- PostgreSQL VM ---'
gcloud compute instances describe janus-postgres-dev \
  --project="${project}" --zone="${GCP_ZONE:-us-central1-a}" \
  --format='yaml(name,status,networkInterfaces[0].networkIP,machineType,disks[0].diskSizeGb)'
