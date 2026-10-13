"""Verify the real Janus CEO Job identity may impersonate the market-mart Gateway caller.

Run once from the existing CEO Job with an ephemeral args override. The probe
deliberately sends malformed JSON to avoid any Gemini call or database write.
The CI service account's separate impersonation permissions do not prove this.
"""
from __future__ import annotations

import json
import time

from ceo_worker_deploy import execution_fence
from ghcr_jobs_rollout import ROOT, cloud, terminal

PROJECT = "gen-lang-client-0593591102"
SOURCE = f"intelligence-mart@{PROJECT}.iam.gserviceaccount.com"
JOB = "janus-ceo-analysis"

# Executed inside the actual Cloud Run Job, not the GitHub runner.
# Never print/return the ID token or the upstream error body.
PROBE_CODE = """
import json
import urllib.error
import urllib.request
import google.auth
from google.auth import impersonated_credentials
from google.auth.transport.requests import Request

project = 'gen-lang-client-0593591102'
source, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
target = impersonated_credentials.Credentials(
    source_credentials=source,
    target_principal='omniagent-codex-market-client@' + project + '.iam.gserviceaccount.com',
    target_scopes=['https://www.googleapis.com/auth/cloud-platform'],
    lifetime=300,
)
audience = 'https://omniagent-agent-gateway-2oo7qbkd5q-uc.a.run.app'
signed = impersonated_credentials.IDTokenCredentials(
    target_credentials=target, target_audience=audience, include_email=True,
)
signed.refresh(Request())
if not signed.token:
    raise RuntimeError('identity_token_missing')
probe = urllib.request.Request(
    'https://gemini-p0v-b03e5f55---omniagent-agent-gateway-2oo7qbkd5q-uc.a.run.app/v1/gemini/execute',
    method='POST', data=b'{}',
    headers={'Authorization': 'Bearer ' + signed.token, 'Content-Type': 'application/json'},
)
try:
    with urllib.request.urlopen(probe, timeout=15):
        raise RuntimeError('malformed_body_unexpectedly_accepted')
except urllib.error.HTTPError as error:
    if error.code != 400:
        raise RuntimeError('gateway_signed_auth_or_route_failed') from None
    body = error.read(256)
    if json.loads(body).get('error') != 'invalid_request':
        raise RuntimeError('gateway_contract_not_matched')
print(json.dumps({'kind':'janus_ceo_gateway_identity_preflight','status':'PASS','provider_calls':0,'database_writes':0}))
"""


def preflight():
    job = cloud(f"{ROOT}/jobs/{JOB}")
    task = job["template"]["template"]
    if task.get("serviceAccount") != SOURCE:
        raise RuntimeError("unexpected_ceo_runtime_identity")
    if task.get("maxRetries", 0) != 0 or job.get("reconciling"):
        raise RuntimeError("ceo_job_not_stable")
    execution_fence()


def execute_once() -> dict:
    preflight()
    path = f"{ROOT}/jobs/{JOB}"
    # The source image/Job/environment are not mutated; replace argv for this run only.
    body = {
        "overrides": {
            "taskCount": 1,
            "timeout": "90s",
            "containerOverrides": [{"name": "ceo", "args": ["-c", PROBE_CODE]}],
        }
    }
    operation = cloud(path + ":run", body, "POST")
    name = operation.get("name", "")
    if not name.startswith(ROOT + "/operations/"):
        raise RuntimeError("iam_probe_operation_unknown")
    deadline = time.monotonic() + 220
    while time.monotonic() < deadline:
        current = cloud(name)
        if current.get("done"):
            if current.get("error"):
                raise RuntimeError("iam_probe_execution_failed_no_retry")
            execution_name = current.get("response", {}).get("name", "")
            if not execution_name.startswith(path + "/executions/"):
                raise RuntimeError("iam_probe_execution_identity_unknown")
            result = cloud(execution_name)
            if not terminal(result) or result.get("succeededCount") != 1 or result.get("failedCount", 0):
                raise RuntimeError("iam_probe_worker_not_pass")
            return {
                "status": "PASS",
                "execution": execution_name,
                "real_worker_identity": SOURCE,
                "model_calls": 0,
                "database_writes": 0,
                "job_updated": False,
                "traffic_changed": False,
            }
        time.sleep(3)
    raise RuntimeError("iam_probe_execution_unknown_no_retry")


if __name__ == "__main__":
    print(json.dumps(execute_once(), sort_keys=True))
