#!/usr/bin/env bash
set -Eeuo pipefail

project="${GCP_PROJECT_ID:?GCP_PROJECT_ID is required}"
region="${GCP_REGION:-us-central1}"
zone="${GCP_ZONE:-us-central1-a}"
billing_account="${GCP_BILLING_ACCOUNT_ID:-}"
mode="${1:-}"
budget_name="Janus dev US\$10 equivalent guard"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"

fail() { echo "WBS-7 acceptance failed: $*" >&2; exit 1; }
[[ "${GCP_ENVIRONMENT:-dev}" == dev ]] || fail 'GCP_ENVIRONMENT must be dev'
[[ -z "${GCP_PRODUCTION_PROJECT_ID:-}" || "${project}" != "${GCP_PRODUCTION_PROJECT_ID}" ]] || \
  fail 'dev and production project IDs must differ'

secret_members() {
  gcloud secrets get-iam-policy "$1" --project="${project}" \
    --flatten='bindings[].members' --filter='bindings.role:roles/secretmanager.secretAccessor' \
    --format='value(bindings.members)'
}

configure() {
  [[ "${ALLOW_DEV_SECURITY_FINOPS:-false}" == true ]] || \
    fail 'set ALLOW_DEV_SECURITY_FINOPS=true to modify existing dev configuration'
  [[ -n "${billing_account}" ]] || fail 'GCP_BILLING_ACCOUNT_ID is required to configure the dev budget'

  for bucket in stage core mart private; do
    gcloud storage buckets update "gs://${project}-dev-${bucket}" --project="${project}" \
      --versioning --public-access-prevention \
      --lifecycle-file="${repo_root}/infra/private-bucket-lifecycle.json" --quiet
  done

  for account in janus-user-api janus-private-pipeline; do
    gcloud storage buckets add-iam-policy-binding "gs://${project}-dev-mart" --project="${project}" \
      --member="serviceAccount:${account}@${project}.iam.gserviceaccount.com" \
      --role=roles/storage.objectViewer --quiet >/dev/null
  done
  gcloud storage buckets remove-iam-policy-binding "gs://${project}-dev-mart" --project="${project}" \
    --member="serviceAccount:web-runtime@${project}.iam.gserviceaccount.com" \
    --role=roles/storage.objectViewer --quiet >/dev/null 2>&1 || true

  for account in janus-user-api janus-private-pipeline; do
    gcloud secrets add-iam-policy-binding janus-postgres-api-bundle --project="${project}" \
      --member="serviceAccount:${account}@${project}.iam.gserviceaccount.com" \
      --role=roles/secretmanager.secretAccessor --quiet >/dev/null
  done
  gcloud secrets remove-iam-policy-binding janus-postgres-api-bundle --project="${project}" \
    --member="serviceAccount:web-runtime@${project}.iam.gserviceaccount.com" \
    --role=roles/secretmanager.secretAccessor --quiet >/dev/null 2>&1 || true
  for account in janus-agent-gateway ingestion-core intelligence-mart; do
    gcloud secrets add-iam-policy-binding janus-agent-provider-bundle --project="${project}" \
      --member="serviceAccount:${account}@${project}.iam.gserviceaccount.com" \
      --role=roles/secretmanager.secretAccessor --quiet >/dev/null
  done

  gcloud run services update janus-api --project="${project}" --region="${region}" \
    --service-account="janus-user-api@${project}.iam.gserviceaccount.com" \
    --min-instances=0 --max-instances=2 --concurrency=20 --timeout=60 --quiet
  gcloud run services update janus-agent-gateway --project="${project}" --region="${region}" \
    --service-account="janus-agent-gateway@${project}.iam.gserviceaccount.com" \
    --min-instances=0 --max-instances=1 --concurrency=2 --timeout=300 --quiet
  for definition in \
    'janus-ingestion-core ingestion-core' \
    'janus-intelligence-mart intelligence-mart' \
    'janus-private-pipeline janus-private-pipeline'; do
    read -r job account <<<"${definition}"
    gcloud run jobs update "${job}" --project="${project}" --region="${region}" \
      --service-account="${account}@${project}.iam.gserviceaccount.com" \
      --tasks=1 --parallelism=1 --max-retries=1 --task-timeout=30m --quiet
  done

  gcloud services enable billingbudgets.googleapis.com --project="${project}" --quiet
  budget="$(gcloud billing budgets list --billing-account="${billing_account}" \
    --filter="displayName='${budget_name}'" --format='value(name)' --limit=1)"
  if [[ -z "${budget}" ]]; then
    gcloud billing budgets create --billing-account="${billing_account}" \
      --display-name="${budget_name}" --budget-amount=320TWD \
      --filter-projects="projects/${project}" \
      --threshold-rule=percent=0.1,basis=current-spend \
      --threshold-rule=percent=0.5,basis=current-spend \
      --threshold-rule=percent=1.0,basis=current-spend --quiet
  fi
  echo 'WBS-7 dev security and FinOps configuration applied.'
}

check_runtime() {
  local kind="$1" name="$2" expected="$3" json
  json="$(gcloud run "${kind}" describe "${name}" --project="${project}" --region="${region}" --format=json)"
  RUNTIME_JSON="${json}" EXPECTED_SA="${expected}@${project}.iam.gserviceaccount.com" \
    RUNTIME_KIND="${kind}" RUNTIME_NAME="${name}" python3 - <<'PY'
import json, os

doc = json.loads(os.environ["RUNTIME_JSON"])
values = {}
def walk(value):
    if isinstance(value, dict):
        for key, item in value.items():
            values.setdefault(key, []).append(item)
            walk(item)
    elif isinstance(value, list):
        for item in value: walk(item)
walk(doc)
accounts = [str(item) for key in ("serviceAccount", "serviceAccountName") for item in values.get(key, []) if isinstance(item, str)]
assert os.environ["EXPECTED_SA"] in accounts, f"{os.environ['RUNTIME_NAME']} service account mismatch"
annotations = {}
for item in values.get("annotations", []):
    if isinstance(item, dict): annotations.update(item)
if os.environ["RUNTIME_KIND"] == "services":
    service_annotations = doc.get("metadata", {}).get("annotations", {})
    template_annotations = doc.get("spec", {}).get("template", {}).get("metadata", {}).get("annotations", {})
    maximum = int(service_annotations.get("run.googleapis.com/maxScale") or service_annotations.get("autoscaling.knative.dev/maxScale") or template_annotations.get("autoscaling.knative.dev/maxScale", "0"))
    minimum = int(service_annotations.get("run.googleapis.com/minScale") or service_annotations.get("autoscaling.knative.dev/minScale") or template_annotations.get("autoscaling.knative.dev/minScale", "0"))
    expected_max = 1 if os.environ["RUNTIME_NAME"] == "janus-agent-gateway" else 2
    assert minimum == 0 and 0 < maximum <= expected_max, f"{os.environ['RUNTIME_NAME']} scaling drift"
else:
    numeric = lambda key, default: int(next((item for item in values.get(key, []) if str(item).isdigit()), default))
    assert numeric("taskCount", 1) == 1 and numeric("parallelism", 1) == 1, "job fan-out drift"
    assert numeric("maxRetries", 0) <= 1, "job retry drift"
PY
}

check_secret() {
  local secret="$1"; shift
  local allowed=" $* " member account
  while IFS= read -r member; do
    [[ -z "${member}" ]] && continue
    [[ "${member}" != allUsers && "${member}" != allAuthenticatedUsers ]] || fail "${secret} is public"
    [[ "${member}" == serviceAccount:*@"${project}".iam.gserviceaccount.com ]] || continue
    account="${member#serviceAccount:}"; account="${account%%@*}"
    if [[ "${allowed}" != *" ${account} "* ]]; then
      fail "${secret} grants an unrelated runtime: ${account}"
    fi
  done < <(secret_members "${secret}")
  for account in "$@"; do
    secret_members "${secret}" | grep -Fx "serviceAccount:${account}@${project}.iam.gserviceaccount.com" >/dev/null || \
      fail "${secret} is missing ${account}"
  done
}

verify() {
  [[ -n "${billing_account}" ]] || fail 'GCP_BILLING_ACCOUNT_ID is required to verify the dev budget'

  check_runtime services janus-api janus-user-api
  check_runtime services janus-agent-gateway janus-agent-gateway
  check_runtime jobs janus-ingestion-core ingestion-core
  check_runtime jobs janus-intelligence-mart intelligence-mart
  check_runtime jobs janus-private-pipeline janus-private-pipeline
  if gcloud run services list --project="${project}" --region="${region}" \
      --filter='metadata.name=janus-web' --format='value(metadata.name)' | grep -Fx janus-web >/dev/null; then
    fail 'legacy janus-web runtime still exists'
  fi

  while IFS= read -r account; do
    [[ -z "${account}" ]] && continue
    keys="$(timeout 20 gcloud iam service-accounts keys list \
      --iam-account="${account}" --project="${project}" \
      --managed-by=user --format='value(name)')" || fail "${account} key lookup timed out or failed"
    [[ -z "${keys}" ]] || fail "${account} has a user-managed key"
  done < <(gcloud iam service-accounts list --project="${project}" --format='value(email)')
  check_secret janus-postgres-api-bundle janus-user-api janus-private-pipeline
  check_secret janus-agent-provider-bundle janus-agent-gateway ingestion-core intelligence-mart
  check_secret janus-codex-owners-bundle janus-agent-gateway

  vm_json="$(gcloud compute instances describe janus-postgres-dev --project="${project}" --zone="${zone}" --format=json)"
  VM_JSON="${vm_json}" PROJECT="${project}" python3 - <<'PY'
import json, os
vm = json.loads(os.environ["VM_JSON"])
assert vm["machineType"].endswith("/e2-micro"), "PostgreSQL machine type drift"
assert not vm["networkInterfaces"][0].get("accessConfigs"), "PostgreSQL has an external IP"
assert vm["serviceAccounts"][0]["email"] == f"postgres-vm@{os.environ['PROJECT']}.iam.gserviceaccount.com"
assert not vm.get("resourcePolicies"), "PostgreSQL snapshot schedule is attached"
PY
  disk_json="$(gcloud compute disks describe janus-postgres-dev --project="${project}" --zone="${zone}" --format=json)"
  DISK_JSON="${disk_json}" python3 - <<'PY'
import json, os
disk = json.loads(os.environ["DISK_JSON"])
assert int(disk["sizeGb"]) <= 30 and disk["type"].endswith("/pd-standard"), "PostgreSQL disk drift"
PY
  firewall_json="$(gcloud compute firewall-rules list --project="${project}" --format=json)"
  FIREWALL_JSON="${firewall_json}" python3 - <<'PY'
import json, os
rules = json.loads(os.environ["FIREWALL_JSON"])
def ports(rule):
    return [(item.get("IPProtocol"), item.get("ports", [])) for item in rule.get("allowed", [])]
for rule in rules:
    public = "0.0.0.0/0" in rule.get("sourceRanges", [])
    assert not (public and any(proto == "tcp" and (not listed or "5432" in listed) for proto, listed in ports(rule))), "public PostgreSQL firewall rule"
assert any("35.235.240.0/20" in rule.get("sourceRanges", []) and any(proto == "tcp" and "22" in listed for proto, listed in ports(rule)) for rule in rules), "IAP SSH rule missing"
PY
  snapshots="$(gcloud compute snapshots list --project="${project}" --filter='sourceDisk~janus-postgres-dev' --format='value(name)')"
  [[ -z "${snapshots}" ]] || fail 'Free Tier PostgreSQL must not retain paid snapshots'

  for layer in stage core mart private; do
    bucket_json="$(gcloud storage buckets describe "gs://${project}-dev-${layer}" --project="${project}" --format=json)"
    BUCKET_JSON="${bucket_json}" python3 - <<'PY'
import json, os
bucket = json.loads(os.environ["BUCKET_JSON"])
assert bucket.get("public_access_prevention") == "enforced"
assert bucket.get("versioning_enabled") is True
assert bucket.get("lifecycle_config", {}).get("rule"), "bucket lifecycle missing"
PY
  done

  for api in containeranalysis.googleapis.com containerscanning.googleapis.com; do
    enabled="$(gcloud services list --enabled --project="${project}" --filter="config.name=${api}" --format='value(config.name)')"
    [[ -z "${enabled}" ]] || fail "prohibited API is enabled: ${api}"
  done
  for repository in janusai-poc janus-postgres; do
    policies="$(gcloud artifacts repositories list-cleanup-policies "${repository}" \
      --project="${project}" --location="${region}" --format=json)"
    POLICIES="${policies}" python3 - <<'PY'
import json, os
policies = json.loads(os.environ["POLICIES"])
assert any(
    item.get("action", {}).get("type") == "Keep"
    and item.get("mostRecentVersions", {}).get("keepCount") == 1
    and not item.get("mostRecentVersions", {}).get("packageNamePrefixes")
    for item in policies
), "cleanup global keepCount drift"
assert any(
    item.get("action", {}).get("type") == "Keep"
    and item.get("mostRecentVersions", {}).get("keepCount") == 2
    and "api" in item.get("mostRecentVersions", {}).get("packageNamePrefixes", [])
    for item in policies
), "cleanup API rollback keepCount drift"
PY
  done

  project_number="$(gcloud projects describe "${project}" --format='value(projectNumber)')"
  budgets="$(gcloud billing budgets list --billing-account="${billing_account}" \
    --filter="displayName='${budget_name}'" --format=json)"
  BUDGETS="${budgets}" PROJECT_NUMBER="${project_number}" python3 - <<'PY'
import json, os
items = json.loads(os.environ["BUDGETS"])
assert len(items) == 1, "expected one Janus dev budget"
budget = items[0]
amount = budget["amount"]["specifiedAmount"]
assert amount.get("currencyCode") == "TWD" and int(amount.get("units", 0)) == 320
assert {float(item["thresholdPercent"]) for item in budget["thresholdRules"]} == {0.1, 0.5, 1.0}
assert f"projects/{os.environ['PROJECT_NUMBER']}" in budget.get("budgetFilter", {}).get("projects", [])
PY
  echo "WBS-7 acceptance passed for ${project}: IAM, secrets, network, scaling, lifecycle, cleanup and budget guards."
}

report() {
  echo "month=$(date -u +%Y-%m) project=${project}"
  for name in janus-api janus-agent-gateway; do
    gcloud run services describe "${name}" --project="${project}" --region="${region}" \
      --format='value(metadata.name,spec.template.spec.serviceAccountName)'
  done
  for name in janus-ingestion-core janus-intelligence-mart janus-private-pipeline; do
    gcloud run jobs describe "${name}" --project="${project}" --region="${region}" \
      --format='value(metadata.name,spec.template.template.serviceAccount,spec.template.template.maxRetries)'
  done
  for layer in stage core mart private; do
    timeout 30 gcloud storage du -s "gs://${project}-dev-${layer}" 2>/dev/null || \
      echo "gs://${project}-dev-${layer}: size unavailable"
  done
  for repository in janusai-poc janus-postgres; do
    timeout 30 gcloud artifacts docker images list "${region}-docker.pkg.dev/${project}/${repository}" \
      --project="${project}" --include-tags --limit=20 --format='value(package,version,updateTime)' || \
      echo "${repository}: image inventory unavailable"
  done
  gcloud compute disks describe janus-postgres-dev --project="${project}" --zone="${zone}" \
    --format='value(name,sizeGb,type.basename())'
  gcloud compute snapshots list --project="${project}" --filter='sourceDisk~janus-postgres-dev' \
    --limit=5 --format='value(name,diskSizeGb,creationTimestamp)'
  if [[ -n "${billing_account}" ]]; then
    gcloud billing budgets list --billing-account="${billing_account}" \
      --filter="displayName='${budget_name}'" --format='value(displayName,amount.specifiedAmount.currencyCode,amount.specifiedAmount.units)'
  fi
  echo 'Actual billed spend remains governed by Cloud Billing budget notifications; no paid BigQuery billing export is created.'
}

case "${mode}" in
  configure) configure ;;
  verify) verify ;;
  report) report ;;
  *) echo "Usage: $0 {configure|verify|report}" >&2; exit 2 ;;
esac
