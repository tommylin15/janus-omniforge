"""Read-only SEQ-08 live artifact acceptance: identity, source and missing-state gates."""
import importlib.util
import json
from pathlib import Path
import pytest

SOURCE=Path(__file__).resolve().parents[1] / "scripts/gcp/seq08_product_readback.py"
spec=importlib.util.spec_from_file_location("seq08_product_readback", SOURCE)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_fixed_one_run_readonly_request():
    correct={
        "intent":"seq08-exact-real-mart-product-readonly",
        "source_sha":module.SOURCE,"successful_mart_run":module.RUN,
        "symbols":["2330","2882"],"diagnostic_attempt":8,"read_only":True,"no_gcp_mutation":True,
        "no_owner_mutation":True,"no_new_resources":True
    }
    module.require_request(correct)
    for key,value in (("read_only",False),("no_owner_mutation",False),
                      ("successful_mart_run","0000"),("symbols",["9999"]),
                      ("source_sha","0"*40)):
        wrong={**correct,key:value}
        with pytest.raises(ValueError,match="readback_request_scope_mismatch"):
            module.require_request(wrong)


def test_log_match_must_be_one_deep_coverage():
    a=lambda eid,op="deep-coverage": {"textPayload":json.dumps({
        "component":"intelligence-mart","operation":op,"execution_id":eid,
        "analysis_as_of":"2026-10-25"})}
    x="12345678-1234-1234-1234-123456789abc"
    assert module.parse_execution_id([a(x),a(x),a(x,"postgres-smoke")],
        "janus-intelligence-mart-aaabc")==x
    with pytest.raises(ValueError,match="identity_unknown"):
        module.parse_execution_id([a(x,"postgres-smoke")],
            "janus-intelligence-mart-aaabc")
    with pytest.raises(ValueError,match="identity_unknown"):
        module.parse_execution_id([a(x),a("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")],
            "janus-intelligence-mart-aaabc")


def test_live_artifact_status_and_no_owner_symbol_leak(monkeypatch):
    import hashlib
    from collections import OrderedDict
    eid="12345678-1234-1234-1234-123456789abc"
    root=f"executions/{eid}/"
    roles={
        "quant":{"status":"FEATURE_INCOMPATIBLE_OR_MISSING","prediction":None,
                 "missing_features":["ret20_market_rank"]},
        "risk":{"status":"ACTIVE_PREDICTED","prediction":0.12},
        "fundamental":{"status":"ABSTAINED_X_ONLY","prediction":None},
        "valuation":{"status":"ACTIVE_PREDICTED","prediction":{"log_pe":2,"log_pb":1}}
    }
    input_doc={"output_hash":"sha256:input","core_snapshot_id":module.EXPECTED_CORE_SNAPSHOT_ID}
    serving={"artifact_kind":"mart_four_model_serving_v1","owner_fields_exposed":False,
             "analysis_as_of":"2026-10-25","core_snapshot_id":module.EXPECTED_CORE_SNAPSHOT_ID,
             "source_analyst_input_hash":"sha256:input",
             "rows":[{"symbol":"2330","roles":roles},{"symbol":"OTHER_OWNER_SYMBOL","roles":roles}]}
    def hash_of(value):
        return "sha256:"+hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
    manifest={"execution_id":eid,"analysis_as_of":"2026-10-25","core_snapshot_id":module.EXPECTED_CORE_SNAPSHOT_ID,
        "four_model_serving":{"artifact_uri":"gs://"+module.BUCKET+"/"+root+"four-model-serving.json",
                              "artifact_hash":hash_of(serving)},
        "analyst_inputs":{"artifact_uri":"gs://"+module.BUCKET+"/"+root+"analyst-inputs.json",
                          "artifact_hash":hash_of(input_doc)}}
    db={root+"specialist-manifest.json":manifest,root+"four-model-serving.json":serving,
        root+"analyst-inputs.json":input_doc}
    monkeypatch.setattr(module,"object_json",lambda path:(db[path],hash_of(db[path])))
    got=module.readback(eid,"janus-intelligence-mart-aaaaa")
    assert got["status"]=="READBACK_PASS"
    assert got["model_status_counts"]["risk"]=={"ACTIVE_PREDICTED":2}
    assert got["samples"]["2330"]["roles"]["fundamental"]["status"]=="ABSTAINED_X_ONLY"
    assert got["samples"]["2882"]=={"present":False}
    assert "OTHER_OWNER_SYMBOL" not in json.dumps(got)
    assert got["pg_product_readback"]=="NOT_VERIFIED"
    assert got["input_diagnostics"]["latest_trade_dates"] == {}
    assert got["input_diagnostics"]["missing_features"]["quant"] == {}


def test_actual_gcs_only_screening_gate_and_percentile_proof(monkeypatch):
    import hashlib
    eid = "12345678-1234-1234-1234-123456789abc"
    identity_hash = "sha256:" + "a"*64
    path = "screening/" + "a"*64 + ".json"
    identity = {"analysis_as_of": "2026-10-26", "core_snapshot_id": module.EXPECTED_CORE_SNAPSHOT_ID}
    rank = {"value": 0.72, "market": "twse", "cohort_size": 100,
            "analysis_as_of": identity["analysis_as_of"],
            "core_snapshot_id": identity["core_snapshot_id"],
            "source_trade_date": "2026-10-22",
            "source": "full_market_core_same_day_pct_rank"}
    artifact = {"artifact_kind": "mart_market_screening_v1",
                "identity_hash": identity_hash, "identity": identity,
                "rows": [
                    {"symbol": "2330", "latest_trade_date": "2026-10-22",
                     "seq08_quant_rank_gate": "ranked", "seq08_quant_rank": rank},
                    {"symbol": "2882", "latest_trade_date": "2026-10-22",
                     "seq08_quant_rank_gate": "ret20_input_missing", "seq08_quant_rank": None}],
                "input_telemetry": {"seq08_quant_rank": {
                    "ranked_rows": 1, "gate_counts": {
                        "ranked": 1, "ret20_input_missing": 1}}}}
    def digest(obj):
        return "sha256:" + hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()
    manifest = {"execution_id": eid, "identity_hash": identity_hash,
                "screening": {"artifact_uri": "gs://" + module.BUCKET + "/" + path,
                              "artifact_hash": digest(artifact)}}
    backing = {"executions/" + eid + "/screening-manifest.json": manifest,
               path: artifact}
    monkeypatch.setattr(module, "object_json", lambda p: (backing[p], digest(backing[p])))
    result = module.readback_market_screening(eid, "janus-intelligence-mart-aaabc")
    assert result["ranked_rows"] == 1
    assert result["status"] == "RANK_NOT_READY_PARTIAL"
    assert result["samples"]["2330"]["rank_valid"] is True
    assert result["samples"]["2882"]["rank_valid"] is False
    assert result["product_projection"] is True
    assert result["pg_product_readback"] == "PENDING_EXACT_SELECT"
    artifact["input_telemetry"]["seq08_quant_rank"]["ranked_rows"] = 2
    # First validate the immutable hash boundary, then deliberately update
    # the fixture manifest to isolate the second, gate-accounting guard.
    with pytest.raises(ValueError, match="hash_or_identity_invalid"):
        module.readback_market_screening(eid, "janus-intelligence-mart-aaabc")
    manifest["screening"]["artifact_hash"] = digest(artifact)
    with pytest.raises(ValueError, match="count_mismatch"):
        module.readback_market_screening(eid, "janus-intelligence-mart-aaabc")


def test_market_screening_cloud_logging_operation_scope():
    eid="12345678-1234-1234-1234-123456789abc"
    log={"textPayload":json.dumps({"component":"intelligence-mart",
                                   "operation":"market-screening","execution_id":eid})}
    assert module.parse_execution_id([log],"janus-intelligence-mart-aaabc",
                                     operation="market-screening")==eid
    with pytest.raises(ValueError):
        module.parse_execution_id([log],"janus-intelligence-mart-aaabc")


def test_new_core_gcs_fallback_proves_percentile_not_pg(monkeypatch):
    from types import SimpleNamespace
    import hashlib
    base=module.BUCKET
    uri="gs://"+base+"/screening/"+"a"*64+".json"
    out=("  750 2026-10-26T14:27:00Z "+uri+"\nTOTAL: 1 objects\n").encode()
    monkeypatch.setattr(module,"run",lambda cmd,timeout=75:SimpleNamespace(returncode=0,stdout=out))
    identity={"analysis_as_of":"2026-10-26","core_snapshot_id":module.EXPECTED_CORE_SNAPSHOT_ID,
              "feature_version":"market-screening-v5-exchange-closure-filter"}
    def hashof(value):
        return "sha256:"+hashlib.sha256(
            json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str).encode()
        ).hexdigest()
    rows=[]
    for i in range(100):
        symbol="2330" if i==0 else str(3000+i)
        rank={"value":(i+1)/100,"market":"twse","cohort_size":100,
              "source_trade_date":"2026-10-22","core_snapshot_id":module.EXPECTED_CORE_SNAPSHOT_ID,
              "analysis_as_of":"2026-10-26","source":"full_market_core_same_day_pct_rank"}
        rows.append({"symbol":symbol,"latest_trade_date":"2026-10-22",
                     "seq08_quant_rank":rank,"seq08_quant_rank_gate":"ranked"})
    artifact={"identity":identity,"identity_hash":hashof(identity),"rows":rows,
              "artifact_kind":"mart_market_screening_v1",
              "input_telemetry":{"seq08_quant_rank":{"ranked_rows":100,"gate_counts":{"ranked":100}}}}
    artifact["output_hash"]=hashof(artifact)
    monkeypatch.setattr(module,"object_json",lambda path:(artifact,"sha256:artifact"))
    proof=module.read_new_core_from_bounded_prefix()
    assert proof["status"]=="RANK_PARTIAL"
    assert proof["ranked_by_market"]=={"twse":100}
    assert proof["pg_product_readback"]=="NOT_VERIFIED"
    artifact["rows"][0]["seq08_quant_rank"]["value"]=1.1
    with pytest.raises(ValueError,match="digest_mismatch"):
        module.read_new_core_from_bounded_prefix()

def test_bounded_fallback_never_claims_exact_execution():
    import inspect
    code=inspect.getsource(module.read_new_core_from_bounded_prefix)
    assert "len(lines)>251" in code
    assert "len(candidates)>24" in code
    assert "BOUNDED_NEW_CORE_GCS_NOT_EXACT_MART_EXECUTION" in code
    assert "pg_product_readback" in code


def test_deep_coverage_requires_exact_new_core_snapshot():
    import inspect
    source=inspect.getsource(module.readback)
    assert "EXPECTED_CORE_SNAPSHOT_ID" in source
    main_source=inspect.getsource(module.main)
    assert 'operation="deep-coverage"' in main_source
    assert "result = readback(execution_id, cloud_execution)" in main_source
