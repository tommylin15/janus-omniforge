"""Official EOD market credit figures must remain money-based and dated."""
from datetime import date, timedelta
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient

from services.api.app import create_app
from services.api import market_leverage_flow as credit


def margin_payload(day, *, current="587871180", previous="591897687"):
    return {
        "stat": "OK", "date": day.strftime("%Y%m%d"),
        "fields": ["項目", "買進", "賣出", "現金(券)償還", "前日餘額", "今日餘額"],
        "data": [
            ["融資(交易單位)", "5", "2", "0", "100", "103"],
            ["融券(交易單位)", "5", "2", "0", "100", "103"],
            ["融資金額(仟元)", "10", "20", "4", previous, current],
        ],
    }


def institutional_payload(day, *, factor=1):
    return {
        "stat": "OK", "date": f"{day.year - 1911:03d}{day.month:02d}{day.day:02d}",
        "fields": ["單位名稱", "買進金額", "賣出金額", "買賣超金額"],
        "data": [
            ["自營商(自行買賣)", "", "", str(40 * factor)],
            ["自營商(避險)", "", "", str(-10 * factor)],
            ["投信", "", "", str(200 * factor)],
            ["外資及陸資(不含外資自營商)", "", "", str(-500 * factor)],
            ["合計", "", "", str(-270 * factor)],
        ],
    }


def test_margin_uses_thousand_twd_money_balance_not_shares():
    day = date(2026, 11, 4)
    row = credit.parse_margin(margin_payload(day), day)
    assert row["balance_thousand_twd"] == "587871180"
    assert row["change_thousand_twd"] == "-4026507"
    assert credit.parse_margin(margin_payload(day), day - timedelta(days=1)) is None
    assert credit.parse_margin({"stat": "查無資料"}, day) is None


def test_institutional_sums_dealer_legs_but_not_shares_or_totals():
    day = date(2026, 11, 4)
    row = credit.parse_institutional(institutional_payload(day), day)
    assert row == {"foreign": "-500", "trust": "200", "dealer": "30"}
    assert credit.parse_institutional({"stat": "OK", "date": "20261104",
                                       "fields": ["單位名稱", "買賣超股數"],
                                       "data": [["投信", "8000"]]}, day) is None


def test_collect_history_is_bounded_to_ten_real_weekdays_and_daily_deltas():
    today = date(2026, 11, 5)
    seen = []

    def fetch(url):
        seen.append(url)
        parts = urlsplit(url)
        q = parse_qs(parts.query)
        raw = (q.get("date") or q.get("dayDate"))[0]
        day = date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
        if "MI_MARGN" in parts.path:
            return margin_payload(day, current=str(100000000 + day.day * 100000),
                                  previous="100000000")
        return institutional_payload(day, factor=day.day)

    result = credit.collect_market_leverage_flow(today, fetcher=fetch)
    margin = result["margin"]
    assert result["scope"] == "TWSE_listed_only"
    assert result["not_intraday"] is True
    assert margin["status"] == "available"
    assert len(margin["history"]) == 10
    assert margin["history"][-1]["date"] == "2026-11-05"
    assert margin["history"][-1]["change_thousand_twd"] == "500000"
    assert len(seen) <= 23
    flows = result["institutional"]
    assert flows["status"] == "available"
    assert flows["as_of"] == "2026-11-05"
    assert flows["previous_as_of"] == "2026-11-04"
    items = {i["investor_type"]: i for i in flows["items"]}
    assert items["foreign"]["net_twd"] == "-2500"
    assert items["foreign"]["previous_net_twd"] == "-2000"
    assert items["foreign"]["delta_twd"] == "-500"
    assert items["dealer"]["net_twd"] == "150"


def test_source_failure_does_not_fabricate_daily_data():
    def blocked(_url):
        raise TimeoutError("source unreachable")

    result = credit.collect_market_leverage_flow(date(2026, 11, 5), fetcher=blocked)
    assert result["margin"]["history"] == []
    assert result["margin"]["status"] == "missing"
    assert result["institutional"]["status"] == "missing"
    assert all(row["net_twd"] is None for row in result["institutional"]["items"])


def test_public_endpoint_independent_of_owner_and_market_home(monkeypatch):
    expected = {"source": "twse_official_eod", "scope": "TWSE_listed_only",
                "not_intraday": True, "margin": {"status": "missing", "history": []},
                "institutional": {"status": "missing", "items": []}}
    monkeypatch.setattr(credit, "cached_market_leverage_flow", lambda: expected)
    app = TestClient(create_app(object(), object()))
    response = app.get("/api/v1/public/market-leverage-flow")
    assert response.status_code == 200
    assert response.json() == expected
