"""One-shot Cloud Run Job entrypoint for raw Stage collection."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from dataclasses import replace
from hashlib import sha256
from http.client import IncompleteRead
import json
import os
import sys
from time import monotonic, sleep
from urllib.error import HTTPError, URLError
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .adapters import CollectionRequest, SourceResponse
from .control import DataState, ExecutionItem, ExecutionStatus, TriggerType
from .dq import validate_ohlcv
from .postgres_control import PostgreSQLControlPlane
from .first_batch import dataset_adapters, effective_trading_day, stage_raw_response
from .liquid_500 import rotate_from_core
from .stage import GcsObjectStore, StageResult, StageWriter
from packages.duckdb_query import DuckDBIcebergCore


try:
    TAIPEI = ZoneInfo("Asia/Taipei")
except ZoneInfoNotFoundError:  # Minimal containers may omit the optional tzdata package.
    TAIPEI = timezone(timedelta(hours=8))


SPARSE_DATASETS = frozenset({"finmind", "twse-events"})


def _current_core_fences(core):
    """Fence unchanged tables too, so a price-only fill preserves financial/event inputs."""
    tables = {}
    with core.mutation_lock():
        for dataset in core.IDENTIFIERS:
            if core.table_exists(dataset):
                table = core.catalog.load_table(core.table_identifier(dataset))
                snapshot = table.current_snapshot()
                if snapshot:
                    tables[core.table_identifier(dataset)] = {"rows": int(snapshot.summary["total-records"]),
                        "snapshot_id": snapshot.snapshot_id, "metadata_location": table.metadata_location}
    return tables


def _core_ready_event(*, core_bucket: str, execution_id: str, config_id: str,
                      analysis_as_of: str, iceberg_tables: dict[str, dict[str, object]],
                      symbols: tuple[str, ...], market: str,
                      industries: list[dict[str, object]] | None = None) -> dict[str, object] | None:
    if not iceberg_tables:
        return None
    tables_payload = json.dumps(iceberg_tables, sort_keys=True, separators=(",", ":")).encode()
    snapshot_id = f"sha256:{sha256(tables_payload).hexdigest()}"
    manifest = {
        "artifact_kind": "core_snapshot_v1", "execution_id": execution_id,
        "analysis_as_of": analysis_as_of, "snapshot_id": snapshot_id, "iceberg_tables": iceberg_tables,
    }
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    object_name = f"executions/{execution_id}/core-snapshot.json"
    store = GcsObjectStore(core_bucket)
    if not store.create(object_name, payload, "application/json") and store.read(object_name) != payload:
        raise RuntimeError("immutable Core snapshot manifest conflict")
    scopes = [{"type": "market", "id": market, "symbols": list(symbols)}]
    for item in industries or []:
        if not isinstance(item, dict):
            continue
        members = sorted(set(map(str, item.get("symbols", []))) & set(symbols))
        if str(item.get("id", "")).strip() and members:
            scopes.append({"type": "industry", "id": str(item["id"]), "name": str(item.get("name", item["id"])), "symbols": members})
    scopes.extend({"type": "symbol", "id": symbol, "symbols": [symbol]} for symbol in symbols)
    return {
        "eventType": "core.dataset.ready.v1", "executionId": execution_id, "configId": config_id,
        "datasetId": "core", "schemaVersion": "1.0.0", "rowCount": sum(int(value["rows"]) for value in iceberg_tables.values()),
        "analysisAsOf": analysis_as_of, "coreSnapshotId": snapshot_id,
        "coreSnapshotUri": f"gs://{core_bucket}/{object_name}",
        "coreSnapshotHash": f"sha256:{sha256(payload).hexdigest()}",
        "martSchemaVersion": os.environ.get("MART_SCHEMA_VERSION", "1"),
        "featureVersion": os.environ.get("MART_FEATURE_VERSION", "2"),
        "modelVersion": os.environ.get("MART_MODEL_VERSION", "deterministic-v1"),
        "governanceSnapshotVersion": os.environ.get("MART_GOVERNANCE_VERSION", "gov-1"),
        "scopes": scopes,
    }


def _trigger_mart(analysis_execution_id: str | None, *, delay_seconds: int = 10) -> dict[str, object]:
    job = os.environ.get("MART_JOB", "").strip()
    project = os.environ.get("GCP_PROJECT_ID", "").strip()
    region = os.environ.get("GCP_REGION", "us-central1").strip()
    if not analysis_execution_id or not job:
        return {"status": "not_required"}
    try:
        import time
        import google.auth
        from google.auth.transport.requests import AuthorizedSession
        credentials, detected_project = google.auth.default(scopes=("https://www.googleapis.com/auth/cloud-platform",))
        project = project or detected_project or ""
        if not project:
            raise ValueError("GCP_PROJECT_ID is required for Mart trigger")
        # Wait for the DB commit to be visible to the mart job before it starts.
        time.sleep(delay_seconds)
        response = AuthorizedSession(credentials).post(
            f"https://run.googleapis.com/v2/projects/{project}/locations/{region}/jobs/{job}:run",
            json={}, timeout=10,
        )
        response.raise_for_status()
        return {"status": "accepted", "analysis_execution_id": analysis_execution_id}
    except Exception as error:
        # The persisted queue remains authoritative and can be safely retriggered.
        return {"status": "deferred", "analysis_execution_id": analysis_execution_id,
                "error_code": type(error).__name__.upper()[:64]}
def _holidays(value: str) -> set[date]:
    return {date.fromisoformat(item.strip()) for item in value.split(",") if item.strip()}


def _control_plane() -> PostgreSQLControlPlane:
    from packages.postgres_bundle import load_postgres_bundle
    load_postgres_bundle("JANUS_INGESTION_POSTGRES_BUNDLE", {
        "CONTROL_DB_PASSWORD": ("ingestion_control_password", "control_password"),
        "CATALOG_DB_PASSWORD": ("ingestion_catalog_password", "catalog_password"),
    })
    required = ("CONTROL_DB_HOST", "CONTROL_DB_NAME", "CONTROL_DB_USER", "CONTROL_DB_PASSWORD")
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    if missing:
        raise ValueError(f"missing control database settings: {','.join(missing)}")
    try:
        import psycopg
    except ImportError as error:
        raise RuntimeError("PostgreSQL runtime dependency is unavailable") from error

    def connect():
        return psycopg.connect(
            host=os.environ["CONTROL_DB_HOST"], dbname=os.environ["CONTROL_DB_NAME"],
            user=os.environ["CONTROL_DB_USER"], password=os.environ["CONTROL_DB_PASSWORD"],
            sslmode=os.environ.get("CONTROL_DB_SSLMODE", "require"), connect_timeout=5,
        )

    return PostgreSQLControlPlane(connect)


def _iceberg_core(core_bucket: str, *, read_only: bool = False) -> DuckDBIcebergCore:
    from packages.postgres_bundle import load_postgres_bundle
    load_postgres_bundle("JANUS_INGESTION_POSTGRES_BUNDLE", {
        "CONTROL_DB_PASSWORD": ("ingestion_control_password", "control_password"),
        "CATALOG_DB_PASSWORD": ("ingestion_catalog_password", "catalog_password"),
    })
    required = ("CATALOG_DB_HOST", "CATALOG_DB_NAME", "CATALOG_DB_USER", "CATALOG_DB_PASSWORD", "GCP_PROJECT_ID")
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    if missing:
        raise ValueError(f"missing Iceberg catalog settings: {','.join(missing)}")
    warehouse = os.environ.get("ICEBERG_WAREHOUSE", f"gs://{core_bucket}/warehouse").strip()
    if not warehouse.startswith(f"gs://{core_bucket}/"):
        raise ValueError("ICEBERG_WAREHOUSE must remain inside CORE_BUCKET")
    catalog_password = os.environ["CATALOG_DB_PASSWORD"].strip().lstrip("\ufeff")
    return DuckDBIcebergCore.from_postgres(
        host=os.environ["CATALOG_DB_HOST"],
        dbname=os.environ["CATALOG_DB_NAME"],
        user=os.environ["CATALOG_DB_USER"],
        password=catalog_password,
        warehouse=warehouse,
        project_id=os.environ["GCP_PROJECT_ID"],
        sslmode=os.environ.get("CATALOG_DB_SSLMODE", "require"),
        read_only=read_only,
    )


def _market_universe(control: object, fallback_symbols: tuple[str, ...]) -> tuple[dict[str, object], tuple[str, ...]]:
    read = getattr(control, "liquid_500_snapshot", None)
    universe = read() if read is not None else {"status": "missing", "items": []}
    if universe["status"] == "available":
        if len(universe["items"]) != 500:
            raise ValueError("effective liquid 500 must contain exactly 500 stocks")
        if any(item["market"] != "TWSE" for item in universe["items"]):
            raise ValueError("effective liquid 500 must contain TWSE-listed stocks only")
        return universe, tuple(item["symbol"] for item in universe["items"])
    return universe, fallback_symbols


def _limit_response(response: SourceResponse, symbols: tuple[str, ...], *, dataset_id: str = "") -> SourceResponse:
    """Keep only selected stock rows before Stage persistence; benchmarks stay market-wide."""
    if dataset_id in {"market-volume", "stock-profile"}:
        return response  # Ranking input retains the full exchange batch in Stage and Core.
    if not response.rows or not any("symbol" in row for row in response.rows):
        return response
    selected = {symbol.upper() for symbol in symbols}
    rows = tuple(row for row in response.rows if str(row.get("symbol", "")).upper() in selected)
    payload = json.dumps([dict(row) for row in rows], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return replace(response, rows=rows, fields=frozenset(rows[0].keys()) if rows else response.fields, raw_payload=payload)


def _empty_is_nonfatal(adapter_key: str) -> bool:
    """Financial and event sources can legitimately have no rows in a window."""
    return adapter_key in SPARSE_DATASETS


def _skip_symbol_adapter_for_500(adapter: object, active_500: bool) -> bool:
    return active_500 and getattr(adapter, "batch_scope", "market") == "symbol"


def _coverage_status(items: list[dict[str, object]], active_500: bool) -> str:
    if not active_500:
        return "not_applicable"
    statuses = {str(item.get("status", "")) for item in items}
    if "failed" in statuses:
        return "failed"
    if statuses & {"partial", "missing", "blocked", "cached_unverified"}:
        return "partial"
    return "complete"


def _finish_collection(control: object, execution_id: str, summary: dict[str, object]):
    if summary.get("coverage_status") == "partial":
        if summary.get("core_created", 0) or summary.get("core_reused", 0) or summary.get("core_updated", 0):
            return control.complete_collection(execution_id, summary.get("ready_event"), partial=True)
        return control.transition_execution(execution_id, ExecutionStatus.PARTIAL), None
    return control.complete_collection(execution_id, summary.get("ready_event"))


def _cursor_key(source_id: str, dataset_id: str, symbols: tuple[str, ...]) -> str:
    scope = ",".join(symbols) if len(symbols) == 1 else "market"
    return f"{source_id}:{dataset_id}:{scope}"


def _cursor_is_fresh(control: object, cursor_key: str, target: date) -> bool:
    cursor = control.get_cursor(cursor_key)
    return cursor.last_success_at is not None and cursor.last_success_at.date() >= target


def _should_collect(adapter_key: str, source_id: str, dataset_id: str, symbols: tuple[str, ...],
                    target: date, control: object, *, force: bool = False) -> tuple[bool, str]:
    """Use committed cursors as the freshness fence; FinMind is fallback-only."""
    if force:
        return True, "forced"
    if _cursor_is_fresh(control, _cursor_key(source_id, dataset_id, symbols), target):
        return False, "already_fresh"
    if adapter_key == "finmind" and _cursor_is_fresh(control, _cursor_key("mops", dataset_id, ()), target):
        return False, "official_source_fresh"
    return True, "missing_target"


def _fetch_source(adapter: object, request: CollectionRequest) -> SourceResponse:
    try:
        return adapter.fetch(request)
    except HTTPError as error:
        if error.code not in {500, 502, 503, 504}:
            raise
    except (json.JSONDecodeError, IncompleteRead, TimeoutError, URLError):
        pass
    sleep(1)
    return adapter.fetch(request)


def _requested_dates(*, today: date, holidays: set[date], single: str = "", start: str = "", end: str = "") -> tuple[date, ...]:
    """Resolve bounded single-day or interval replay input for a job run."""
    if single.strip() and (start.strip() or end.strip()):
        raise ValueError("INGESTION_DATE cannot be combined with BACKFILL_START_DATE or BACKFILL_END_DATE")
    if bool(start.strip()) != bool(end.strip()):
        raise ValueError("BACKFILL_START_DATE and BACKFILL_END_DATE must be supplied together")
    if single.strip():
        requested = date.fromisoformat(single.strip())
        return (effective_trading_day(requested, holidays=holidays),)
    if start.strip():
        first, last = date.fromisoformat(start.strip()), date.fromisoformat(end.strip())
        if first > last:
            raise ValueError("BACKFILL_START_DATE must not be after BACKFILL_END_DATE")
        if (last - first).days > 366:
            raise ValueError("backfill range cannot exceed 367 calendar days")
        return tuple(effective_trading_day(day, holidays=holidays) for day in (first + timedelta(days=offset) for offset in range((last - first).days + 1)))
    return (effective_trading_day(today - timedelta(days=1), holidays=holidays),)


def collect_stage(*, execution_id: str | None = None, symbols: tuple[str, ...] | None = None,
                  config_id: str | None = None, request_options: dict[str, object] | None = None,
                  control: object | None = None, trace_id: str | None = None) -> dict[str, object]:
    bucket = os.environ.get("STAGE_BUCKET", "").strip()
    core_bucket = os.environ.get("CORE_BUCKET", "").strip()
    if not bucket:
        raise ValueError("STAGE_BUCKET is required")
    if not core_bucket:
        raise ValueError("CORE_BUCKET is required")
    configured = dataset_adapters()
    options = request_options or {}
    selected_sources = set(options.get("source_ids", ()))
    dataset_setting = os.environ.get("INGESTION_DATASETS", "").strip()
    default_datasets = ",".join(key for key, adapter in configured.items() if adapter.dataset_id != "ohlcv")
    selected = tuple(item.strip() for item in (dataset_setting or default_datasets).split(",") if item.strip())
    if selected_sources:
        selected = tuple(key for key in selected if key in selected_sources or configured[key].source_id in selected_sources)
    unknown = sorted(set(selected) - set(configured))
    if unknown:
        raise ValueError(f"unsupported INGESTION_DATASETS: {','.join(unknown)}")

    # This job runs before market open, so the current calendar date cannot be
    # a completed observation day. Exchange holidays can be injected without
    # rebuilding the image.
    owned_control = control is None
    control = control or _control_plane()
    config_id = config_id or os.environ.get("CONTROL_COLLECTION_CONFIG", "first-batch")
    config = control.get_collection_config(config_id)
    allowed_sources = set(config.source_ids)
    selected = tuple(key for key in selected if configured[key].source_id in allowed_sources)
    if not selected:
        if owned_control:
            control.close()
        raise ValueError("no enabled sources selected")
    symbols = symbols or control.config_symbols(config_id)
    if not symbols:
        if owned_control:
            control.close()
        raise ValueError("control database returned no enabled ingestion symbols")
    universe, market_symbols = _market_universe(control, symbols)
    active_500 = universe["status"] == "available"
    if active_500 and not selected:
        raise ValueError("no TWSE sources selected for listed-only liquid 500")
    members_by_market = {
        market: {item["symbol"] for item in universe["items"] if item["market"] == market}
        for market in ("TWSE",)
    } if active_500 else {}
    holding_symbols = set(control.portfolio_coverage_symbols()) if active_500 and hasattr(control, "portfolio_coverage_symbols") else set()
    local_now = datetime.now(TAIPEI)
    schedule_setting = control.get_admin_setting("schedule")
    schedule = schedule_setting[0] if schedule_setting and isinstance(schedule_setting[0], dict) else {}
    holidays = _holidays(os.environ.get("MARKET_HOLIDAYS", "")) | {
        date.fromisoformat(item) for item in schedule.get("holiday_overrides", ())
    }
    dates = tuple(dict.fromkeys(_requested_dates(
        today=local_now.date(), holidays=holidays,
        single=str(options.get("date", os.environ.get("INGESTION_DATE", ""))),
        start=str(options.get("start_date", os.environ.get("BACKFILL_START_DATE", ""))),
        end=str(options.get("end_date", os.environ.get("BACKFILL_END_DATE", ""))))))
    persisted_execution = execution_id is not None
    execution_id = execution_id or str(uuid4())
    trace_id = trace_id or str(uuid4())
    store = GcsObjectStore(bucket)
    stage_writer = StageWriter(store)
    core = _iceberg_core(core_bucket)
    staged: list[str] = []
    core_created = core_updated = core_reused = 0
    iceberg_tables: dict[str, dict[str, object]] = {}
    failures: list[dict[str, str]] = []
    empty_items: list[dict[str, object]] = []
    skipped_items: list[dict[str, object]] = []
    stage_results: list[StageResult] = []
    dq_items: list[dict[str, object]] = []
    coverage_items: list[dict[str, object]] = []
    holding_prices_by_date: dict[str, set[str]] = {}
    serving_projection = None
    serving_published = 0
    if os.environ.get("STOCK_SERVING_PROJECTION_ENABLED", "false").lower() in {"1", "true", "yes"}:
        from .serving_projection import StockServingProjection
        serving_projection = StockServingProjection.from_env()
    execution_scoped = os.environ.get("STAGE_EXECUTION_SCOPED", "true").lower() in {"1", "true", "yes"}
    force_refresh = os.environ.get("FORCE_REFRESH", "false").lower() in {"1", "true", "yes"}

    for as_of in dates:
        for key in selected:
            adapter = configured[key]
            if active_500 and key == "finmind":
                coverage_items.append({"date": as_of.isoformat(), "dataset": adapter.dataset_id,
                                       "source": adapter.source_id, "status": "blocked",
                                       "reason": "no_compliant_market_batch_endpoint"})
                continue
            if _skip_symbol_adapter_for_500(adapter, active_500):
                # The approved market-volume batches provide the 500 prices and off-list holdings.
                skipped_items.append({"dataset": key, "date": as_of.isoformat(), "reason": "market_batch_only"})
                continue
            if (key == "finmind" or getattr(adapter, "batch_scope", "market") == "symbol") and len(symbols) > 50:
                coverage_items.append({"date": as_of.isoformat(), "dataset": adapter.dataset_id,
                                       "source": adapter.source_id, "status": "blocked",
                                       "reason": "symbol_source_exceeds_50"})
                continue
            scoped_symbols = (market_symbols if active_500 and getattr(adapter, "batch_scope", "market") == "market"
                              and adapter.dataset_id not in {"market-volume", "stock-profile", "benchmark"}
                              else symbols)
            request_symbols = tuple((symbol,) for symbol in scoped_symbols) if key == "finmind" or getattr(adapter, "batch_scope", "market") == "symbol" else (scoped_symbols,)
            for requested_symbols in request_symbols:
                price_coverage: dict[str, object] | None = None
                market = "ALL" if adapter.source_id == "mops" else "TWSE"
                expected = (members_by_market[market] if active_500 and adapter.source_id == "twse"
                            else set(market_symbols) if active_500 and adapter.source_id == "mops"
                            else set(requested_symbols))
                if adapter.dataset_id == "benchmark":
                    expected = {"TAIEX"}
                item_scope = "market" if len(requested_symbols) > 50 else ",".join(requested_symbols)
                item_key = f"{key}:{as_of.isoformat()}:{item_scope}"
                should_collect, reason = _should_collect(
                    key, adapter.source_id, adapter.dataset_id, requested_symbols, as_of, control,
                    force=force_refresh,
                )
                if not should_collect:
                    skipped_items.append({"dataset": key, "date": as_of.isoformat(), "reason": reason})
                    control.record_health(
                        adapter.source_id, adapter.dataset_id, state=DataState.SUCCESS, latency_ms=0,
                        fetched_at=datetime.now(timezone.utc), latest_observation_at=datetime.combine(as_of, datetime.min.time(), timezone.utc),
                        expected_symbols=0, received_symbols=0, cache_hit=True,
                    )
                    coverage_items.append({"date": as_of.isoformat(), "dataset": adapter.dataset_id,
                                           "source": adapter.source_id, "market": market,
                                           "expected": sorted(expected), "received": None, "missing": None,
                                           "status": "cached_unverified", "reason": reason})
                    if persisted_execution:
                        control.save_item(ExecutionItem(execution_id, item_key, adapter.source_id, adapter.dataset_id,
                                                       DataState.SUCCESS, 0, 0, True, False, None, reason))
                    continue
                request = CollectionRequest(
                    execution_id=execution_id,
                    trace_id=trace_id,
                    source_id=adapter.source_id,
                    dataset_id=adapter.dataset_id,
                    market="TWSE" if market == "ALL" else market,
                    symbols=requested_symbols,
                    window_start=as_of - timedelta(days=400) if adapter.dataset_id == "financials" else as_of,
                    window_end=as_of,
                    timeout_seconds=30,
                )
                try:
                    response = _limit_response(_fetch_source(adapter, request), requested_symbols, dataset_id=adapter.dataset_id)
                    if not response.rows:
                        if _empty_is_nonfatal(key):
                            empty_items.append({
                                "dataset": key,
                                "date": as_of.isoformat(),
                                "symbols": list(requested_symbols),
                            })
                            control.record_health(
                                adapter.source_id, adapter.dataset_id, state=DataState.EMPTY, latency_ms=0,
                                fetched_at=datetime.now(timezone.utc), expected_symbols=len(requested_symbols), received_symbols=0,
                            )
                            if persisted_execution:
                                control.save_item(ExecutionItem(execution_id, item_key, adapter.source_id, adapter.dataset_id,
                                                               DataState.EMPTY, 0, 0, False, key == "finmind", None, "source returned no rows"))
                            continue
                        raise ValueError("source returned no rows for configured symbols")
                    quarantine_violations: list[dict[str, str]] = []
                    if adapter.dataset_id == "ohlcv":
                        dq = validate_ohlcv((dict(row) for row in response.rows), analysis_as_of=as_of)
                        quarantine_violations = [
                            violation.to_dict()
                            for _, violations in dq.quarantined
                            for violation in violations
                        ]
                        fields = ("open", "high", "low", "close", "volume_shares", "turnover_twd", "change_percent")
                        dq_items.append({
                            "dataset": key,
                            "date": as_of.isoformat(),
                            "symbols": list(requested_symbols),
                            "accepted": len(dq.accepted),
                            "quarantined": len(dq.quarantined),
                            "warnings": len(dq.warnings),
                            "null_profile": {field: sum(row.get(field) is None for row in dq.accepted) for field in fields},
                        })
                        response = replace(response, rows=dq.accepted,
                                           fields=frozenset(dq.accepted[0].keys()) if dq.accepted else frozenset())
                    result, _ = stage_raw_response(
                        response, request, bucket=bucket, store=store,
                        execution_scoped=execution_scoped,
                        quarantine_violations=quarantine_violations,
                    )
                    staged.append(result.object_name)
                    stage_results.append(result)
                    response = replace(response, raw_payload=None)
                    if not response.rows:
                        raise ValueError("OHLCV DQ rejected all rows")
                    core_dataset_id = getattr(adapter, "core_dataset_id", None) or adapter.dataset_id
                    committed = core.write(dataset_id=core_dataset_id,
                                           rows=list(response.rows),
                                           execution_id=execution_id, provenance_id=result.idempotency_key,
                                           source_id=adapter.source_id, partition_date=as_of)
                    if serving_projection is not None and core_dataset_id in serving_projection.DATASETS:
                        serving_published += serving_projection.publish(
                            core_dataset_id,
                            [dict(row) for row in response.rows],
                            execution_id=execution_id,
                            provenance_id=result.idempotency_key,
                            source_id=adapter.source_id,
                            core_snapshot_id=committed.snapshot_id,
                        )
                    if adapter.dataset_id == "stock-profile":
                        control.refresh_official_stock_profiles(tuple(dict(row) for row in response.rows))
                    core_created += committed.inserted
                    core_updated += committed.updated
                    core_reused += committed.reused
                    iceberg_tables[committed.table_identifier] = {
                        "rows": committed.row_count,
                        "snapshot_id": committed.snapshot_id,
                        "metadata_location": committed.metadata_location,
                    }
                    if adapter.dataset_id == "market-volume":
                        target_symbols = (set(market_symbols) if active_500 else set(symbols)) | holding_symbols
                        price_rows = tuple({key: row.get(key) for key in
                                            ("symbol", "market", "trade_date", "open", "high", "low", "close",
                                             "volume_shares", "turnover_twd", "source_id", "observed_at")}
                                           | {"change_percent": None}
                                           for row in response.rows if row["symbol"] in target_symbols)
                        received_prices = {row["symbol"] for row in price_rows if row.get("close") is not None}
                        coverage_items.append({"date": as_of.isoformat(), "dataset": "ohlcv",
                                               "source": adapter.source_id, "market": market,
                                               "expected": sorted(expected),
                                               "received": sorted(expected & received_prices),
                                               "missing": sorted(expected - received_prices),
                                               "status": "complete" if expected <= received_prices else "partial",
                                               "stage_provenance_id": result.idempotency_key,
                                               "snapshot_id": committed.snapshot_id})
                        price_coverage = coverage_items[-1]
                        if price_rows:
                            checked = validate_ohlcv(price_rows, analysis_as_of=as_of)
                            received_prices = {row["symbol"] for row in checked.accepted}
                            holding_prices_by_date.setdefault(as_of.isoformat(), set()).update(received_prices)
                            price_coverage.update(received=sorted(expected & received_prices),
                                missing=sorted(expected - received_prices),
                                status="complete" if expected <= received_prices else "partial",
                                quarantined_rows=len(checked.quarantined))
                            if checked.accepted:
                                price_rows_to_publish = [dict(row) for row in checked.accepted]
                                price_commit = core.write(dataset_id="ohlcv", rows=price_rows_to_publish,
                                                          execution_id=execution_id, provenance_id=result.idempotency_key,
                                                          source_id=adapter.source_id, partition_date=as_of)
                                if serving_projection is not None:
                                    serving_published += serving_projection.publish(
                                        "ohlcv",
                                        price_rows_to_publish,
                                        execution_id=execution_id,
                                        provenance_id=result.idempotency_key,
                                        source_id=adapter.source_id,
                                        core_snapshot_id=price_commit.snapshot_id,
                                    )
                                core_created += price_commit.inserted
                                core_updated += price_commit.updated
                                core_reused += price_commit.reused
                                iceberg_tables[price_commit.table_identifier] = {
                                    "rows": price_commit.row_count,
                                    "snapshot_id": price_commit.snapshot_id,
                                    "metadata_location": price_commit.metadata_location,
                                }
                                price_coverage["snapshot_id"] = price_commit.snapshot_id
                    if adapter.dataset_id in {"valuation", "institutional", "financials", "benchmark", "financing", "securities_lending_short", "day_trading"} and active_500:
                        date_field = "observed_date" if adapter.dataset_id == "valuation" else "trade_date"
                        received = {str(row.get("benchmark_id" if adapter.dataset_id == "benchmark" else "symbol", ""))
                                    for row in response.rows
                                    if (adapter.dataset_id == "financials" or str(row.get(date_field, ""))[:10] == as_of.isoformat())
                                    and (adapter.dataset_id not in {"financing", "securities_lending_short", "day_trading"}
                                         or row.get("value") is not None)}
                        coverage_items.append({"date": as_of.isoformat(), "dataset": adapter.dataset_id,
                                               "source": adapter.source_id, "market": market,
                                               "expected": sorted(expected), "received": sorted(expected & received),
                                               "missing": sorted(expected - received),
                                               "status": "complete" if expected <= received else "partial",
                                               "stage_provenance_id": result.idempotency_key,
                                               "snapshot_id": committed.snapshot_id})
                    observed_at = datetime.combine(as_of, datetime.min.time(), timezone.utc)
                    control.advance_cursor(_cursor_key(adapter.source_id, adapter.dataset_id, requested_symbols), observed_at, successful=True)
                    item_coverage = (price_coverage if price_coverage is not None else
                                     coverage_items[-1] if coverage_items and
                                     coverage_items[-1].get("dataset") == adapter.dataset_id else None)
                    state = (DataState.FALLBACK if key == "finmind" else
                             DataState.PARTIAL if active_500 and item_coverage and
                             item_coverage.get("missing") else DataState.SUCCESS)
                    control.record_health(
                        adapter.source_id, adapter.dataset_id, state=state, latency_ms=0,
                        fetched_at=datetime.now(timezone.utc), latest_observation_at=observed_at,
                        expected_symbols=len(expected),
                        received_symbols=len({str(row.get("benchmark_id" if adapter.dataset_id == "benchmark" else "symbol", ""))
                                              for row in response.rows} & expected),
                    )
                    if persisted_execution:
                        control.save_item(ExecutionItem(execution_id, item_key, adapter.source_id, adapter.dataset_id,
                                                       state, len(response.rows), 0, False, key == "finmind", None, "Core committed"))
                except Exception as error:
                    failures.append({"dataset": key, "date": as_of.isoformat(), "error": type(error).__name__, "message": "source collection failed"})
                    if price_coverage is not None:
                        price_coverage.update(status="failed", received=[], missing=price_coverage["expected"], snapshot_id=None)
                    if active_500:
                        coverage_items.append({"date": as_of.isoformat(), "dataset": adapter.dataset_id,
                                               "source": adapter.source_id, "market": market,
                                               "expected": sorted(expected), "received": [],
                                               "missing": sorted(expected), "status": "failed",
                                               "reason": type(error).__name__.upper()[:64]})
                    control.record_health(
                        adapter.source_id, adapter.dataset_id, state=DataState.FAILED, latency_ms=0,
                        fetched_at=datetime.now(timezone.utc), expected_symbols=len(expected), received_symbols=0,
                    )
                    if persisted_execution:
                        control.save_item(ExecutionItem(execution_id, item_key, adapter.source_id, adapter.dataset_id,
                                                       DataState.FAILED, 0, 0, False, key == "finmind",
                                                       type(error).__name__.upper(), "source collection failed"))

    core_committed = bool(iceberg_tables)
    if core_committed:
        for dataset_id in sorted({getattr(configured[key], "core_dataset_id", None) or configured[key].dataset_id
                                  for key in selected}):
            identifier = core.table_identifier(dataset_id)
            if identifier in iceberg_tables or not core.table_exists(dataset_id):
                continue
            table = core.catalog.load_table(identifier)
            snapshot = table.current_snapshot()
            if snapshot:
                iceberg_tables[identifier] = {
                    "rows": int(snapshot.summary.get("total-records", 0)),
                    "snapshot_id": snapshot.snapshot_id,
                    "metadata_location": table.metadata_location,
                }

    if active_500:
        for as_of in dates:
            outside_holdings = holding_symbols - set(market_symbols)
            received = holding_prices_by_date.get(as_of.isoformat(), set()) & outside_holdings
            holdings_cached = any(item["date"] == as_of.isoformat() and item["dataset"] == "twse-market-volume"
                                  for item in skipped_items)
            coverage_items.append({"date": as_of.isoformat(), "dataset": "outside_500_registered_portfolio_ohlcv",
                                   "expected": sorted(outside_holdings), "received": sorted(received),
                                   "missing": None if holdings_cached else sorted(outside_holdings - received),
                                   "status": "cached_unverified" if holdings_cached else
                                             "complete" if received == outside_holdings else "missing"})
            required = {
                ("ohlcv", "TWSE"): "twse",
                ("valuation", "TWSE"): "twse",
                ("institutional", "TWSE"): "twse",
                ("financials", "ALL"): "mops",
                ("benchmark", "TWSE"): "taiex",
                ("financing", "TWSE"): "twse",
                ("securities_lending_short", "TWSE"): "twse",
                ("day_trading", "TWSE"): "twse",
            }
            for (dataset_id, market), source_id in required.items():
                if any(item.get("date") == as_of.isoformat() and item.get("dataset") == dataset_id
                       and item.get("market") == market for item in coverage_items):
                    continue
                missing_scope = (set(market_symbols) if market == "ALL" else
                                 {"TAIEX"} if dataset_id == "benchmark" else members_by_market[market])
                coverage_items.append({"date": as_of.isoformat(), "dataset": dataset_id,
                                       "source": source_id, "market": market,
                                       "expected": sorted(missing_scope), "received": [],
                                       "missing": sorted(missing_scope),
                                       "status": "blocked", "reason": "no_approved_market_batch_adapter"})
    for item in coverage_items:
        for field in ("expected", "received", "missing"):
            item[f"{field}_count"] = len(item[field]) if isinstance(item.get(field), list) else None
    enabled_symbols = set(control.enabled_stock_symbols()) if hasattr(control, "enabled_stock_symbols") else set(symbols)
    coverage_status = _coverage_status(coverage_items, active_500)
    coverage_inventory = {
        "schema_version": 1, "execution_id": execution_id, "config_id": config_id,
        "coverage_status": coverage_status,
        "universe_status": universe["status"], "universe_version": universe.get("version"),
        "universe_source_snapshot": universe.get("source_snapshot"),
        "effective_500": sorted(market_symbols) if active_500 else [],
        "enabled_outside_weekly_coverage": sorted(enabled_symbols - set(market_symbols)) if active_500 else sorted(enabled_symbols),
        "items": coverage_items,
    }
    inventory_payload = json.dumps(coverage_inventory, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()
    inventory_name = f"executions/{execution_id}/coverage-inventory.json"
    inventory_store = GcsObjectStore(core_bucket)
    try:
        if not inventory_store.create(inventory_name, inventory_payload, "application/json") and inventory_store.read(inventory_name) != inventory_payload:
            raise RuntimeError("immutable coverage inventory conflict")
    except Exception:
        core.close()
        if owned_control:
            control.close()
        raise

    summary: dict[str, object] = {
        "component": "ingestion-core",
        "execution_id": execution_id,
        "trace_id": trace_id,
        "as_of": dates[-1].isoformat(),
        "dates": [item.isoformat() for item in dates],
        "symbols": list(symbols),
        "requested": len(selected),
        "staged": len(staged),
        "failed": len(failures),
        "empty": len(empty_items),
        "empty_items": empty_items,
        "skipped": len(skipped_items),
        "skipped_items": skipped_items,
        "dq": dq_items,
        "core_created": core_created,
        "core_updated": core_updated,
        "core_reused": core_reused,
        "serving_published": serving_published,
        "iceberg_tables": iceberg_tables,
        "coverage_inventory_uri": f"gs://{core_bucket}/{inventory_name}",
        "coverage_inventory_hash": f"sha256:{sha256(inventory_payload).hexdigest()}",
        "coverage_status": coverage_status,
        "objects": staged,
        "failures": failures,
    }
    try:
        if failures:
            raise RuntimeError(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        if execution_scoped:
            stage_writer.mark_core_committed(execution_id, stage_results=stage_results)
            if persisted_execution:
                industry_setting = control.get_admin_setting("mart_industry_scopes")
                industries = industry_setting[0] if industry_setting and isinstance(industry_setting[0], list) else []
                summary["ready_event"] = _core_ready_event(
                    core_bucket=core_bucket, execution_id=execution_id, config_id=config_id,
                    analysis_as_of=(local_now.date() if options.get("start_date") or os.environ.get("BACKFILL_START_DATE")
                                    else dates[-1]).isoformat(),
                    iceberg_tables=_current_core_fences(core) if core_committed else {},
                    symbols=tuple(symbols), market=config.market, industries=industries,
                )
            retention_setting = control.get_admin_setting("retention")
            retention = retention_setting[0] if retention_setting and isinstance(retention_setting[0], dict) else {}
            cleanup_results = []
            if retention.get("cleanup_enabled", False):
                cutoff = datetime.now(timezone.utc) - timedelta(days=int(retention.get("days", 30)))
                for previous in control.cleanup_candidates(before=cutoff):
                    result = stage_writer.cleanup_committed_execution(previous)
                    cleanup_results.append({"execution_id": previous, **result})
                    if persisted_execution:
                        control.save_item(ExecutionItem(
                            execution_id, f"cleanup:{previous}", "stage", "cleanup",
                            DataState.SUCCESS if result["committed"] else DataState.UNAVAILABLE,
                            int(result["deleted"]), 0, False, False, None,
                            "committed Stage cleaned" if result["committed"] else "cleanup fence unavailable",
                        ))
            summary["cleanup"] = cleanup_results
        return summary
    finally:
        core.close()
        if owned_control:
            control.close()


def consume_queued_collection() -> dict[str, object]:
    worker_id = os.environ.get("QUEUE_WORKER_ID", os.environ.get("K_REVISION", "ingestion-core")).strip()
    max_retries = int(os.environ.get("QUEUE_MAX_RETRIES", "1"))
    with _control_plane() as control:
        execution = control.claim_execution(worker_id, trigger_type=TriggerType.COLLECTION)
        if execution is None:
            return {"component": "ingestion-core", "status": "idle", "claimed": False}
        try:
            summary = collect_stage(execution_id=execution.execution_id, symbols=execution.requested_symbols,
                                    config_id=execution.config_id, request_options=execution.request_options,
                                    control=control, trace_id=execution.trace_id)
            completed, analysis = _finish_collection(control, execution.execution_id, summary)
            return {**summary, "status": completed.status.value, "claimed": True,
                    "analysis_execution_id": analysis.execution_id if analysis else None,
                    "mart_trigger": _trigger_mart(analysis.execution_id if analysis else None)}
        except Exception:
            retry_count = execution.retry_count + 1
            status = ExecutionStatus.RETRYING if retry_count <= max_retries else ExecutionStatus.FAILED
            control.transition_execution(execution.execution_id, status, error_code="COLLECTION_FAILED", retry_count=retry_count)
            raise


def run_scheduled_collection() -> dict[str, object]:
    with _control_plane() as control:
        current = control.get_admin_setting("schedule")
        schedule = current[0] if current and isinstance(current[0], dict) else {"enabled": True}
        if schedule.get("enabled", True) is False:
            return {"component": "ingestion-core", "status": "disabled", "scheduled": False}
        local_today = datetime.now(TAIPEI).date()
        explicit_backfill = any(os.environ.get(key, "").strip() for key in (
            "INGESTION_DATE", "BACKFILL_START_DATE", "BACKFILL_END_DATE"))
        rotate_once = os.environ.get("LIQUID_500_ROTATE_ONCE", "false").lower() in {"1", "true", "yes"}
        if (local_today.weekday() == 6 or rotate_once) and not explicit_backfill:
            holidays = _holidays(os.environ.get("MARKET_HOLIDAYS", "")) | {
                date.fromisoformat(item) for item in schedule.get("holiday_overrides", ())
            }
            week_start = local_today - timedelta(days=6 if local_today.weekday() == 6 else local_today.weekday() + 7)
            trading_days = tuple(week_start + timedelta(days=offset) for offset in range(5)
                                 if week_start + timedelta(days=offset) not in holidays)
            effective_day = local_today if rotate_once else local_today + timedelta(days=1)
            while effective_day.weekday() >= 5 or effective_day in holidays:
                effective_day += timedelta(days=1)
            core = _iceberg_core(os.environ["CORE_BUCKET"])
            version = rotate_from_core(core.catalog, control, week_start=week_start,
                                       trading_days=trading_days,
                                       effective_from=datetime.now(TAIPEI) if rotate_once and effective_day == local_today
                                       else datetime.combine(effective_day, datetime.min.time(), TAIPEI))
            return {"component": "ingestion-core", "status": "succeeded", "scheduled": True,
                    "operation": "liquid_500_rotation", "version": version}
        config_id = os.environ.get("CONTROL_COLLECTION_CONFIG", "first-batch")
        execution = control.enqueue_collection(config_id)
        control.transition_execution(execution.execution_id, ExecutionStatus.RUNNING)
        try:
            summary = collect_stage(execution_id=execution.execution_id, symbols=execution.requested_symbols,
                                    config_id=config_id, request_options=execution.request_options,
                                    control=control, trace_id=execution.trace_id)
            completed, analysis = _finish_collection(control, execution.execution_id, summary)
            return {**summary, "status": completed.status.value, "scheduled": True,
                    "analysis_execution_id": analysis.execution_id if analysis else None,
                    "mart_trigger": _trigger_mart(analysis.execution_id if analysis else None)}
        except Exception:
            control.transition_execution(execution.execution_id, ExecutionStatus.FAILED, error_code="COLLECTION_FAILED")
            raise


def main() -> None:
    started = monotonic()
    try:
        operation = consume_queued_collection if os.environ.get("QUEUE_CONSUMER", "false").lower() in {"1", "true", "yes"} else run_scheduled_collection
        result = operation()
        result["duration_ms"] = round((monotonic() - started) * 1000)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    except Exception as error:
        print(json.dumps({"component": "ingestion-core", "status": "failed",
                          "error_code": type(error).__name__.upper()[:64],
                          "duration_ms": round((monotonic() - started) * 1000)}, sort_keys=True), file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
