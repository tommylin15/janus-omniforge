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
