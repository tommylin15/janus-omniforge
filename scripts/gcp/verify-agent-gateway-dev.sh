#!/usr/bin/env bash
set -Eeuo pipefail

project="${GCP_PROJECT_ID:?GCP_PROJECT_ID is required}"
region="${GCP_REGION:-us-central1}"
service="janus-agent-gateway"
build_account="${GCP_BUILD_SERVICE_ACCOUNT:-$(gcloud projects describe "${project}" --format='value(projectNumber)')-compute@developer.gserviceaccount.com}"
invoker="janus-agent-poc-invoker@${project}.iam.gserviceaccount.com"
provider_bundle="${AGENT_PROVIDER_BUNDLE_SECRET_NAME:-janus-agent-provider-bundle}"
url="$(gcloud run services describe janus-agent-gateway \
  --project="${project}" --region="${region}" --format='value(status.url)')"

member="serviceAccount:${build_account}"
token_added=false
token_existing="$(gcloud iam service-accounts get-iam-policy "${invoker}" --project="${project}" \
  --flatten='bindings[].members' \
  --filter="bindings.role:roles/iam.serviceAccountTokenCreator AND bindings.members:${member}" \
  --format='value(bindings.members)')"
if [[ -z "${token_existing}" ]]; then
  gcloud iam service-accounts add-iam-policy-binding "${invoker}" --project="${project}" \
    --member="${member}" --role=roles/iam.serviceAccountTokenCreator --quiet >/dev/null
  token_added=true
fi
cleanup() {
  if [[ "${token_added}" == true ]]; then
    gcloud iam service-accounts remove-iam-policy-binding "${invoker}" --project="${project}" \
      --member="${member}" --role=roles/iam.serviceAccountTokenCreator --quiet >/dev/null || true
  fi
}
trap cleanup EXIT

if [[ "${token_added}" == true ]]; then
  wait_seconds="${IAM_PROPAGATION_WAIT_SECONDS:-300}"
  while (( wait_seconds > 0 )); do
    echo "Waiting for temporary IAM propagation: ${wait_seconds}s"
    sleep 30
    wait_seconds=$((wait_seconds - 30))
  done
fi

if ! gcloud secrets get-iam-policy "${provider_bundle}" --project="${project}" \
  --flatten='bindings[].members' --filter="bindings.role:roles/secretmanager.secretAccessor AND bindings.members:serviceAccount:${build_account}" \
  --format='value(bindings.members)' | grep -q .; then
  gcloud secrets add-iam-policy-binding "${provider_bundle}" --project="${project}" \
    --member="serviceAccount:${build_account}" --role=roles/secretmanager.secretAccessor --quiet >/dev/null
fi

gcloud builds submit . --project="${project}" \
  --config=scripts/gcp/cloudbuild-agent-gateway-verify.yaml \
  --substitutions="_SERVICE_URL=${url},_TOKEN_SERVICE_ACCOUNT=${invoker},_LIVE_VERIFY=${LIVE_VERIFY:-false},_AGENT_PROVIDER_BUNDLE_SECRET_NAME=${provider_bundle},_OWNER_ID=${CODEX_OWNER_ID:-00000000-0000-4000-8000-000000000001}"
