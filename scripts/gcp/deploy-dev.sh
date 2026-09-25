#!/usr/bin/env bash
set -Eeuo pipefail

# GitHub Actions is the deployment controller for dev. This script deliberately
# does not call Terraform; Cloud Build builds/pushes the image and may stage the
# runtime image, while this script applies the canonical runtime configuration.

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
    image_name="private-pipeline"
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

if [[ "${component}" == api || "${component}" == private-pipeline ]]; then
  : "${GOOGLE_USER_CLIENT_ID:?GOOGLE_USER_CLIENT_ID is required for the Janus Web build}"
  : "${GOOGLE_ADMIN_CLIENT_ID:?GOOGLE_ADMIN_CLIENT_ID is required for the Janus Web build}"
fi

if [[ "${ALLOW_DEV_DEPLOY:-false}" != "true" ]]; then
  echo "Refusing deployment: set ALLOW_DEV_DEPLOY=true explicitly." >&2
  exit 1
fi

gcloud builds submit . \
  --project="${project}" \
  --config=cloudbuild.yaml \
  --substitutions="_DOCKERFILE=${dockerfile},_IMAGE_NAME=${image_name},_IMAGE_TAG=${tag},_DEPLOY_TARGET=${deploy_target},_RUNTIME_NAME=${runtime_name},_REGION=${region},_GIT_SHA=${git_sha},_NO_TRAFFIC=${no_traffic},_TRAFFIC_TAG=${traffic_tag},_REVISION_SUFFIX=${revision_suffix},_GOOGLE_USER_CLIENT_ID=${GOOGLE_USER_CLIENT_ID:-},_GOOGLE_ADMIN_CLIENT_ID=${GOOGLE_ADMIN_CLIENT_ID:-}"

# Keep job configurations aligned with their immutable image and current Secret bundle.
case "${component}" in
  ingestion-core)
    gcloud run jobs update "${runtime_name}" --project="${project}" --region="${region}" \
      --service-account="ingestion-core@${project}.iam.gserviceaccount.com" \
      --tasks=1 --parallelism=1 --max-retries=1 --task-timeout=30m \
      --update-env-vars="MART_JOB=janus-intelligence-mart,GCP_REGION=${region},MART_OPERATION=queue" \
      --remove-secrets="CONTROL_DB_PASSWORD,CATALOG_DB_PASSWORD" \
      --update-secrets="JANUS_INGESTION_POSTGRES_BUNDLE=janus-runtime-bundle:latest" --quiet
    gcloud run jobs add-iam-policy-binding janus-intelligence-mart \
      --project="${project}" --region="${region}" \
      --member="serviceAccount:ingestion-core@${project}.iam.gserviceaccount.com" \
      --role=roles/run.invoker --quiet
    ;;
  intelligence-mart)
    gcloud run jobs update "${runtime_name}" --project="${project}" --region="${region}" \
      --service-account="intelligence-mart@${project}.iam.gserviceaccount.com" \
      --tasks=1 --parallelism=1 --max-retries=1 --task-timeout=30m \
      --remove-secrets="CATALOG_DB_PASSWORD,PUBLICATION_DB_PASSWORD" \
      --update-secrets="JANUS_MART_POSTGRES_BUNDLE=janus-runtime-bundle:latest" --quiet
    ;;
  private-pipeline)
    gcloud run jobs update "${runtime_name}" --project="${project}" --region="${region}" \
      --service-account="janus-private-pipeline@${project}.iam.gserviceaccount.com" \
      --tasks=1 --parallelism=1 --max-retries=1 --task-timeout=30m \
      --remove-env-vars="VALUATION_DATE" \
      --remove-secrets="CORE_CATALOG_PASSWORD,PRIVATE_DATABASE_URL,PRIVATE_CATALOG_PASSWORD,JANUS_PIPELINE_POSTGRES_BUNDLE" \
      --update-secrets="JANUS_API_POSTGRES_BUNDLE=janus-runtime-bundle:latest" --quiet
    ;;
  api)
    # A canonical API deploy must create a distinct revision. Reusing an old
    # template revision can leave 100% traffic on stale Flutter assets even
    # when the service template image digest has changed.
    service_revision_suffix="${revision_suffix}"
    if [[ -z "${service_revision_suffix}" ]]; then
      if [[ "${git_sha}" =~ ^[0-9a-f]{7,64}$ ]]; then
        service_revision_suffix="g${git_sha:0:12}"
      else
        service_revision_suffix="manual-$(date -u +%Y%m%d%H%M%S)"
      fi
    fi

    service_flags=()
    if [[ "${no_traffic}" == "true" ]]; then service_flags+=(--no-traffic); fi
    if [[ -n "${traffic_tag}" ]]; then service_flags+=(--tag="${traffic_tag}"); fi
    service_flags+=(--revision-suffix="${service_revision_suffix}-config")

    api_env="${MCP_OAUTH_ENABLED:+MCP_OAUTH_ENABLED=${MCP_OAUTH_ENABLED}}"
    if [[ -n "${GOOGLE_ADMIN_ALLOWED_EMAILS:-}" ]]; then
      api_env="${api_env:+${api_env},}GOOGLE_ADMIN_ALLOWED_EMAILS=${GOOGLE_ADMIN_ALLOWED_EMAILS}"
    fi
    if [[ "${MCP_OAUTH_ENABLED:-}" == "true" ]]; then
      oauth_issuer="${MCP_OAUTH_ISSUER:?MCP_OAUTH_ISSUER is required when MCP_OAUTH_ENABLED=true}"
      oauth_resource="${MCP_RESOURCE_URL:?MCP_RESOURCE_URL is required when MCP_OAUTH_ENABLED=true}"
      oauth_emails="${GOOGLE_USER_ALLOWED_EMAILS:?GOOGLE_USER_ALLOWED_EMAILS is required when MCP_OAUTH_ENABLED=true}"
      [[ "${oauth_issuer}" == https://mcp-oauth---*.a.run.app ]] || { echo "Dev OAuth issuer must use the mcp-oauth tag." >&2; exit 1; }
      [[ "${oauth_resource}" == https://mcp-adapter---*.a.run.app/mcp ]] || { echo "Dev MCP resource must use the mcp-adapter tag." >&2; exit 1; }
      api_env="${api_env:+${api_env},}MCP_OAUTH_ISSUER=${oauth_issuer},MCP_RESOURCE_URL=${oauth_resource},GOOGLE_USER_ALLOWED_EMAILS=${oauth_emails}"
    fi
    service_env_flags=()
    if [[ -n "${api_env}" ]]; then service_env_flags+=(--update-env-vars="${api_env}"); fi
    deployed_digest="$(gcloud artifacts docker images describe \
      "us-central1-docker.pkg.dev/${project}/janusai-poc/api:${tag}" \
      --project="${project}" --format='value(image_summary.digest)')"
    gcloud run services update "${runtime_name}" --project="${project}" --region="${region}" \
      --image="us-central1-docker.pkg.dev/${project}/janusai-poc/api@${deployed_digest}" \
      --service-account="janus-user-api@${project}.iam.gserviceaccount.com" \
      --min-instances=0 --max-instances=2 --concurrency=20 --timeout=60 \
      "${service_env_flags[@]}" \
      --remove-env-vars="INTERNAL_ASSISTANT_AUDIENCE,ASSISTANT_SERVICE_ACCOUNTS,MCP_GATEWAY_URL" \
      --update-secrets="JANUS_API_POSTGRES_BUNDLE=janus-runtime-bundle:latest" \
      "${service_flags[@]}" --quiet

    if [[ "${no_traffic}" != "true" ]]; then
      gcloud run services update-traffic "${runtime_name}" \
        --project="${project}" --region="${region}" --to-latest --quiet
    fi
    ;;
esac

echo "Dev deployment completed for ${runtime_name}; verify the immutable digest and live revision."
