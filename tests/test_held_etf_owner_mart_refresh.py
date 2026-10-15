from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/gcp/held_etf_owner_mart_refresh.py"


def test_one_owner_live_etf_refresh_fences_ledger_and_image():
    source = SCRIPT.read_text()
    assert 'SOURCE = "536598f2528550fd60c73786597fdf2740860c9e"' in source
    assert 'IMAGE = "ghcr.io/tommylin15/janus-private-pipeline@sha256:' in source
    assert 'SELECT DISTINCT user_id FROM private.current_positions WHERE symbol=%s' in source
    assert 'len(owners) != 1' in source
    assert 'before != after' in source
    assert 'quote["source"] != "tpex_openapi_eod"' in source
    assert 'private_mart_write_lock' in source
    assert 'rollout.fence()' in source and 'rollout.LEASE+["acquire"]' in source
    assert '"--safe-to-release"' in source
    assert '"taskCount":1' in source
    assert "INSERT INTO private.ledger_events" not in source
    assert "DELETE FROM private.ledger_events" not in source


def test_owner_live_request_is_derived_only_and_single_owner():
    data = json.loads((ROOT / "ops/held-etf-owner-live-request.json").read_text())
    assert data["intent"]=="single-owner-official-held-etf-mart"
    assert data["symbol"]=="00697B"
    assert data["source_sha"]=="536598f2528550fd60c73786597fdf2740860c9e"
    assert data["release_run"]=="38691316772"
    assert data["jobs_rollout_run"]=="38692371269"
    assert data["no_ledger_mutation"] is True
    assert data["private_mart_write_only"] is True
    assert data["single_owner_only"] is True
    assert data["no_job_template_mutation"] is True
