#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-gen-lang-client-0593591102}"
ZONE="${GCP_ZONE:-us-central1-a}"
POSTGRES_VM="${POSTGRES_VM:-janus-postgres-dev}"
MIGRATION="029_twse_2026_holiday_overrides.sql"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SOURCE="${ROOT}/infra/postgres/migrations/${MIGRATION}"
REMOTE="/tmp/janus-control-migration-${MIGRATION}"
CONTAINER_PATH="/tmp/${MIGRATION}"

command -v gcloud >/dev/null 2>&1 || { echo 'gcloud is required' >&2; exit 2; }
test -f "${SOURCE}" || { echo "migration not found: ${SOURCE}" >&2; exit 2; }

active_account="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -1)"
[[ -n "${active_account}" ]] || { echo 'no active gcloud account; authenticate with the existing operator identity first' >&2; exit 2; }

echo "Applying ${MIGRATION} to ${POSTGRES_VM} in ${PROJECT_ID}/${ZONE} as ${active_account}."

cleanup() {
  gcloud compute ssh "${POSTGRES_VM}" \
    --project="${PROJECT_ID}" --zone="${ZONE}" \
    --tunnel-through-iap --quiet \
    --command="sudo rm -f '${REMOTE}'; sudo docker exec janus-postgres rm -f '${CONTAINER_PATH}' >/dev/null 2>&1 || true" \
    >/dev/null 2>&1 || true
}
trap cleanup EXIT

gcloud compute scp "${SOURCE}" "${POSTGRES_VM}:${REMOTE}" \
  --project="${PROJECT_ID}" --zone="${ZONE}" \
  --tunnel-through-iap --quiet

gcloud compute ssh "${POSTGRES_VM}" \
  --project="${PROJECT_ID}" --zone="${ZONE}" \
  --tunnel-through-iap --quiet --command="
    set -eu
    sudo docker cp '${REMOTE}' janus-postgres:'${CONTAINER_PATH}'
    sudo docker exec --user postgres janus-postgres \
      psql -v ON_ERROR_STOP=1 -U postgres -d janus_control \
      -f '${CONTAINER_PATH}'

    marker=\$(sudo docker exec --user postgres janus-postgres \
      psql -v ON_ERROR_STOP=1 -U postgres -d janus_control -Atc \
      \"SELECT version FROM control.schema_migrations WHERE version='029_twse_2026_holiday_overrides';\")
    test \"\${marker}\" = '029_twse_2026_holiday_overrides'
    echo \"migration_marker=\${marker}\"

    sudo docker exec --user postgres janus-postgres \
      psql -v ON_ERROR_STOP=1 -U postgres -d janus_control -Atc \
      \"SELECT jsonb_build_object(
          'time', value_json->'time',
          'enabled', value_json->'enabled',
          'holiday_overrides', value_json->'holiday_overrides',
          'version', version,
          'updated_by', updated_by
        )
        FROM control.admin_settings
        WHERE setting_key='schedule';\"
  "
