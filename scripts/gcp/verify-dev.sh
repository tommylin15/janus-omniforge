#!/usr/bin/env bash
set -Eeuo pipefail

project="${GCP_PROJECT_ID:?GCP_PROJECT_ID is required}"
region="${GCP_REGION:-us-central1}"
component="${1:-all}"

verify_job() {
  local job="$1"
  echo "--- Cloud Run job: ${job} ---"
  gcloud run jobs describe "${job}" \
    --project="${project}" --region="${region}" \
    --format='yaml(metadata.name,spec.template.template.containers[0].image,status.conditions)'
  local ready
  ready="$(gcloud run jobs describe "${job}" \
    --project="${project}" --region="${region}" \
    --format='value(status.conditions[0].status)')"
  if [[ "${ready}" != "True" ]]; then
    echo "Cloud Run job ${job} is not Ready" >&2
    return 1
  fi
}

verify_service() {
  local service="$1"
  echo "--- Cloud Run service: ${service} ---"
  gcloud run services describe "${service}" \
    --project="${project}" --region="${region}" \
    --format='yaml(metadata.name,status.url,status.conditions,spec.template.spec.containers[0].image)'
  local ready
  ready="$(gcloud run services describe "${service}" \
    --project="${project}" --region="${region}" \
    --format='value(status.conditions[0].status)')"
  if [[ "${ready}" != "True" ]]; then
    echo "Cloud Run service ${service} is not Ready" >&2
    return 1
  fi
}

case "${component}" in
  ingestion-core)
    verify_job janus-ingestion-core
    ;;
  intelligence-mart)
    verify_job janus-intelligence-mart
    ;;
  api)
    verify_service janus-api
    ;;
  postgres)
    echo '--- PostgreSQL VM ---'
    gcloud compute instances describe janus-postgres-dev \
      --project="${project}" --zone="${GCP_ZONE:-us-central1-a}" \
      --format='yaml(name,status,networkInterfaces[0].networkIP,machineType,disks[0].diskSizeGb)'
    ;;
  all)
    verify_job janus-ingestion-core
    verify_job janus-intelligence-mart
    verify_service janus-api
    if [[ "${VERIFY_POSTGRES_VM:-false}" == "true" ]]; then
      "$0" postgres
    fi
    ;;
  *)
    echo "unsupported dev verification component: ${component}" >&2
    exit 2
    ;;
esac
