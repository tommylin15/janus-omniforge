"""Single integrated P0 contract: owner ledger holdings and public official TPEx EOD."""
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from services.api.intraday_quotes import TAIPEI, value_holdings
from services.api.private_pipeline import owner_price_reader
from services.api.private_recalc_queue import (
    CloudRunPrivateRecalcTrigger, QueuedPrivateRecalculator,
)
from services.api.quote_router import QuoteRouter
from services.api.tpex_quotes import TpexDailyQuotes, parse_tpex_daily_quotes

UTC8 = TAIPEI
NOW = datetime(2026, 10, 12, 15, 25, tzinfo=UTC8)
SEC = {"00719B": {"symbol": "00719B", "market": "TPEX_UNVERIFIED", "enabled": True}}


class QuoteDb:
    def __init__(self):
        self.saved = {}
        self.core = {}
    def last_quotes(self, identities):
        return {s: dict(q) for s, q in self.saved.items() if s in identities}
    def eod_quotes(self, identities):
        return {s: dict(q) for s, q in self.core.items() if s in identities}
    def save_last_quotes(self, quotes):
        self.saved.update(quotes)


class NeverMis:
    def prices(self, identities):
        raise AssertionError("TPEx EOD must never route to TWSE MIS")


def test_public_tpex_eod_strict_source_date_and_unit():
    rows = [
        {"Date": "1151012", "SecuritiesCompanyCode": "00719B",
         "SecuritiesCompanyName": "元大美債1-3", "Close": "31.11"},
        {"Date": "1151012", "SecuritiesCompanyCode": "9999", "Close": "100"},
        {"Date": "1151013", "SecuritiesCompanyCode": "00719B", "Close": "99"},
    ]
    result = parse_tpex_daily_quotes(rows, {"00719B"}, NOW)
    assert list(result) == ["00719B"]
    assert result["00719B"]["price"] == "31.11"
    assert result["00719B"]["price_date"] == "2026-10-12"
    assert result["00719B"]["source"] == "tpex_openapi_eod"
    assert result["00719B"]["quote_at"].startswith("2026-10-12T13:30:")
    assert parse_tpex_daily_quotes([{"Date":"1151012", "SecuritiesCompanyCode":"00719B",
                                    "Close":"NaN"}], {"00719B"}, NOW) == {}
    assert parse_tpex_daily_quotes([{"Date":"1151013", "SecuritiesCompanyCode":"00719B",
                                    "Close":"31"}], {"00719B"}, NOW) == {}


def test_tpex_is_not_an_intraday_quote_and_retains_owner_last_success():
    db = QuoteDb()
    api_calls = []
    def fetch():
        api_calls.append(1)
        return [{"Date": "1151012", "SecuritiesCompanyCode": "00719B",
                 "Close": "31.12"}]
    official = TpexDailyQuotes(fetch=fetch)
    route = QuoteRouter(db, NeverMis(), tpex_source=official)
    assert route.refresh_tpex(SEC, now=datetime(2026,10,12,10,0,tzinfo=UTC8))["updated"] == 0
    assert api_calls == [1]
    assert route.refresh_tpex(SEC, now=NOW)["updated"] == 1
    assert db.saved["00719B"]["source"] == "tpex_openapi_eod"
    q = route.read(SEC, now=NOW)["00719B"]
    assert q["state"] == "eod_final"
    assert q["price_date"] == "2026-10-12"
    assert q["is_final"] is True
    assert q["source"] == "tpex_openapi_eod"
    assert route.refresh_tpex(SEC, now=NOW)["status"] == "fresh"
    assert api_calls == [1, 1]
    position = value_holdings(
        [{"symbol":"00719B", "currency":"TWD", "shares":"30000",
          "average_cost":"31.16"}], {"00719B": q}, NOW)
    row = position["positions"][0]
    assert row["shares"] == "30000"
    assert row["unrealized_pnl"] == str(
        (Decimal("31.12")-Decimal("31.16"))*30000)
    assert position["items"][0]["aggregate_status"] == "available"


def test_closed_symbol_still_shows_shares_and_cost_when_public_quote_unavailable():
    summary = value_holdings(
        [{"symbol":"00719B", "currency":"TWD", "shares":"30000",
          "average_cost":"31.16"}], {}, NOW)
    assert summary["positions"][0]["shares"] == "30000"
    assert summary["positions"][0]["market_price"] is None
    assert summary["items"][0]["aggregate_status"] == "withheld"
    assert summary["items"][0]["unrealized_pnl"] is None


def test_private_mart_accepts_only_persisted_official_tpex_not_mis_or_future():
    db = QuoteDb()
    def core(_symbols, _when):
        return {"2330": (Decimal("100"), date(2026,10,12))}
    db.saved = {
        "00719B": {
            "source": "tpex_openapi_eod", "price": "31.12",
            "quote_at": "2026-10-12T13:30:00+08:00",
        },
        "9999": {
            "source": "twse_mis", "price": "55",
            "quote_at": "2026-10-12T10:00:00+08:00",
        },
    }
    reader = owner_price_reader(db, core)
    result = reader({"2330","00719B","9999"}, date(2026,10,12))
    assert result["2330"][0] == Decimal("100")
    assert result["00719B"] == (Decimal("31.12"), date(2026,10,12))
    assert "9999" not in result
    assert "00719B" not in reader({"00719B"}, date(2026,10,11))


def test_job_dispatch_403_records_specific_missing_override_permission():
    class Response:
        status_code = 403
    class Repository:
        def __init__(self):
            self.failed = None
        def enqueue_recalculation(self, user_id, _source):
            return {"request_id": "req", "status": "QUEUED",
                    "should_dispatch": True}
        def fail_recalculation_dispatch(self, *args):
            self.failed = args

    repo = Repository()
    trigger = CloudRunPrivateRecalcTrigger(
        "existing-dev", "us-central1",
        post=lambda _url, **_kwargs: Response())
    queue = QueuedPrivateRecalculator(repo, lambda: 2, trigger)
    try:
        queue.run_user("owner", "manual")
        assert False, "403 cannot be presented as success"
    except Exception:
        assert repo.failed[1] == "RUN_WITH_OVERRIDES_DENIED"
        assert "權限不足" in repo.failed[2]


def test_pre_handoff_can_initialize_yesterdays_close_but_not_todays_partial_data():
    calls = []
    def fetch():
        calls.append(1)
        return [{'Date': '1151014', 'SecuritiesCompanyCode': '00697B', 'Close': '31.25'},
                {'Date': '1151015', 'SecuritiesCompanyCode': '00719B', 'Close': '32.50'}]
    source = TpexDailyQuotes(fetch=fetch)
    before = datetime(2026,10,15,14,29,tzinfo=UTC8)
    result = source.quotes({'00697B','00719B'}, before)
    assert set(result) == {'00697B'}
    assert result['00697B']['price_date'] == '2026-10-14'
    after = before+timedelta(minutes=1)
    result = source.quotes({'00697B','00719B'}, after)
    assert result['00719B']['price_date'] == '2026-10-15'
    assert calls == [1,1]  # Handoff must fetch again instead of blessing pre-close cached rows.


def test_official_tpex_multiday_payload_chooses_latest_eligible_regardless_of_order():
    from services.api.tpex_quotes import parse_tpex_daily_quotes
    now = datetime(2026, 10, 15, 15, 0, tzinfo=TAIPEI)
    records = [
        {"Date":"1151013","SecuritiesCompanyCode":"00697B","Close":"33.10"},
        {"Date":"1151015","SecuritiesCompanyCode":"00697B","Close":"33.45"},
        {"Date":"1151014","SecuritiesCompanyCode":"00697B","Close":"33.20"},
        {"Date":"1151012","SecuritiesCompanyCode":"00697B","Close":"32.99"},
    ]
    for rows in (records, list(reversed(records))):
        result = parse_tpex_daily_quotes(rows, {"00697B"}, now)["00697B"]
        assert result["price_date"] == "2026-10-15"
        assert result["price"] == "33.45"
    before_handoff = datetime(2026, 10, 15, 14, 29, tzinfo=TAIPEI)
    pending = parse_tpex_daily_quotes(records, {"00697B"}, before_handoff)["00697B"]
    assert pending["price_date"] == "2026-10-14"
    assert pending["price"] == "33.20"


def test_official_tpex_failed_source_is_bounded_and_can_recover(monkeypatch):
    from services.api import tpex_quotes as module
    clock = [100.0]
    monkeypatch.setattr(module, "monotonic", lambda: clock[0])
    calls = []
    def fetch():
        calls.append(clock[0])
        if len(calls) == 1:
            raise ValueError("invalid json from public source")
        return [{"Date":"1151014","SecuritiesCompanyCode":"00697B","Close":"33.20"}]
    source = TpexDailyQuotes(fetch=fetch)
    now = datetime(2026,10,15,15,0,tzinfo=TAIPEI)
    import pytest
    with pytest.raises(ValueError):
        source.quotes({"00697B"},now)
    clock[0] += 20
    with pytest.raises(RuntimeError, match="retry cooldown"):
        source.quotes({"00697B"},now)
    assert calls == [100.0]
    clock[0] += 41
    recovered=source.quotes({"00697B"},now)
    assert len(calls)==2
    assert recovered["00697B"]["price_date"]=="2026-10-14"
    assert recovered["00697B"]["source"]=="tpex_openapi_eod"

def test_multi_date_official_history_is_pit_scoped_and_immutable():
    from services.api.tpex_quotes import parse_tpex_daily_quote_history
    now = datetime(2026, 10, 15, 15, 30, tzinfo=TAIPEI)
    raw = [
        {"Date":"1151014","SecuritiesCompanyCode":"00697B","Close":"33.20"},
        {"Date":"1151015","SecuritiesCompanyCode":"00697B","Close":"33.40"},
        {"Date":"1151013","SecuritiesCompanyCode":"00697B","Close":"33.10"},
    ]
    days = parse_tpex_daily_quote_history(raw, {"00697B"}, now)["00697B"]
    assert [r["price_date"] for r in days] == ["2026-10-13","2026-10-14","2026-10-15"]
    assert all(len(r["record_sha256"])==64 for r in days)
    assert days[1]["source_uri"].startswith("https://www.tpex.org.tw/")
    class Historical(QuoteDb):
        def __init__(self):
            super().__init__()
            self.history_rows = {}
        def stock_identities(self, symbols):
            return {s:{"market":"TPEX","enabled":True} for s in symbols}
        def save_official_eod_quotes(self, history):
            for sym, records in history.items():
                for r in records:
                    key = (sym,r["price_date"])
                    assert key not in self.history_rows or self.history_rows[key] == r
                    self.history_rows[key] = r
        def official_eod_quotes(self, symbols, as_of):
            return {s: max((r for (sym,_),r in self.history_rows.items()
                            if sym==s and r["price_date"]<=as_of.isoformat()),
                           key=lambda r:r["price_date"])
                    for s in symbols if any(sym==s and day<=as_of.isoformat()
                                             for sym,day in self.history_rows)}
    db=Historical()
    db.saved["00697B"]={"source":"tpex_openapi_eod","price":"33.40",
                           "quote_at":"2026-10-15T13:30:00+08:00"}
    official=TpexDailyQuotes(fetch=lambda:raw)
    router=QuoteRouter(db,None,tpex_source=official)
    assert router.refresh_tpex({"00697B":{"market":"TPEX","enabled":True}},now=now,as_of=date(2026,10,14))["updated"]==1
    assert len(db.history_rows)==3
    def core(_symbols,_when):return {}
    from unittest.mock import patch
    with patch("services.api.tpex_quotes.TpexDailyQuotes",return_value=official):
        reader=owner_price_reader(db,core)
        assert reader({"00697B"}, date(2026,10,14))["00697B"]==(Decimal("33.20"),date(2026,10,14))
        assert reader({"00697B"}, date(2026,10,13))["00697B"]==(Decimal("33.10"),date(2026,10,13))
        assert "00697B" not in reader({"00697B"}, date(2026,10,12))


def test_dated_legacy_official_fallback_validates_day(monkeypatch):
    import json
    from services.api import tpex_quotes as tp
    calls=[]
    class Response:
        def __init__(self,data):self.data=data
        def __enter__(self):return self
        def __exit__(self,*_):pass
        def read(self,_):return self.data
    def urlopen(request,timeout):
        calls.append(request.full_url)
        if len(calls)==1:return Response(b"<html>WAF</html>")
        return Response(json.dumps({"date":"115/10/14","tables":[
            {"fields":["代號","收盤"],"data":[["00697B","33.20"]]}]}).encode())
    monkeypatch.setattr(tp,"urlopen",urlopen)
    monkeypatch.setattr(tp,"datetime",type("Clock",(datetime,),{"now":classmethod(lambda _cls,tz:datetime(2026,10,15,10,0,tzinfo=tz))}))
    source=tp.TpexDailyQuotes()
    result=source.quotes({"00697B"},datetime(2026,10,15,10,0,tzinfo=TAIPEI))
    assert result["00697B"]["price_date"]=="2026-10-14"
    assert "o=json" in result["00697B"]["source_uri"]
    assert len(calls)==2
