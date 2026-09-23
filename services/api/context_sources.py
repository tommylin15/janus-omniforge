"""Bounded Janus market and owner-scoped context reads for MCP."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
from typing import Any, Mapping, Sequence

from .models import ContextSelector


MAX_CONTEXT_BYTES = 32_768
DATE_FIELDS = ("trade_date", "observed_date", "published_at", "valuation_date", "updated_at", "date")
STORAGE_FIELDS = frozenset({"user_id", "artifact_ref", "artifact_reference", "object_path", "gcs_uri",
                            "storage_uri", "raw_payload", "credential", "password", "secret", "token",
                            "table", "table_name"})


@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    kind: str
    owner_scope: str
    resources: tuple[str, ...]
    freshness: str
    disclosure: str


SOURCES = (
    SourceSpec("janus-core", "core", "public", ("ohlcv", "valuation", "institutional", "financials", "events", "market-activity", "benchmark"), "published daily data", "Published Janus market data."),
    SourceSpec("janus-private-core", "private_core", "owner", ("notes", "watchlist", "trades"), "latest owner snapshot", "Private notes, watchlist, or trades selected by you."),
    SourceSpec("janus-private-mart", "private_mart", "owner", ("positions", "annual-pnl", "investment-profile", "exposure", "performance", "stress-tests"), "latest completed valuation", "Private portfolio calculations selected by you."),
)
SOURCE_BY_ID = {source.source_id: source for source in SOURCES}
class ContextSourceError(ValueError): pass


class CoreContextReader:
    """Read-only PyIceberg scan over fixed Core identifiers."""

    def __init__(self, catalog: Any) -> None: self.catalog = catalog

    @classmethod
    def from_env(cls) -> "CoreContextReader":
        from .private_pipeline import CorePriceReader
        return cls(CorePriceReader.from_env().catalog)

    def page(self, dataset_id: str, symbol: str, limit: int) -> Sequence[Mapping[str, Any]]:
        if dataset_id not in SOURCE_BY_ID["janus-core"].resources:
            raise ContextSourceError("resource is not allowed for source")
        identifier = f"core.{dataset_id.replace('-', '_')}_v1"
        if not self.catalog.table_exists(identifier): return ()
        from pyiceberg.expressions import EqualTo
        field = "benchmark_id" if dataset_id == "benchmark" else "symbol"
        return self.catalog.load_table(identifier).scan(row_filter=EqualTo(field,symbol),limit=min(limit,200)).to_arrow().to_pylist()


class ContextSourceService:
    def __init__(self, repository: Any, store: Any, core: Any) -> None:
        self.repository, self.store, self.core = repository, store, core

    @staticmethod
    def sources() -> list[dict[str, Any]]:
        return [{"source_id":source.source_id, "kind":source.kind, "capabilities":["date_range"],
                 "as_of":None, "freshness":source.freshness, "owner_scope":source.owner_scope,
                 "status":"available", "quota":{"max_records":20,"max_range_days":366,"max_output_bytes":MAX_CONTEXT_BYTES},
                 "disclosure":source.disclosure} for source in SOURCES]

    def read(self, owner_id: Any, selector: ContextSelector) -> dict[str, Any]:
        source = SOURCE_BY_ID.get(selector.source_id)
        if source is None or selector.resource not in source.resources:
            raise ContextSourceError("source or resource is not allowed")
        rows = self._date_filter(self._load(owner_id, selector), selector)
        records = [self._sanitize(row) for row in rows[:selector.limit]]
        truncated = len(rows) > len(records)
        while records and len(json.dumps(records,default=str,separators=(",", ":")).encode()) > MAX_CONTEXT_BYTES:
            records.pop(); truncated = True
        return {"schema_version":"janus.mcp.v1", "status":"partial" if truncated else "available" if records else "missing",
                "resource":selector.resource, "as_of":self._as_of(records), "records":records,
                "provenance":self._provenance(selector.source_id,records),
                "bounds":{"limit":selector.limit,"returned":len(records),"truncated":truncated,
                          "max_output_bytes":MAX_CONTEXT_BYTES},
                "disclosure":f"{source.disclosure} Data is shared with an external AI service."}

    def _load(self, owner_id: Any, selector: ContextSelector) -> Sequence[Mapping[str, Any]]:
        if selector.source_id == "janus-core":
            if not selector.symbol: raise ContextSourceError("symbol is required for Janus Core")
            return self.core.page(selector.resource,selector.symbol,200)
        if selector.resource == "notes":
            return self.store.read_notes(owner_id,self.repository.notes(owner_id,selector.symbol))
        if selector.resource == "watchlist":
            rows = self.repository.watchlist(owner_id)
            return [row for row in rows if not selector.symbol or row.get("symbol") == selector.symbol]
        if selector.resource == "trades":
            return self.repository.ledger_history(owner_id,selector.symbol,selector.year,limit=200)
        if selector.resource == "investment-profile":
            profile=self.repository.investment_profile(owner_id)
            if not profile.get("ai_context_opt_in"): raise ContextSourceError("investment profile context is not enabled")
            return [profile]
        table = {"positions":"mart_user_positions","annual-pnl":"mart_user_annual_pnl",
                 "exposure":"mart_user_exposure","performance":"mart_user_annual_performance",
                 "stress-tests":"mart_user_stress_tests"}[selector.resource]
        filters = {key:value for key,value in (("symbol",selector.symbol),("year",selector.year)) if value is not None}
        return self.store.mart(table,owner_id,**filters)

    @classmethod
    def _date_filter(cls, rows: Sequence[Mapping[str, Any]], selector: ContextSelector) -> list[Mapping[str, Any]]:
        if not selector.start_date and not selector.end_date: return list(rows)
        result=[]
        for row in rows:
            raw=next((row.get(field) for field in DATE_FIELDS if row.get(field) is not None),None)
            try: value=raw.date() if isinstance(raw,datetime) else raw if isinstance(raw,date) else date.fromisoformat(str(raw)[:10])
            except (TypeError,ValueError): continue
            if (not selector.start_date or value >= selector.start_date) and (not selector.end_date or value <= selector.end_date): result.append(row)
        return result

    @classmethod
    def _sanitize(cls, value: Any) -> Any:
        if isinstance(value,Mapping):
            return {key:cls._sanitize(item) for key,item in value.items()
                    if str(key).lower() not in STORAGE_FIELDS and not str(key).lower().endswith(("_uri","_path","_credential","_password","_secret","_token"))}
        if isinstance(value,(list,tuple)): return [cls._sanitize(item) for item in value]
        if isinstance(value,str) and len(value) > 2_000: return value[:2_000]
        return value

    @staticmethod
    def _as_of(rows: Sequence[Mapping[str, Any]]) -> str | None:
        values=[str(row[field]) for row in rows for field in DATE_FIELDS if row.get(field) is not None]
        return max(values) if values else None

    @staticmethod
    def _provenance(source_id: str, rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        fields=("source_id","provenance_id","snapshot_id","ledger_version","valuation_date")
        items={tuple((field,str(row[field])) for field in fields if row.get(field) is not None) for row in rows}
        return [{"context_source_id":source_id,**dict(item)} for item in sorted(items)] or [{"context_source_id":source_id}]
