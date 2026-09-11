#!/usr/bin/env bash
set -Eeuo pipefail

project="${GCP_PROJECT_ID:?GCP_PROJECT_ID is required}"
auth_file="${1:?Usage: $0 /path/to/codex/auth.json}"
owner="${CODEX_OWNER_ID:?CODEX_OWNER_ID is required}"
secret="${CODEX_AUTH_SECRET_NAME:-janus-codex-owners-bundle}"

if [[ "${ALLOW_CODEX_AUTH_UPLOAD:-false}" != "true" ]]; then
  echo 'Refusing credential upload: set ALLOW_CODEX_AUTH_UPLOAD=true explicitly.' >&2
  exit 1
fi
[[ -f "${auth_file}" ]] || { echo 'Codex auth file does not exist.' >&2; exit 1; }
python3 -c 'import json,sys; json.load(open(sys.argv[1], encoding="utf-8"))' "${auth_file}"
[[ "${owner}" =~ ^[0-9a-fA-F-]{36}$ ]] || { echo 'CODEX_OWNER_ID is invalid.' >&2; exit 1; }

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

if ! gcloud secrets describe "${secret}" --project="${project}" >/dev/null 2>&1; then
  gcloud secrets create "${secret}" --project="${project}" \
    --replication-policy=automatic --labels=environment=dev,service=agent-gateway --quiet
fi
latest="$(gcloud secrets versions list "${secret}" --project="${project}" --filter='state=ENABLED' --format='value(name)' --limit=1)"
if [[ -z "${latest}" ]]; then
  python3 -c 'import pathlib,sys; pathlib.Path(sys.argv[1]).write_text("{}")' "${tmp}/current.json"
else
  gcloud secrets versions access "${latest}" --secret="${secret}" --project="${project}" --out-file="${tmp}/current.json" --quiet
fi
python3 -c 'import json,pathlib,sys; bundle=json.load(open(sys.argv[1])); bundle[sys.argv[3].lower()]=json.load(open(sys.argv[2])); pathlib.Path(sys.argv[4]).write_text(json.dumps(bundle,separators=(",",":")))' \
  "${tmp}/current.json" "${auth_file}" "${owner}" "${tmp}/updated.json"
added="$(gcloud secrets versions add "${secret}" --project="${project}" --data-file="${tmp}/updated.json" --format='value(name)' --quiet)"
version="${added##*/}"
gcloud secrets versions access "${version}" --secret="${secret}" --project="${project}" --out-file="${tmp}/verify.json" --quiet
python3 -c 'import json,sys; assert sys.argv[2].lower() in json.load(open(sys.argv[1]))' "${tmp}/verify.json" "${owner}"
while IFS= read -r old; do
  [[ -z "${old}" || "${old}" == "${version}" ]] || gcloud secrets versions destroy "${old}" --secret="${secret}" --project="${project}" --quiet
done < <(gcloud secrets versions list "${secret}" --project="${project}" --filter='state=ENABLED' --format='value(name)')
echo "Uploaded Codex managed auth for ${owner} to ${secret}; no credential content was printed."
