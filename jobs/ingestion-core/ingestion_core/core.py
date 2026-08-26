"""Deterministic Core OHLCV materialisation and dataset-ready evidence."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
from typing import Any, Protocol

from .dq import DqResult, merge_without_null_overwrite, validate_ohlcv
from .stage import ObjectStore
from packages.provenance import Provenance, content_hash


class EventSink(Protocol):
    def publish(self, event: dict[str, Any]) -> None: ...


class LocalEventSink:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
    def publish(self, event: dict[str, Any]) -> None:
        self.events.append(event)


@dataclass(frozen=True)
class CoreResult:
    rows: tuple[dict[str, Any], ...]
    row_count: int
    content_hash: str
    date_from: str | None
    date_to: str | None
    null_profile: dict[str, int]
    warning_count: int
    quarantined_count: int
    provenance_id: str


class CoreWriter:
    def __init__(self, store: ObjectStore, events: EventSink | None = None) -> None:
        self.store, self.events = store, events or LocalEventSink()

    def write(self, *, rows: list[dict[str, Any]], execution_id: str, analysis_as_of: date,
              provenance: Provenance, existing: list[dict[str, Any]] | None = None,
              dq: DqResult | None = None) -> CoreResult:
        result = dq or validate_ohlcv(rows, analysis_as_of=analysis_as_of)
        merged: dict[tuple[str, str], dict[str, Any]] = {
            (str(row["symbol"]), str(row["trade_date"])): dict(row) for row in (existing or [])
        }
        for row in result.accepted:
            key = (str(row["symbol"]), str(row["trade_date"]))
            merged[key] = merge_without_null_overwrite(merged.get(key, {}), dict(row))
        materialized = sorted(merged.values(), key=lambda row: (str(row["symbol"]), str(row["trade_date"])))
        for row in materialized:
            row.update(provenance_id=provenance.provenance_id, execution_id=execution_id,
                       source_id=provenance.source_id,
                       observed_at=provenance.observed_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"))
        logical_rows = [{key: value for key, value in row.items() if key not in {"execution_id", "provenance_id"}} for row in materialized]
        digest = content_hash(json.dumps(logical_rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode())
        payload = json.dumps(materialized, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()
        prefix = f"core/ohlcv/v1/symbol={materialized[0]['symbol'] if materialized else 'unknown'}"
        self.store.create(f"{prefix}/data.json", payload, "application/json")
        summary = {"schema_version": "1.0.0", "dataset_id": "core", "execution_id": execution_id,
                   "row_count": len(materialized), "content_hash": digest,
                   "date_from": min((str(row["trade_date"]) for row in materialized), default=None),
                   "date_to": max((str(row["trade_date"]) for row in materialized), default=None),
                   "null_profile": {field: sum(row.get(field) is None for row in materialized) for field in ("open", "high", "low", "close", "volume_shares", "turnover_twd", "change_percent")},
                   "warning_count": len(result.warnings), "quarantined_count": len(result.quarantined),
                   "provenance_id": provenance.provenance_id}
        self.store.create(f"{prefix}/metadata.json", json.dumps(summary, sort_keys=True).encode(), "application/json")
        self.events.publish({"eventType": "core.dataset.ready.v1", "executionId": execution_id,
                             "datasetId": "core", "schemaVersion": "1.0.0", "rowCount": len(materialized)})
        return CoreResult(tuple(materialized), **{key: summary[key] for key in ("row_count", "content_hash", "date_from", "date_to", "null_profile", "warning_count", "quarantined_count", "provenance_id")})
