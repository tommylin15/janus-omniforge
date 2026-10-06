"""First-batch Taiwan market dataset adapters and deterministic normalisers.

Adapters keep transport and upstream JSON shape separate from Core contracts.
Every adapter is injectable, making fixtures and replay possible without
calling an exchange or filing provider during tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from uuid import uuid4

from .adapters import CollectionRequest, SourceResponse, validate_source_url
from .control import CacheMetadata, DataState
from .sources import (CompanyProfileAdapter, ExchangeOhlcvAdapter, MarketVolumeAdapter,
                      twse_ohlcv_adapter, twse_market_volume_adapter, twse_company_profile_adapter)
from .stage import StageResult, StageWriter
from packages.provenance import Provenance, content_hash


def _text(value: Any) -> str | None:
    if value is None or str(value).strip() in {"", "-", "--", "N/A", "null"}:
        return None
    return str(value).strip().replace(",", "")


def _iso_date(value: Any) -> str:
    text = str(value).strip().replace("/", "-")
    if text.isdigit() and len(text) == 8:
        return date(int(text[:4]), int(text[4:6]), int(text[6:])).isoformat()
    if text.isdigit() and len(text) == 7:
        return date(int(text[:3]) + 1911, int(text[3:5]), int(text[5:])).isoformat()
    if len(text) == 9 and text.count("-") == 2:
        year, month, day = text.split("-")
        text = f"{int(year) + 1911:04d}-{int(month):02d}-{int(day):02d}"
    return date.fromisoformat(text).isoformat()


def _pick(row: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in row:
            return row[name]
    return None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _integer_sum(*values: Any) -> str | None:
    parsed = [_text(value) for value in values]
    if any(value is None for value in parsed):
        return None
    try:
        return str(sum(int(value) for value in parsed if value is not None))
    except ValueError:
        return None


def _financial_unit(metric: str, row: Mapping[str, Any]) -> str | None:
    explicit = _text(_pick(row, "unit", "Unit"))
    if explicit:
        return explicit
    normalized = metric.strip().lower()
    if "每股" in metric or normalized in {"eps", "earningspershare", "earnings_per_share"}:
        return "TWD_per_share"
    if "%" in metric or "百分比" in metric or normalized.endswith(("_percent", "_percentage")):
        return "percent"
    if "stock_id" in row:
        return None
    return "TWD_thousands"


def normalise_benchmark(rows: Iterable[Mapping[str, Any]], benchmark_id: str = "TAIEX") -> tuple[dict[str, Any], ...]:
    result = []
    for row in rows:
        result.append({"benchmark_id": str(_pick(row, "benchmark_id", "index", "name") or benchmark_id),
                       "trade_date": _iso_date(_pick(row, "trade_date", "date", "Date", "日期")),
                       "close": _text(_pick(row, "close", "value", "index_value", "Close", "ClosingIndex", "收盤指數")),
                       "return_percent": _text(_pick(row, "return_percent", "change_percent", "change", "Change")),
                       "index_kind": str(_pick(row, "index_kind", "kind") or "price")})
    return tuple(result)


def normalise_valuation(rows: Iterable[Mapping[str, Any]], *, market: str = "TWSE") -> tuple[dict[str, Any], ...]:
    return tuple({"symbol": str(_pick(row, "symbol", "code", "Code", "SecuritiesCompanyCode", "證券代號")), "market": str(_pick(row, "market") or market),
                  "observed_date": _iso_date(_pick(row, "observed_date", "date", "Date")),
                  "pe_ratio": _text(_pick(row, "pe_ratio", "pe", "PEratio", "PriceEarningRatio", "本益比")), "pb_ratio": _text(_pick(row, "pb_ratio", "pb", "PBratio", "PriceBookRatio", "股價淨值比")),
                  "dividend_yield_percent": _text(_pick(row, "dividend_yield_percent", "dividend_yield", "DividendYield", "YieldRatio", "殖利率(%)"))}
                 for row in rows)


def normalise_institutional(rows: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    result = []
    groups = (
        ("foreign", "外陸資買進股數(不含外資自營商)", "外陸資賣出股數(不含外資自營商)", "外陸資買賣超股數(不含外資自營商)"),
        ("investment_trust", "投信買進股數", "投信賣出股數", "投信買賣超股數"),
    )
    for row in rows:
        if _pick(row, "investor_type", "investor") is not None:
            groups_for_row = ((str(_pick(row, "investor_type", "investor")), "buy_shares", "sell_shares", "net_shares"),)
            for investor, buy, sell, net in groups_for_row:
                result.append({"symbol": str(_pick(row, "symbol", "code", "證券代號")), "market": str(_pick(row, "market") or "TWSE"),
                               "trade_date": _iso_date(_pick(row, "trade_date", "date", "Date")),
                               "investor_type": investor, "buy_shares": _text(_pick(row, buy, "buy")),
                               "sell_shares": _text(_pick(row, sell, "sell")), "net_shares": _text(_pick(row, net, "net"))})
            continue

        common = {"symbol": str(_pick(row, "symbol", "code", "證券代號")),
                  "market": str(_pick(row, "market") or "TWSE"),
                  "trade_date": _iso_date(_pick(row, "trade_date", "date", "Date"))}
        for investor, buy, sell, net in groups:
            result.append({**common, "investor_type": investor,
                           "buy_shares": _text(_pick(row, buy)),
                           "sell_shares": _text(_pick(row, sell)),
                           "net_shares": _text(_pick(row, net))})

        dealer_buy = _integer_sum(_pick(row, "自營商買進股數(自行買賣)"), _pick(row, "自營商買進股數(避險)"))
        dealer_sell = _integer_sum(_pick(row, "自營商賣出股數(自行買賣)"), _pick(row, "自營商賣出股數(避險)"))
        dealer_net = _text(_pick(row, "自營商買賣超股數"))
        result.append({**common, "investor_type": "dealer", "buy_shares": dealer_buy,
                       "sell_shares": dealer_sell, "net_shares": dealer_net})
    return tuple(result)


def normalise_tpex_institutional(rows: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    # Keep "foreign" consistent with TWSE: foreign dealers are excluded.
    groups = (
        ("foreign", "Foreign Investors include Mainland Area Investors (Foreign Dealers excluded)-Total Buy",
         " Foreign Investors include Mainland Area Investors (Foreign Dealers excluded)-Total Sell",
         "Foreign Investors include Mainland Area Investors (Foreign Dealers excluded)-Difference"),
        ("investment_trust", "SecuritiesInvestmentTrustCompanies-TotalBuy",
         "SecuritiesInvestmentTrustCompanies-TotalSell", "SecuritiesInvestmentTrustCompanies-Difference"),
        ("dealer", "Dealers-TotalBuy", "Dealers-TotalSell", "Dealers-Difference"),
    )
    return normalise_institutional(
        {"symbol": row["SecuritiesCompanyCode"], "market": "TPEX", "date": row["Date"],
         "investor_type": investor, "buy_shares": row[buy], "sell_shares": row[sell], "net_shares": row[net]}
        for row in rows for investor, buy, sell, net in groups
    )


def normalise_financials(rows: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    result = []
    identity = {"出表日期", "年度", "季別", "公司代號", "公司名稱"}
    for row in rows:
        source_report_date: str | None = None
        fiscal_period_end: str | None = None
        if "stock_id" in row:
            fiscal_date = date.fromisoformat(str(row["date"]))
            metrics = ((str(row.get("type") or row.get("origin_name") or "unknown"), row.get("value")),)
            symbol, year, quarter, published = str(row["stock_id"]), fiscal_date.year, (fiscal_date.month - 1) // 3 + 1, fiscal_date.isoformat()
            fiscal_period_end = fiscal_date.isoformat()
            statement = str(row.get("statement_type") or "financial")
        elif _pick(row, "fiscal_year", "year") is not None:
            symbol = str(_pick(row, "symbol", "code"))
            year = int(_pick(row, "fiscal_year", "year"))
            quarter = int(_pick(row, "fiscal_quarter", "quarter") or 0)
            published = str(_pick(row, "published_at", "published") or "")
            source_report_date = _text(_pick(row, "source_report_date"))
            fiscal_period_end = _text(_pick(row, "fiscal_period_end"))
            statement = str(_pick(row, "statement_type", "statement") or "unknown")
            metrics = ((str(_pick(row, "metric", "name") or "unknown"), _pick(row, "value", "amount")),)
        else:
            year_value = int(str(row.get("年度", "0")))
            year = year_value + 1911 if year_value < 1911 else year_value
            quarter = int(str(row.get("季別", "0")))
            source_report_date = _iso_date(row.get("出表日期"))
            symbol, published = str(row.get("公司代號", "")), source_report_date
            statement = str(row.get("statement_type") or "income")
            metrics = tuple((str(key), value) for key, value in row.items() if key not in identity)
        for metric, value in metrics:
            item = {"symbol": symbol, "fiscal_year": year, "fiscal_quarter": quarter,
                    "statement_type": statement, "published_at": published, "metric": metric,
                    "value": _text(value), "unit": _financial_unit(metric, row),
                    "currency": str(_pick(row, "currency", "Currency") or "TWD")}
            if source_report_date:
                item["source_report_date"] = source_report_date
            if fiscal_period_end:
                item["fiscal_period_end"] = fiscal_period_end
            result.append(item)
    return tuple(result)


def normalise_events(rows: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    result = []
    for position, row in enumerate(rows):
        published_date = _pick(row, "published_at", "published", "發言日期", "出表日期")
        published = str(published_date or "")
        if published_date and str(published_date).isdigit():
            published = _iso_date(published_date) + "T" + str(row.get("發言時間", "000000")).zfill(6)[:2] + ":" + str(row.get("發言時間", "000000")).zfill(6)[2:4] + ":" + str(row.get("發言時間", "000000")).zfill(6)[4:6] + "+08:00"
        symbol = str(_pick(row, "symbol", "code", "公司代號") or "")
        event_id = str(_pick(row, "event_id", "id") or f"{symbol}-{published_date}-{position}")
        result.append({"event_id": event_id, "symbol": symbol,
                       "event_type": str(_pick(row, "event_type", "type", "符合條款") or "material_information"),
                       "published_at": published,
                       "effective_date": _iso_date(_pick(row, "effective_date", "effective", "事實發生日")) if _pick(row, "effective_date", "effective", "事實發生日") else None,
                       "severity": _text(_pick(row, "severity")), "details": _pick(row, "details", "body", "說明", "主旨 ")})
    return tuple(result)


def normalise_market_activity(rows: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    result = []
    for row in rows:
        if "證券代號" in row and "當日沖銷交易成交股數" in row:
            for metric, field, unit in (
                ("day_trade_shares", "當日沖銷交易成交股數", "shares"),
                ("day_trade_buy_twd", "當日沖銷交易買進成交金額", "TWD"),
                ("day_trade_sell_twd", "當日沖銷交易賣出成交金額", "TWD"),
            ):
                result.append({"symbol": str(row["證券代號"]), "market": "TWSE", "trade_date": _iso_date(row["Date"]),
                               "metric": metric, "value": _text(row.get(field)), "unit": unit})
            continue
        official_day_trade = "Code" in row and "Suspension" in row
        result.append({"symbol": str(_pick(row, "symbol", "code", "Code")), "market": str(_pick(row, "market") or "TWSE"),
                       "trade_date": _iso_date(_pick(row, "trade_date", "date", "Date")),
                       "metric": "day_trading_suspension" if official_day_trade else str(_pick(row, "metric", "name")),
                       "value": _text(row.get("Suspension") or "eligible") if official_day_trade else _text(_pick(row, "value", "amount")),
                       "unit": "status" if official_day_trade else _text(_pick(row, "unit"))})
    return tuple(result)


def _activity_rows(symbol: str, trade_date: str,
                   values: Iterable[tuple[str, Any, str]]) -> tuple[dict[str, Any], ...]:
    return tuple({"symbol": symbol, "market": "TWSE", "trade_date": trade_date,
                  "metric": metric, "value": _text(value), "unit": unit}
                 for metric, value, unit in values)


def normalise_twse_financing(rows: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    result = []
    for row in rows:
        cells = row.get("_cells")
        if not isinstance(cells, list) or len(cells) < 16:
            continue
        symbol = str(cells[0]).strip()
        if not (symbol.isascii() and symbol.isalnum() and 4 <= len(symbol) <= 6):
            continue
        result.extend(_activity_rows(symbol, _iso_date(row["Date"]), (
            ("margin_buy", cells[2], "trading_units"),
            ("margin_sell", cells[3], "trading_units"),
            ("margin_cash_redemption", cells[4], "trading_units"),
            ("margin_balance", cells[6], "trading_units"),
        )))
    return tuple(result)


def normalise_twse_securities_lending_short(rows: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    result = []
    for row in rows:
        cells = row.get("_cells")
        if not isinstance(cells, list) or len(cells) < 15:
            continue
        symbol = str(cells[0]).strip()
        if not (symbol.isascii() and symbol.isalnum() and 4 <= len(symbol) <= 6):
            continue
        result.extend(_activity_rows(symbol, _iso_date(row["Date"]), (
            ("margin_short_sell", cells[3], "shares"),
            ("margin_short_balance", cells[6], "shares"),
            ("sbl_short_sell", cells[9], "shares"),
            ("sbl_short_balance", cells[12], "shares"),
        )))
    return tuple(result)


@dataclass
class JsonDatasetAdapter:
    source_id: str
    dataset_id: str
    endpoint: str
    normalizer: Callable[[Iterable[Mapping[str, Any]]], tuple[dict[str, Any], ...]]
    transport: Callable[[str], bytes] | None = None
    url_builder: Callable[[CollectionRequest], str] | None = None
    observation_mode: str = "window_end"
    max_replay_age_days: int | None = None
    row_date_field: str | None = None
    availability_field: str | None = None
    publication_time_authoritative: bool | None = None
    clock: Callable[[], datetime] = _now_utc
    core_dataset_id: str | None = None
    extra_endpoints: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        validate_source_url(self.endpoint)
        if self.observation_mode not in {"window_end", "fetch_time"}:
            raise ValueError("invalid observation_mode")
        if self.max_replay_age_days is not None and self.max_replay_age_days < 0:
            raise ValueError("max_replay_age_days must be non-negative")
        for endpoint in self.extra_endpoints:
            validate_source_url(endpoint)

    def fetch(self, request: CollectionRequest) -> SourceResponse:
        fetched = self.clock()
        if fetched.tzinfo is None:
            raise ValueError("adapter clock must return a timezone-aware datetime")
        fetched = fetched.astimezone(timezone.utc)
        if self.max_replay_age_days is not None:
            oldest = fetched.date() - timedelta(days=self.max_replay_age_days)
            if request.window_end < oldest:
                raise ValueError("snapshot source does not support historical replay")
        url = self.url_builder(request) if self.url_builder else self.endpoint
        parsed_url = urlsplit(url)
        validate_source_url(urlunsplit((parsed_url.scheme, parsed_url.netloc, parsed_url.path, "", "")))
        raw = self.transport(url) if self.transport else self._https(url)
        endpoint_payloads: list[tuple[str, bytes]] = []
        if self.extra_endpoints:
            initial_rows = json.loads(raw)
            if not isinstance(initial_rows, list):
                raise ValueError("batch source must return a JSON list")
            endpoint_payloads.append((url, raw))

            selected = {symbol.upper() for symbol in request.symbols}

            def is_selected(row: Mapping[str, Any]) -> bool:
                return not selected or str(_pick(row, "symbol", "code", "公司代號")).strip().upper() in selected

            def upstream_batches():
                yield (row for row in initial_rows if is_selected(row))
                initial_rows.clear()
                for endpoint in self.extra_endpoints:
                    payload = self.transport(endpoint) if self.transport else self._https(endpoint)
                    endpoint_payloads.append((endpoint, payload))
                    batch = json.loads(payload)
                    if not isinstance(batch, list):
                        raise ValueError("batch source must return a JSON list")
                    yield (row for row in batch if is_selected(row))
                    batch.clear()

            batches = upstream_batches()
            fields = None
        else:
            document = json.loads(raw)
            if isinstance(document, list):
                upstream_rows = document
            else:
                if document.get("tables"):
                    upstream_rows = []
                    for table in document["tables"]:
                        fields = table.get("fields", [])
                        upstream_rows.extend(dict(zip(fields, row, strict=False)) | {"Date": document.get("date"), "_cells": row} for row in table.get("data", []))
                    fields = None
                else:
                    upstream_rows = document.get("data", document.get("rows", []))
                    fields = document.get("fields")
                if fields and upstream_rows and isinstance(upstream_rows[0], list):
                    upstream_rows = [dict(zip(fields, row, strict=False)) | {"Date": document.get("date"), "_cells": row} for row in upstream_rows]
        rows = tuple(
            {**row, "source_id": self.source_id}
            for batch in batches
            for row in self.normalizer(batch)
        ) if endpoint_payloads else tuple(
            {**row, "source_id": self.source_id} for row in self.normalizer(upstream_rows)
        )
        if endpoint_payloads:
            parts = [b"{"]
            for index, (source_url, payload) in enumerate(endpoint_payloads):
                if index:
                    parts.append(b",")
                parts.extend((json.dumps(source_url, ensure_ascii=False).encode(), b":", payload))
            parts.append(b"}")
            raw = b"".join(parts)
        if self.row_date_field:
            rows = tuple(row for row in rows
                         if row.get(self.row_date_field)
                         and date.fromisoformat(str(row[self.row_date_field])[:10]) <= request.window_end)
        observed = fetched if self.observation_mode == "fetch_time" else datetime.combine(
            request.window_end, datetime.min.time(), tzinfo=timezone.utc
        )
        observed_text = observed.isoformat().replace("+00:00", "Z")
        lineage: dict[str, Any] = {"observed_at": observed_text}
        if self.availability_field:
            lineage[self.availability_field] = observed_text
        if self.publication_time_authoritative is not None:
            lineage["publication_time_authoritative"] = self.publication_time_authoritative
        rows = tuple({**row, **lineage} for row in rows)
        return SourceResponse(rows=rows, observed_at=observed, raw_payload=raw, source_url=url,
                              fields=frozenset(rows[0].keys()) if rows else frozenset())

    @staticmethod
    def _https(url: str) -> bytes:
        request = Request(url, headers={
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
            "User-Agent": "Mozilla/5.0 (compatible; JanusAI-Ingestion/1.0; +https://github.com/tommylin15/janus-omniforge)",
        })
        with urlopen(request, timeout=30) as response:
            payload = response.read()
            content_type = response.headers.get_content_type()
        if payload.lstrip()[:1] not in {b"[", b"{"}:
            raise ValueError(f"upstream returned non-JSON content ({content_type})")
        return payload


def stage_raw_response(
    response: SourceResponse,
    request: CollectionRequest,
    *,
    bucket: str,
    store: object,
    cache_ttl: timedelta = timedelta(hours=24),
    fetched_at: datetime | None = None,
    execution_scoped: bool = False,
    quarantine_violations: list[dict[str, str]] | None = None,
) -> tuple[StageResult, CacheMetadata]:
    """Write upstream bytes to Stage and return metadata for the control plane.

    The PostgreSQL implementation deliberately accepts only the returned
    ``CacheMetadata``; the payload itself is kept in the supplied GCS-backed
    object store.  ``store`` is typed structurally at runtime by StageWriter.
    """
    if not bucket or "/" in bucket:
        raise ValueError("invalid GCS bucket")
    if not response.source_url:
        raise ValueError("source response must include source_url")
    fetched = fetched_at or datetime.now(timezone.utc)
    observed = response.observed_at or datetime.combine(request.window_end, datetime.min.time(), tzinfo=timezone.utc)
    payload = response.raw_payload
    if payload is None:
        payload = json.dumps(response.rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    provenance = Provenance(
        provenance_id=str(uuid4()),
        source_id=request.source_id,
        source_url=response.source_url,
        dataset_id=request.dataset_id,
        observed_at=observed,
        published_at=response.published_at,
        fetched_at=fetched,
        content_hash=content_hash(payload),
        is_fallback=response.is_fallback,
    )
    writer = StageWriter(store)
    staged = writer.write_raw(
        payload=payload,
        media_type="application/json",
        extension="json",
        execution_id=request.execution_id,
        provenance=provenance,
        execution_scoped=execution_scoped,
    )
    if quarantine_violations:
        writer.quarantine(
            payload=payload,
            media_type="application/json",
            extension="json",
            execution_id=request.execution_id,
            provenance=provenance,
            violations=quarantine_violations,
            execution_scoped=execution_scoped,
        )
    metadata = CacheMetadata(
        cache_key=staged.idempotency_key,
        source_id=request.source_id,
        dataset_id=request.dataset_id,
        payload_uri=f"gs://{bucket}/{staged.object_name}",
        content_hash=provenance.content_hash,
        fetched_at=fetched,
        expires_at=fetched + cache_ttl,
        observed_at=observed,
        state=DataState.FALLBACK if response.is_fallback else DataState.SUCCESS,
    )
    return staged, metadata


def effective_trading_day(as_of: date, *, holidays: set[date] = frozenset()) -> date:
    """Return the latest usable exchange day for holiday/weekend or pre-open runs."""
    current = as_of
    while current.weekday() >= 5 or current in holidays:
        current -= timedelta(days=1)
    return current


def dataset_adapters(transport: Callable[[str], bytes] | None = None) -> dict[str, JsonDatasetAdapter | ExchangeOhlcvAdapter | MarketVolumeAdapter | CompanyProfileAdapter]:
    """Configured first-batch source set; URLs are credential-free endpoints."""
    def dated(endpoint: str, **fixed: str) -> Callable[[CollectionRequest], str]:
        def build(request: CollectionRequest) -> str:
            values = {**fixed, "date": request.window_end.strftime("%Y%m%d")}
            return endpoint + "?" + urlencode(values)
        return build

    def finmind(request: CollectionRequest) -> str:
        values = {
            "dataset": "TaiwanStockFinancialStatements",
            "data_id": request.symbols[0] if request.symbols else "2330",
            "start_date": (request.window_start or request.window_end).isoformat(),
            "end_date": request.window_end.isoformat(),
        }
        return "https://api.finmindtrade.com/api/v4/data?" + urlencode(values)

    return {
        "twse-stock-profile": twse_company_profile_adapter(transport),
        "twse-market-volume": twse_market_volume_adapter(transport),
        "twse-ohlcv": twse_ohlcv_adapter(transport),
        "taiex": JsonDatasetAdapter("taiex", "benchmark", "https://www.twse.com.tw/rwd/zh/TAIEX/MI_5MINS_HIST", lambda rows: normalise_benchmark(rows, "TAIEX"), transport, dated("https://www.twse.com.tw/rwd/zh/TAIEX/MI_5MINS_HIST", response="json")),
        "twse-valuation": JsonDatasetAdapter("twse", "valuation", "https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d", normalise_valuation, transport, dated("https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d", selectType="ALL", response="json")),
        "twse-institutional": JsonDatasetAdapter("twse", "institutional", "https://www.twse.com.tw/rwd/zh/fund/T86", normalise_institutional, transport, dated("https://www.twse.com.tw/rwd/zh/fund/T86", selectType="ALL", response="json")),
        "mops": JsonDatasetAdapter("mops", "financials", "https://openapi.twse.com.tw/v1/opendata/t187ap06_L_ci", normalise_financials, transport,
                                   observation_mode="fetch_time", max_replay_age_days=7,
                                   availability_field="availability_at", publication_time_authoritative=False,
                                   extra_endpoints=tuple("https://openapi.twse.com.tw/v1/opendata/t187ap06_L_" + suffix
                                                         for suffix in ("basi", "bd", "fh", "ins", "mim"))),
        "finmind": JsonDatasetAdapter("finmind", "financials", "https://api.finmindtrade.com/api/v4/data", normalise_financials, transport, finmind,
                                      observation_mode="fetch_time", max_replay_age_days=7,
                                      availability_field="availability_at", publication_time_authoritative=False),
        "twse-events": JsonDatasetAdapter("twse", "events", "https://openapi.twse.com.tw/v1/opendata/t187ap04_L", normalise_events, transport,
                                          observation_mode="fetch_time", max_replay_age_days=7, row_date_field="published_at"),
        "twse-financing": JsonDatasetAdapter("twse", "financing", "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN", normalise_twse_financing, transport, dated("https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN", selectType="ALL", response="json"), core_dataset_id="market-activity"),
        "twse-securities-lending-short": JsonDatasetAdapter("twse", "securities_lending_short", "https://www.twse.com.tw/exchangeReport/TWT93U", normalise_twse_securities_lending_short, transport, dated("https://www.twse.com.tw/exchangeReport/TWT93U", response="json"), core_dataset_id="market-activity"),
        "twse-market-activity": JsonDatasetAdapter("twse", "day_trading", "https://www.twse.com.tw/exchangeReport/TWTB4U", normalise_market_activity, transport, dated("https://www.twse.com.tw/exchangeReport/TWTB4U", response="json"), core_dataset_id="market-activity"),
    }
