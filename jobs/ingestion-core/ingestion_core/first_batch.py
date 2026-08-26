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
from urllib.request import Request, urlopen
from uuid import uuid4

from .adapters import CollectionRequest, SourceResponse, validate_source_url
from .control import CacheMetadata, DataState
from .stage import StageResult, StageWriter
from packages.provenance import Provenance, content_hash


def _text(value: Any) -> str | None:
    if value is None or str(value).strip() in {"", "-", "--", "N/A", "null"}:
        return None
    return str(value).strip().replace(",", "")


def _iso_date(value: Any) -> str:
    text = str(value).strip().replace("/", "-")
    if len(text) == 9 and text.count("-") == 2:
        year, month, day = text.split("-")
        text = f"{int(year) + 1911:04d}-{int(month):02d}-{int(day):02d}"
    return date.fromisoformat(text).isoformat()


def _pick(row: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in row:
            return row[name]
    return None


def normalise_benchmark(rows: Iterable[Mapping[str, Any]], benchmark_id: str = "TAIEX") -> tuple[dict[str, Any], ...]:
    result = []
    for row in rows:
        result.append({"benchmark_id": str(_pick(row, "benchmark_id", "index", "name") or benchmark_id),
                       "trade_date": _iso_date(_pick(row, "trade_date", "date")),
                       "close": _text(_pick(row, "close", "value", "index_value")),
                       "return_percent": _text(_pick(row, "return_percent", "change_percent", "change")),
                       "index_kind": str(_pick(row, "index_kind", "kind") or "price")})
    return tuple(result)


def normalise_valuation(rows: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    return tuple({"symbol": str(_pick(row, "symbol", "code")), "market": str(_pick(row, "market") or "TWSE"),
                  "observed_date": _iso_date(_pick(row, "observed_date", "date")),
                  "pe_ratio": _text(_pick(row, "pe_ratio", "pe")), "pb_ratio": _text(_pick(row, "pb_ratio", "pb")),
                  "dividend_yield_percent": _text(_pick(row, "dividend_yield_percent", "dividend_yield"))}
                 for row in rows)


def normalise_institutional(rows: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    return tuple({"symbol": str(_pick(row, "symbol", "code")), "market": str(_pick(row, "market") or "TWSE"),
                  "trade_date": _iso_date(_pick(row, "trade_date", "date")),
                  "investor_type": str(_pick(row, "investor_type", "investor") or "unknown"),
                  "buy_shares": _text(_pick(row, "buy_shares", "buy")), "sell_shares": _text(_pick(row, "sell_shares", "sell")),
                  "net_shares": _text(_pick(row, "net_shares", "net"))} for row in rows)


def normalise_financials(rows: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    return tuple({"symbol": str(_pick(row, "symbol", "code")), "fiscal_year": int(_pick(row, "fiscal_year", "year")),
                  "fiscal_quarter": int(_pick(row, "fiscal_quarter", "quarter") or 0),
                  "statement_type": str(_pick(row, "statement_type", "statement") or "unknown"),
                  "published_at": str(_pick(row, "published_at", "published") or ""),
                  "metric": str(_pick(row, "metric", "name") or "unknown"),
                  "value": _text(_pick(row, "value", "amount")), "unit": _text(_pick(row, "unit")),
                  "currency": _text(_pick(row, "currency") or "TWD")} for row in rows)


def normalise_events(rows: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    return tuple({"event_id": str(_pick(row, "event_id", "id")), "symbol": str(_pick(row, "symbol", "code") or ""),
                  "event_type": str(_pick(row, "event_type", "type") or "unknown"),
                  "published_at": str(_pick(row, "published_at", "published") or ""),
                  "effective_date": _iso_date(_pick(row, "effective_date", "effective")) if _pick(row, "effective_date", "effective") else None,
                  "severity": _text(_pick(row, "severity")), "details": _pick(row, "details", "body")} for row in rows)


def normalise_market_activity(rows: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    result = []
    for row in rows:
        result.append({"symbol": str(_pick(row, "symbol", "code")), "market": str(_pick(row, "market") or "TWSE"),
                       "trade_date": _iso_date(_pick(row, "trade_date", "date")),
                       "metric": str(_pick(row, "metric", "name")), "value": _text(_pick(row, "value", "amount")),
                       "unit": _text(_pick(row, "unit"))})
    return tuple(result)


@dataclass
class JsonDatasetAdapter:
    source_id: str
    dataset_id: str
    endpoint: str
    normalizer: Callable[[Iterable[Mapping[str, Any]]], tuple[dict[str, Any], ...]]
    transport: Callable[[str], bytes] | None = None

    def __post_init__(self) -> None:
        validate_source_url(self.endpoint)

    def fetch(self, request: CollectionRequest) -> SourceResponse:
        url = self.endpoint
        raw = self.transport(url) if self.transport else self._https(url)
        document = json.loads(raw)
        upstream_rows = document.get("data", document.get("rows", document if isinstance(document, list) else []))
        rows = tuple({**row, "source_id": self.source_id} for row in self.normalizer(upstream_rows))
        observed = datetime.combine(request.window_end, datetime.min.time(), tzinfo=timezone.utc)
        rows = tuple({**row, "observed_at": observed.isoformat().replace("+00:00", "Z")} for row in rows)
        return SourceResponse(rows=rows, observed_at=observed, raw_payload=raw, source_url=self.endpoint,
                              fields=frozenset(rows[0].keys()) if rows else frozenset())

    @staticmethod
    def _https(url: str) -> bytes:
        with urlopen(Request(url, headers={"User-Agent": "JanusAI/1.0"}), timeout=30) as response:
            return response.read()


def stage_raw_response(
    response: SourceResponse,
    request: CollectionRequest,
    *,
    bucket: str,
    store: object,
    cache_ttl: timedelta = timedelta(hours=24),
    fetched_at: datetime | None = None,
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
    staged = StageWriter(store).write_raw(
        payload=payload,
        media_type="application/json",
        extension="json",
        execution_id=request.execution_id,
        provenance=provenance,
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


def dataset_adapters(transport: Callable[[str], bytes] | None = None) -> dict[str, JsonDatasetAdapter]:
    """Configured first-batch source set; URLs are credential-free endpoints."""
    return {
        "taiex": JsonDatasetAdapter("taiex", "benchmark", "https://www.twse.com.tw/exchangeReport/MI_INDEX", lambda rows: normalise_benchmark(rows, "TAIEX"), transport),
        "tpex-benchmark": JsonDatasetAdapter("tpex-benchmark", "benchmark", "https://www.tpex.org.tw/www/zh-tw/indices/taiex", lambda rows: normalise_benchmark(rows, "TPEx"), transport),
        "twse-valuation": JsonDatasetAdapter("twse", "valuation", "https://www.twse.com.tw/exchangeReport/BWIBBU_d", normalise_valuation, transport),
        "twse-institutional": JsonDatasetAdapter("twse", "institutional", "https://www.twse.com.tw/fund/T86", normalise_institutional, transport),
        "mops": JsonDatasetAdapter("mops", "financials", "https://mops.twse.com.tw/mops/web/ajax_t164sb01", normalise_financials, transport),
        "finmind": JsonDatasetAdapter("finmind", "financials", "https://api.finmindtrade.com/api/v4/data", normalise_financials, transport),
        "twse-events": JsonDatasetAdapter("twse", "events", "https://www.twse.com.tw/news/newsDetail", normalise_events, transport),
        "twse-market-activity": JsonDatasetAdapter("twse", "market-activity", "https://www.twse.com.tw/exchangeReport/TWTB4U", normalise_market_activity, transport),
    }
