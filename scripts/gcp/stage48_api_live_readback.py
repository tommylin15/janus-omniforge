"""Read-only, bounded Stage-48H API serving post-promotion acceptance.

Uses only GCP Service/Revision metadata and public unauthenticated health/auth
boundaries. A real authenticated Admin GCS scan remains separately NOT_VERIFIED.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROJECT = "gen-lang-client-0593591102"
REGION = "us-central1"
BASE = "https://janus-api-2oo7qbkd5q-uc.a.run.app"
REQ = Path("ops/stage48-api-live-readback.json")
PROOF = Path("/tmp/stage48-promotion-proof/ghcr-api-promote.json")


def cloud_json(*cmd: str) -> dict:
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=True)
    return json.loads(out.stdout)


def request(path: str, *, method: str = "GET") -> tuple[int, str]:
    headers = {"Accept": "text/plain"}
    data = None
    if method == "POST":
        headers["Content-Type"] = "application/json"
        data = b"{}"
    req = Request(BASE + path, method=method, data=data, headers=headers)
    try:
        with urlopen(req, timeout=25) as response:
            return response.status, response.read(256).decode("utf-8", "replace").strip()
    except HTTPError as error:
        return error.code, ""


def main() -> None:
    cfg = json.loads(REQ.read_text())
    if (cfg.get("intent") != "stage48-read-only-api-traffic"
            or cfg.get("no_gcp_mutation") is not True
            or cfg.get("no_owner_mutation") is not True
            or cfg.get("no_traffic_mutation") is not True):
        raise ValueError("read-only acceptance contract not authorized")
    proof = json.loads(PROOF.read_text())
    sha = cfg["source_sha"]
    if (proof.get("phase") != "PASS" or proof.get("source_sha") != sha
            or proof.get("rollback_rehearsal") != "PASS"
            or proof.get("previous_sha") != cfg["previous_sha"]):
        raise RuntimeError("promotion receipt not independently accepted")
    svc = cloud_json("gcloud", "run", "services", "describe", "janus-api",
                     "--project=" + PROJECT, "--region=" + REGION, "--format=json")
    traffic = svc.get("status", {}).get("traffic", [])
    active = [x for x in traffic if (x.get("percent") or 0) > 0]
    if len(active) != 1 or active[0]["percent"] != 100 or active[0]["revisionName"] != proof["candidate"]:
        raise RuntimeError("serving API traffic or active revision mismatch")
    tags = {x["tag"]: x["revisionName"] for x in traffic if x.get("tag")}
    if tags != proof["tags"]:
        raise RuntimeError("API revision tags drifted")
    revision = cloud_json("gcloud", "run", "revisions", "describe", proof["candidate"],
                          "--project=" + PROJECT, "--region=" + REGION, "--format=json")
    image = revision.get("spec", {}).get("containers", [{}])[0].get("image", "")
    if image.removeprefix("cache.us-docker.pkg.dev/") != proof["image"]:
        raise RuntimeError("serving immutable GHCR image mismatch")
    if request("/app/build-id.txt") != (200, sha):
        raise RuntimeError("API build SHA mismatch")
    for path in ("/health", "/api/v1/public/health"):
        if request(path)[0] != 200:
            raise RuntimeError("API health not ready")
    if request("/api/v1/me/profile")[0] not in (401, 403):
        raise RuntimeError("private Owner auth boundary open")
    code, _ = request("/api/v1/admin/gcs-storage/inspect", method="POST")
    if code not in (401, 403):
        raise RuntimeError("Admin GCS inventory unauthenticated boundary open")
    result = {"status": "PASS", "scope": "API_TRAFFIC_AND_NEGATIVE_AUTH_ONLY",
              "source_sha": sha, "promotion_run": cfg["promotion_run"],
              "active_revision": proof["candidate"], "traffic_percent": 100,
              "rollback_rehearsal": "PASS", "image_digest_match": True,
              "build_sha_match": True, "health_ok": True,
              "unauth_admin_inventory_http": code, "real_admin_inventory": "NOT_VERIFIED",
              "new_stage_payload_reuse_live": "NOT_VERIFIED",
              "daily_1830_natural_due": "NOT_VERIFIED", "gcp_mutations": 0}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
