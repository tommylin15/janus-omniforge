#!/usr/bin/env bash
set -Eeuo pipefail

# GitHub Actions is the deployment controller for dev. This script deliberately
# does not call Terraform; Cloud Build remains the image builder and runtime
# deployer, while GitHub supplies the authenticated invocation.

project="${GCP_PROJECT_ID:?GCP_PROJECT_ID is required}"
region="${GCP_REGION:-us-central1}"
tag="${IMAGE_TAG:-dev-${GITHUB_SHA:-local}}"
git_sha="${GITHUB_SHA:-$(git rev-parse HEAD)}"
no_traffic="${DEV_DEPLOY_NO_TRAFFIC:-false}"
traffic_tag="${DEV_TRAFFIC_TAG:-}"
revision_suffix="${DEV_REVISION_SUFFIX:-}"

if [[ "${no_traffic}" != "true" && "${no_traffic}" != "false" ]]; then
  echo "DEV_DEPLOY_NO_TRAFFIC must be true or false." >&2
  exit 2
fi

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
  api)
    dockerfile="services/api/Dockerfile"
    image_name="api"
    deploy_target="service"
    runtime_name="janus-api"
    ;;
  *)
    echo "Usage: $0 {ingestion-core|intelligence-mart|private-pipeline|api}" >&2
    exit 2
    ;;
esac

if [[ "${ALLOW_DEV_DEPLOY:-false}" != "true" ]]; then
  echo "Refusing deployment: set ALLOW_DEV_DEPLOY=true explicitly." >&2
  exit 1
fi

gcloud builds submit . \
  --project="${project}" \
  --config=cloudbuild.yaml \
  --substitutions="_DOCKERFILE=${dockerfile},_IMAGE_NAME=${image_name},_IMAGE_TAG=${tag},_DEPLOY_TARGET=${deploy_target},_RUNTIME_NAME=${runtime_name},_REGION=${region},_GIT_SHA=${git_sha},_NO_TRAFFIC=${no_traffic},_TRAFFIC_TAG=${traffic_tag},_REVISION_SUFFIX=${revision_suffix}"

# The new image accepts both legacy and merged field names. Deploy it before
# changing the Secret reference so service revisions never see an incompatible payload.
case "${component}" in
  ingestion-core)
    gcloud run jobs update "${runtime_name}" --project="${project}" --region="${region}" \
      --service-account="ingestion-core@${project}.iam.gserviceaccount.com" \
      --tasks=1 --parallelism=1 --max-retries=1 --task-timeout=30m \
      --update-env-vars="MART_JOB=janus-intelligence-mart,GCP_REGION=${region}" \
      --remove-secrets="CONTROL_DB_PASSWORD,CATALOG_DB_PASSWORD" \
      --update-secrets="JANUS_INGESTION_POSTGRES_BUNDLE=janus-agent-provider-bundle:latest" --quiet
    ;;
  intelligence-mart)
    gcloud run jobs update "${runtime_name}" --project="${project}" --region="${region}" \
      --service-account="intelligence-mart@${project}.iam.gserviceaccount.com" \
      --tasks=1 --parallelism=1 --max-retries=1 --task-timeout=30m \
      --remove-secrets="CATALOG_DB_PASSWORD,PUBLICATION_DB_PASSWORD" \
      --update-secrets="JANUS_MART_POSTGRES_BUNDLE=janus-agent-provider-bundle:latest" --quiet
    ;;
  private-pipeline)
    gcloud run jobs update "${runtime_name}" --project="${project}" --region="${region}" \
    --service-account="janus-private-pipeline@${project}.iam.gserviceaccount.com" \
    --tasks=1 --parallelism=1 --max-retries=1 --task-timeout=30m \
      --remove-secrets="PRIVATE_DATABASE_URL,PRIVATE_CATALOG_PASSWORD,JANUS_PIPELINE_POSTGRES_BUNDLE" \
      --update-secrets="CORE_CATALOG_PASSWORD=janus-postgres-api-bundle:latest,JANUS_API_POSTGRES_BUNDLE=janus-postgres-api-bundle:latest" --quiet
    ;;
  api)
    service_flags=()
    if [[ "${no_traffic}" == "true" ]]; then service_flags+=(--no-traffic); fi
    if [[ -n "${traffic_tag}" ]]; then service_flags+=(--tag="${traffic_tag}"); fi
    if [[ -n "${revision_suffix}" ]]; then service_flags+=(--revision-suffix="${revision_suffix}-config"); fi
    api_env="MCP_OAUTH_ENABLED=${MCP_OAUTH_ENABLED:-false}"
    if [[ "${MCP_OAUTH_ENABLED:-false}" == "true" ]]; then
      oauth_issuer="${MCP_OAUTH_ISSUER:?MCP_OAUTH_ISSUER is required when MCP_OAUTH_ENABLED=true}"
      oauth_resource="${MCP_RESOURCE_URL:?MCP_RESOURCE_URL is required when MCP_OAUTH_ENABLED=true}"
      oauth_emails="${GOOGLE_USER_ALLOWED_EMAILS:?GOOGLE_USER_ALLOWED_EMAILS is required when MCP_OAUTH_ENABLED=true}"
      api_env="${api_env},MCP_OAUTH_ISSUER=${oauth_issuer},MCP_RESOURCE_URL=${oauth_resource},GOOGLE_USER_ALLOWED_EMAILS=${oauth_emails}"
    fi
    gcloud run services update "${runtime_name}" --project="${project}" --region="${region}" \
      --service-account="janus-user-api@${project}.iam.gserviceaccount.com" \
      --min-instances=0 --max-instances=2 --concurrency=20 --timeout=60 \
      --update-env-vars="${api_env}" \
      --update-secrets="JANUS_API_POSTGRES_BUNDLE=janus-postgres-api-bundle:latest" \
      "${service_flags[@]}" --quiet
    ;;
esac

echo "Dev deployment completed for ${runtime_name}; verify the immutable digest in Cloud Build logs."
