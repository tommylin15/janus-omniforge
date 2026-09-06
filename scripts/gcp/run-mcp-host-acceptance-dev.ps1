$ErrorActionPreference = 'Stop'
$project = 'gen-lang-client-0593591102'
$region = 'us-central1'
$job = 'janus-mcp-acceptance'
$invoker = "janus-agent-poc-invoker@$project.iam.gserviceaccount.com"
$builder = "$(gcloud projects describe $project --format='value(projectNumber)')-compute@developer.gserviceaccount.com"
$imageRepo = "us-central1-docker.pkg.dev/$project/janusai-poc/mcp-acceptance"
$tag = 'wbs4c-host-20260906'
$secret = 'janus-mcp-owner-signing-key'

gcloud secrets add-iam-policy-binding $secret --project=$project --member="serviceAccount:$invoker" --role=roles/secretmanager.secretAccessor --quiet | Out-Null
try {
  gcloud builds submit . --project=$project --config=cloudbuild.yaml --substitutions="_DOCKERFILE=scripts/gcp/mcp-acceptance.Dockerfile,_IMAGE_NAME=mcp-acceptance,_IMAGE_TAG=$tag,_DEPLOY_TARGET=,_RUNTIME_NAME=,_REGION=$region" | Out-Host
  $digest = gcloud artifacts docker images describe "$imageRepo`:$tag" --project=$project --format='value(image_summary.digest)'
  $image = "$imageRepo@$digest"
  $gateway = gcloud run services describe janus-agent-gateway --project=$project --region=$region --format='value(status.url)'
  gcloud run jobs deploy $job --project=$project --region=$region --image=$image --service-account=$invoker --set-secrets="MCP_ACCEPTANCE_SECRET=${secret}:latest" --args=$gateway --max-retries=0 --task-timeout=10m --quiet | Out-Host
  gcloud run jobs execute $job --project=$project --region=$region --wait --quiet | Out-Host
  gcloud run jobs executions list --job=$job --project=$project --region=$region --limit=1 --format='value(status.conditions[0].state)' 
} finally {
  gcloud run jobs delete $job --project=$project --region=$region --quiet | Out-Null
  gcloud secrets remove-iam-policy-binding $secret --project=$project --member="serviceAccount:$invoker" --role=roles/secretmanager.secretAccessor --quiet | Out-Null
}
