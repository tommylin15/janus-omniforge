"""Prepromotion revision inventory must be count-only and never authorize deletion."""
from __future__ import annotations

import copy
import runpy
from pathlib import Path
import pytest

ROOT = Path(__file__).parents[1]
api = runpy.run_path(str(ROOT / "scripts/gcp/ghcr_revision_retention_preview.py"))
preview, PreviewBlocked = api["preview"], api["PreviewBlocked"]


def fixture():
    revisions = [
        {"metadata": {
            "name": f"janus-api-{i:05d}",
            "creationTimestamp": f"2026-10-{i:02d}T10:00:00Z",
            "labels": {"serving.knative.dev/service": "janus-api"}}}
        for i in range(1, 16)
    ]
    service = {
        "metadata": {"name": "janus-api", "generation": 12},
        "status": {
            "observedGeneration": 12,
            "conditions": [{"type": "Ready", "status": "True"}],
            "latestReadyRevisionName": "janus-api-00015",
            "latestCreatedRevisionName": "janus-api-00015",
            "traffic": [
                {"revisionName": "janus-api-00009", "percent": 100},
                {"revisionName": "janus-api-00015", "tag": "ghcr-aabbcc", "percent": None},
            ],
        },
        "spec": {"traffic": [{"revisionName": "janus-api-00009", "percent": 100}]},
    }
    return service, revisions


def test_preview_protects_active_candidate_and_latest_ten():
    service, revisions = fixture()
    result = preview(service, revisions)
    assert result["total_revisions"] == 15
    assert result["latest_ten_count"] == 10
    assert result["protected_tagged_count"] == 1
    assert result["active_revision_names"] == ["janus-api-00009"]
    assert result["provisional_unreferenced_count"] == 5
    assert result["revisions_to_delete_now"] == 0
    assert result["apply_authorized"] is False
    assert result["resource_writes"] == 0


def test_old_tag_protects_revision_beyond_last_ten():
    service, revisions = fixture()
    service["status"]["traffic"].append(
        {"revisionName": "janus-api-00001", "tag": "mcp-oauth"})
    result = preview(service, revisions)
    assert result["provisional_unreferenced_count"] == 4
    assert "janus-api-00001" in result["tagged_revision_names"]


@pytest.mark.parametrize("change", [
    lambda s, r: s["status"].update(conditions=[]),
    lambda s, r: s["status"].update(observedGeneration=11),
    lambda s, r: s["status"]["traffic"][0].update(percent=90),
    lambda s, r: s["status"]["traffic"][0].update(latestRevision=True),
    lambda s, r: s["spec"].update(traffic=[{"latestRevision": True}]),
    lambda s, r: s["status"]["traffic"][1].update(revisionName="janus-api-99999"),
    lambda s, r: r[0]["metadata"]["labels"].update({"serving.knative.dev/service": "other"}),
    lambda s, r: r[0]["metadata"].update(creationTimestamp="invalid"),
    lambda s, r: r.append(copy.deepcopy(r[0])),
])
def test_invalid_unknown_or_dynamic_release_state_blocks_preview(change):
    service, revisions = fixture()
    change(service, revisions)
    with pytest.raises(PreviewBlocked):
        preview(service, revisions)


def test_revision_preview_has_no_mutation_or_release_permission():
    script = (ROOT / "scripts/gcp/ghcr_revision_retention_preview.py").read_text()
    assert "revisions_to_delete_now" in script
    assert '"apply_authorized": False' in script
    assert "subprocess" not in script
    assert "gcloud " not in script
    wf = (ROOT / ".github/workflows/ghcr-revision-retention-preview.yml").read_text()
    assert "ghcr_revision_retention_preview.py" in wf
    assert "gcloud run revisions list" in wf
    assert "gcloud run services describe" in wf
    for mutation in (
        "gcloud run revisions delete", "gcloud run deploy",
        "gcloud run services update-traffic", "gcloud builds submit",
        "gcloud run jobs update", "gcloud storage rm",
    ):
        assert mutation not in wf
