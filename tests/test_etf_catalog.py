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



def test_isin_uses_official_etf_filter(monkeypatch):
    class _Headers:
        def get_content_charset(self): return "utf-8"
    class _Response:
        headers = _Headers()
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self, _): return _html([_row()]).encode("utf-8")
    seen = []
    def fake_open(request, timeout):
        seen.append((request.full_url, timeout))
        return _Response()
    rows = catalog.fetch_isin_etfs("TWSE", opener=fake_open)
    assert rows[0].symbol == "0050"
    assert "issuetype=I&market=1" in seen[0][0]
    assert seen[0][1] <= 4


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
    monkeypatch.setattr(catalog, "fetch_isin_etfs", lambda market, **kw: [])
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


def test_new_listing_is_available_before_monthly_twse_file_refresh(monkeypatch):
    catalog._lookup_cached.cache_clear()
    fresh = OfficialEtf("00999", "當月新上市ETF", "TWSE", date(2026, 10, 20))
    stale = OfficialEtf("0050", "元大台灣50", "TWSE", date(2003, 6, 30))

    monkeypatch.setattr(
        catalog, "fetch_market_etfs",
        lambda market, **kwargs: [stale] if market == "TWSE" else [],
    )
    monkeypatch.setattr(
        catalog, "fetch_isin_etfs",
        lambda market, **kwargs: [fresh] if market == "TWSE" else [],
    )
    assert find_official_etf("00999") == fresh
    catalog._lookup_cached.cache_clear()


def test_twse_falls_back_to_isin_with_explicit_provenance(monkeypatch):
    bond = OfficialEtf("0050", "元大台灣50", "TWSE", date(2003, 6, 30))
    def unavailable(**kwargs):
        raise EtfCatalogUnavailable("blocked")
    monkeypatch.setattr(catalog, "fetch_twse_openapi_etfs", unavailable)
    monkeypatch.setattr(catalog, "fetch_isin_etfs", lambda market, **kwargs: [bond])
    assert catalog.fetch_market_etfs("TWSE") == [bond]

def test_weekly_requires_both_markets(monkeypatch):
    monkeypatch.setattr(catalog, "fetch_isin_etfs", lambda market, **kw: [])
    monkeypatch.setattr(catalog, "fetch_market_etfs", lambda market, **kw: [
        OfficialEtf(f"00{i:03d}", f"ETF-{i}", market, date(2020, 1, 1))
        for i in range(10)
    ] if market == "TWSE" else [])
    with pytest.raises(EtfCatalogUnavailable):
        weekly_official_catalogue()


def test_weekly_adds_new_listed_etf_from_isin(monkeypatch):
    def monthly(market, **kwargs):
        return [
            OfficialEtf(f"00{i:03d}", f"monthly-{i}", market, date(2020, 1, 1))
            for i in range(10)
        ]

    fresh = OfficialEtf("00999", "新上市ETF", "TWSE", date(2026, 11, 3))
    monkeypatch.setattr(catalog, "fetch_market_etfs", monthly)
    monkeypatch.setattr(
        catalog, "fetch_isin_etfs",
        lambda market, **kwargs: [fresh] if market == "TWSE" else [],
    )
    with pytest.raises(EtfCatalogUnavailable):
        # Same codes for OTC and TWSE in the fake dataset are inconsistent.
        weekly_official_catalogue()

    monkeypatch.setattr(catalog, "fetch_market_etfs", lambda market, **kwargs: [
        OfficialEtf(f"00{i:03d}" if market == "TWSE" else f"01{i:03d}",
                    f"monthly-{i}", market, date(2020, 1, 1))
        for i in range(10)
    ])
    records = weekly_official_catalogue()
    assert any(item == fresh for item in records)


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
    assert "register_verified_etf('0050'" in sql
    assert "register_verified_etf('006208'" in sql
    assert "register_verified_etf('00878'" in sql

    assert "REVOKE CREATE ON SCHEMA control FROM janus_private_api" in sql


def test_twse_openapi_parses_compact_gregorian_and_roc_dates_and_excludes_foreign_currency():
    rows = [
        {"基金代號": "0050", "基金簡稱": "元大台灣50", "上市日期": "2003/06/30", "計幣別": "新台幣"},
        {"基金代號": "0056", "基金簡稱": "元大高股息", "上市日期": "20071226", "計幣別": "新臺幣"},
        {"基金代號": "00919", "基金簡稱": "群益台灣精選高息", "上市日期": "111/10/20", "計幣別": "TWD"},
        {"基金代號": "00929", "基金簡稱": "復華台灣科技優息", "上市日期": "1120609"},
        {"基金代號": "00988", "基金簡稱": "美元ETF", "上市日期": "20240110", "計幣別": "美元"},
    ]
    found = parse_twse_openapi_etfs(rows, as_of=date(2026, 11, 25))
    by_sym = {r.symbol: r for r in found}
    assert set(by_sym) == {"0050", "0056", "00919", "00929"}
    assert by_sym["0056"] == OfficialEtf("0056", "元大高股息", "TWSE", date(2007, 12, 26), "twse_openapi_etf")
    assert by_sym["00919"] == OfficialEtf("00919", "群益台灣精選高息", "TWSE", date(2022, 10, 20), "twse_openapi_etf")
    assert by_sym["00929"] == OfficialEtf("00929", "復華台灣科技優息", "TWSE", date(2023, 6, 9), "twse_openapi_etf")


def test_cloud_run_uses_asia_east1_proxy_and_caches_market_for_one_hour(monkeypatch):
    import json

    catalog.clear_cache()
    monkeypatch.setenv("K_SERVICE", "janus-api")
    monkeypatch.delenv("JANUS_SHIOAJI_PROXY_URL", raising=False)
    monkeypatch.setenv("JANUS_ETF_PROXY_ENABLED", "true")

    calls = []

    def fake_proxy(url, *, timeout_seconds, opener=None):
        calls.append(url)
        if url == catalog.TWSE_OPENAPI_URL:
            return json.dumps([
                {"基金代號": "0056", "基金簡稱": "元大高股息", "上市日期": "0961226"},
                {"基金代號": "00919", "基金簡稱": "群益台灣精選高息", "上市日期": "20221020"},
            ])
        if "market=1" in url:
            return _html([
                _row("0056", "元大高股息", listed="2007/12/26"),
                _row("00919", "群益台灣精選高息", listed="2022/10/20"),
            ])
        return _html([_row("00697B", "元大美債7-10", market="上櫃", listed="2017/06/23")])

    def fail_direct(*_, **__):
        raise AssertionError("Direct urlopen must not be called when proxy succeeds")

    monkeypatch.setattr(catalog, "_fetch_text_via_proxy", fake_proxy)
    monkeypatch.setattr(catalog, "urlopen", fail_direct)

    try:
        # Typing 0091 (non-match) populates all market caches; subsequent 00919/0056 do 0 network calls.
        assert find_official_etf("0091") is None
        assert len(calls) == 3
        r_919 = find_official_etf("00919")
        r_56 = find_official_etf("0056")
        assert r_919 is not None and r_919.name == "群益台灣精選高息"
        assert r_56 is not None and r_56.listed_on == date(2007, 12, 26)
        assert len(calls) == 3
    finally:
        catalog.clear_cache()


def test_proxy_fallback_to_direct_and_unapproved_proxy_rejected(monkeypatch):
    import json

    catalog.clear_cache()
    monkeypatch.setenv("CLOUD_RUN_JOB", "janus-ingestion-core")

    class _Headers:
        def get_content_charset(self):
            return "utf-8"

    class _Resp:
        def __init__(self, raw):
            self.headers = _Headers()
            self._raw = raw

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, _):
            return self._raw

    try:
        # Unapproved proxy endpoint must fail closed without falling back to direct.
        monkeypatch.setenv("JANUS_SHIOAJI_PROXY_URL", "https://evil.example.com")
        monkeypatch.setattr(catalog, "urlopen", lambda *_, **__: _Resp(b"[]"))
        with pytest.raises(EtfCatalogUnavailable):
            catalog.fetch_twse_openapi_etfs()

        # Approved proxy failing transiently falls back to direct urlopen.
        monkeypatch.delenv("JANUS_SHIOAJI_PROXY_URL", raising=False)
        monkeypatch.setattr(
            catalog,
            "_fetch_text_via_proxy",
            lambda *_, **__: (_ for _ in ()).throw(EtfCatalogUnavailable("proxy 502")),
        )
        direct_json = json.dumps([
            {"基金代號": "0056", "基金簡稱": "元大高股息", "上市日期": "20071226"},
        ]).encode("utf-8")
        monkeypatch.setattr(catalog, "urlopen", lambda *_, **__: _Resp(direct_json))
        records = catalog.fetch_twse_openapi_etfs()
        assert records[0].symbol == "0056"
    finally:
        catalog.clear_cache()


def test_direct_isin_fetch_decodes_cp950_bytes():
    html = _html([
        _row("0056", "元大高股息", listed="2007/12/26"),
        _row("00919", "群益台灣精選高息", listed="2022/10/20"),
    ])
    cp950_bytes = html.encode("cp950")

    class _Headers:
        def get_content_charset(self):
            return None

    class _Resp:
        headers = _Headers()

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, _):
            return cp950_bytes

    records = catalog.fetch_isin_etfs("TWSE", opener=lambda *_, **__: _Resp(), use_proxy=False)
    assert [r.symbol for r in records] == ["0056", "00919"]
