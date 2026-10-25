"""Daily bounded public screening; no deep specialists, training or CEO calls."""
from __future__ import annotations

from datetime import date, timedelta
from hashlib import sha256
import json
import os
from statistics import fmean, pstdev
from math import sqrt
from urllib.error import HTTPError

from .facts import _change, canonical_json
from .runtime import _fenced_core_manifest, _write_immutable_json
from .specialists import digest, number, price_series, screening, screening_quality, validated_inputs

VERSION = "market-screening-v2-full-market"
TABLES = ("core.ohlcv_v1", "core.benchmark_v1", "core.valuation_v1")
# Keep every field used by source/PIT validation; omit heavy payloads and unrelated features.
COMMON = ("symbol", "source_id", "provenance_id", "observed_at", "trade_date", "quality_flag",
          "source_authorization", "published_at", "availability_at", "record_at", "effective_date", "observed_date")
FIELDS = {TABLES[0]: COMMON + ("market", "open", "high", "low", "close", "volume_shares", "turnover_twd",
                               "is_corporate_action"),
          TABLES[1]: COMMON + ("benchmark_id", "index_kind", "close"),
          TABLES[2]: COMMON + ("pe_ratio", "pb_ratio", "dividend_yield_percent")}


def read_plan(core, as_of):
    end = date.fromisoformat(as_of)
    bounds = {key: ("observed_date" if key == TABLES[2] else "trade_date", (end - timedelta(days=241)).isoformat(), as_of)
              for key in TABLES if key in core.get("iceberg_tables", {})}
    inputs = dict(core, iceberg_tables={k: v for k, v in core.get("iceberg_tables", {}).items() if k in TABLES})
    if "datasets" in core:
        inputs["datasets"] = {k: rows for k, rows in core["datasets"].items() if k in {"ohlcv", "benchmark", "valuation"}}
    if "datasets" not in inputs and not {TABLES[0], TABLES[1]} <= set(inputs["iceberg_tables"]):
        raise ValueError("screening requires pinned OHLCV and benchmark")
    return inputs, bounds


def market_features(datasets, symbols, as_of, snapshot, *, rank=True):
    # Index once instead of rescanning the market cohort for each symbol.
    indexed = {}
    for name, rows in datasets.items():
        indexed[name] = {}
        for row in rows:
            indexed[name].setdefault(row.get("symbol"), []).append(row)
    output = []
    for symbol in sorted(symbols):
        # Query row order is not part of input identity or duplicate admission.
        scoped = {name: sorted(groups.get(symbol, []) + groups.get(None, []), key=canonical_json)
                  for name, groups in indexed.items()}
        row = screening(scoped, (symbol,), as_of, snapshot)[0]
        valid, evidence, rejected = validated_inputs(scoped, symbol, as_of, snapshot)
        prices = price_series(valid.get("ohlcv", []))
        benchmark = price_series(valid.get("benchmark", []))
        days = list(prices)
        values = list(prices.values())
        returns = [b / a - 1 for a, b in zip(values[-21:], values[-20:])] if len(values) >= 21 else []
        recent = {str(r["trade_date"]): r for r in valid.get("ohlcv", []) if str(r["trade_date"]) in days[-20:]}
        turnover = [number(r.get("turnover_twd")) for r in recent.values()]
        row["metrics"]["turnover_20d_mean_twd"] = fmean(turnover) if len(turnover) == 20 and all(v is not None and v >= 0 for v in turnover) else None
        row["metrics"]["volatility_20d_annualized"] = pstdev(returns) * sqrt(252) if returns else None
        for window in (5, 20, 60, 120):
            aligned = len(days) > window and all(day in benchmark for day in (days[-window - 1], days[-1]))
            market_return = _change([benchmark[days[-window - 1]], benchmark[days[-1]]], 1) if aligned else None
            stock_return = row["metrics"][f"return_{window}d_percent"]
            row["metrics"][f"relative_strength_{window}d_percent"] = round(stock_return - market_return, 6) if stock_return is not None and market_return is not None else None
        valuations = sorted(valid.get("valuation", []), key=lambda r: str(r.get("observed_date", r.get("trade_date"))))
        latest = valuations[-1] if valuations else {}
        row["valuation_as_of"] = str(latest.get("observed_date", latest.get("trade_date"))) if latest else None
        for key in ("pe_ratio", "pb_ratio", "dividend_yield_percent"):
            row["metrics"][key] = number(latest.get(key))
        row["input_hash"] = digest(evidence)
        row["engine_version"] = VERSION
        row["missing_metrics"] = sorted(k for k, v in row["metrics"].items() if v is None)
        row["status"] = "partial" if rejected or row["missing_metrics"] or row["latest_trade_date"] != as_of else "ready"
        output.append(row)
    return rank_features(output, as_of) if rank else output


def rank_features(output, as_of):
    # Stable descending rank, with symbol resolving ties; missing values remain unranked.
    for key in ("return_20d_percent", "relative_strength_20d_percent", "turnover_20d_mean_twd"):
        ranked = sorted((r for r in output if r["metrics"][key] is not None and r["latest_trade_date"] == as_of),
                        key=lambda r: (-r["metrics"][key], r["symbol"]))
        ranks = {r["symbol"]: i for i, r in enumerate(ranked, 1)}
        for row in output:
            row.setdefault("cross_sectional_rank", {})[key] = ranks.get(row["symbol"])
    candidates = sorted((r for r in output if r["screening_score"] is not None and r["latest_trade_date"] == as_of),
                        key=lambda r: (-r["screening_score"], r["symbol"]))
    ranks = {r["symbol"]: i for i, r in enumerate(candidates, 1)}
    return [dict(r, candidate_rank=ranks.get(r["symbol"])) for r in output]


def read_market_chunks(reader, inputs, symbols, as_of, snapshot, *, risk_model=None,
                       risk_target_symbols=()):
    rows = []
    risk_shadow = []
    risk_exclusion_reasons = {}
    # All-market screening remains cheap; deep Risk inference is explicit and
    # bounded to the de-identified held/watchlisted symbol union.
    targets = frozenset(risk_target_symbols)
    totals = {}
    backend = None
    for offset in range(0, len(symbols), 250):
        chunk = symbols[offset:offset + 250]
        result = reader.read(inputs, chunk, core_snapshot_id=snapshot, row_limit=150_000)
        if result.core_snapshot_id != snapshot:
            raise RuntimeError("screening reader snapshot mismatch")
        backend = result.telemetry.get("source")
        for dataset, count in result.telemetry.get("rows_by_dataset", {}).items():
            totals[dataset] = totals.get(dataset, 0) + count
        rows.extend(market_features(result.datasets, chunk, as_of, snapshot, rank=False))
        selected = targets.intersection(chunk)
        if risk_model is not None and selected:
            from .risk_shadow import predict_core_shadow
            risk = predict_core_shadow(result.datasets.get("ohlcv", []), as_of,
                                       risk_model, core_snapshot_id=snapshot,
                                       target_symbols=selected)
            risk_shadow.extend(risk["predictions"])
            for reason, count in risk.get("excluded_target_reasons", {}).items():
                risk_exclusion_reasons[reason] = risk_exclusion_reasons.get(reason, 0) + count
    telemetry = {"source": backend, "rows_by_dataset": totals,
                 "total_rows": sum(totals.values()), "chunks": (len(symbols) + 249) // 250}
    if risk_model is not None:
        telemetry["risk_shadow"] = risk_shadow
        telemetry["risk_target_count"] = len(targets)
        telemetry["risk_prediction_count"] = len(risk_shadow)
        telemetry["risk_nonordinary_target_count"] = len(targets - set(symbols))
        telemetry["risk_excluded_target_count"] = len(targets) - len(risk_shadow)
        telemetry["risk_exclusion_reasons"] = {
            **risk_exclusion_reasons,
            "NOT_IN_ORDINARY_STOCK_UNIVERSE_INCLUDING_ETF": len(targets - set(symbols)),
        }
        if sum(telemetry["risk_exclusion_reasons"].values()) != telemetry["risk_excluded_target_count"]:
            raise ValueError("risk target accounting mismatch")
    return rank_features(rows, as_of), telemetry


def screening_processor(execution, connection, *, store_factory=None, reader_factory=None,
                        candidate_factory=None, risk_model_factory=None):
    from .specialist_runtime import load_market_membership
    from .storage import sql_catalog_from_environment
    from .analytics_reader import IcebergSnapshotReader
    if store_factory is None:
        from ingestion_core.stage import GcsObjectStore
        store_factory = GcsObjectStore
    bucket = os.environ["MART_BUCKET"]
    store = store_factory(bucket)
    core = _fenced_core_manifest(execution, store_factory)
    as_of = str(execution.request_options["analysis_as_of"])
    if core.get("analysis_as_of") != as_of:
        raise ValueError("screening data date fence mismatch")
    membership = load_market_membership(connection, as_of)
    symbols = tuple(membership["symbols"])
    inputs, bounds = read_plan(core, as_of)
    shadow_enabled = os.environ.get("MART_RISK_SHADOW_ENABLED", "false").lower() == "true"
    risk_targets = ()
    if shadow_enabled:
        from .risk_shadow import MODEL_SHA256, FEATURE_VERSION
        from .coverage import load_target_rows, _hash
        # De-identified PIT target union. Current stock ownership/weights and
        # other owner fields never become model features or public artifacts.
        target_rows = load_target_rows(connection, as_of)
        risk_targets = tuple(sorted({row["symbol"] for row in target_rows}))
        # Keep full de-identified union for aggregate ETF/nonordinary exclusion;
        # selected ordinary shares alone are passed into the model.
    identity = {"analysis_as_of": as_of, "core_snapshot_id": execution.core_snapshot_id,
                "core_manifest_hash": execution.request_options["core_snapshot_hash"],
                "tables": inputs.get("iceberg_tables", {}), "membership": membership,
                "feature_version": VERSION, "date_bounds": bounds}
    if shadow_enabled:
        identity["risk_shadow"] = {"model_sha256": MODEL_SHA256, "feature_version": FEATURE_VERSION,
                                    "target_membership_hash": _hash(risk_targets),
                                    "target_count": len(risk_targets),
                                    "scope": "HELD_AND_WATCHLISTED_ORDINARY_SHARES",
                                    "publication_allowed": False}
    identity_hash = digest(identity)
    name = f"screening/{identity_hash[7:]}.json"
    try:
        raw = store.read(name)
    except (FileNotFoundError, HTTPError) as error:
        if isinstance(error, HTTPError) and error.code != 404:
            raise
        raw = None
    reused = raw is not None
    if reused:
        artifact = json.loads(raw)
        if artifact.get("identity") != json.loads(json.dumps(identity)) or artifact.get("output_hash") != digest({k: v for k, v in artifact.items() if k != "output_hash"}):
            raise RuntimeError("screening cache identity/hash mismatch")
        ref = {"artifact_uri": f"gs://{bucket}/{name}", "artifact_hash": "sha256:" + sha256(raw).hexdigest()}
    else:
        reader = reader_factory(inputs, bounds) if reader_factory else IcebergSnapshotReader(sql_catalog_from_environment(), date_bounds=bounds, selected_fields=FIELDS)
        try:
            risk_model = None
            if shadow_enabled:
                from .risk_shadow import load_model_from_pinned_store
                risk_model = risk_model_factory() if risk_model_factory else load_model_from_pinned_store(store)
            rows, input_telemetry = read_market_chunks(
                reader, inputs, symbols, as_of, execution.core_snapshot_id,
                risk_model=risk_model, risk_target_symbols=risk_targets)
        finally:
            reader.close()
        shadow_rows = input_telemetry.pop("risk_shadow", None)
        shadow_reference = None
        if shadow_rows is not None:
            from .risk_shadow import MODEL_VERSION, MODEL_SHA256, FEATURE_VERSION
            if any(row.get("publication_allowed") is not False for row in shadow_rows):
                raise ValueError("Risk shadow attempted publication")
            risk_artifact = {"artifact_kind": "mart_risk_shadow_v1", "schema_version": "1.0.0",
                             "core_snapshot_id": execution.core_snapshot_id,
                             "analysis_as_of": as_of, "model_version": MODEL_VERSION,
                             "model_sha256": MODEL_SHA256, "feature_version": FEATURE_VERSION,
                             "source_manifest_hash": execution.request_options["core_snapshot_hash"],
                             "rows": sorted(shadow_rows, key=lambda row: row["symbol"]),
                             "scope": "HELD_AND_WATCHLISTED_ORDINARY_SHARES",
                             "target_membership_hash": _hash(risk_targets),
                             "target_count": len(risk_targets),
                             "publication_allowed": False,
                             "status": "SHADOW_UNVALIDATED"}
            risk_artifact["output_hash"] = digest(risk_artifact)
            risk_name = f"risk-shadow/{digest(identity)[7:]}.json"
            shadow_reference = _write_immutable_json(store, bucket, risk_name, risk_artifact)
            if json.loads(store.read(risk_name)) != risk_artifact:
                raise RuntimeError("Risk shadow artifact readback mismatch")
        audit = {"backend": input_telemetry.get("source"), "candidate": "not_requested", "default": "pyiceberg"}
        if candidate_factory:
            candidate = None
            try:
                candidate = candidate_factory(inputs, bounds)
                other, candidate_telemetry = read_market_chunks(candidate, inputs, symbols, as_of, execution.core_snapshot_id)
                audit.update(candidate="pass" if digest(rows) == digest(other) else "fidelity_failed",
                             output_equal=digest(rows) == digest(other), telemetry=candidate_telemetry)
            except Exception as error:
                audit.update(candidate="failed", error_code=type(error).__name__.upper()[:64])
            finally:
                if candidate:
                    candidate.close()
        artifact = {"artifact_kind": "mart_market_screening_v1", "identity": identity,
                    "identity_hash": identity_hash, "rows": rows, "quality": screening_quality(rows),
                    "input_telemetry": input_telemetry, "canary": audit,
                    "specialist_count": 0, "llm_api_tokens": 0, "ceo_triggered": False,
                    "risk_shadow": shadow_reference,
                    "publication_authority": False}
        if artifact["quality"]["latest_market_date"] != as_of:
            raise ValueError("EOD canonical input not ready for screening date")
        artifact["output_hash"] = digest(artifact)
        ref = _write_immutable_json(store, bucket, name, artifact)
        if store.read(name) != canonical_json(artifact):
            raise RuntimeError("screening immutable readback mismatch")
    if connection is not None and os.getenv('MART_PRODUCT_PROJECTION') == 'true':
        from .product_runtime import persist_screening
        persist_screening(connection, artifact)
    receipt = {"execution_id": execution.execution_id, "identity_hash": identity_hash, "reused": reused,
               "artifact_growth_bytes": 0 if reused else len(canonical_json(artifact)), "retention_days": 90,
               "screening": ref, "screening_count": len(artifact["rows"]), "quality": artifact["quality"],
               "canary": artifact["canary"], "risk_shadow": artifact.get("risk_shadow"),
               "specialist_count": 0, "llm_api_tokens": 0, "ceo_triggered": False}
    receipt["output_hash"] = digest(receipt)
    receipt_name = f"executions/{execution.execution_id}/screening-manifest.json"
    try:
        saved = json.loads(store.read(receipt_name))
    except (FileNotFoundError, HTTPError) as error:
        if isinstance(error, HTTPError) and error.code != 404:
            raise
        saved = None
    if saved is not None:
        if saved["execution_id"] != execution.execution_id or saved["identity_hash"] != identity_hash or saved["screening"] != ref \
                or saved.get("output_hash") != digest({k: v for k, v in saved.items() if k != "output_hash"}):
            raise RuntimeError("immutable screening receipt fence mismatch")
        receipt_ref = _write_immutable_json(store, bucket, receipt_name, saved)
        return {**saved, **receipt_ref, "reused": True, "artifact_growth_bytes": 0}
    receipt_ref = _write_immutable_json(store, bucket, receipt_name, receipt)
    return {**receipt, **receipt_ref}


def run_daily():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from ingestion_core.stage import GcsObjectStore
    from .specialist_runtime import latest_training_input, _run_event
    if os.environ.get("GCP_PROJECT_ID") != "gen-lang-client-0593591102" or os.environ.get("MART_BUCKET") != "gen-lang-client-0593591102-dev-mart":
        raise ValueError("screening is restricted to existing dev resources")
    today = datetime.now(ZoneInfo("Asia/Taipei")).date()
    requested = os.environ.get("SCREENING_DATE", today.isoformat())
    event = latest_training_input(GcsObjectStore("gen-lang-client-0593591102-dev-core"), today)
    if requested != "latest" and event["analysisAsOf"] != requested:
        raise ValueError("scheduled EOD canonical snapshot not ready")
    return _run_event(event, "market-screening", processor=screening_processor)


def run_acceptance():
    from urllib.parse import urlparse
    from ingestion_core.stage import GcsObjectStore
    from .specialist_runtime import run_acceptance as run
    result = run(processor=screening_processor, operation="market-screening-acceptance")
    target = os.environ.get("MART_ACCEPTANCE_RESULT_URI", "").strip()
    if not target:
        return result
    uri = urlparse(target)
    bucket = os.environ.get("MART_BUCKET", "").strip()
    if uri.scheme != "gs" or uri.netloc != bucket or not uri.path.startswith("/acceptance/b3-live/"):
        raise ValueError("B3 acceptance result must stay inside existing Mart dev acceptance prefix")
    name = uri.path.lstrip("/")
    if not name.endswith(".json") or ".." in name.split("/"):
        raise ValueError("invalid B3 acceptance result object")
    store = GcsObjectStore(bucket)
    _write_immutable_json(store, bucket, name, result)
    if json.loads(store.read(name)) != result:
        raise RuntimeError("B3 acceptance result readback mismatch")
    return result
