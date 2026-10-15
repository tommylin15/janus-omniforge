import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts" / "gcp"))
import ghcr_terminal_lease_recovery as r


def owner():
    return {"id": r.OWNER_RUN, "head_sha": r.OWNER_SHA, "run_attempt": 1,
            "name": "Janus GHCR controlled Jobs rollout",
            "status": "completed", "conclusion": "failure"}


def lease():
    ref = {"ref": f"refs/tags/{r.TAG}", "object": {
        "sha": r.TAG_SHA, "type": "tag",
        "url": f"https://api.github.com/repos/{r.REPO}/git/tags/{r.TAG_SHA}"}}
    tag = {"sha": r.TAG_SHA, "tag": r.TAG,
           "object": {"type": "commit", "sha": r.OWNER_SHA},
           "message": r.MARKER + json.dumps({"run_id": r.OWNER_RUN,
                "run_attempt": 1, "source_sha": r.OWNER_SHA})}
    return ref, tag


def service():
    return {"metadata": {"name": "janus-api"},
            "status": {"conditions": [{"type": "Ready", "status": "True"}],
                       "traffic": [{"revisionName": "old-ready", "percent": 100},
                                   {"revisionName": "candidate", "percent": 0}]},
            "spec": {"template": {"metadata": {"annotations": {
                "autoscaling.knative.dev/minScale": "0"}}}}}


def test_only_exact_failed_terminal_owner_can_be_recovered():
    r.verify_owner(owner())
    for field, value in (("status", "in_progress"), ("conclusion", "success"),
                         ("run_attempt", 2), ("head_sha", "0"*40),
                         ("id", 1), ("name", "unrelated")):
        with pytest.raises(ValueError, match="owner_run_not_exactly_terminal_failed"):
            r.verify_owner(dict(owner(), **{field: value}))


def test_annotated_tag_and_owner_must_be_exact():
    ref, tag = lease()
    r.verify_lease(ref, tag)
    with pytest.raises(ValueError):
        r.verify_lease(dict(ref, ref="refs/tags/other"), tag)
    with pytest.raises(ValueError):
        r.verify_lease(ref, dict(tag, message=r.MARKER + json.dumps({
            "run_id": r.OWNER_RUN+1, "run_attempt": 1, "source_sha": r.OWNER_SHA})))
    with pytest.raises(ValueError):
        r.verify_lease(ref, dict(tag, object={"type": "commit", "sha": "0"*40}))


def test_live_api_requires_readiness_single_100_and_zero_min_instances():
    assert r.service_identity(service())[0] == "old-ready"
    for bad in (
        {**service(), "status": {"conditions": [{"type": "Ready", "status": "False"}],
                                  "traffic": service()["status"]["traffic"]}},
        {**service(), "status": {"conditions": [{"type": "Ready", "status": "True"}],
                                  "traffic": [{"revisionName": "old-ready", "percent": 80},
                                              {"revisionName": "new", "percent": 20}]}},
        {**service(), "spec": {"template": {"metadata": {"annotations": {
            "autoscaling.knative.dev/minScale": "1"}}}}},
    ):
        with pytest.raises(ValueError):
            r.service_identity(bad)
