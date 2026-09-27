"""Contract checks for official one-request market volume adapters."""
from datetime import date, datetime, timezone
from http.client import IncompleteRead
import json

import pytest

from ingestion_core.adapters import CollectionRequest
from ingestion_core import sources
from ingestion_core.sources import (tpex_market_volume_adapter,
                                    twse_company_profile_adapter,
                                    twse_market_volume_adapter)
from packages.provenance import Provenance, content_hash


def test_twse_market_batch_parses_date_specific_bulk_response():
    fields = ["證券代號", "證券名稱", "成交股數", "成交筆數", "成交金額", "開盤價", "最高價", "最低價", "收盤價"]
    rows = [[str(code), f"公司{code}", "1,000", "25", "10,000", "10", "11", "9", "10"]
            for code in range(1000, 1500)]
    rows.append(["0050", "ETF", "9,999", "25", "9,999", "10", "11", "9", "10"])
    raw = json.dumps({"date": "20260924", "tables": [{"fields": fields, "data": rows}]}).encode()
    urls = []
    adapter = twse_market_volume_adapter(lambda url: urls.append(url) or raw)
    request = CollectionRequest("execution", "trace", "twse", "market-volume", "TWSE",
                                ("2330",), date(2026, 9, 24), date(2026, 9, 24), 30)
    response = adapter.fetch(request)
    assert "date=20260924" in urls[0]
    assert len(response.rows) == 500
    assert response.raw_payload == raw
    assert response.rows[0]["volume_shares"] == 1000
    assert all(row["symbol"] != "0050" for row in response.rows)
    with pytest.raises(ValueError, match="requested trading date"):
        twse_market_volume_adapter(lambda _: raw.replace(b"20260924", b"20260923")).fetch(request)


def test_tpex_market_batch_reads_mainboard_table_from_bulk_response():
    fields = ["代號", "名稱", "收盤", "漲跌", "開盤", "最高", "最低", "均價", "成交股數", "成交金額(元)"]
    rows = [[str(code), f"公司{code}", "10", "0", "10", "11", "9", "10", "1,000", "10,000"]
            for code in range(1000, 1500)]
    rows.append(["0050", "ETF", "10", "0", "10", "11", "9", "10", "9,999", "9,999"])
    raw = json.dumps({"date": "20260924", "tables": [
        {"title": "上櫃股票行情", "fields": fields, "data": rows},
        {"title": "管理股票", "fields": fields, "data": []},
    ]}, ensure_ascii=False).encode()
    urls = []
    adapter = tpex_market_volume_adapter(lambda url: urls.append(url) or raw)
    request = CollectionRequest("execution", "trace", "tpex", "market-volume", "TPEX",
                                (), date(2026, 9, 24), date(2026, 9, 24), 30)
    response = adapter.fetch(request)
    assert "date=2026%2F09%2F24" in urls[0]
    assert len(response.rows) == 500
    assert response.rows[0]["stock_name"] == "公司1000"
    assert response.rows[0]["trade_date"] == "2026-09-24"
    assert all(row["symbol"] != "0050" for row in response.rows)


def test_market_input_datasets_are_allowed_in_provenance():
    observed_at = datetime(2026, 9, 24, tzinfo=timezone.utc)
    for dataset_id in ("stock-profile", "market-volume"):
        provenance = Provenance(
            provenance_id=f"test-{dataset_id}", source_id="twse",
            source_url="https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date=20260924",
            dataset_id=dataset_id, observed_at=observed_at, published_at=None,
            fetched_at=observed_at, content_hash=content_hash(b"{}"),
        )
        assert "?" not in provenance.source_url


def test_company_profile_retains_official_names_and_excludes_nonstock_codes():
    records = [{"公司代號": str(code), "公司簡稱": f"公司{code}"} for code in range(1000, 1500)]
    records.append({"公司代號": "0050", "公司簡稱": "ETF"})
    request = CollectionRequest("execution", "trace", "twse", "stock-profile", "TWSE",
                                (), date(2026, 9, 24), date(2026, 9, 24), 30)
    response = twse_company_profile_adapter(lambda _: json.dumps(records).encode()).fetch(request)
    assert len(response.rows) == 500
    assert response.rows[0]["stock_name"] == "公司1000"
    assert all(row["symbol"] != "0050" for row in response.rows)


def test_exchange_http_retries_once_after_truncated_response(monkeypatch):
    calls = 0

    class Response:
        def __init__(self, truncated):
            self.truncated = truncated

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self):
            if self.truncated:
                raise IncompleteRead(b"partial", 10)
            return b"complete"

    def fake_urlopen(request, timeout):
        nonlocal calls
        calls += 1
        return Response(calls == 1)

    monkeypatch.setattr(sources, "urlopen", fake_urlopen)
    assert sources.ExchangeOhlcvAdapter._https("https://example.com/data") == b"complete"
    assert calls == 2
