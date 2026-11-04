"""Official ETF identity validation; never make network calls in unit tests."""
from datetime import date
from pathlib import Path

import pytest

from packages import etf_catalog as catalog
from packages.etf_catalog import (
    EtfCatalogUnavailable, OfficialEtf, looks_like_etf_code,
    parse_isin_etfs, parse_twse_openapi_etfs, find_official_etf, weekly_official_catalogue,
)


def _html(rows):
    return "<html><table>" + "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>"
        for row in rows
    ) + "</table></html>"


def _row(symbol="0050", name="元大台灣50", *, market="上市", kind="ETF",
         listed="2003/06/30"):
    return ["1", "TW0000050004", symbol, name, market, kind,
            "", listed, "CEOGEU", ""]


def test_strict_official_etf_classification_and_market():
    html = _html([
        _row(),
        _row("0051", "元大中型100", kind="ETN"),
        _row("006201", "元大富櫃50", market="上櫃"),
        _row("0052", "偽ETF", listed="2035/01/01"),
        _row("2330", "台積電"),
    ])
    records = parse_isin_etfs(html, market="TWSE", as_of=date(2026, 11, 4))
    assert [(i.symbol, i.name, i.market) for i in records] == [
        ("0050", "元大台灣50", "TWSE")
    ]
    assert looks_like_etf_code("0050")
    assert looks_like_etf_code("00697B")
    assert not looks_like_etf_code("2330")
    assert not looks_like_etf_code("0050' OR 1=1")



def test_twse_openapi_uses_explicit_listing_date_and_preserves_source():
    rows = [
        {"基金代號": "0050", "基金簡稱": "元大台灣50", "上市日期": "2003/06/30"},
        {"基金代號": "00687C", "基金簡稱": "美元加掛", "上市日期": "2025/01/10"},
        {"基金代號": "2330", "基金簡稱": "非ETF", "上市日期": "1994/01/01"},
        {"基金代號": "00999", "基金簡稱": "尚未上市", "上市日期": "2027/01/01"},
    ]
    found = parse_twse_openapi_etfs(rows, as_of=date(2026, 11, 4))
    assert found == [OfficialEtf("0050", "元大台灣50", "TWSE", date(2003, 6, 30), "twse_openapi_etf")]


def test_foreign_currency_classes_are_not_twd_ledger_options():
    with pytest.raises(EtfCatalogUnavailable):
        parse_isin_etfs(_html([_row("00687C", "美元加掛")]), market="TWSE")

def test_missing_or_corrupt_source_fails_closed():
    with pytest.raises(EtfCatalogUnavailable):
        parse_isin_etfs("<html>blocked</html>", market="TWSE")
    with pytest.raises(EtfCatalogUnavailable):
        parse_isin_etfs(_html([_row(name="\ufffd")]), market="TWSE")


def test_official_code_lookup_only_uses_exact_match(monkeypatch):
    catalog._lookup_cached.cache_clear()
    record = OfficialEtf("0050", "元大台灣50", "TWSE", date(2003, 6, 30))
    monkeypatch.setattr(catalog, "fetch_market_etfs", lambda market, **kw: [record] if market == "TWSE" else [])
    assert find_official_etf("0050") == record
    assert find_official_etf("005") is None
    assert find_official_etf("2330") is None
    assert find_official_etf("0051") is None
    catalog._lookup_cached.cache_clear()



def test_otc_official_lookup_continues_when_twse_unavailable(monkeypatch):
    catalog._lookup_cached.cache_clear()
    bond = OfficialEtf("00697B", "元大美債7-10", "TPEX", date(2017, 6, 23))

    def fetch(market, **kwargs):
        if market == "TWSE":
            raise EtfCatalogUnavailable("TWSE unavailable")
        return [bond]

    monkeypatch.setattr(catalog, "fetch_market_etfs", fetch)
    assert find_official_etf("00697B") == bond
    catalog._lookup_cached.cache_clear()


def test_twse_falls_back_to_isin_with_explicit_provenance(monkeypatch):
    bond = OfficialEtf("0050", "元大台灣50", "TWSE", date(2003, 6, 30))
    def unavailable(**kwargs):
        raise EtfCatalogUnavailable("blocked")
    monkeypatch.setattr(catalog, "fetch_twse_openapi_etfs", unavailable)
    monkeypatch.setattr(catalog, "fetch_isin_etfs", lambda market, **kwargs: [bond])
    assert catalog.fetch_market_etfs("TWSE") == [bond]

def test_weekly_requires_both_markets(monkeypatch):
    monkeypatch.setattr(catalog, "fetch_market_etfs", lambda market, **kw: [
        OfficialEtf(f"00{i:03d}", f"ETF-{i}", market, date(2020, 1, 1))
        for i in range(10)
    ] if market == "TWSE" else [])
    with pytest.raises(EtfCatalogUnavailable):
        weekly_official_catalogue()


def test_migration_is_owner_only_and_research_universe_unchanged():
    sql = Path("infra/postgres/migrations/075_etf_tradeable_catalog.sql").read_text()
    assert "SECURITY DEFINER" in sql
    assert "REVOKE ALL ON FUNCTION control.register_verified_etf" in sql
    assert "janus_private_api" in sql
    assert "control.market_universe_members" in sql
    assert "ip.instrument_kind IS DISTINCT FROM 'ETF'" in sql
    assert sql.count("$$") == 4
    assert "-- PHASE: private-api" in sql
    assert "-- PHASE: control-finalize" in sql
    assert "-- PHASE: acceptance" in sql
    assert "GRANT CREATE ON SCHEMA control TO janus_private_api" in sql
    assert "REVOKE CREATE ON SCHEMA control FROM janus_private_api" in sql
