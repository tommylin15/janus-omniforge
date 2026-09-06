#!/usr/bin/env bash
set -Eeuo pipefail

project="${GCP_PROJECT_ID:?GCP_PROJECT_ID is required}"
region="${GCP_REGION:-us-central1}"
secret="${CODEX_AUTH_SECRET_NAME:-janus-codex-managed-auth}"
service="janus-agent-gateway"
account="janus-agent-gateway@${project}.iam.gserviceaccount.com"
invoker="janus-agent-poc-invoker@${project}.iam.gserviceaccount.com"
operator="${AGENT_GATEWAY_OPERATOR:?AGENT_GATEWAY_OPERATOR is required}"
bucket="${project}-dev-private"
repository="${region}-docker.pkg.dev/${project}/janusai-poc"
tag="${IMAGE_TAG:-agent-poc-${GITHUB_SHA:-$(date -u +%Y%m%d%H%M%S)}}"

if [[ "${ALLOW_AGENT_GATEWAY_DEV_DEPLOY:-false}" != "true" ]]; then
  echo 'Refusing deployment: set ALLOW_AGENT_GATEWAY_DEV_DEPLOY=true explicitly.' >&2
  exit 1
fi
gcloud secrets describe "${secret}" --project="${project}" >/dev/null
gcloud storage buckets describe "gs://${bucket}" --project="${project}" >/dev/null

if ! gcloud iam service-accounts describe "${account}" --project="${project}" >/dev/null 2>&1; then
  gcloud iam service-accounts create janus-agent-gateway --project="${project}" \
    --display-name='Janus Agent Gateway dev' --quiet
fi
if ! gcloud iam service-accounts describe "${invoker}" --project="${project}" >/dev/null 2>&1; then
  gcloud iam service-accounts create janus-agent-poc-invoker --project="${project}" \
    --display-name='Janus Agent Gateway dev invoker' --quiet
fi
for role in roles/storage.objectCreator roles/storage.objectViewer; do
  gcloud storage buckets add-iam-policy-binding "gs://${bucket}" \
    --member="serviceAccount:${account}" --role="${role}" --quiet
done
for role in roles/secretmanager.secretAccessor roles/secretmanager.secretVersionAdder; do
  gcloud secrets add-iam-policy-binding "${secret}" --project="${project}" \
    --member="serviceAccount:${account}" --role="${role}" --quiet
done

if [[ "${SKIP_AGENT_GATEWAY_BUILD:-false}" != "true" ]]; then
  gcloud builds submit . --project="${project}" --config=cloudbuild.yaml \
    --substitutions="_DOCKERFILE=services/agent-gateway/Dockerfile,_IMAGE_NAME=agent-gateway,_IMAGE_TAG=${tag},_DEPLOY_TARGET=,_RUNTIME_NAME=,_REGION=${region}"
fi
digest="$(gcloud artifacts docker images describe "${repository}/agent-gateway:${tag}" \
  --project="${project}" --format='value(image_summary.digest)')"
[[ -n "${digest}" ]]

gcloud run deploy "${service}" --project="${project}" --region="${region}" \
  --image="${repository}/agent-gateway@${digest}" --service-account="${account}" \
  --no-allow-unauthenticated --ingress=all --execution-environment=gen2 \
  --min-instances=0 --max-instances=1 --concurrency=1 --timeout=300 \
  --cpu=1 --memory=1Gi \
  --add-volume=name=agent-sandbox,type=in-memory,size-limit=256Mi \
  --add-volume-mount=volume=agent-sandbox,mount-path=/var/run/janus \
  --set-env-vars="CODEX_POC_ENABLED=true,CODEX_AUTH_SECRET=projects/${project}/secrets/${secret},AGENT_CHECKPOINT_BUCKET=${bucket}" \
  --quiet
gcloud run services add-iam-policy-binding "${service}" --project="${project}" --region="${region}" \
  --member="serviceAccount:${invoker}" --role=roles/run.invoker --quiet
gcloud run services add-iam-policy-binding "${service}" --project="${project}" --region="${region}" \
  --member="user:${operator}" --role=roles/run.invoker --quiet
gcloud iam service-accounts add-iam-policy-binding "${invoker}" --project="${project}" \
  --member="user:${operator}" --role=roles/iam.serviceAccountTokenCreator --quiet

echo "Deployed private dev ${service} at immutable digest ${digest}."
