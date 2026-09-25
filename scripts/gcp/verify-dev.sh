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
    --format='yaml(metadata.name,status.url,status.latestCreatedRevisionName,status.latestReadyRevisionName,status.traffic,status.conditions,spec.template.spec.containers[0].image)'
  local ready
  ready="$(gcloud run services describe "${service}" \
    --project="${project}" --region="${region}" \
    --format='value(status.conditions[0].status)')"
  if [[ "${ready}" != "True" ]]; then
    echo "Cloud Run service ${service} is not Ready" >&2
    return 1
  fi

  if [[ "${service}" == "janus-api" ]]; then
    local latest_ready traffic_revision traffic_percent
    latest_ready="$(gcloud run services describe "${service}" \
      --project="${project}" --region="${region}" --format='value(status.latestReadyRevisionName)')"
    traffic_revision="$(gcloud run services describe "${service}" \
      --project="${project}" --region="${region}" --format='value(status.traffic[].revisionName)')"
    traffic_percent="$(gcloud run services describe "${service}" \
      --project="${project}" --region="${region}" --format='value(status.traffic[].percent)')"
    if [[ -z "${latest_ready}" || "${traffic_revision}" != "${latest_ready}" || "${traffic_percent}" != "100" ]]; then
      echo "janus-api traffic is not 100% on latest ready revision: latest=${latest_ready} traffic=${traffic_revision} percent=${traffic_percent}" >&2
      return 1
    fi
  fi

  if [[ "${service}" == "janus-api" && "${GITHUB_SHA:-}" =~ ^[0-9a-f]{7,64}$ ]]; then
    local service_url build_id index_html expected_bootstrap
    service_url="$(gcloud run services describe "${service}" \
      --project="${project}" --region="${region}" --format='value(status.url)')"
    build_id="$(curl -fsS --retry 6 --retry-delay 2 \
      "${service_url}/app/build-id.txt?expected=${GITHUB_SHA}")"
    if [[ "${build_id}" != "${GITHUB_SHA}" ]]; then
      echo "janus-api web build mismatch: expected ${GITHUB_SHA}, got ${build_id}" >&2
      return 1
    fi
    expected_bootstrap="flutter_bootstrap.${GITHUB_SHA}.js"
    index_html="$(curl -fsS --retry 6 --retry-delay 2 \
      "${service_url}/app/?expected=${GITHUB_SHA}")"
    if [[ "${index_html}" != *"Janus · OmniForge"* ]]; then
      echo "janus-api index is not the customized Janus entrypoint" >&2
      return 1
    fi
    if [[ "${index_html}" != *"${expected_bootstrap}"* ]]; then
      echo "janus-api index does not reference ${expected_bootstrap}" >&2
      return 1
    fi
    echo "janus-api traffic and web build match ${GITHUB_SHA}"
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
