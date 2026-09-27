"""Official Taiwan exchange OHLCV adapters.

The transport is injectable so production uses the standard-library HTTPS
client while tests can exercise the exact normalisation without the network.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from http.client import IncompleteRead
import json
import re
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .adapters import CollectionRequest, SourceResponse, validate_source_url


def _number(value: Any) -> str | None:
    text = str(value).strip().replace(",", "") if value is not None else ""
    if not text or text in {"--", "-", "N/A", "null"}:
        return None
    return text


def _date(value: Any) -> str:
    text = str(value).strip().replace("/", "-")
    if len(text) == 8 and text.isdigit():
        return datetime.strptime(text, "%Y%m%d").date().isoformat()
    if len(text) == 7 and text.isdigit():
        text = f"{int(text[:3]) + 1911:04d}-{text[3:5]}-{text[5:7]}"
    if len(text) == 9 and text.count("-") == 2:
        year, month, day = text.split("-")
        text = f"{int(year) + 1911:04d}-{int(month):02d}-{int(day):02d}"
    return date.fromisoformat(text).isoformat()


def _row(symbol: str, market: str, values: list[Any]) -> dict[str, Any]:
    if len(values) < 9:
        raise ValueError("OHLCV row has too few columns")
    return {"symbol": symbol, "market": market, "trade_date": _date(values[0]),
            "open": _number(values[3]), "high": _number(values[4]),
            "low": _number(values[5]), "close": _number(values[6]),
            "volume_shares": int(str(values[1]).replace(",", "") or 0),
            "turnover_twd": _number(values[2]), "change_percent": None}


def parse_twse(payload: bytes, symbol: str = "2330") -> tuple[dict[str, Any], ...]:
    document = json.loads(payload)
    return tuple(_row(symbol, "TWSE", values) for values in document.get("data", []))


def parse_tpex(payload: bytes, symbol: str = "2330") -> tuple[dict[str, Any], ...]:
    document = json.loads(payload)
    rows = document.get("tables", [{}])[0].get("data", []) if document.get("tables") else document.get("data", [])
    return tuple(_row(symbol, "TPEX", values) for values in rows)


@dataclass
class ExchangeOhlcvAdapter:
    source_id: str
    market: str
    endpoint: str
    parser: Callable[[bytes, str], tuple[dict[str, Any], ...]]
    transport: Callable[[str], bytes] | None = None
    dataset_id: str = "ohlcv"
    batch_scope: str = "symbol"

    def __post_init__(self) -> None:
        validate_source_url(self.endpoint)

    def fetch(self, request: CollectionRequest) -> SourceResponse:
        symbol = request.symbols[0] if request.symbols else "2330"
        month = (request.window_end or date.today()).strftime("%Y%m01")
        query = {"response": "json", "date": month, "stockNo": symbol}
        url = f"{self.endpoint}?{urlencode(query)}"
        raw = self.transport(url) if self.transport else self._https(url)
        observed = datetime.combine(request.window_end, datetime.min.time(), tzinfo=timezone.utc)
        rows = tuple({**row, "source_id": self.source_id, "observed_at": observed.isoformat().replace("+00:00", "Z")}
                      for row in self.parser(raw, symbol))
        fields = frozenset(rows[0].keys()) if rows else frozenset()
        return SourceResponse(rows=rows, fields=fields, observed_at=observed,
                              raw_payload=raw, source_url=self.endpoint)

    @staticmethod
    def _https(url: str) -> bytes:
        for attempt in range(2):
            request = Request(url, headers={"Accept": "application/json",
                                            "User-Agent": "Mozilla/5.0 (compatible; JanusAI-Ingestion/1.0)"})
            try:
                with urlopen(request, timeout=30) as response:
                    return response.read()
            except IncompleteRead:
                if attempt:
                    raise


def twse_ohlcv_adapter(transport: Callable[[str], bytes] | None = None) -> ExchangeOhlcvAdapter:
    return ExchangeOhlcvAdapter("twse", "TWSE", "https://www.twse.com.tw/exchangeReport/STOCK_DAY", parse_twse, transport)


def tpex_ohlcv_adapter(transport: Callable[[str], bytes] | None = None) -> ExchangeOhlcvAdapter:
    return ExchangeOhlcvAdapter("tpex", "TPEX", "https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes", parse_tpex, transport)


@dataclass
class MarketVolumeAdapter:
    """One official market response per day; preserve the full payload in Stage."""

    source_id: str
    market: str
    endpoint: str
    code_field: str
    name_field: str
    volume_field: str
    value_field: str
    open_field: str
    high_field: str
    low_field: str
    close_field: str
    transport: Callable[[str], bytes] | None = None
    url_builder: Callable[[CollectionRequest], str] | None = None
    dataset_id: str = "market-volume"
    batch_scope: str = "market"

    def __post_init__(self) -> None:
        validate_source_url(self.endpoint)

    def fetch(self, request: CollectionRequest) -> SourceResponse:
        url = self.url_builder(request) if self.url_builder else self.endpoint
        raw = self.transport(url) if self.transport else ExchangeOhlcvAdapter._https(url)
        document = json.loads(raw)
        if isinstance(document, list):
            records = document
            snapshot_date = None
        elif isinstance(document, dict) and document.get("tables"):
            snapshot_date = document.get("date")
            table = next((item for item in document["tables"]
                          if isinstance(item, dict) and self.code_field in item.get("fields", ())), None)
            if table is None:
                raise ValueError("market volume response has no stock table")
            fields = table["fields"]
            records = [dict(zip(fields, row, strict=False)) | {"Date": snapshot_date}
                       for row in table.get("data", ())]
        else:
            raise ValueError("market volume response is empty or invalid")
        if not records:
            raise ValueError("market volume response is empty or invalid")
        observed = datetime.combine(request.window_end, datetime.min.time(), tzinfo=timezone.utc)
        rows = []
        for item in records:
            if not isinstance(item, dict) or not all(field in item for field in
                ("Date", self.code_field, self.name_field, self.volume_field, self.value_field,
                 self.open_field, self.high_field, self.low_field, self.close_field)):
                raise ValueError("market volume response schema changed")
            trade_date = _date(item["Date"] or snapshot_date)
            if trade_date != request.window_end.isoformat():
                raise ValueError("market volume response is not for requested trading date")
            symbol = str(item[self.code_field]).strip()
            if not re.fullmatch(r"[1-9][0-9]{3}", symbol):
                continue
            name = str(item[self.name_field]).strip()
            volume = _number(item[self.volume_field])
            value = _number(item[self.value_field])
            if not name or volume is None or value is None:
                raise ValueError("market volume response has incomplete stock row")
            rows.append({"symbol": symbol, "stock_name": name, "market": self.market,
                         "trade_date": trade_date, "volume_shares": int(volume),
                         "turnover_twd": value,
                         "open": _number(item[self.open_field]),
                         "high": _number(item[self.high_field]),
                         "low": _number(item[self.low_field]),
                         "close": _number(item[self.close_field]),
                         "source_id": self.source_id,
                         "observed_at": observed.isoformat().replace("+00:00", "Z")})
        if len(rows) < 500:
            raise ValueError("market volume response has too few stock candidates")
        return SourceResponse(rows=tuple(rows), observed_at=observed, raw_payload=raw,
                              source_url=url)


def twse_market_volume_adapter(transport: Callable[[str], bytes] | None = None) -> MarketVolumeAdapter:
    endpoint = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
    return MarketVolumeAdapter(
        "twse", "TWSE", endpoint, "證券代號", "證券名稱", "成交股數", "成交金額",
        "開盤價", "最高價", "最低價", "收盤價", transport,
        lambda request: f"{endpoint}?{urlencode({'date': request.window_end.strftime('%Y%m%d'), 'type': 'ALLBUT0999', 'response': 'json'})}",
    )


def tpex_market_volume_adapter(transport: Callable[[str], bytes] | None = None) -> MarketVolumeAdapter:
    endpoint = "https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes"
    return MarketVolumeAdapter(
        "tpex", "TPEX", endpoint, "代號", "名稱", "成交股數", "成交金額(元)",
        "開盤", "最高", "最低", "收盤", transport,
        lambda request: f"{endpoint}?{urlencode({'date': request.window_end.strftime('%Y/%m/%d'), 'id': '', 'response': 'json'})}",
    )


@dataclass
class CompanyProfileAdapter:
    """Official company list used to distinguish stocks and resolve names."""

    source_id: str
    market: str
    endpoint: str
    code_field: str
    name_field: str
    dataset_id: str = "stock-profile"
    batch_scope: str = "market"
    transport: Callable[[str], bytes] | None = None

    def __post_init__(self) -> None:
        validate_source_url(self.endpoint)

    def fetch(self, request: CollectionRequest) -> SourceResponse:
        raw = self.transport(self.endpoint) if self.transport else ExchangeOhlcvAdapter._https(self.endpoint)
        document = json.loads(raw)
        if not isinstance(document, list) or not document:
            raise ValueError("company profile response is empty or invalid")
        observed = datetime.now(timezone.utc)
        rows = []
        for item in document:
            if not isinstance(item, dict) or self.code_field not in item or self.name_field not in item:
                raise ValueError("company profile response schema changed")
            symbol = str(item[self.code_field]).strip()
            if not re.fullmatch(r"[1-9][0-9]{3}", symbol):
                continue
            name = str(item[self.name_field]).strip()
            if not name:
                raise ValueError("company profile has unnamed stock")
            rows.append({"symbol": symbol, "stock_name": name, "market": self.market,
                         "observed_date": observed.date().isoformat(), "source_id": self.source_id,
                         "observed_at": observed.isoformat().replace("+00:00", "Z")})
        if len(rows) < 500:
            raise ValueError("company profile has too few stocks")
        return SourceResponse(rows=tuple(rows), observed_at=observed, raw_payload=raw,
                              source_url=self.endpoint)


def twse_company_profile_adapter(transport: Callable[[str], bytes] | None = None) -> CompanyProfileAdapter:
    return CompanyProfileAdapter("twse", "TWSE", "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
                                 "公司代號", "公司簡稱", transport=transport)


def tpex_company_profile_adapter(transport: Callable[[str], bytes] | None = None) -> CompanyProfileAdapter:
    return CompanyProfileAdapter("tpex", "TPEX", "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O",
                                 "SecuritiesCompanyCode", "CompanyAbbreviation", transport=transport)
