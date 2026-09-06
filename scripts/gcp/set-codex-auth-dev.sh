#!/usr/bin/env bash
set -Eeuo pipefail

project="${GCP_PROJECT_ID:?GCP_PROJECT_ID is required}"
auth_file="${1:?Usage: $0 /path/to/codex/auth.json}"
secret="${CODEX_AUTH_SECRET_NAME:-janus-codex-managed-auth}"

if [[ "${ALLOW_CODEX_AUTH_UPLOAD:-false}" != "true" ]]; then
  echo 'Refusing credential upload: set ALLOW_CODEX_AUTH_UPLOAD=true explicitly.' >&2
  exit 1
fi
[[ -f "${auth_file}" ]] || { echo 'Codex auth file does not exist.' >&2; exit 1; }
python3 -c 'import json,sys; json.load(open(sys.argv[1], encoding="utf-8"))' "${auth_file}"

if ! gcloud secrets describe "${secret}" --project="${project}" >/dev/null 2>&1; then
  gcloud secrets create "${secret}" --project="${project}" \
    --replication-policy=automatic --labels=environment=dev,service=agent-gateway --quiet
fi
gcloud secrets versions add "${secret}" --project="${project}" --data-file="${auth_file}" --quiet
echo "Uploaded Codex managed auth to ${secret}; no credential content was printed."
