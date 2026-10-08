#!/usr/bin/env bash
set -Eeuo pipefail
# Shadow build: no deployment, migration, Scheduler or IAM mutation.
project=gen-lang-client-0593591102
region=us-central1
repository="${region}-docker.pkg.dev/${project}/janusai-poc"
state=/workspace/v2-state
case "${1:-}" in
  prepare)
    mkdir -p "${state}"
    sha="${JANUS_TRIGGER_SHA:-${JANUS_MANUAL_SHA:-}}"
    [[ "${sha}" =~ ^[0-9a-f]{40}$ ]] || { echo 'Full commit SHA required' >&2; exit 2; }
    if [[ -n "${JANUS_TRIGGER_SHA:-}" && -n "${JANUS_MANUAL_SHA:-}" && "${JANUS_TRIGGER_SHA}" != "${JANUS_MANUAL_SHA}" ]]; then
      echo 'Trigger and manual SHA mismatch' >&2; exit 2
    fi
    # Public source only. No GitHub credential is passed to git or Docker.
    git init -q /workspace/v2-source
    git -C /workspace/v2-source remote add origin https://github.com/tommylin15/janus-omniforge.git
    git -C /workspace/v2-source fetch -q --depth=1 origin "${sha}"
    git -C /workspace/v2-source checkout -q --detach FETCH_HEAD
    cd /workspace/v2-source
    [[ "$(git rev-parse HEAD)" == "${sha}" ]]
    flags=(--sha "${sha}" --output "${state}/plan.json")
    if [[ -n "${JANUS_BASE_SHA:-}" ]]; then
      [[ "${JANUS_BASE_SHA}" =~ ^[0-9a-f]{40}$ ]]
      git fetch -q --depth=1 origin "${JANUS_BASE_SHA}"
      flags+=(--base "${JANUS_BASE_SHA}")
    fi
    if [[ "${JANUS_COMPONENTS:-all}" != all ]]; then
      IFS=, read -ra components <<< "${JANUS_COMPONENTS}"
      for component in "${components[@]}"; do flags+=(--component "${component}"); done
    fi
    python3 scripts/gcp/cicd-v2.py plan "${flags[@]}"
    python3 - "${state}" <<'PY'
import json, pathlib, sys
state = pathlib.Path(sys.argv[1])
plan = json.loads((state / 'plan.json').read_text())
(state / 'components').write_text('\n'.join(plan['components']) + '\n')
(state / 'sha').write_text(plan['sha'])
PY
    ;;
  test)
    [[ -s "${state}/plan.json" ]]
    # Even document-only plans run the controller contracts, without runtime builds.
    python -m pip install -r requirements-dev.txt
    python -m pytest -q tests/test_cicd_v2.py
    if [[ -z "$(tr -d '[:space:]' < "${state}/components")" ]]; then exit 0; fi
    # Reuse the existing dependency locks and targeted suites; no new test framework.
    python -m pip install -r jobs/ingestion-core/requirements.lock
    python -m pip install -r jobs/intelligence-mart/requirements.lock
    python -m pip install -r services/api/requirements.lock
    export PYTHONPATH=jobs/ingestion-core:jobs/intelligence-mart:.
    python - <<'PY'
import pathlib, re, subprocess, sys
workflow = pathlib.Path('.github/workflows/deploy-dev.yml').read_text()
tests = set(re.findall(r'tests/[a-zA-Z0-9_/]+\.py', workflow))
tests.add('tests/test_cicd_v2.py')
subprocess.run([sys.executable, '-m', 'pytest', '-q', *sorted(tests)], check=True)
PY
    touch "${state}/tests-pass"
    ;;
  build)
    sha="$(cat "${state}/sha")"
    [[ "${sha}" =~ ^[0-9a-f]{40}$ ]]
    if [[ -z "$(tr -d '[:space:]' < "${state}/components")" ]]; then exit 0; fi
    [[ -f "${state}/tests-pass" ]]
    while IFS= read -r component; do
      [[ -n "${component}" ]] || continue
      flags=()
      case "${component}" in
        ingestion-core) dockerfile=jobs/ingestion-core/Dockerfile ;;
        intelligence-mart) dockerfile=jobs/intelligence-mart/Dockerfile; flags+=(--target=mart-specialist) ;;
        api|private-pipeline)
          dockerfile=services/api/Dockerfile
          flags+=("--target=${component}")
          if [[ "${component}" == api ]]; then
            : "${GOOGLE_USER_CLIENT_ID:?public user OAuth client ID required}"
            : "${GOOGLE_ADMIN_CLIENT_ID:?public admin OAuth client ID required}"
            flags+=("--build-arg=GOOGLE_USER_CLIENT_ID=${GOOGLE_USER_CLIENT_ID}" "--build-arg=GOOGLE_ADMIN_CLIENT_ID=${GOOGLE_ADMIN_CLIENT_ID}")
          fi
          ;;
        *) echo 'Unsupported component' >&2; exit 2 ;;
      esac
      # The two API targets share the same Docker daemon/base cache.
      image="${repository}/${component}:v2-${sha}"
      docker build --file="${dockerfile}" "${flags[@]}" --build-arg="JANUS_GIT_SHA=${sha}" --tag="${image}" .
      docker push "${image}"
    done < "${state}/components"
    ;;
  receipt)
    python3 - "${state}" "${repository}" "${project}" <<'PY'
import json, os, pathlib, re, subprocess, sys
state, repository, project = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
plan = json.loads((state / 'plan.json').read_text())
images = {}
for component in plan['components']:
    result = subprocess.run(['gcloud', 'artifacts', 'docker', 'images', 'describe',
        f"{repository}/{component}:v2-{plan['sha']}", f'--project={project}',
        '--format=value(image_summary.digest)'], capture_output=True, text=True, check=True, timeout=60)
    digest = result.stdout.strip()
    assert re.fullmatch(r'sha256:[0-9a-f]{64}', digest)
    images[component] = f'{repository}/{component}@{digest}'
receipt = {**plan, 'build_id': os.environ['JANUS_BUILD_ID'], 'images': images,
           'tests': 'PASS' if images else 'controller-contracts-only',
           'runtime_acceptance': 'NOT_RUN', 'promotion': 'NOT_RUN', 'status': 'SHADOW_BUILD_ONLY'}
(state / 'build-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt))
PY
    # Existing regional bucket only; logs remain in Cloud Logging.
    gcloud storage cp "${state}/build-receipt.json" \
      "gs://${project}-cloudbuild-regional/v2/evidence/${JANUS_BUILD_ID}/build-receipt.json" \
      --if-generation-match=0 --quiet
    ;;
  *) echo 'Usage: cicd-v2-build.sh prepare|test|build|receipt' >&2; exit 2 ;;
esac
