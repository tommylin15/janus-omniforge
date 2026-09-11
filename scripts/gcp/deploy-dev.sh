#!/usr/bin/env bash
set -Eeuo pipefail

# GitHub Actions is the deployment controller for dev. This script deliberately
# does not call Terraform; Cloud Build remains the image builder and runtime
# deployer, while GitHub supplies the authenticated invocation.

project="${GCP_PROJECT_ID:?GCP_PROJECT_ID is required}"
region="${GCP_REGION:-us-central1}"
tag="${IMAGE_TAG:-dev-${GITHUB_SHA:-local}}"

component="${1:-}"
case "${component}" in
  ingestion-core)
    dockerfile="jobs/ingestion-core/Dockerfile"
    image_name="ingestion-core"
    deploy_target="job"
    runtime_name="janus-ingestion-core"
    ;;
  intelligence-mart)
    dockerfile="jobs/intelligence-mart/Dockerfile"
    image_name="intelligence-mart"
    deploy_target="job"
    runtime_name="janus-intelligence-mart"
    ;;
  private-pipeline)
    dockerfile="services/api/Dockerfile"
    image_name="api"
    deploy_target="job"
    runtime_name="janus-private-pipeline"
    ;;
  web)
    dockerfile="apps/web/Dockerfile"
    image_name="web"
    deploy_target="service"
    runtime_name="janus-web"
    ;;
  *)
    echo "Usage: $0 {ingestion-core|intelligence-mart|private-pipeline|web}" >&2
    exit 2
    ;;
esac

if [[ "${ALLOW_DEV_DEPLOY:-false}" != "true" ]]; then
  echo "Refusing deployment: set ALLOW_DEV_DEPLOY=true explicitly." >&2
  exit 1
fi

case "${component}" in
  ingestion-core)
    gcloud run jobs update "${runtime_name}" --project="${project}" --region="${region}" \
      --remove-secrets="CONTROL_DB_PASSWORD,CATALOG_DB_PASSWORD" \
      --update-secrets="JANUS_INGESTION_POSTGRES_BUNDLE=janus-postgres-ingestion-bundle:latest" --quiet
    ;;
  intelligence-mart)
    gcloud run jobs update "${runtime_name}" --project="${project}" --region="${region}" \
      --remove-secrets="CATALOG_DB_PASSWORD,PUBLICATION_DB_PASSWORD" \
      --update-secrets="JANUS_MART_POSTGRES_BUNDLE=janus-postgres-mart-bundle:latest" --quiet
    ;;
  private-pipeline)
    gcloud run jobs update "${runtime_name}" --project="${project}" --region="${region}" \
      --remove-secrets="PRIVATE_DATABASE_URL,CORE_CATALOG_PASSWORD,PRIVATE_CATALOG_PASSWORD" \
      --update-secrets="JANUS_PIPELINE_POSTGRES_BUNDLE=janus-postgres-pipeline-bundle:latest,JANUS_API_POSTGRES_BUNDLE=janus-postgres-api-bundle:latest" --quiet
    ;;
esac

gcloud builds submit . \
  --project="${project}" \
  --config=cloudbuild.yaml \
  --substitutions="_DOCKERFILE=${dockerfile},_IMAGE_NAME=${image_name},_IMAGE_TAG=${tag},_DEPLOY_TARGET=${deploy_target},_RUNTIME_NAME=${runtime_name},_REGION=${region}"

echo "Dev deployment completed for ${runtime_name}; verify the immutable digest in Cloud Build logs."
