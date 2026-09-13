#!/usr/bin/env bash
set -Eeuo pipefail

project="${GCP_PROJECT_ID:?GCP_PROJECT_ID is required}"
region="${GCP_REGION:-us-central1}"
zone="${GCP_ZONE:-us-central1-a}"
service="janus-api"
vm="janus-postgres-dev"
expected_sa="janus-user-api@${project}.iam.gserviceaccount.com"

actual_sa="$(gcloud run services describe "${service}" --project="${project}" --region="${region}" \
  --format='value(spec.template.spec.serviceAccountName)')"
[[ "${actual_sa}" == "${expected_sa}" ]] || { echo "Unexpected API service account." >&2; exit 1; }
gcloud run services get-iam-policy "${service}" --project="${project}" --region="${region}" \
  --flatten='bindings[].members' --filter='bindings.role:roles/run.invoker AND bindings.members:allUsers' \
  --format='value(bindings.members)' | grep -Fx allUsers >/dev/null

gcloud compute scp scripts/gcp/postgres-deep-acceptance.sql \
  "${vm}:/tmp/janus-postgres-deep-acceptance.sql" --project="${project}" --zone="${zone}" --tunnel-through-iap --quiet >/dev/null
gcloud compute scp scripts/gcp/postgres-migration-rollback-probe.sql \
  "${vm}:/tmp/janus-postgres-migration-rollback-probe.sql" --project="${project}" --zone="${zone}" --tunnel-through-iap --quiet >/dev/null
gcloud compute ssh "${vm}" --project="${project}" --zone="${zone}" --tunnel-through-iap --command \
  "sudo docker cp /tmp/janus-postgres-deep-acceptance.sql janus-postgres:/tmp/acceptance.sql && sudo docker exec --user postgres janus-postgres psql -U postgres -d janus_control -f /tmp/acceptance.sql && sudo docker cp /tmp/janus-postgres-migration-rollback-probe.sql janus-postgres:/tmp/rollback.sql && ! sudo docker exec --user postgres janus-postgres psql -U postgres -d janus_control -f /tmp/rollback.sql && sudo docker exec --user postgres janus-postgres psql -U postgres -d janus_control -Atc \"SELECT to_regclass('control.janus_migration_rollback_probe') IS NULL\" | grep -Fx t && rm -f /tmp/janus-postgres-deep-acceptance.sql /tmp/janus-postgres-migration-rollback-probe.sql" --quiet

service_url="$(gcloud run services describe "${service}" --project="${project}" --region="${region}" --format='value(status.url)')"
headers_file="$(mktemp)"
trap 'rm -f "${headers_file}"' EXIT
curl -sS -D "${headers_file}" -o /dev/null "${service_url}/api/v1/admin/stocks?q=must-not-appear"
request_id="$(sed -n 's/^[Xx]-[Rr]equest-[Ii][Dd]:[[:space:]]*\([^[:space:]\r]*\).*/\1/p' "${headers_file}" | tail -1)"
[[ -n "${request_id}" ]] || { echo 'Admin audit probe returned no request ID.' >&2; exit 1; }
for _ in $(seq 1 12); do
  audit="$(gcloud run services logs read "${service}" --project="${project}" --region="${region}" \
    --limit=40 --format='value(textPayload,jsonPayload.message)' 2>/dev/null | grep -F "${request_id}" || true)"
  if [[ "${audit}" == *'api_audit family=admin method=GET'* && "${audit}" != *'must-not-appear'* ]]; then
    break
  fi
  sleep 5
done
[[ "${audit:-}" == *'api_audit family=admin method=GET'* ]] || { echo 'Admin audit log was not observed.' >&2; exit 1; }

SERVICE_URL="${service_url}" python3 - <<'PY'
import concurrent.futures, json, os, urllib.error, urllib.request
base = os.environ["SERVICE_URL"]
def get(_):
    try:
        with urllib.request.urlopen(base + "/api/v1/public/kline/2330?limit=200", timeout=30) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code
with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
    statuses = list(pool.map(get, range(24)))
assert set(statuses) <= {200, 404, 429, 503}, statuses
print("bounded pool acceptance statuses", json.dumps(statuses))
PY

if [[ "${ALLOW_DEV_POSTGRES_RESTART:-false}" != true ]]; then
  echo 'Set ALLOW_DEV_POSTGRES_RESTART=true to run the restart/reconnect gate.' >&2
  exit 2
fi
gcloud compute instances reset "${vm}" --project="${project}" --zone="${zone}" --quiet
for _ in $(seq 1 60); do
  if curl -fsS "${service_url}/api/v1/public/history/2330?limit=1" >/dev/null 2>&1; then
    echo 'GCP dev PostgreSQL restart/reconnect acceptance passed.'
    exit 0
  fi
  sleep 5
done
echo 'API did not recover after the dev PostgreSQL restart.' >&2
exit 1
