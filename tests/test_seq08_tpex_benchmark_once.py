"""Approval/identity tests for single existing Dev TPEx benchmark fill."""
import importlib.util
from pathlib import Path
import pytest
p=Path(__file__).resolve().parents[1]/"scripts/gcp/seq08_tpex_benchmark_once.py"
spec=importlib.util.spec_from_file_location("seq08_tpex_once",p)
import sys
sys.path.insert(0,str(p.parent))
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def valid():
    return {"intent":"seq08-official-tpex-price-benchmark-only",
            "approved":True,"apply":True,"scope":"existing-dev-ingestion-one-job",
            "months":["2026-09","2026-10"],"date_start":"2026-09-01",
            "date_end":"2026-10-22","max_runs":1,
            "new_resources_allowed":False,"owner_mutation_allowed":False,
            "job_template_mutation_allowed":False,"scheduler_mutation_allowed":False,
            "retraining_allowed":False,"source_sha":"a"*40,
            "release_run":"40300000000","jobs_run":"40300000001"}
def test_bounded_approval():
    module.approved(valid())
    for item,val in (("apply",False),("date_end","2026-10-26"),
                     ("months",["2026-01","2026-12"]),
                     ("owner_mutation_allowed",True),
                     ("job_template_mutation_allowed",True),
                     ("source_sha","main"),("max_runs",2)):
        with pytest.raises(ValueError,match="bounded_request_invalid"):
            module.approved(dict(valid(),**{item:val}))

def test_exact_snapshot_metadata_without_fake_core(monkeypatch):
    import json
    from unittest.mock import Mock
    proof={"execution_id":"12345678-1234-1234-1234-123456789abc",
           "core_snapshot_uri":"gs://"+module.CORE_BUCKET+"/executions/12345678-1234-1234-1234-123456789abc/core-snapshot.json",
           "core_snapshot_id":"sha256:"+"c"*64,
           "months":{"2026-09":{"official_sessions":20},
                     "2026-10":{"official_sessions":15}},
           "market_stock_ohlcv_writes":0}
    raw={"execution_id":proof["execution_id"],
         "snapshot_id":proof["core_snapshot_id"],
         "analysis_as_of":"2026-10-26",
         "iceberg_tables":{"core.benchmark_v1":{"snapshot_id":123}}}
    monkeypatch.setattr(module,"command",lambda args:json.dumps(raw))
    assert module.snapshot(proof)["core_snapshot_id"]==proof["core_snapshot_id"]
    bad=dict(proof,market_stock_ohlcv_writes=1)
    with pytest.raises(ValueError,match="new_core_fence_invalid"):
        module.snapshot(bad)
