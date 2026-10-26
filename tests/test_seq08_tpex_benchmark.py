"""SEQ08 TPEx official benchmark: no synthetic prices or wrong index kind."""
import json
from datetime import date
import pytest
from ingestion_core.tpex_benchmark import parse_tpex_month, endpoint, BENCHMARK

def fixture(*rows):
    return json.dumps({"stat": "ok", "tables": [
        {"fields": ["日期", "開市", "最高", "最低", "收市"],
         "data": [list(row) for row in rows]}]}, ensure_ascii=False).encode()

def test_official_tpex_index_price_and_roc_calendar():
    raw = fixture(("115/09/24", "200", "211", "199", "210"),
                  ("115/09/23", "198", "206", "197", "201"))
    values = parse_tpex_month(raw, "2026-09")
    assert [row["trade_date"] for row in values] == ["2026-09-23", "2026-09-24"]
    assert all(row["benchmark_id"] == BENCHMARK and row["index_kind"] == "price"
               and row["return_percent"] is None for row in values)
    assert values[0]["close"] == "201.0"
    assert "date=2026%2F09%2F01" in endpoint("2026-09")

def test_fixture_dict_rows_support_and_upperbound():
    raw = json.dumps({"stat":"OK","data":[
        {"日期":"115/10/22","開市":"200","最高":"212","最低":"199","收市":"211"},
        {"日期":"115/10/27","開市":"200","最高":"212","最低":"199","收市":"211"}]},
        ensure_ascii=False).encode()
    rows=parse_tpex_month(raw,"2026-10",through=date(2026,10,22))
    assert len(rows)==1 and rows[0]["trade_date"]=="2026-10-22"

@pytest.mark.parametrize("bad",[
    fixture(("115/09/23", "200", "211", "199", "0")),
    fixture(("115/09/23", "200", "199", "199", "210")),
    fixture(("115/08/23", "200", "211", "199", "210")),
    json.dumps({"stat":"NOT OK","data":[]}).encode(),
    json.dumps({"stat":"OK","data":[]}).encode(),
])
def test_bad_benchmark_rejected_not_imputed(bad):
    with pytest.raises((ValueError,TypeError)):
        parse_tpex_month(bad,"2026-09")

def test_no_taiex_or_stock_price_surrogate():
    import inspect
    from ingestion_core import tpex_benchmark as mod
    content=inspect.getsource(mod.run_bounded_tpex_benchmark)
    assert 'dataset_id="benchmark"' in content
    assert 'dataset_id="ohlcv"' not in content
    assert '"source_id": SOURCE' in content
    assert 'core_snapshot_uri' in content
