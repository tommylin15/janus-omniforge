"""SEQ-08: native five-head model-serving, no Risk8 or deterministic fallback."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "jobs/intelligence-mart"))
from intelligence_mart.seq08_native_serving import (
    ACTIVE_NAME, HEADS, Session, expected_pointer, validate_pointer,
)
from intelligence_mart.analyst_inputs import (
    QUANT15, RISK12, FUND15, SEQ08_FEATURE_VERSION,
)
from intelligence_mart.valuation_ml_mapping import FEATURES as VAL5, VERSION as VAL_VERSION
from intelligence_mart.four_model_serving import canonical, fingerprint
from intelligence_mart.market_screening import rank_features


class Store:
    def __init__(self):
        self.data = {}
        self.created = []
    def read(self, name):
        if name not in self.data:
            raise FileNotFoundError(name)
        return self.data[name]
    def create(self, name, raw, mime):
        assert mime == "application/json"
        self.created.append(name)
        if name in self.data:
            return False
        self.data[name] = raw
        return True


class FakeNativeSession(Session):
    def _model(self, head):
        return head


def base_rows(complete=True, abstain=False):
    roles = {}
    for role, order in [
        ("quant", QUANT15), ("risk", RISK12),
        ("fundamental", FUND15), ("valuation", VAL5),
    ]:
        values = {k: 0.42 for k in order}
        if role == "quant":
            values["ret20_market_rank"] = 0.72 if complete else None
        version = VAL_VERSION if role == "valuation" else SEQ08_FEATURE_VERSION[role]
        missing = [] if complete or role != "quant" else ["ret20_market_rank"]
        roles[role] = {
            "feature_order": list(order), "values": values,
            "feature_version": version, "input_as_of": "2026-10-23",
            "feature_ready": not missing, "missing_features": missing,
        }
    roles["fundamental"]["abstention_reasons"] = ["LOW_BASE_TWD"] if abstain else []
    artifact = {"analysis_as_of": "2026-10-23", "core_snapshot_id": "core-123",
                "rows": [{"symbol":"2330","roles":roles}]}
    artifact["output_hash"] = fingerprint(artifact)
    return artifact


def fake_predict(model, vectors, order):
    if order == list(QUANT15):
        return [0.73 for _ in vectors]
    if order == list(RISK12):
        return [-0.4 for _ in vectors]
    if order == list(FUND15):
        return [12.5 for _ in vectors]
    if order == list(VAL5):
        return [1.6 for _ in vectors]
    raise AssertionError("unknown model head")


def test_missing_registry_returns_all_four_missing_with_no_legacy_risk():
    got = Session(Store(), "mart").run(base_rows())
    roles = got["rows"][0]["roles"]
    assert len(roles) == 4
    assert all(r["status"]=="MISSING_OR_INACTIVE_ARTIFACT" and r["prediction"] is None
               for r in roles.values())
    assert got["owner_fields_exposed"] is False


def test_five_heads_predictions_nonnegative_rms_double_valuation_and_cache():
    store=Store()
    store.data[ACTIVE_NAME] = canonical(expected_pointer())
    first=FakeNativeSession(store,"mart",loader=lambda raw,order:object(),
                  predictor=fake_predict).run(base_rows())
    role=first["rows"][0]["roles"]
    assert role["quant"]["prediction"] == 0.73
    assert role["risk"]["prediction"] == 0.
    assert role["fundamental"]["prediction"] == 12.5
    assert role["valuation"]["prediction"] == {"log_pe":1.6,"log_pb":1.6}
    assert all(r["status"]=="ACTIVE_PREDICTED" for r in role.values())
    assert len(store.created) == 5
    second=FakeNativeSession(store,"mart",loader=lambda *_:pytest.fail("cache missed"),
                   predictor=lambda *_:pytest.fail("cache missed")).run(base_rows())
    assert all(r["status"]=="ACTIVE_CACHED" for r in second["rows"][0]["roles"].values())
    assert len(second["rows"]) == 1 and second["rows"][0]["symbol"] == "2330"


def test_rank_missing_does_not_generate_quant_probability_and_fund_policy_abstains():
    store=Store()
    store.data[ACTIVE_NAME]=canonical(expected_pointer())
    result=FakeNativeSession(store,"mart",loader=lambda *_:None,
                   predictor=fake_predict).run(base_rows(complete=False,abstain=True))
    status=result["rows"][0]["roles"]
    assert status["quant"]["prediction"] is None
    assert status["quant"]["status"]=="FEATURE_INCOMPATIBLE_OR_MISSING"
    assert status["fundamental"]["status"]=="ABSTAINED_X_ONLY"
    assert status["fundamental"]["prediction"] is None
    assert status["risk"]["status"]=="ACTIVE_PREDICTED"


def test_registry_requires_all_five_exact_model_shas():
    ptr=expected_pointer()
    assert validate_pointer(ptr) == ptr
    ptr["heads"]["risk"]["model_sha256"] = "0"*64
    with pytest.raises(ValueError,match="differs"):
        validate_pointer(ptr)


def test_screening_rank_is_market_wide_average_ties_not_target_only():
    rows=[]
    for n in range(101):
        rows.append({
            "symbol":str(n), "latest_trade_date":"2026-10-22",
            "metrics":{"return_20d_percent":n,"relative_strength_20d_percent":None,
                       "turnover_20d_mean_twd":None},
            "screening_score":None,
            "seq08_quant_rank_input":{
                "market":"twse","ret20":float(n//2),
                "core_snapshot_id":"123","analysis_as_of":"2026-10-26"},
        })
    result=rank_features(rows,"2026-10-26")
    assert result[0]["seq08_quant_rank"]["cohort_size"]==101
    assert result[0]["seq08_quant_rank"]["value"]==pytest.approx(1.5/101)
    assert result[-1]["seq08_quant_rank"]["value"]==1.
    assert "seq08_quant_rank_input" not in result[0]
