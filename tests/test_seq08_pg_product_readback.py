"""Bounded read-only PostgreSQL acceptance: never enumerate Owner symbols."""
from pathlib import Path
from unittest.mock import patch
import importlib.util, json
import pytest

SOURCE=Path(__file__).resolve().parents[1]/"scripts/gcp/seq08_pg_product_readback.py"
spec=importlib.util.spec_from_file_location("seq08_pg_product_readback",SOURCE)
# The operator uses the existing scripts/gcp helper; tests never call cloud.
import sys
sys.path.insert(0,str(SOURCE.parent))
probe=importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def test_exact_one_dev_execution_scope(tmp_path,monkeypatch):
    request={"intent":"seq08-one-existing-dev-pg-readonly","approved":True,
        "scope":"existing-dev-mart-one-select-execution",
        "no_pg_mutation":True,"no_owner_mutation":True,
        "no_new_resources":True,"one_job_execution":True,
        "source_sha":"a"*40,"mart_execution_id":"12345678-1234-1234-1234-123456789abc"}
    monkeypatch.setattr(probe.Path,"read_text",lambda *_:json.dumps(request))
    assert probe.request()==request
    for field,value in (("approved",False),("no_pg_mutation",False),
                        ("no_owner_mutation",False),("one_job_execution",False),
                        ("source_sha","x"*40),("mart_execution_id","not-a-uuid")):
        variant=dict(request,**{field:value})
        monkeypatch.setattr(probe.Path,"read_text",lambda *_,v=variant:json.dumps(v))
        with pytest.raises(ValueError,match="request_invalid"):
            probe.request()


def test_exact_cloud_run_log_identity():
    x="12345678-1234-1234-1234-123456789abc"
    payload={"status":"PG_SELECT_READBACK_PASS","mart_execution_id":x,
             "rows":8,"private_symbols_exposed":False}
    logs=[{"textPayload":"unrelated log"},
          {"textPayload":"SEQ08_PG_PROOF:"+json.dumps(payload)}]
    assert probe.parse_log(logs,x)["rows"]==8
    with pytest.raises(ValueError):
        probe.parse_log(logs,"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    with pytest.raises(ValueError):
        probe.parse_log(logs+logs[1:],x)
    assert "SELECT" in probe.PROBE and "READ ONLY" in probe.PROBE
    assert "positions" not in probe.PROBE


def test_public_two_stock_inline_probe_compiles_and_is_cache_only():
    compile(probe.PROBE,"<dev_mart_sql_and_public_probe>","exec")
    assert "independent_of_owner_portfolio" in probe.PROBE
    assert '("2330","2882")' in probe.PROBE
    assert "gcs_persistent_writes" in probe.PROBE
    assert "class LocalOnlyCache" in probe.PROBE
    assert "self.backing.create" not in probe.PROBE
    assert "SET TRANSACTION READ ONLY" in probe.PROBE
    assert "jsonb_typeof(payload_json->'seq08_quant_rank')='object'" in probe.PROBE
    assert "json_null_rank_count" in probe.PROBE
    assert "public_market_rank_input_gates" in probe.PROBE
    assert "rank=False" in probe.PROBE
    assert "accepted_stock_sessions" in probe.PROBE
    assert "accepted_all_benchmark_sessions" in probe.PROBE
