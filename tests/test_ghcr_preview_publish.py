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
    with pytest.raises(ValueError,match="preview_canonical_traffic_drift"):
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
