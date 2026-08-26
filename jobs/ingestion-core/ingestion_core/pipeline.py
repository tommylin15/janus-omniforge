"""One-shot 2330 Source -> Stage -> Core orchestration.

The runner deliberately accepts repositories and transports as dependencies;
the same code is used by the local integration tests and the Cloud Run Job.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
from typing import Any, Mapping
from uuid import uuid4

from packages.provenance import Provenance, content_hash
from .adapters import SourceAdapter
from .control import CollectionConfig, SQLiteControlPlane, Stock
from .core import CoreResult, CoreWriter, EventSink
from .dq import validate_ohlcv
from .framework import IngestionFramework, IngestionResult
from .stage import ObjectStore, StageWriter


EXPECTED_OHLCV_FIELDS = frozenset({"symbol", "market", "trade_date", "open", "high", "low", "close", "volume_shares", "turnover_twd", "change_percent", "source_id", "observed_at"})


@dataclass(frozen=True)
class ClosedLoopResult:
    execution_id: str
    trace_id: str
    ingestion: IngestionResult
    core: CoreResult | None
    raw_object_names: tuple[str, ...]
    quarantine_prefixes: tuple[str, ...]


async def run_2330(*, control: SQLiteControlPlane, store: ObjectStore,
                   adapters: Mapping[str, SourceAdapter], as_of: date,
                   events: EventSink | None = None, existing_core: list[dict[str, Any]] | None = None) -> ClosedLoopResult:
    control.upsert_stock(Stock("2330", "台積電", "TWSE"))
    control.put_collection_config(CollectionConfig("twse-ohlcv-2330", "ohlcv", tuple(adapters), EXPECTED_OHLCV_FIELDS,
                                                    market="TWSE", lookback_days=30, overlap_days=2, batch_scope="symbol"), ["2330"])
    execution = control.enqueue_collection("twse-ohlcv-2330", ["2330"])
    ingestion = await IngestionFramework(control).collect(execution.execution_id, adapters, as_of=as_of)
    raw_names: list[str] = []
    quarantine: list[str] = []
    core_result: CoreResult | None = None
    if ingestion.rows:
        primary = next((adapter for adapter in adapters.values() if getattr(adapter, "source_id", None) == "twse"), next(iter(adapters.values())))
        raw = json.dumps([dict(row) for row in ingestion.rows], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        observed = datetime.combine(as_of, datetime.min.time(), tzinfo=timezone.utc)
        provenance = Provenance(str(uuid4()), getattr(primary, "source_id", "twse"), getattr(primary, "endpoint", "https://www.twse.com.tw"), "ohlcv", observed, None, datetime.now(timezone.utc), content_hash(raw), is_fallback=bool(control.list_items(execution.execution_id)[0].is_fallback))
        staged = StageWriter(store).write_raw(payload=raw, media_type="application/json", extension="json", execution_id=execution.execution_id, provenance=provenance)
        raw_names.append(staged.object_name)
        dq = validate_ohlcv(ingestion.rows, analysis_as_of=as_of)
        for _, violations in dq.quarantined:
            quarantine.append(StageWriter(store).quarantine(payload=raw, media_type="application/json", extension="json", execution_id=execution.execution_id, provenance=provenance, violations=[violation.to_dict() for violation in violations]))
        core_result = CoreWriter(store, events).write(rows=list(ingestion.rows), execution_id=execution.execution_id, analysis_as_of=as_of, provenance=provenance, existing=existing_core, dq=dq)
    return ClosedLoopResult(execution.execution_id, execution.trace_id, ingestion, core_result, tuple(raw_names), tuple(quarantine))
