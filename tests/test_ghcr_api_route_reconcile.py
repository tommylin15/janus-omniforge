"""Same-revision routing repair cannot bypass original-owner lease or image gate."""
import json
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts/gcp"))
import ghcr_api_route_reconcile as rr


def test_guard_rejects_broader_approval(tmp_path):
    p = tmp_path / "req.json"
    baseline = {"intent":"reassert-existing-ghcr-api-route-under-owner-lease",
        "approved":True,"scope":"existing-dev-janus-api-only",
        "source_sha":rr.final.SHA,"original_owner_run":rr.final.ORIGINAL_RUN,
        "route_target":rr.final.CANDIDATE,
        "allow_only_same_100_percent":True,"allow_no_old_ar_rollback":True}
    with patch.object(rr, "REQUEST", p):
        p.write_text(json.dumps(baseline))
        rr.checked_request()
        for field, bad in [("approved",False),("scope","all-projects"),
                           ("route_target","other"),("allow_only_same_100_percent",False)]:
            d = {**baseline, field:bad}
            p.write_text(json.dumps(d))
            with pytest.raises(ValueError,match="route_reconcile_not_approved"):
                rr.checked_request()


def test_failure_never_releases_or_writes_traffic_without_preflight(tmp_path):
    with (patch.object(rr, "checked_request"),
          patch.object(rr.final, "assert_original_lease", return_value=["owner"]),
          patch.object(rr, "preflight", side_effect=ValueError("not_exact_known_route_failure")),
          patch.object(rr, "command") as cmd):
        assert rr.run(tmp_path / "receipt.json") == 78
    cmd.assert_not_called()
    assert json.loads((tmp_path / "receipt.json").read_text())["lease_released"] is False


def test_workflow_single_explicit_request_global_lock():
    text = (ROOT / ".github/workflows/ghcr-api-route-reconcile-dev.yml").read_text()
    assert "ops/ghcr-api-route-reconcile-request.json" in text
    assert "janus-dev-runtime-writers" in text
    assert "workflow_dispatch:" not in text
    assert "cancel-in-progress: false" in text
    assert "ghcr_api_route_reconcile.py" in text
