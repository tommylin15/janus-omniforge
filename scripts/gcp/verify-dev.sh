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

verify_png() {
  local path="$1"
  local expected_width="$2"
  local expected_height="$3"
  python - "${path}" "${expected_width}" "${expected_height}" <<'PY'
import pathlib
import struct
import sys

payload = pathlib.Path(sys.argv[1]).read_bytes()
expected = (int(sys.argv[2]), int(sys.argv[3]))
if len(payload) < 32 or not payload.startswith(b"\x89PNG\r\n\x1a\n"):
    raise SystemExit("payload is not a valid PNG")
width, height = struct.unpack(">II", payload[16:24])
if (width, height) != expected:
    raise SystemExit(f"unexpected PNG size {(width, height)} != {expected}")
PY
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
    local traffic_state latest_ready traffic_revision traffic_percent active_count
    traffic_state="$(gcloud run services describe "${service}" \
      --project="${project}" --region="${region}" --format=json | \
      python -c 'import json,sys; d=json.load(sys.stdin); s=d.get("status",{}); active=[t for t in s.get("traffic",[]) if int(t.get("percent") or 0)>0]; latest=s.get("latestReadyRevisionName",""); rev=active[0].get("revisionName","") if len(active)==1 else ""; pct=str(active[0].get("percent",0)) if len(active)==1 else "0"; print("\t".join((latest,rev,pct,str(len(active)))))')"
    IFS=$'\t' read -r latest_ready traffic_revision traffic_percent active_count <<< "${traffic_state}"
    if [[ -z "${latest_ready}" || "${active_count}" != "1" || "${traffic_revision}" != "${latest_ready}" || "${traffic_percent}" != "100" ]]; then
      echo "janus-api traffic is not 100% on latest ready revision: latest=${latest_ready} traffic=${traffic_revision} percent=${traffic_percent} active=${active_count}" >&2
      return 1
    fi
  fi

  if [[ "${service}" == "janus-api" && "${GITHUB_SHA:-}" =~ ^[0-9a-f]{7,64}$ ]]; then
    local service_url build_id index_html expected_bootstrap brand_image app_icon pwa_icon pwa_icon_512 maskable_icon manifest_json
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
    if [[ "${index_html}" != *"/app/manifest.json"* || "${index_html}" != *"/app/apple-touch-icon.png"* || "${index_html}" != *"/app/favicon.png"* ]]; then
      echo "janus-api index does not advertise the canonical /app PWA metadata" >&2
      return 1
    fi

    brand_image="$(mktemp)"
    curl -fsS --retry 6 --retry-delay 2 \
      "${service_url}/app/og-image.jpg?expected=${GITHUB_SHA}" -o "${brand_image}"
    python - "${brand_image}" <<'PY'
import pathlib
import sys
payload = pathlib.Path(sys.argv[1]).read_bytes()
if len(payload) < 10_000 or not payload.startswith(b"\xff\xd8"):
    raise SystemExit("Janus brand image is missing or is not a valid JPEG payload")
PY
    rm -f "${brand_image}"

    app_icon="$(mktemp)"
    curl -fsS --retry 6 --retry-delay 2 \
      "${service_url}/app/assets/assets/branding/janus_app_icon_512.png?expected=${GITHUB_SHA}" -o "${app_icon}"
    verify_png "${app_icon}" 512 512
    rm -f "${app_icon}"

    pwa_icon="$(mktemp)"
    curl -fsS --retry 6 --retry-delay 2 \
      "${service_url}/app/icons/Icon-192.png?expected=${GITHUB_SHA}" -o "${pwa_icon}"
    verify_png "${pwa_icon}" 192 192
    rm -f "${pwa_icon}"

    pwa_icon_512="$(mktemp)"
    curl -fsS --retry 6 --retry-delay 2 \
      "${service_url}/app/icons/Icon-512.png?expected=${GITHUB_SHA}" -o "${pwa_icon_512}"
    verify_png "${pwa_icon_512}" 512 512
    rm -f "${pwa_icon_512}"

    maskable_icon="$(mktemp)"
    curl -fsS --retry 6 --retry-delay 2 \
      "${service_url}/app/icons/maskable-512.png?expected=${GITHUB_SHA}" -o "${maskable_icon}"
    verify_png "${maskable_icon}" 512 512
    rm -f "${maskable_icon}"

    manifest_json="$(curl -fsS --retry 6 --retry-delay 2 \
      "${service_url}/app/manifest.json?expected=${GITHUB_SHA}")"
    python - "${manifest_json}" <<'PY'
import json
import sys
manifest = json.loads(sys.argv[1])
if manifest.get("id") != "/app/":
    raise SystemExit("Janus manifest id is not /app/")
if manifest.get("start_url") != "/app/":
    raise SystemExit("Janus manifest start_url is not /app/")
if manifest.get("scope") != "/app/":
    raise SystemExit("Janus manifest scope is not /app/")
icons = {(item.get("src"), item.get("sizes"), item.get("type"), item.get("purpose")) for item in manifest.get("icons", [])}
required = {
    ("/app/icons/Icon-192.png", "192x192", "image/png", "any"),
    ("/app/icons/Icon-512.png", "512x512", "image/png", "any"),
    ("/app/icons/maskable-512.png", "512x512", "image/png", "maskable"),
}
missing = required - icons
if missing:
    raise SystemExit(f"Janus manifest is missing PNG install icons: {sorted(missing)}")
PY

    echo "janus-api traffic, web build, high-resolution PNG branding, and PWA metadata match ${GITHUB_SHA}"
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
