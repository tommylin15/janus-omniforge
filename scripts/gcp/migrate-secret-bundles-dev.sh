#!/usr/bin/env bash
set -Eeuo pipefail

project="${GCP_PROJECT_ID:?GCP_PROJECT_ID is required}"
phase="${1:-}"
api_bundle="janus-postgres-api-bundle"
agent_bundle="janus-agent-provider-bundle"
owner_bundle="janus-codex-owners-bundle"
legacy=(janus-postgres-web-bundle janus-postgres-pipeline-bundle janus-postgres-mart-bundle janus-postgres-ingestion-bundle janus-codex-owner-a janus-codex-owner-b)

if [[ "${ALLOW_SECRET_BUNDLE_MIGRATION:-false}" != "true" ]]; then
  echo 'Refusing migration: set ALLOW_SECRET_BUNDLE_MIGRATION=true explicitly.' >&2
  exit 1
fi

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

access() {
  gcloud secrets versions access latest --secret="$1" --project="${project}" --out-file="$2" --quiet
}

replace_bundle() {
  local secret="$1" payload="$2" expected="$3" added version
  added="$(gcloud secrets versions add "${secret}" --project="${project}" --data-file="${payload}" --format='value(name)' --quiet)"
  added="${added//$'\r'/}"
  version="${added##*/}"
  for attempt in {1..10}; do
    gcloud secrets versions access "${version}" --secret="${secret}" --project="${project}" --out-file="${tmp}/verify.json" --quiet && break
    [[ "${attempt}" == 10 ]] && exit 1
    sleep 2
  done
  python3 -c 'import json,sys; actual=json.load(open(sys.argv[1])); expected=set(sys.argv[2].split(",")); missing=expected-set(actual); assert not missing, "missing fields: "+",".join(sorted(missing))' "${tmp}/verify.json" "${expected}"
  while IFS= read -r old; do
    old="${old//$'\r'/}"
    [[ -z "${old}" || "${old}" == "${version}" ]] || gcloud secrets versions destroy "${old}" --secret="${secret}" --project="${project}" --quiet
  done < <(gcloud secrets versions list "${secret}" --project="${project}" --filter='state=ENABLED' --format='value(name)')
}

case "${phase}" in
  prepare)
    access "${api_bundle}" "${tmp}/api.json"
    access janus-postgres-web-bundle "${tmp}/web.json"
    access janus-postgres-pipeline-bundle "${tmp}/pipeline.json"
    access "${agent_bundle}" "${tmp}/agent.json"
    access janus-postgres-mart-bundle "${tmp}/mart.json"
    access janus-postgres-ingestion-bundle "${tmp}/ingestion.json"
    python3 - "${tmp}" <<'PY'
import json, pathlib, sys

root = pathlib.Path(sys.argv[1])
load = lambda name: json.loads((root / f"{name}.json").read_text())
api, web, pipeline = load("api"), load("web"), load("pipeline")
agent, mart, ingestion = load("agent"), load("mart"), load("ingestion")
api.update({
    "web_control_password": web["control_password"],
    "web_catalog_password": web["catalog_password"],
    "web_google_client_id": web["google_client_id"],
    "web_session_secret": web["session_secret"],
    "pipeline_database_url": pipeline["database_url"],
    "pipeline_catalog_password": pipeline["catalog_password"],
})
agent.update({
    "mart_catalog_password": mart["catalog_password"],
    "mart_publication_password": mart["publication_password"],
    "ingestion_control_password": ingestion["control_password"],
    "ingestion_catalog_password": ingestion["catalog_password"],
})
(root / "api-merged.json").write_text(json.dumps(api, separators=(",", ":")))
(root / "agent-merged.json").write_text(json.dumps(agent, separators=(",", ":")))
PY
    replace_bundle "${api_bundle}" "${tmp}/api-merged.json" 'database_url,catalog_password,core_catalog_password,google_user_client_id,mcp_owner_signing_key,web_control_password,web_catalog_password,web_google_client_id,web_session_secret,pipeline_database_url,pipeline_catalog_password'
    replace_bundle "${agent_bundle}" "${tmp}/agent-merged.json" 'gemini_api_key,openrouter_api_key,mcp_owner_signing_key,mart_catalog_password,mart_publication_password,ingestion_control_password,ingestion_catalog_password'
    if ! gcloud secrets describe "${owner_bundle}" --project="${project}" >/dev/null 2>&1; then
      gcloud secrets create "${owner_bundle}" --project="${project}" --replication-policy=automatic --labels=environment=dev,service=agent-gateway --quiet
    fi
    owner_bundle_latest="$(gcloud secrets versions list "${owner_bundle}" --project="${project}" --filter='state=ENABLED' --format='value(name)' --limit=1 || true)"
    if [[ -z "${owner_bundle_latest}" ]]; then
      for source in a b; do
        legacy_secret="janus-codex-owner-${source}"
        latest="$(gcloud secrets versions list "${legacy_secret}" --project="${project}" --filter='state=ENABLED' --format='value(name)' --limit=1 || true)"
        [[ -z "${latest}" ]] || gcloud secrets versions access "${latest}" --secret="${legacy_secret}" --project="${project}" --out-file="${tmp}/owner-${source}.json" --quiet
      done
      owner_keys="$(python3 - "${tmp}" <<'PY'
import json, pathlib, sys

root = pathlib.Path(sys.argv[1])
owners = {}
for suffix, owner in (("a", "00000000-0000-4000-8000-000000000001"), ("b", "00000000-0000-4000-8000-000000000002")):
    path = root / f"owner-{suffix}.json"
    if path.exists():
        owners[owner] = json.loads(path.read_text())
(root / "owners-merged.json").write_text(json.dumps(owners, separators=(",", ":")))
print(",".join(owners))
PY
)"
      [[ -z "${owner_keys}" ]] || replace_bundle "${owner_bundle}" "${tmp}/owners-merged.json" "${owner_keys}"
    fi
    for member in janus-user-api web-runtime janus-private-pipeline; do
      gcloud secrets add-iam-policy-binding "${api_bundle}" --project="${project}" --member="serviceAccount:${member}@${project}.iam.gserviceaccount.com" --role=roles/secretmanager.secretAccessor --quiet >/dev/null
    done
    for member in janus-agent-gateway ingestion-core intelligence-mart; do
      gcloud secrets add-iam-policy-binding "${agent_bundle}" --project="${project}" --member="serviceAccount:${member}@${project}.iam.gserviceaccount.com" --role=roles/secretmanager.secretAccessor --quiet >/dev/null
    done
    for role in roles/secretmanager.secretAccessor roles/secretmanager.secretVersionAdder roles/secretmanager.secretVersionManager; do
      gcloud secrets add-iam-policy-binding "${owner_bundle}" --project="${project}" --member="serviceAccount:janus-agent-gateway@${project}.iam.gserviceaccount.com" --role="${role}" --quiet >/dev/null
    done
    echo 'Prepared two merged payloads and the empty Codex owner bundle. Deploy and verify all consumers before cleanup.'
    ;;
  cleanup)
    if [[ "${ALLOW_SECRET_BUNDLE_CLEANUP:-false}" != "true" ]]; then
      echo 'Refusing cleanup: set ALLOW_SECRET_BUNDLE_CLEANUP=true after dev acceptance.' >&2
      exit 1
    fi
    for secret in "${legacy[@]}"; do
      gcloud secrets delete "${secret}" --project="${project}" --quiet
    done
    echo 'Deleted six legacy Secret containers after explicit cleanup approval.'
    ;;
  *)
    echo "Usage: $0 {prepare|cleanup}" >&2
    exit 2
    ;;
esac
