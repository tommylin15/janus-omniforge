#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

project="${GCP_PROJECT_ID:?GCP_PROJECT_ID is required}"
zone="${GCP_ZONE:-us-central1-a}"
bucket="${LEDGER_BACKUP_BUCKET:-${project}-dev-private}"
prefix="pilot-ledger-backups"
mode="${1:-}"
backup_id="${2:-}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
python_bin=python3
python3 -c 'pass' >/dev/null 2>&1 || python_bin=python

fail() { echo "Pilot ledger durability failed: $*" >&2; exit 1; }
[[ "${GCP_ENVIRONMENT:-dev}" == dev ]] || fail 'GCP_ENVIRONMENT must be dev'
[[ -z "${GCP_PRODUCTION_PROJECT_ID:-}" || "${project}" != "${GCP_PRODUCTION_PROJECT_ID}" ]] || fail 'dev and production project IDs must differ'

vm() {
  gcloud compute ssh janus-postgres-dev --project="${project}" --zone="${zone}" \
    --tunnel-through-iap --quiet --command "$1"
}

configure() {
  local build_sa
  [[ "${ALLOW_DEV_LEDGER_DURABILITY:-false}" == true ]] || \
    fail 'set ALLOW_DEV_LEDGER_DURABILITY=true to configure the existing dev VM and bucket prefix'
  gcloud storage buckets describe "gs://${bucket}" --project="${project}" >/dev/null
  if ! gcloud storage managed-folders describe "gs://${bucket}/${prefix}/" --project="${project}" >/dev/null 2>&1; then
    gcloud storage managed-folders create "gs://${bucket}/${prefix}/" --project="${project}" --quiet >/dev/null
  fi
  gcloud storage managed-folders add-iam-policy-binding "gs://${bucket}/${prefix}/" --project="${project}" \
    --member="serviceAccount:postgres-vm@${project}.iam.gserviceaccount.com" \
    --role=roles/storage.objectAdmin \
    --quiet >/dev/null
  build_sa="$(gcloud builds get-default-service-account --project="${project}")"
  gcloud storage managed-folders add-iam-policy-binding "gs://${bucket}/${prefix}/" --project="${project}" \
    --member="serviceAccount:${build_sa}" --role=roles/storage.objectViewer \
    --quiet >/dev/null
  gcloud compute scp "$0" "janus-postgres-dev:/tmp/janus-ledger-durability" \
    --project="${project}" --zone="${zone}" --tunnel-through-iap --quiet
  vm "sudo env GCP_PROJECT_ID='${project}' LEDGER_BACKUP_BUCKET='${bucket}' GCP_ENVIRONMENT=dev bash /tmp/janus-ledger-durability install"
  echo 'Pilot ledger daily backup timer configured on the existing dev PostgreSQL VM.'
}

install_timer() {
  install -d -m 755 /var/lib/janus
  install -m 700 "$0" /var/lib/janus/ledger-durability
  cat >/etc/systemd/system/janus-ledger-backup.service <<EOF
[Unit]
Description=Janus bounded Pilot ledger logical backup
After=docker.service network-online.target

[Service]
Type=oneshot
Environment=GCP_PROJECT_ID=${project}
Environment=LEDGER_BACKUP_BUCKET=${bucket}
Environment=GCP_ENVIRONMENT=dev
ExecStart=/bin/bash /var/lib/janus/ledger-durability vm-backup
EOF
  cat >/etc/systemd/system/janus-ledger-backup.timer <<'EOF'
[Unit]
Description=Daily Janus Pilot ledger logical backup

[Timer]
OnCalendar=*-*-* 18:00:00 UTC
Persistent=true
RandomizedDelaySec=10m

[Install]
WantedBy=timers.target
EOF
  systemctl daemon-reload
  systemctl enable --now janus-ledger-backup.timer >/dev/null
  rm -f /tmp/janus-ledger-durability
}

access_token() {
  curl -fsS -H 'Metadata-Flavor: Google' \
    'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token' \
    | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p'
}

gcs_object() {
  local operation="$1" name="$2" file="${3:-}" keep="${4:-0}" token
  token="$(access_token)"; [[ -n "${token}" ]] || fail 'VM identity token unavailable'
  GCS_TOKEN="${token}" GCS_BUCKET="${bucket}" GCS_PREFIX="${name}" GCS_FILE="${file}" GCS_KEEP="${keep}" \
    python3 - "${operation}" <<'PY'
import json, os, sys
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

operation = sys.argv[1]
bucket, name = os.environ["GCS_BUCKET"], os.environ["GCS_PREFIX"]
headers = {"Authorization": f"Bearer {os.environ['GCS_TOKEN']}"}

def request(url, *, method="GET", data=None, content_type=None):
    values = dict(headers)
    if content_type: values["Content-Type"] = content_type
    return urlopen(Request(url, data=data, headers=values, method=method), timeout=120)

if operation == "upload":
    query = urlencode({"uploadType": "media", "name": name, "ifGenerationMatch": "0"})
    try:
        with open(os.environ["GCS_FILE"], "rb") as source:
            request(f"https://storage.googleapis.com/upload/storage/v1/b/{quote(bucket, safe='')}/o?{query}",
                    method="POST", data=source.read(), content_type="application/octet-stream")
    except HTTPError as error:
        if error.code != 412: raise
elif operation == "download":
    url = f"https://storage.googleapis.com/download/storage/v1/b/{quote(bucket, safe='')}/o/{quote(name, safe='')}?alt=media"
    with request(url) as response, open(os.environ["GCS_FILE"], "wb") as target:
        target.write(response.read())
elif operation == "prune":
    query = urlencode({"prefix": name, "fields": "items(name,generation,size),nextPageToken"})
    with request(f"https://storage.googleapis.com/storage/v1/b/{quote(bucket, safe='')}/o?{query}") as response:
        items = json.load(response).get("items", [])
    for item in sorted(items, key=lambda value: value["name"], reverse=True)[int(os.environ["GCS_KEEP"]):]:
        target = f"https://storage.googleapis.com/storage/v1/b/{quote(bucket, safe='')}/o/{quote(item['name'], safe='')}?generation={item['generation']}"
        request(target, method="DELETE")
elif operation == "latest":
    query = urlencode({"prefix": name, "fields": "items(name)"})
    with request(f"https://storage.googleapis.com/storage/v1/b/{quote(bucket, safe='')}/o?{query}") as response:
        items = json.load(response).get("items", [])
    if items: print(sorted(item["name"] for item in items)[-1])
PY
  unset token
}

vm_backup() {
  local temporary day month bytes digest owners ledger_events
  temporary="$(mktemp -d /tmp/janus-ledger-backup.XXXXXX)"
  trap "rm -rf -- '${temporary}'" EXIT
  day="$(date -u +%F)"; month="${day%-*}"
  docker exec --user postgres janus-postgres \
    pg_dump --format=custom --compress=9 --no-owner --no-acl --dbname=janus_control >"${temporary}/ledger.dump"
  bytes="$(stat -c %s "${temporary}/ledger.dump")"
  digest="$(sha256sum "${temporary}/ledger.dump" | cut -d' ' -f1)"
  owners="$(docker exec --user postgres janus-postgres psql -At -d janus_control -c 'SELECT count(*) FROM private.users')"
  ledger_events="$(docker exec --user postgres janus-postgres psql -At -d janus_control -c 'SELECT count(*) FROM private.ledger_events')"
  gcs_object upload "${prefix}/daily/${day}.dump" "${temporary}/ledger.dump"
  gcs_object upload "${prefix}/monthly/${month}.dump" "${temporary}/ledger.dump"
  gcs_object prune "${prefix}/daily/" '' 14
  gcs_object prune "${prefix}/monthly/" '' 6
  printf '{"backup_id":"%s","owners":%s,"ledger_events":%s,"bytes":%s,"sha256":"sha256:%s","projected_retention_bytes":%s}\n' \
    "${day}" "${owners}" "${ledger_events}" "${bytes}" "${digest}" "$((bytes * 20))"
}

restore_build() {
  local object
  if [[ -z "${backup_id}" ]]; then
    object="$(gcloud storage ls "gs://${bucket}/${prefix}/daily/*.dump" --project="${project}" 2>/dev/null | sort | tail -1)"
    [[ -n "${object}" ]] || fail 'no daily ledger backup is available'
    backup_id="${object##*/}"; backup_id="${backup_id%.dump}"
  fi
  [[ "${backup_id}" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || fail 'backup ID must be YYYY-MM-DD'
  object="${prefix}/daily/${backup_id}.dump"
  gcloud builds submit "${repo_root}" --project="${project}" \
    --config="${repo_root}/scripts/gcp/cloudbuild-ledger-restore.yaml" \
    --substitutions="_BUCKET=${bucket},_OBJECT=${object}" --quiet
}

verify() {
  local build_sa policy
  vm "sudo systemctl is-enabled janus-ledger-backup.timer && sudo systemctl is-active janus-ledger-backup.timer"
  build_sa="$(gcloud builds get-default-service-account --project="${project}")"
  policy="$(gcloud storage managed-folders get-iam-policy "gs://${bucket}/${prefix}/" --project="${project}" --format=json)"
  POLICY_JSON="${policy}" EXPECTED_MEMBER="serviceAccount:postgres-vm@${project}.iam.gserviceaccount.com" \
    EXPECTED_BUILD_MEMBER="serviceAccount:${build_sa}" \
    "${python_bin}" - <<'PY'
import json, os
policy = json.loads(os.environ["POLICY_JSON"])
for role, member in (("roles/storage.objectAdmin", os.environ["EXPECTED_MEMBER"]),
                     ("roles/storage.objectViewer", os.environ["EXPECTED_BUILD_MEMBER"])):
    matches = [binding for binding in policy.get("bindings", [])
               if binding.get("role") == role and member in binding.get("members", [])]
    assert len(matches) == 1
PY
  echo 'Pilot ledger timer and managed-folder backup/restore access are configured.'
}

case "${mode}" in
  configure) configure ;;
  run) vm "sudo env GCP_PROJECT_ID='${project}' LEDGER_BACKUP_BUCKET='${bucket}' GCP_ENVIRONMENT=dev /bin/bash /var/lib/janus/ledger-durability vm-backup" ;;
  restore) restore_build ;;
  verify) verify ;;
  install) install_timer ;;
  vm-backup) vm_backup ;;
  *) echo "Usage: $0 {configure|run|verify|restore [YYYY-MM-DD]}" >&2; exit 2 ;;
esac
