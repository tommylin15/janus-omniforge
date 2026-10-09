#!/usr/bin/env python3
"""Repair only the two existing dev MCP tags under the shared release lease."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.error import HTTPError

from ghcr_candidate_lease_guard import ready_and_reconciled

PROJECT = "gen-lang-client-0593591102"
REGION = "us-central1"
SERVICE = "janus-api"
TAGS = ("mcp-oauth", "mcp-adapter")
BASE = "https://janus-api-2oo7qbkd5q-uc.a.run.app"
CODEX = "https://chatgpt.com/oauth/codex/client.json"
LEASE = [sys.executable, "scripts/gcp/ghcr_release_lease.py"]


def command(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=120)
    if result.returncode:
        # gcloud/API errors can include runtime config or OAuth query payloads.
        raise RuntimeError("bounded_command_failed")
    return result.stdout


def routes(snapshot):
    entries = snapshot["status"]["traffic"]
    tags = {v["tag"]: (v["revisionName"], v.get("percent") or 0) for v in entries if v.get("tag")}
    if len(tags) != sum(bool(v.get("tag")) for v in entries):
        raise ValueError("duplicate_routes")
    active = sorted((v["revisionName"], v["percent"]) for v in entries if (v.get("percent") or 0) > 0)
    return active, tags


def validate(before, after, candidate, restored=False):
    if not ready_and_reconciled(after) or after.get("metadata", {}).get("name") != SERVICE:
        raise ValueError("service_not_reconciled")
    old_active, old_tags = routes(before)
    new_active, new_tags = routes(after)
    if len(old_active) != 1 or old_active[0][1] != 100 or new_active != old_active:
        raise ValueError("canonical_traffic_changed")
    if not all(tag in old_tags and old_tags[tag][1] == 0 for tag in TAGS):
        raise ValueError("existing_mcp_routes_required")
    expected = dict(old_tags)
    if not restored:
        expected.update({tag: (candidate, 0) for tag in TAGS})
    if new_tags != expected:
        raise ValueError("unexpected_tag_change")


def describe():
    return json.loads(command(["gcloud", "run", "services", "describe", SERVICE,
                               f"--project={PROJECT}", f"--region={REGION}", "--format=json"]))


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with build_opener(NoRedirect).open(req, timeout=25) as response:
            return response.status, response.headers, response.read(96000)
    except HTTPError as error:
        return error.code, error.headers, error.read(96000)


def probe(base, sha):
    code, _, body = request(base + "/app/build-id.txt")
    if code != 200 or body.decode().strip() != sha:
        raise ValueError("build_identity_mismatch")
    code, _, body = request(base + "/.well-known/oauth-authorization-server")
    metadata = json.loads(body)
    issuer = "https://mcp-oauth---" + urlsplit(BASE).netloc
    resource = "https://mcp-adapter---" + urlsplit(BASE).netloc + "/mcp"
    if code != 200 or metadata.get("issuer") != issuer or "S256" not in metadata.get("code_challenge_methods_supported", []):
        raise ValueError("oauth_metadata_mismatch")
    code, _, body = request(base + "/.well-known/oauth-protected-resource")
    if code != 200 or json.loads(body).get("resource") != resource:
        raise ValueError("resource_metadata_mismatch")
    query = {"response_type": "code", "client_id": CODEX,
             "redirect_uri": "http://127.0.0.1:59164/callback", "resource": resource,
             "scope": "janus.private.read", "state": "bounded-prelogin-probe",
             "code_challenge": "x" * 43, "code_challenge_method": "S256"}
    code, headers, _ = request(base + "/oauth/authorize?" + urlencode(query))
    target = urlsplit(headers.get("Location", ""))
    google = parse_qs(target.query)
    if (code != 302 or target.scheme != "https" or target.netloc != "accounts.google.com"
            or google.get("redirect_uri") != [issuer + "/oauth/google/callback"]):
        raise ValueError("codex_authorization_not_accepted")
    query["redirect_uri"] = "http://127.0.0.2:59164/callback"
    if request(base + "/oauth/authorize?" + urlencode(query))[0] != 400:
        raise ValueError("loopback_negative_guard_failed")
    code, _, _ = request(base + "/mcp", {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "janus_private_context", "arguments": {"resource": "positions", "limit": 1}}})
    if code != 401:
        raise ValueError("private_auth_boundary_failed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-run", required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    args = parser.parse_args()
    sha = json.loads(Path("ops/ghcr-candidate-request.json").read_text())["sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", sha) or not re.fullmatch(r"[0-9]+", args.release_run):
        raise ValueError("invalid_release_identity")
    command(["git", "merge-base", "--is-ancestor", sha, "HEAD"])
    run = json.loads(command(["gh", "run", "view", args.release_run, "--json",
                              "headSha,status,conclusion,jobs,workflowName"]))
    names = {job["name"] for job in run["jobs"] if job["conclusion"] == "success"}
    if (run["headSha"] != sha or run["status"] != "completed" or run["conclusion"] != "success"
            or run["workflowName"] != "Janus GHCR full-test image publication"
            or not {"python-tests", "flutter-tests", "publish (api)", "public-pull-gate"}.issubset(names)):
        raise ValueError("full_release_gate_not_passed")
    command(LEASE + ["acquire"])
    before = None
    mutation = False
    try:
        before = describe()
        tag = "ghcr-" + sha[:12]
        active, existing = routes(before)
        candidate = existing[tag][0]
        validate(before, before, candidate, restored=True)
        if existing[tag][1] != 0 or candidate == active[0][0]:
            raise ValueError("zero_traffic_candidate_required")
        # Persist only bounded routing metadata for independent recovery after crash.
        args.baseline.write_text(json.dumps({"source_sha": sha, "candidate": candidate,
            "active": active, "tags": existing}, sort_keys=True))
        triggers = json.loads(command(["gcloud", "builds", "triggers", "list", f"--project={PROJECT}",
            f"--region={REGION}", "--filter=name=janus-dev-v2", "--format=json(id,name,disabled)"]))
        if len(triggers) != 1 or triggers[0].get("disabled") is not True:
            raise ValueError("legacy_writer_not_disabled")
        builds = json.loads(command(["gcloud", "builds", "list", f"--project={PROJECT}",
            f"--region={REGION}", "--filter=status=QUEUED OR status=WORKING", "--format=json(id,status)", "--limit=1"]))
        if builds:
            raise ValueError("legacy_build_active")
        revision = json.loads(command(["gcloud", "run", "revisions", "describe", candidate,
            f"--project={PROJECT}", f"--region={REGION}", "--format=json"]))
        image = revision["spec"]["containers"][0]["image"].removeprefix("cache.us-docker.pkg.dev/")
        if not re.fullmatch(r"ghcr\.io/tommylin15/janus-api@sha256:[0-9a-f]{64}", image):
            raise ValueError("candidate_not_fixed_ghcr_digest")
        if int(revision.get("metadata", {}).get("annotations", {}).get("autoscaling.knative.dev/minScale", "0")) != 0:
            raise ValueError("candidate_min_instances_not_zero")
        if not any(c.get("type") == "Ready" and c.get("status") == "True" for c in revision["status"]["conditions"]):
            raise ValueError("candidate_not_ready")
        candidate_url = next(t["url"] for t in before["status"]["traffic"] if t.get("tag") == tag)
        probe(candidate_url, sha)
        command(LEASE + ["assert"])
        mutation = True
        command(["gcloud", "run", "services", "update-traffic", SERVICE, f"--project={PROJECT}",
            f"--region={REGION}", "--update-tags=" + ",".join(f"{tag}={candidate}" for tag in TAGS), "--quiet"])
        validate(before, describe(), candidate)
        for tag in TAGS:
            probe("https://" + tag + "---" + urlsplit(BASE).netloc, sha)
        command(LEASE + ["assert"])
        command(LEASE + ["release", "--safe-to-release"])
        print(json.dumps({"result": "PASS", "source_sha": sha, "revision": candidate,
            "image": image, "tags": TAGS, "canonical_traffic_unchanged": True,
            "codex_prelogin_gate": "PASS", "authenticated_mcp": "PENDING"}, sort_keys=True))
        return 0
    except Exception:
        if before is None:
            raise RuntimeError("baseline_unknown_lease_retained") from None
        try:
            command(LEASE + ["assert"])
            if mutation:
                old_tags = routes(before)[1]
                command(["gcloud", "run", "services", "update-traffic", SERVICE, f"--project={PROJECT}",
                    f"--region={REGION}", "--update-tags=" + ",".join(f"{t}={old_tags[t][0]}" for t in TAGS), "--quiet"])
            validate(before, describe(), "", restored=True)
            command(LEASE + ["release", "--safe-to-release"])
        except Exception:
            raise RuntimeError("recovery_unknown_lease_retained") from None
        raise RuntimeError("route_repair_failed_baseline_verified") from None


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(json.dumps({"result": "BLOCKED", "reason": type(error).__name__}), file=sys.stderr)
        sys.exit(78)
