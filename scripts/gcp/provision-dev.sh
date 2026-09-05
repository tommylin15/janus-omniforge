#!/usr/bin/env bash
set -Eeuo pipefail

# Idempotent dev bootstrap. This is the replacement for the former Terraform
# resource creation path. It only creates missing resources or applies the
# declared IAM/configuration; it never destroys resources.

project="${GCP_PROJECT_ID:?GCP_PROJECT_ID is required}"
region="${GCP_REGION:-us-central1}"
zone="${GCP_ZONE:-us-central1-a}"
repo="${GITHUB_REPOSITORY:-tommylin15/janus-omniforge}"
ci_sa="${GCP_CI_SERVICE_ACCOUNT:-janus-ci@${project}.iam.gserviceaccount.com}"
network="janusai-lake-poc"
subnet="janusai-lake-poc-uscentral1"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
cleanup_policy="${repo_root}/infra/artifact-registry-cleanup-policy.json"

if [[ "${ALLOW_DEV_PROVISION:-false}" != "true" ]]; then
  echo "Refusing provisioning: set ALLOW_DEV_PROVISION=true explicitly." >&2
  exit 1
fi

gcloud config set project "${project}" >/dev/null

# Keep this allowlist aligned with the project cost policy. In particular, do
# not add Artifact Analysis, Container Scanning, or occurrence APIs.
gcloud services enable \
  compute.googleapis.com iam.googleapis.com iap.googleapis.com \
  oslogin.googleapis.com run.googleapis.com cloudscheduler.googleapis.com \
  serviceusage.googleapis.com secretmanager.googleapis.com \
  artifactregistry.googleapis.com cloudbuild.googleapis.com \
  iamcredentials.googleapis.com --quiet

ensure_sa() {
  local account="$1" display="$2"
  if ! gcloud iam service-accounts describe "${account}@${project}.iam.gserviceaccount.com" >/dev/null 2>&1; then
    gcloud iam service-accounts create "${account}" --display-name="${display}" --quiet
  fi
}

ensure_sa janus-ingestion-scheduler 'Janus ingestion scheduler'
ensure_sa postgres-vm 'PostgreSQL VM runtime'
ensure_sa janus-user-api 'Janus private User API'
ensure_sa janus-private-pipeline 'Janus private pipeline'

for layer in stage core mart private; do
  bucket="${project}-dev-${layer}"
  if ! gcloud storage buckets describe "gs://${bucket}" >/dev/null 2>&1; then
    gcloud storage buckets create "gs://${bucket}" --project="${project}" \
      --location="${region}" --uniform-bucket-level-access --public-access-prevention
  fi
  gcloud storage buckets update "gs://${bucket}" \
    --versioning --public-access-prevention --update-labels="environment=dev,layer=${layer},managed_by=github" \
    --quiet
done
gcloud storage buckets update "gs://${project}-dev-private" \
  --lifecycle-file="${repo_root}/infra/private-bucket-lifecycle.json" --quiet
for account in janus-user-api janus-private-pipeline; do
  gcloud storage buckets add-iam-policy-binding "gs://${project}-dev-private" \
    --member="serviceAccount:${account}@${project}.iam.gserviceaccount.com" \
    --role=roles/storage.objectAdmin --quiet
done

for repository in janus-postgres janusai-poc; do
  if ! gcloud artifacts repositories describe "${repository}" --location="${region}" >/dev/null 2>&1; then
    gcloud artifacts repositories create "${repository}" --location="${region}" \
      --repository-format=docker --description="Janus dev images; scanning APIs are prohibited." --quiet
  fi
  gcloud artifacts repositories set-cleanup-policies "${repository}" \
    --location="${region}" --policy="${cleanup_policy}" --no-dry-run --quiet
done

pool="github-actions"
provider="github"
if ! gcloud iam workload-identity-pools describe "${pool}" --location=global >/dev/null 2>&1; then
  gcloud iam workload-identity-pools create "${pool}" --location=global \
    --display-name='GitHub Actions' --description='Janus GitHub OIDC identities' --quiet
fi
if ! gcloud iam workload-identity-pools providers describe "${provider}" \
    --workload-identity-pool="${pool}" --location=global >/dev/null 2>&1; then
  gcloud iam workload-identity-pools providers create-oidc "${provider}" \
    --workload-identity-pool="${pool}" --location=global \
    --issuer-uri='https://token.actions.githubusercontent.com' \
    --attribute-mapping='google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.actor=assertion.actor,attribute.ref=assertion.ref' \
    --attribute-condition="assertion.repository == '${repo}' && assertion.ref == 'refs/heads/main'" \
    --display-name='GitHub Actions OIDC' --quiet
fi
gcloud iam workload-identity-pools providers update-oidc "${provider}" \
  --workload-identity-pool="${pool}" --location=global \
  --attribute-mapping='google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.actor=assertion.actor,attribute.ref=assertion.ref' \
  --attribute-condition="assertion.repository == '${repo}' && assertion.ref == 'refs/heads/main'" \
  --quiet

pool_name="$(gcloud iam workload-identity-pools describe "${pool}" --location=global --format='value(name)')"
gcloud iam service-accounts add-iam-policy-binding "${ci_sa}" \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/${pool_name}/attribute.repository/${repo}" --quiet

# Runtime repository access and the minimum deploy permissions used by the
# existing Cloud Build config. IAM bindings are additive and idempotent.
gcloud artifacts repositories add-iam-policy-binding janusai-poc --location="${region}" \
  --member="serviceAccount:${ci_sa}" --role=roles/artifactregistry.writer --quiet
gcloud projects add-iam-policy-binding "${project}" \
  --member="serviceAccount:${ci_sa}" --role=roles/run.admin --condition=None --quiet

# Existing Free Tier PostgreSQL is intentionally not auto-created here. Fail
# closed if the fixed, private topology is absent or has drifted.
vm="$(gcloud compute instances describe janus-postgres-dev --zone="${zone}" --format='value(name)' 2>/dev/null || true)"
if [[ "${vm}" != janus-postgres-dev ]]; then
  echo 'janus-postgres-dev is missing; manual review is required before creating the Free Tier VM.' >&2
  exit 1
fi
machine="$(gcloud compute instances describe janus-postgres-dev --zone="${zone}" --format='value(machineType.basename())')"
disk="$(gcloud compute disks describe janus-postgres-dev --zone="${zone}" --format='value(sizeGb)' 2>/dev/null || true)"
if [[ "${machine}" != e2-micro || "${disk}" != 30 ]]; then
  echo "PostgreSQL Free Tier guard failed: machine=${machine}, disk=${disk}" >&2
  exit 1
fi

echo "Dev bootstrap complete. WIF provider: ${pool_name}/providers/${provider}"
