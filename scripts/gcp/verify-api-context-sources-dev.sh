#!/usr/bin/env bash
set -Eeuo pipefail

project="${GCP_PROJECT_ID:?GCP_PROJECT_ID is required}"
region="${GCP_REGION:-us-central1}"
api_url="$(gcloud run services describe janus-api --project="${project}" --region="${region}" --format='value(status.url)')"
project_number="$(gcloud projects describe "${project}" --format='value(projectNumber)')"
build_account="${GCP_BUILD_SERVICE_ACCOUNT:-${project_number}-compute@developer.gserviceaccount.com}"
user_api="janus-user-api@${project}.iam.gserviceaccount.com"
gateway="janus-agent-gateway@${project}.iam.gserviceaccount.com"
added_user=false
added_gateway=false
added_bundle=false

cleanup() {
  if [[ "${added_user}" == true ]]; then
    gcloud iam service-accounts remove-iam-policy-binding "${user_api}" --project="${project}" \
      --member="serviceAccount:${build_account}" --role=roles/iam.serviceAccountTokenCreator --quiet >/dev/null || true
  fi
  if [[ "${added_gateway}" == true ]]; then
    gcloud iam service-accounts remove-iam-policy-binding "${gateway}" --project="${project}" \
      --member="serviceAccount:${build_account}" --role=roles/iam.serviceAccountTokenCreator --quiet >/dev/null || true
  fi
  if [[ "${added_bundle}" == true ]]; then
    gcloud secrets remove-iam-policy-binding janus-postgres-api-bundle --project="${project}" \
      --member="serviceAccount:${build_account}" --role=roles/secretmanager.secretAccessor --quiet >/dev/null || true
  fi
}
trap cleanup EXIT

for account in "${user_api}" "${gateway}"; do
  existing="$(gcloud iam service-accounts get-iam-policy "${account}" --project="${project}" \
    --flatten='bindings[].members' --filter="bindings.role:roles/iam.serviceAccountTokenCreator AND bindings.members:serviceAccount:${build_account}" \
    --format='value(bindings.members)')"
  if [[ -z "${existing}" ]]; then
    gcloud iam service-accounts add-iam-policy-binding "${account}" --project="${project}" \
      --member="serviceAccount:${build_account}" --role=roles/iam.serviceAccountTokenCreator --quiet >/dev/null
    if [[ "${account}" == "${user_api}" ]]; then added_user=true; else added_gateway=true; fi
  fi
done

if ! gcloud secrets get-iam-policy janus-postgres-api-bundle --project="${project}" \
  --flatten='bindings[].members' --filter="bindings.role:roles/secretmanager.secretAccessor AND bindings.members:serviceAccount:${build_account}" \
  --format='value(bindings.members)' | grep -q .; then
  gcloud secrets add-iam-policy-binding janus-postgres-api-bundle --project="${project}" \
    --member="serviceAccount:${build_account}" --role=roles/secretmanager.secretAccessor --quiet >/dev/null
  added_bundle=true
fi

if [[ "${added_user}" == true || "${added_gateway}" == true ]]; then
  wait_seconds="${IAM_PROPAGATION_WAIT_SECONDS:-300}"
  while (( wait_seconds > 0 )); do
    echo "Waiting for temporary IAM propagation: ${wait_seconds}s"
    sleep 30
    wait_seconds=$((wait_seconds - 30))
  done
fi

gcloud builds submit . --project="${project}" \
  --config=scripts/gcp/cloudbuild-api-context-verify.yaml \
  --substitutions="_API_URL=${api_url},_USER_API_SERVICE_ACCOUNT=${user_api},_TOKEN_SERVICE_ACCOUNT=${gateway}"
