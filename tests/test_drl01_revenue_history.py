"""DRL-01 existing-MOPS bulk month repair: scope, embedded job syntax, unit/PIT."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from ingestion_core.data_supplement import normalise_monthly


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gcp" / "drl01_revenue_history.py"


def _worker_script():
    sys.path.insert(0, str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("drl01_revenue_history", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _request(tmp_path, **changes):
    baseline = {
        "intent": "drl01-existing-mops-monthly-market-archive",
        "approved": True,
        "market": "TWSE",
        "months": ["2026-08", "2026-09"],
        "no_new_provider": True,
        "no_owner_mutation": True,
        "no_job_template_change": True,
    }
    baseline.update(changes)
    target = tmp_path / "request.json"
    target.write_text(json.dumps(baseline))
    return target


def test_month_repair_scope_is_two_unique_approved_exchange_months(tmp_path):
    script = _worker_script()
    assert script.checked(_request(tmp_path))["months"] == ["2026-08", "2026-09"]
    assert script.checked(_request(tmp_path, market="TPEX"))["market"] == "TPEX"
    for change in ({"market": "UNKNOWN"}, {"approved": False},
                   {"months": ["2026-07", "2026-08", "2026-09"]},
                   {"months": ["2026-09", "2026-08"]},
                   {"months": ["2026-08", "2026-08"]},
                   {"months": ["2026-10"]}, {"no_owner_mutation": False},
                   {"no_new_provider": False}):
        with pytest.raises(ValueError):
            script.checked(_request(tmp_path, **change))


def test_inline_existing_cloud_run_probe_compiles():
    script = _worker_script()
    compile(script.PROBE, "drl01-MOPS-revenue-probe", "exec")
    assert "source_is_approved(\"mops\")" in script.PROBE
    assert "stage_results" not in script.PROBE or "mark_core_committed" in script.PROBE
    assert "mark_core_committed" in script.PROBE
    assert 'segment="sii" if req["market"]=="TWSE" else "otc"' in script.PROBE
    assert 'title="上市" if req["market"]=="TWSE" else "上櫃"' in script.PROBE


def test_revenue_archive_months_have_canonical_unit_without_guessing_publication():
    observed = normalise_monthly({
        "code": 200,
        "result": {"yymm": "11509", "companyAbbreviation": "台積電",
                   "data": [["本月", "1,234"]]},
    }, "2330", 2026, 9,
        received_at="2026-10-16T00:00:00+00:00", expected_name="台積電")[0]
    assert observed["value"] == "1234000"
    assert observed["unit"] == "TWD"
    assert observed["published_at"] is None
    assert observed["publication_time_authoritative"] is False
    assert observed["fiscal_month"] == 9
    assert observed["fiscal_period_end"] == "2026-09-30"
    # Bulk projection converts official TWD back to TWD_thousands,
    # same source unit as the existing published monthly_revenue metric.
    from decimal import Decimal
    assert Decimal(observed["value"]) / 1000 == Decimal("1234")
