#!/usr/bin/env bash
set -Eeuo pipefail

project="${GCP_PROJECT_ID:?GCP_PROJECT_ID is required}"
region="${GCP_REGION:-us-central1}"
identity="janus-ingestion-scheduler@${project}.iam.gserviceaccount.com"
job="janus-private-pipeline"
target="https://run.googleapis.com/v2/projects/${project}/locations/${region}/jobs/${job}:run"

if [[ "${JANUS_ENVIRONMENT:-}" != "dev" || "${ALLOW_DEV_SCHEDULER_APPLY:-false}" != "true" ]]; then
  echo 'Refusing Scheduler/IAM apply: require JANUS_ENVIRONMENT=dev and ALLOW_DEV_SCHEDULER_APPLY=true.' >&2
  exit 1
fi

gcloud run jobs add-iam-policy-binding "${job}" --project="${project}" --region="${region}" \
  --member="serviceAccount:${identity}" --role=roles/run.invoker --quiet

while IFS='|' read -r name schedule; do
  command=(gcloud scheduler jobs)
  if gcloud scheduler jobs describe "${name}" --project="${project}" --location="${region}" >/dev/null 2>&1; then
    command+=(update http)
  else
    command+=(create http)
  fi
  "${command[@]}" "${name}" --project="${project}" --location="${region}" \
    --schedule="${schedule}" --time-zone=Asia/Taipei --uri="${target}" --http-method=POST \
    --headers=Content-Type=application/json --message-body='{}' \
    --oauth-service-account-email="${identity}" --oauth-token-scope=https://www.googleapis.com/auth/cloud-platform \
    --max-retry-attempts=3 --min-backoff=60s --max-backoff=300s --max-doublings=2 --attempt-deadline=30m --quiet
done <<'SCHEDULES'
janus-private-pipeline-0740|40 7 * * MON-FRI
janus-private-pipeline-1100|0 11 * * MON-FRI
janus-private-pipeline-1400|0 14 * * MON-FRI
janus-private-pipeline-2130|30 21 * * MON-FRI
SCHEDULES
