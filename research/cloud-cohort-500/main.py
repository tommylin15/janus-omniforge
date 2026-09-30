#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

METADATA_TOKEN_URL = (
    "http://metadata.google.internal/computeMetadata/v1/instance/"
    "service-accounts/default/token"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required env: {name}")
    return value


def access_token() -> str:
    req = urllib.request.Request(METADATA_TOKEN_URL, headers={"Metadata-Flavor": "Google"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    token = payload.get("access_token")
    if not token:
        raise RuntimeError("metadata server returned no access_token")
    return token


def gcs_get_json(bucket: str, object_name: str, token: str) -> dict[str, Any]:
    quoted = urllib.parse.quote(object_name, safe="")
    url = f"https://storage.googleapis.com/storage/v1/b/{bucket}/o/{quoted}?alt=media"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def gcs_put_json(bucket: str, object_name: str, payload: dict[str, Any], token: str) -> None:
    query = urllib.parse.urlencode({"uploadType": "media", "name": object_name})
    url = f"https://storage.googleapis.com/upload/storage/v1/b/{bucket}/o?{query}"
    body = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        if resp.status not in (200, 201):
            raise RuntimeError(f"GCS upload failed with status {resp.status}")


def bootstrap(bucket: str, prefix: str, request: dict[str, Any], run_id: str, research_sa: str, token: str) -> dict[str, Any]:
    result = {
        "schema_version": "janus.research.cloud-cohort-500.v1",
        "status": "ok",
        "action": "bootstrap",
        "generated_at": utc_now(),
        "run_id": run_id,
        "research_bucket": bucket,
        "research_prefix": prefix,
        "research_service_account": research_sa,
        "isolation": {
            "postgresql_used": False,
            "database_used": False,
            "existing_janus_iceberg_catalog_used": False,
            "janus_core_written": False,
            "janus_mart_written": False,
            "janus_private_mart_written": False,
            "secrets_mounted": False,
        },
        "capabilities": {"gcs_read_write": True, "cloud_run_job_execution": True},
        "next_gate": "stage_source_then_build_cohort",
        "request": request,
    }
    gcs_put_json(bucket, f"{prefix}/executions/{run_id}/bootstrap_result.json", result, token)
    return result


def main() -> int:
    bucket = required_env("RESEARCH_BUCKET")
    prefix = required_env("RESEARCH_PREFIX").strip("/")
    request_object = required_env("RESEARCH_REQUEST_OBJECT")
    run_id = required_env("RESEARCH_RUN_ID")
    research_sa = required_env("RESEARCH_SERVICE_ACCOUNT")
    token = access_token()
    request = gcs_get_json(bucket, request_object, token)
    action = str(request.get("action", "")).strip()

    if action == "bootstrap":
        result = bootstrap(bucket, prefix, request, run_id, research_sa, token)
    elif action == "build_cohort":
        import cohort_build
        result = cohort_build.run(request, bucket, prefix, run_id)
        gcs_put_json(bucket, f"{prefix}/executions/{run_id}/cohort_build_result.json", result, token)
    elif action == "preflight_and_outcomes":
        import outcome_run
        result = outcome_run.run(request, bucket, prefix, run_id)
        gcs_put_json(bucket, f"{prefix}/executions/{run_id}/outcome_run_result.json", result, token)
    elif action == "sensitivity_and_report":
        import sensitivity_run
        result = sensitivity_run.run(request, bucket, prefix, run_id)
        gcs_put_json(bucket, f"{prefix}/executions/{run_id}/sensitivity_result.json", result, token)
    elif action == "eventize_waves":
        import eventize_run_v2 as eventize_run
        result = eventize_run.run(request, bucket, prefix, run_id)
        gcs_put_json(bucket, f"{prefix}/executions/{run_id}/eventization_result.json", result, token)
    elif action == "matched_antecedent_features":
        import matched_feature_run
        result = matched_feature_run.run(request, bucket, prefix, run_id)
        gcs_put_json(bucket, f"{prefix}/executions/{run_id}/matched_feature_result.json", result, token)
    else:
        raise RuntimeError(f"unsupported Cloud Run research action: {action!r}")

    print(json.dumps({"status": result.get("status"), "action": action, "run_id": run_id}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise
