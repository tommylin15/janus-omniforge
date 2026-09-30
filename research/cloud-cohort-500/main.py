#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

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
    req = urllib.request.Request(
        METADATA_TOKEN_URL,
        headers={"Metadata-Flavor": "Google"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    token = payload.get("access_token")
    if not token:
        raise RuntimeError("metadata server returned no access_token")
    return token


def gcs_get_json(bucket: str, object_name: str, token: str) -> dict:
    quoted = urllib.parse.quote(object_name, safe="")
    url = f"https://storage.googleapis.com/storage/v1/b/{bucket}/o/{quoted}?alt=media"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def gcs_put_json(bucket: str, object_name: str, payload: dict, token: str) -> None:
    query = urllib.parse.urlencode({"uploadType": "media", "name": object_name})
    url = f"https://storage.googleapis.com/upload/storage/v1/b/{bucket}/o?{query}"
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status not in (200, 201):
            raise RuntimeError(f"GCS upload failed with status {resp.status}")


def main() -> int:
    bucket = required_env("RESEARCH_BUCKET")
    prefix = required_env("RESEARCH_PREFIX").strip("/")
    request_object = required_env("RESEARCH_REQUEST_OBJECT")
    run_id = required_env("RESEARCH_RUN_ID")
    research_sa = required_env("RESEARCH_SERVICE_ACCOUNT")

    token = access_token()
    request_payload = gcs_get_json(bucket, request_object, token)
    action = str(request_payload.get("action", "bootstrap")).strip() or "bootstrap"

    if action != "bootstrap":
        raise RuntimeError(
            "research execution surface is bootstrapped but only action=bootstrap is enabled; "
            f"received action={action!r}"
        )

    result = {
        "schema_version": "janus.research.cloud-cohort-500.v1",
        "status": "ok",
        "action": "bootstrap",
        "generated_at": utc_now(),
        "run_id": run_id,
        "request_object": request_object,
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
            "secrets_mounted": False
        },
        "capabilities": {
            "gcs_read_write": True,
            "cloud_run_job_execution": True,
            "historical_source_materialization": False,
            "cohort_selection": False,
            "mfe_computation": False
        },
        "next_gate": "dedicated_research_market_data_credential_or_approved_public_source",
        "request": request_payload
    }

    result_object = f"{prefix}/executions/{run_id}/bootstrap_result.json"
    gcs_put_json(bucket, result_object, result, token)
    print(json.dumps({"status": "ok", "result_object": result_object}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        raise
