#!/usr/bin/env bash
set -Eeuo pipefail

# 在 ingestion-daily（07:30 Asia/Taipei）之後排 mart job（09:00）作為保底。
# ingestion-core 完成後會透過 MART_JOB 直接觸發；此 scheduler 確保即使
# ingestion 未觸發，mart 仍會每天執行一次。

project="${GCP_PROJECT_ID:?GCP_PROJECT_ID is required}"
region="${GCP_REGION:-us-central1}"
identity="janus-ingestion-scheduler@${project}.iam.gserviceaccount.com"
job="janus-intelligence-mart"
target="https://run.googleapis.com/v2/projects/${project}/locations/${region}/jobs/${job}:run"
name="janus-mart-daily"

if [[ "${JANUS_ENVIRONMENT:-}" != "dev" || "${ALLOW_DEV_SCHEDULER_APPLY:-false}" != "true" ]]; then
  echo 'Refusing Scheduler apply: require JANUS_ENVIRONMENT=dev and ALLOW_DEV_SCHEDULER_APPLY=true.' >&2
  exit 1
fi

gcloud run jobs add-iam-policy-binding "${job}" --project="${project}" --region="${region}" \
  --member="serviceAccount:${identity}" --role=roles/run.invoker --quiet

scheduler_cmd=(gcloud scheduler jobs)
if gcloud scheduler jobs describe "${name}" --project="${project}" --location="${region}" >/dev/null 2>&1; then
  scheduler_cmd+=(update http)
else
  scheduler_cmd+=(create http)
fi
"${scheduler_cmd[@]}" "${name}" \
  --project="${project}" --location="${region}" \
  --schedule="0 9 * * MON-FRI" --time-zone=Asia/Taipei \
  --uri="${target}" --http-method=POST \
  --headers=Content-Type=application/json --message-body='{}' \
  --oauth-service-account-email="${identity}" \
  --oauth-token-scope=https://www.googleapis.com/auth/cloud-platform \
  --max-retry-attempts=2 --min-backoff=120s --max-backoff=600s \
  --max-doublings=2 --attempt-deadline=30m --quiet

echo "janus-mart-daily scheduler applied (09:00 Asia/Taipei, MON-FRI)."
