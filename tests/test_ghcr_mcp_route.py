import copy
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts/gcp"))
import ghcr_mcp_route as route
SOURCE_SHA = route.json.loads((ROOT / "ops/ghcr-candidate-request.json").read_text())["sha"]


def baseline():
    return {"metadata": {"name": "janus-api", "generation": 4}, "status": {
        "observedGeneration": 4, "conditions": [{"type": "Ready", "status": "True"}],
        "traffic": [{"revisionName": "stable", "percent": 100},
                    {"tag": "ghcr-" + SOURCE_SHA[:12], "revisionName": "candidate"},
                    {"tag": "mcp-oauth", "revisionName": "old-oauth"},
                    {"tag": "mcp-adapter", "revisionName": "old-adapter"},
                    {"tag": "unrelated", "revisionName": "other"}]}}


def switched():
    result = baseline()
    for entry in result["status"]["traffic"]:
        if entry.get("tag") in route.TAGS:
            entry["revisionName"] = "candidate"
    return result


def test_only_two_mcp_tags_change_and_rollback_restores_original_routes():
    route.validate(baseline(), switched(), "candidate")
    route.validate(baseline(), baseline(), "", restored=True)
    with pytest.raises(ValueError):
        route.validate(baseline(), switched(), "", restored=True)


@pytest.mark.parametrize("change", ["traffic", "unrelated", "missing", "duplicate", "generation", "ready"])
def test_readback_rejects_incomplete_or_unrelated_runtime_changes(change):
    after = switched()
    traffic = after["status"]["traffic"]
    if change == "traffic":
        traffic[0]["revisionName"] = "candidate"
    elif change == "unrelated":
        traffic[-1]["revisionName"] = "candidate"
    elif change == "missing":
        traffic.pop(2)
    elif change == "duplicate":
        traffic.append(copy.deepcopy(traffic[2]))
    elif change == "generation":
        after["status"]["observedGeneration"] = 3
    else:
        after["status"]["conditions"][0]["status"] = "False"
    with pytest.raises(ValueError):
        route.validate(baseline(), after, "candidate")


def test_prelogin_probe_verifies_google_callback_and_negative_private_boundary():
    sha = "a" * 40
    issuer = "https://mcp-oauth---janus-api-2oo7qbkd5q-uc.a.run.app"
    resource = "https://mcp-adapter---janus-api-2oo7qbkd5q-uc.a.run.app/mcp"
    responses = [(200, {}, sha.encode()),
                 (200, {}, route.json.dumps({"issuer": issuer, "code_challenge_methods_supported": ["S256"]}).encode()),
                 (200, {}, route.json.dumps({"resource": resource}).encode()),
                 (302, {"Location": "https://accounts.google.com/o/oauth2/v2/auth?" + route.urlencode({"redirect_uri": issuer + "/oauth/google/callback"})}, b""),
                 (400, {}, b""), (401, {}, b""),
                 (200, {}, route.json.dumps({"result": {"tools": [
                     {"name": name, "annotations": {"readOnlyHint": True}}
                     for name in ("janus_sources", "janus_market_context", "janus_private_context")
                 ]}}).encode()),
                 (200, {}, route.json.dumps({"error": {"code": -32602, "message": "Unknown tool"}}).encode())]
    with patch.object(route, "request", side_effect=responses) as request:
        route.probe("https://candidate.test", sha)
    query = route.parse_qs(route.urlsplit(request.call_args_list[3].args[0]).query)
    assert query["client_id"] == [route.CODEX]
    assert query["redirect_uri"] == ["http://127.0.0.1:59164/callback"]


def test_route_probe_rejects_candidate_advertising_retired_write_scope():
    metadata={"issuer": "https://mcp-oauth---janus-api-2oo7qbkd5q-uc.a.run.app",
              "code_challenge_methods_supported": ["S256"], "scopes_supported": ["janus.private.write"]}
    with patch.object(route, "request", side_effect=[
            (200, {}, b"sha"), (200, {}, route.json.dumps(metadata).encode())]):
        with pytest.raises(ValueError, match="retired_write_scope_advertised"):
            route.probe("https://candidate.test", "sha")


def test_workflow_is_manual_and_shared_lease_fences_tag_mutation():
    workflow = (ROOT / ".github/workflows/ghcr-mcp-route-dev.yml").read_text()
    assert "workflow_dispatch:" in workflow and "push:" not in workflow
    assert "group: janus-dev-runtime-writers" in workflow
    assert "cancel-in-progress: false" in workflow
    source = (ROOT / "scripts/gcp/ghcr_mcp_route.py").read_text()
    assert source.index('command(LEASE + ["acquire"])') < source.index('"--update-tags="')
    assert '"headSha"' in source and '"public-pull-gate"' in source
    assert "validate(before, describe(), candidate)" in source
    assert 'validate(before, describe(), "", restored=True)' in source
    assert "lease_retained" in source
    assert "--to-revisions" not in source and '"run", "jobs"' not in source


@pytest.mark.parametrize("recovery_safe", [True, False])
def test_failed_live_probe_restores_tags_and_only_releases_after_verified_recovery(tmp_path, recovery_safe):
    sha = route.json.loads((ROOT / "ops/ghcr-candidate-request.json").read_text())["sha"]
    calls = []

    def command(args):
        calls.append(args)
        if args[:3] == ["gh", "run", "view"]:
            return route.json.dumps({"headSha": sha, "status": "completed", "conclusion": "success",
                "workflowName": "Janus GHCR full-test image publication",
                "jobs": [{"name": name, "conclusion": "success"} for name in
                         ("python-tests", "flutter-tests", "publish (api)", "public-pull-gate")]})
        if args[:4] == ["gcloud", "builds", "triggers", "list"]:
            return '[{"disabled": true}]'
        if args[:3] == ["gcloud", "builds", "list"]:
            return "[]"
        if args[:4] == ["gcloud", "run", "revisions", "describe"]:
            return route.json.dumps({"spec": {"containers": [{"image": "ghcr.io/tommylin15/janus-api@sha256:" + "a" * 64}]},
                "status": {"conditions": [{"type": "Ready", "status": "True"}]}})
        return ""

    before = baseline()
    before["status"]["traffic"][1]["url"] = "https://candidate.test"
    restored = baseline() if recovery_safe else switched()
    with patch.object(sys, "argv", ["repair", "--release-run", "123", "--baseline", str(tmp_path / "baseline.json")]), \
         patch.object(route, "command", side_effect=command), \
         patch.object(route, "describe", side_effect=[before, switched(), restored]), \
         patch.object(route, "probe", side_effect=[None, ValueError("live-probe-failed")]):
        with pytest.raises(RuntimeError, match="baseline_verified" if recovery_safe else "lease_retained"):
            route.main()
    updates = [arg for call in calls for arg in call if arg.startswith("--update-tags=")]
    assert updates == ["--update-tags=mcp-oauth=candidate,mcp-adapter=candidate",
                       "--update-tags=mcp-oauth=old-oauth,mcp-adapter=old-adapter"]
    released = route.LEASE + ["release", "--safe-to-release"] in calls
    assert released is recovery_safe
