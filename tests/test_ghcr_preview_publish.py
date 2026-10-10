import json
from pathlib import Path
import sys
from unittest.mock import patch
import pytest

ROOT=Path(__file__).parents[1]
sys.path.insert(0,str(ROOT/"scripts/gcp"))
import ghcr_preview_publish as preview


def snapshot(preview_rev="previous",candidate="new"):
    rows=[{"revisionName":"live","percent":100,"tag":"active"},
          {"revisionName":candidate,"percent":0,"tag":"ghcr-038498c70e12"},
          {"revisionName":"mcp","tag":"mcp-oauth"},
          {"revisionName":"mcp","tag":"mcp-adapter"}]
    if preview_rev is not None:
        rows.append({"revisionName":preview_rev,"tag":"preview"})
    return {"status":{"traffic":rows,"conditions":[{"type":"Ready","status":"True"},
           {"type":"RoutesReady","status":"True"}]},
            "spec":{"template":{"spec":{"containers":[{"image":"image"}]}}}}


def test_only_preview_tag_can_change_and_canonical_100_stays_fixed():
    old=snapshot()
    after=snapshot(preview_rev="new")
    preview.assert_routes(old,after,"new")
    wrong=snapshot(preview_rev="new")
    wrong["status"]["traffic"][0]["percent"]=90
    with pytest.raises(ValueError,match="preview_baseline_split_traffic"):
        preview.assert_routes(old,wrong,"new")
    wrong2=snapshot(preview_rev="new")
    wrong2["status"]["traffic"][2]["revisionName"]="wrong"
    with pytest.raises(ValueError,match="preview_other_tags_changed"):
        preview.assert_routes(old,wrong2,"new")


def test_restore_requires_previous_tag_and_identical_baseline():
    before=snapshot()
    preview.assert_routes(before,snapshot(), "", restored=True)
    before_missing=snapshot(preview_rev=None)
    preview.assert_routes(before_missing,snapshot(preview_rev=None),"",restored=True)


def test_preview_failure_before_mutation_does_not_update_traffic(tmp_path):
    receipt=tmp_path/"r.json"
    with (patch.object(preview,"authorized"),
          patch.object(preview,"provenance",side_effect=ValueError("release_incomplete")),
          patch.object(preview,"update_preview") as update):
        assert preview.apply(receipt)==78
    update.assert_not_called()
    r=json.loads(receipt.read_text())
    assert r["canonical_traffic_write"] is False
    assert r["lease_released"] is False


def test_safe_tag_update_and_rollback_use_scoped_gcloud_flags():
    with patch.object(preview,"command") as cmd:
        preview.update_preview("candidate")
        preview.update_preview("old")
        preview.update_preview(remove=True)
    args=[c.args[0] for c in cmd.call_args_list]
    assert all("--to-revisions" not in " ".join(x) for x in args)
    assert "--update-tags=preview=candidate" in args[0]
    assert "--update-tags=preview=old" in args[1]
    assert "--remove-tags=preview" in args[2]


def test_preview_workflow_is_explicit_global_lease_without_traffic_promotion():
    text=(ROOT/".github/workflows/ghcr-preview-publish-dev.yml").read_text()
    assert "ops/ghcr-preview-request.json" in text
    assert "janus-dev-runtime-writers" in text
    assert "cancel-in-progress: false" in text
    assert "ghcr_preview_publish.py" in text
    assert "workflow_dispatch:" not in text
    assert "gcloud run deploy" not in text


def test_previous_preview_build_identity_must_be_known_for_recovery():
    with patch.object(preview,"request",return_value=(200,{},b"a"*40)):
        assert preview.read_preview_build_sha()=="a"*40
    with patch.object(preview,"request",return_value=(404,{},b"not-found")):
        with pytest.raises(ValueError,match="previous_preview_identity_unknown"):
            preview.read_preview_build_sha()


def test_preview_provenance_checks_exact_request_sha_at_each_successful_run():
    source="a"*40
    runs=[
        {"headSha":source,"status":"completed","conclusion":"success",
         "workflowName":"Janus GHCR full-test image publication"},
        {"headSha":"b"*40,"status":"completed","conclusion":"success",
         "workflowName":"Janus GHCR Cloud Run 0-percent candidate"},
        {"headSha":"c"*40,"status":"completed","conclusion":"success",
         "workflowName":"GHCR candidate OAuth and private-boundary probe"}]
    req={"source_sha":source,"release_run":"1","candidate_run":"2","boundary_run":"3"}
    def cmd(args):
        if args[:3]==["gh","run","view"]:
            return json.dumps(runs[int(args[3])-1])
        if args[:2]==["git","show"]:
            return json.dumps({"sha":source})
        assert args[:3]==["git","merge-base","--is-ancestor"]
        return ""
    with patch.object(preview,"command",side_effect=cmd):
        preview.provenance(req)
    def incorrect(args):
        if args[:3]==["gh","run","view"]:
            return json.dumps(runs[int(args[3])-1])
        if args[:2]==["git","show"]:
            return json.dumps({"sha":"d"*40})
        return ""
    with patch.object(preview,"command",side_effect=incorrect):
        with pytest.raises(ValueError,match="preview_workflow_source_identity_mismatch"):
            preview.provenance(req)


def test_preview_app_html_and_sha_both_required():
    source="a"*40
    with patch.object(preview,"request",return_value=(200,{},b"<html>OK</html>")) as req, \
         patch.object(preview,"probe") as probe:
        preview.verify_preview_web(source)
    req.assert_called_once_with(preview.EXPECTED_URL+"/app/")
    probe.assert_called_once_with(preview.EXPECTED_URL,source)
    with patch.object(preview,"request",return_value=(404,{},b"")):
        with pytest.raises(ValueError,match="preview_app_page_unavailable"):
            preview.verify_preview_web(source)


def test_nontraffic_service_setting_cannot_change_while_preview_updates():
    before=snapshot()
    after=snapshot(preview_rev="new")
    after["spec"]["other-setting"]="drift"
    with pytest.raises(ValueError,match="preview_service_runtime_config_changed"):
        preview.assert_routes(before,after,"new")


def test_same_verified_sha_is_read_only_idempotent_retry(tmp_path):
    receipt=tmp_path/"result.json"
    source="a"*40
    req={"source_sha":source}
    before=snapshot(preview_rev="new")
    with (patch.object(preview,"authorized",return_value=req),
          patch.object(preview,"provenance"),
          patch.object(preview.jobs,"legacy_writers"),
          patch.object(preview,"command") as cmd,
          patch.object(preview,"describe",return_value=before),
          patch.object(preview,"check_candidate",return_value="new"),
          patch.object(preview,"read_preview_build_sha",return_value=source),
          patch.object(preview,"reconciled") as reconciled,
          patch.object(preview,"verify_preview_web") as web,
          patch.object(preview,"update_preview") as update):
        assert preview.apply(receipt)==0
    update.assert_not_called()
    reconciled.assert_called_once()
    web.assert_called_once_with(source)
    result=json.loads(receipt.read_text())
    assert result["status"]=="PASS"
    assert result["phase"]=="VERIFIED_FIXED_PREVIEW_IDEMPOTENT"
    assert result["preview_tag_mutation_attempted"] is False
    assert result["lease_released"] is True
    assert cmd.call_count==4  # acquire, assert (before), assert (after), release
    assert all("update-traffic" not in " ".join(call.args[0]) for call in cmd.call_args_list)


def test_fault_injection_after_preview_update_restores_previous_revision_and_sha(tmp_path):
    """Exercise the real apply/recovery choreography without touching live routing."""
    from copy import deepcopy
    receipt=tmp_path/"preview.json"
    previous="previous"
    source="a"*40
    previous_sha="b"*40
    current=deepcopy(snapshot(preview_rev=previous))
    updates=[]
    lease=[]
    web_checks=[]

    def update(target=None,remove=False):
        assert remove is False
        updates.append(target)
        for route in current["status"]["traffic"]:
            if route.get("tag")=="preview":
                route["revisionName"]=target

    def serve_sha():
        assert current["status"]["traffic"][-1]["revisionName"] == previous or updates
        return previous_sha if len(updates)==0 or current["status"]["traffic"][-1]["revisionName"]==previous else source

    def verify_web(_):
        web_checks.append("injected_failure")
        raise ValueError("preview_post_update_health_failed")

    def command(args):
        if "update-traffic" in " ".join(args):
            raise AssertionError("All GCP updates must use the mock tag updater")
        lease.append(args)
        return ""

    with (patch.object(preview,"authorized",return_value={"source_sha":source}),
          patch.object(preview,"provenance"),
          patch.object(preview.jobs,"legacy_writers"),
          patch.object(preview,"command",side_effect=command),
          patch.object(preview,"describe",side_effect=lambda:deepcopy(current)),
          patch.object(preview,"check_candidate",return_value="new"),
          patch.object(preview,"read_preview_build_sha",side_effect=serve_sha),
          patch.object(preview,"verify_preview_web",side_effect=verify_web),
          patch.object(preview,"update_preview",side_effect=update),
          patch.object(preview.time,"sleep",return_value=None)):
        assert preview.apply(receipt)==78
    data=json.loads(receipt.read_text())
    assert updates==["new",previous]
    assert data["phase"]=="RESTORED_PREVIEW_OR_NO_MUTATION"
    assert data["restored_previous_preview"] is True
    assert data["lease_released"] is True
    assert data["canonical_traffic_write"] is False
    assert data["error_type"]=="ValueError"
    assert len(web_checks)==1
    assert current["status"]["traffic"][0]["revisionName"]=="live"
    assert current["status"]["traffic"][0]["percent"]==100
    assert [r for r in current["status"]["traffic"] if r.get("tag")=="preview"][0]["revisionName"]==previous
    assert lease[0]==preview.LEASE+["acquire"]
    assert lease[-1]==preview.LEASE+["release","--safe-to-release"]


def test_fault_injection_restore_failure_keeps_owner_lease_and_blocked_receipt(tmp_path):
    from copy import deepcopy
    receipt=tmp_path/"preview.json"
    source="a"*40
    current=deepcopy(snapshot(preview_rev="previous"))
    count=[0]
    def fail_rollback(target=None,remove=False):
        count[0]+=1
        if count[0]==1:
            current["status"]["traffic"][-1]["revisionName"]="new"
        else:
            raise ValueError("injected_preview_restore_failure")

    seen=[]
    with (patch.object(preview,"authorized",return_value={"source_sha":source}),
          patch.object(preview,"provenance"),
          patch.object(preview.jobs,"legacy_writers"),
          patch.object(preview,"command",side_effect=lambda args:seen.append(args) or ""),
          patch.object(preview,"describe",side_effect=lambda:deepcopy(current)),
          patch.object(preview,"check_candidate",return_value="new"),
          patch.object(preview,"read_preview_build_sha",return_value="b"*40),
          patch.object(preview,"verify_preview_web",side_effect=ValueError("preview_post_update_health_failed")),
          patch.object(preview,"update_preview",side_effect=fail_rollback)):
        assert preview.apply(receipt)==78
    data=json.loads(receipt.read_text())
    assert count[0]==2
    assert data["phase"]=="RECOVERY_BLOCKED_LEASE_RETAINED"
    assert data["lease_released"] is False
    assert data["restored_previous_preview"] is False
    assert all(args!=preview.LEASE+["release","--safe-to-release"] for args in seen)
