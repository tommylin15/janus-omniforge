"""Official Taiwan exchange OHLCV adapters.

The transport is injectable so production uses the standard-library HTTPS
client while tests can exercise the exact normalisation without the network.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
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
            "volume_shares": int(float(str(values[1]).replace(",", "") or 0)) * 1000,
            "turnover_twd": _number(values[2]), "change_percent": _number(values[8])}


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
        request = Request(url, headers={"User-Agent": "JanusAI/1.0"})
        with urlopen(request, timeout=30) as response:
            return response.read()


def twse_ohlcv_adapter(transport: Callable[[str], bytes] | None = None) -> ExchangeOhlcvAdapter:
    return ExchangeOhlcvAdapter("twse", "TWSE", "https://www.twse.com.tw/exchangeReport/STOCK_DAY", parse_twse, transport)


def tpex_ohlcv_adapter(transport: Callable[[str], bytes] | None = None) -> ExchangeOhlcvAdapter:
    return ExchangeOhlcvAdapter("tpex", "TPEX", "https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes", parse_tpex, transport)
