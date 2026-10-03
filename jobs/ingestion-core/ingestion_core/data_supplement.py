"""Bounded official historical fill through the existing Stage/Core runtime."""
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
import os
import re
from time import sleep
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from uuid import uuid4

from packages.provenance import Provenance
from .control import ExecutionStatus
from .dq import validate_ohlcv
from .financial_publication import normalise_xbrl_financials, parse_filing_index
from .first_batch import normalise_benchmark
from .sources import parse_twse
from .stage import GcsObjectStore, StageWriter


def months_ending(year, month, count):
    if not 1 <= month <= 12 or not 1 <= count <= 12:
        raise ValueError("invalid bounded monthly window")
    last = year * 12 + month - 1
    return [divmod(value, 12) for value in range(last - count + 1, last + 1)]


def normalise_monthly(document, symbol, year, month, *, received_at, expected_name):
    result = document.get("result")
    if document.get("code") != 200 or not isinstance(result, dict):
        raise ValueError("monthly revenue source is unavailable")
    if result.get("yymm") != f"{year-1911}{month:02d}":
        raise ValueError("monthly revenue period mismatch")
    # An asterisk is the exchange's annotation for a changed share denomination.
    if str(result.get("companyAbbreviation", "")).rstrip("*") != expected_name.rstrip("*"):
        raise ValueError("monthly revenue company name mismatch")
    values = [row[1] for row in result.get("data", []) if len(row) == 2 and row[0] == "本月"]
    if len(values) != 1:
        raise ValueError("monthly revenue value missing or ambiguous")
    amount = Decimal(str(values[0]).replace(",", ""))
    if not amount.is_finite() or amount != amount.to_integral_value():
        raise ValueError("invalid monthly revenue amount")
    received = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
    if received.tzinfo is None:
        raise ValueError("monthly receipt requires timezone")
    return [{"symbol": symbol, "fiscal_year": year, "fiscal_quarter": (month-1)//3+1,
             "fiscal_month": month, "statement_type": "monthly_revenue",
             "metric": f"monthly_revenue_{month:02d}", "value": str(amount*1000),
             "unit": "TWD", "source_unit": "TWD_thousands", "currency": "TWD",
             "period_start": f"{year}-{month:02d}-01",
             "fiscal_period_end": f"{year}-{month:02d}-{monthrange(year, month)[1]}",
             "period_basis": "monthly", "report_scope": "source_reported",
             "published_at": None, "publication_time_authoritative": False,
             "availability_at": received_at, "observed_at": received_at,
             "availability_basis": "source_response_receipt", "historical_publication_status": "unknown"}]


def _fetch(url, payload=None):
    request = Request(url, data=urlencode(payload).encode() if payload is not None else None,
                      headers={"User-Agent": "Mozilla/5.0 (compatible; JanusAI-Ingestion/1.0)"})
    for attempt in range(2):
        try:
            with urlopen(request, timeout=30) as response:
                raw, encoding = response.read(), response.headers.get_content_charset() or "utf-8"
            break
        except HTTPError as error:
            if attempt or error.code not in {500, 502, 503, 504}:
                raise
        except (URLError, TimeoutError):
            if attempt:
                raise
        sleep(1)
    sleep(1)
    return raw, encoding


def run_backfill():
    from .__main__ import _control_plane, _core_ready_event, _iceberg_core, TAIPEI
    today = datetime.now(TAIPEI).date()
    control = _control_plane()
    core = None
    stage_results = []
    execution = None
    collection_finished = False
    summary = {"operation": "data_supplement_backfill", "analysis_as_of": today.isoformat(),
               "core_created": 0, "core_reused": 0, "failures": [], "symbols": [], "items": []}
    try:
        core = _iceberg_core(os.environ["CORE_BUCKET"])
        writer = StageWriter(GcsObjectStore(os.environ["STAGE_BUCKET"]))
        supplied = os.environ.get("JANUS_DATA_SUPPLEMENT_SYMBOLS", "").strip()
        if supplied:
            symbols = tuple(sorted(set(supplied.split(","))))
        else:
            with control.connection.cursor() as cursor:
                cursor.execute("SELECT symbol FROM control.mart_ai_target_symbols(%s::date) ORDER BY symbol", (today,))
                symbols = tuple(row[0] for row in cursor.fetchall())
        if not symbols or len(symbols) > 50 or any(not re.fullmatch(r"[1-9][0-9]{3}", s) for s in symbols):
            raise ValueError("supplement requires 1..50 bounded stock symbols")
        with control.connection.cursor() as cursor:
            cursor.execute("SELECT symbol,name,market FROM control.stock_master WHERE enabled AND symbol=ANY(%s)", (list(symbols),))
            stocks = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
        if set(stocks) != set(symbols) or any(market != "TWSE" for _, market in stocks.values()):
            raise ValueError("supplement currently supports verified TWSE stocks only")
        if not control.source_is_approved("mops") or not control.source_is_approved("twse"):
            raise ValueError("official supplement sources are not approved")
        execution = control.enqueue_collection("first-batch", symbols, request_options={"operation": "data_supplement_backfill"})
        control.transition_execution(execution.execution_id, ExecutionStatus.RUNNING)
        summary.update(execution_id=execution.execution_id, symbols=list(symbols))

        def stage(raw, url, source, dataset, extension, request_identity=None):
            received = datetime.now(timezone.utc)
            provenance = Provenance(str(uuid4()), source, url, dataset, received, None, received, "sha256:"+sha256(raw).hexdigest(), False,
                                    quality_details={"request_identity": request_identity or {}})
            staged = writer.write_raw(payload=raw, media_type="application/json" if extension == "json" else "text/html",
                                      extension=extension, execution_id=execution.execution_id,
                                      provenance=provenance, execution_scoped=True)
            stage_results.append(staged)
            return staged.idempotency_key, received.isoformat().replace("+00:00", "Z")

        def commit(rows, provenance_id, source, dataset, item):
            if not rows:
                raise ValueError("no accepted supplement rows")
            result = core.write(dataset_id=dataset, rows=rows, execution_id=execution.execution_id,
                                provenance_id=provenance_id, source_id=source, partition_date=today)
            summary["core_created"] += result.inserted
            summary["core_reused"] += result.reused
            summary["items"].append({**item, "dataset": dataset, "rows": len(rows),
                                     "inserted": result.inserted, "reused": result.reused})

        def failure(dataset, symbol, period, error):
            summary["failures"].append({"dataset": dataset, "symbol": symbol, "period": period,
                                        "reason": type(error).__name__})

        for symbol in symbols:
            filings = []
            for year in range(today.year-3, today.year+1):
                url = "https://doc.twse.com.tw/server-java/t57sb01?"+urlencode({"step": "1", "colorchg": "1", "co_id": symbol, "year": str(year-1911), "mtype": "A"})
                try:
                    raw, encoding = _fetch(url)
                    stage(raw, url, "mops", "financials", "html", {"kind": "filing_index", "symbol": symbol, "year": year})
                    filings.extend(parse_filing_index(raw.decode(encoding), symbol, year))
                except Exception as error:
                    failure("financial-index", symbol, str(year), error)
            unique = {(r["fiscal_year"], r["fiscal_quarter"]): r for r in sorted(filings, key=lambda r: r["official_uploaded_at"])
                      if datetime.fromisoformat(r["official_uploaded_at"]) <= datetime.now(timezone.utc)}
            for (year, quarter), filing in sorted(unique.items())[-12:]:
                url = "https://mopsov.twse.com.tw/server-java/t164sb01?"+urlencode({"step": "1", "CO_ID": symbol, "SYEAR": year, "SSEASON": quarter, "REPORT_ID": "C"})
                try:
                    raw, _ = _fetch(url)
                    provenance, received = stage(raw, url, "mops", "financials", "html", {"symbol": symbol, "year": year, "quarter": quarter})
                    rows = normalise_xbrl_financials(raw.decode("latin-1"), symbol, year, quarter, received_at=received)
                    for row in rows:
                        row.update(source_document_sha256=sha256(raw).hexdigest(), official_filing_uploaded_at=filing["official_uploaded_at"],
                                   filing_filename=filing["filename"], source_id="mops")
                    commit(rows, provenance, "mops", "financials", {"symbol": symbol, "period": f"{year}Q{quarter}"})
                except Exception as error:
                    failure("financials", symbol, f"{year}Q{quarter}", error)
            # The latest not-yet-due month is not a historical coverage failure.
            latest = today.replace(day=1) - timedelta(days=1)
            if today.day <= 10:
                latest = latest.replace(day=1) - timedelta(days=1)
            for year, zero_month in months_ending(latest.year, latest.month, 12):
                month = zero_month+1
                url = "https://mops.twse.com.tw/mops/api/t05st10_ifrs"
                try:
                    raw, _ = _fetch(url, {"companyId": symbol, "subsidiaryCompanyId": "", "dataType": "2", "year": str(year-1911), "month": str(month)})
                    provenance, received = stage(raw, url, "mops", "financials", "json", {"symbol": symbol, "year": year, "month": month})
                    rows = normalise_monthly(json.loads(raw), symbol, year, month, received_at=received, expected_name=stocks[symbol][0])
                    for row in rows:
                        row.update(source_id="mops", source_document_sha256=sha256(raw).hexdigest())
                    commit(rows, provenance, "mops", "financials", {"symbol": symbol, "period": f"{year}-{month:02d}"})
                except Exception as error:
                    failure("monthly-revenue", symbol, f"{year}-{month:02d}", error)

        target = today-timedelta(days=1)
        market_months = [(year, month+1) for year, month in months_ending(target.year, target.month, 8)]
        for year, month in market_months:
            for symbol in symbols:
                url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY?"+urlencode({"date": f"{year}{month:02d}01", "stockNo": symbol, "response": "json"})
                try:
                    raw, _ = _fetch(url)
                    provenance, _ = stage(raw, url, "twse", "ohlcv", "json", {"symbol": symbol, "year": year, "month": month})
                    rows = [{**row, "source_id": "twse", "observed_at": row["trade_date"]+"T00:00:00Z"}
                            for row in parse_twse(raw, symbol) if row["trade_date"] <= target.isoformat()]
                    checked = validate_ohlcv(rows, analysis_as_of=today)
                    if checked.quarantined:
                        failure("ohlcv-dq", symbol, f"{year}-{month:02d}", ValueError())
                    commit(list(checked.accepted), provenance, "twse", "ohlcv", {"symbol": symbol, "period": f"{year}-{month:02d}"})
                except Exception as error:
                    failure("ohlcv", symbol, f"{year}-{month:02d}", error)
            url = "https://www.twse.com.tw/rwd/zh/TAIEX/MI_5MINS_HIST?"+urlencode({"date": f"{year}{month:02d}01", "response": "json"})
            try:
                raw, _ = _fetch(url)
                provenance, _ = stage(raw, url, "taiex", "benchmark", "json")
                document = json.loads(raw)
                rows = normalise_benchmark(dict(zip(document["fields"], cells)) for cells in document.get("data", []))
                rows = [{**row, "source_id": "taiex", "observed_at": row["trade_date"]+"T00:00:00Z"}
                        for row in rows if row["trade_date"] <= target.isoformat()]
                commit(rows, provenance, "taiex", "benchmark", {"symbol": "TAIEX", "period": f"{year}-{month:02d}"})
            except Exception as error:
                failure("benchmark", "TAIEX", f"{year}-{month:02d}", error)

        tables = {}
        with core.mutation_lock():
            for dataset in core.IDENTIFIERS:
                if core.table_exists(dataset):
                    table = core.catalog.load_table(core.table_identifier(dataset))
                    snapshot = table.current_snapshot()
                    if snapshot:
                        tables[core.table_identifier(dataset)] = {"rows": int(snapshot.summary["total-records"]),
                            "snapshot_id": snapshot.snapshot_id, "metadata_location": table.metadata_location}
        from pyiceberg.expressions import In
        scope = In("symbol", set(symbols))
        financial_rows = core.catalog.load_table(core.table_identifier("financials")).scan(row_filter=scope).to_arrow().to_pylist() if core.table_exists("financials") else []
        price_rows = core.catalog.load_table(core.table_identifier("ohlcv")).scan(row_filter=scope).to_arrow().to_pylist() if core.table_exists("ohlcv") else []
        coverage = {}
        for symbol in symbols:
            financial = [r for r in financial_rows if r["symbol"] == symbol and r.get("availability_at")]
            quarters = {(r["fiscal_year"], r["fiscal_quarter"]) for r in financial if r["statement_type"] != "monthly_revenue"}
            months = {(r["fiscal_year"], r.get("fiscal_month")) for r in financial if r["statement_type"] == "monthly_revenue"}
            dates = {str(r["trade_date"]) for r in price_rows if r["symbol"] == symbol and str(r["trade_date"]) <= target.isoformat()}
            coverage[symbol] = {"financial_quarters": len(quarters), "revenue_months": len(months), "price_trading_dates": len(dates),
                                "history_complete": len(quarters) >= 12 and len(months) >= 12 and len(dates) >= 121,
                                "historical_publication_status": "unknown", "original_numeric_revision_status": "unknown"}
        summary["coverage"] = coverage
        if not summary["core_created"] and not summary["core_reused"]:
            raise RuntimeError(json.dumps({"failures": [{"dataset": f["dataset"], "date": f["period"], "error": f["reason"]}
                                                         for f in summary["failures"]]}))
        ready = _core_ready_event(core_bucket=os.environ["CORE_BUCKET"], execution_id=execution.execution_id,
                                  config_id="first-batch", analysis_as_of=today.isoformat(), iceberg_tables=tables,
                                  symbols=symbols, market="TWSE")
        ready["featureVersion"] = "2"
        completed, analysis = control.complete_collection(execution.execution_id, ready,
            partial=bool(summary["failures"]) or not all(row["history_complete"] for row in coverage.values()))
        collection_finished = True
        if not summary["failures"]:
            writer.mark_core_committed(execution.execution_id, stage_results=stage_results)
        summary.update(status=completed.status.value, analysis_execution_id=analysis.execution_id if analysis else None,
                       core_snapshot_id=ready["coreSnapshotId"])
        control.put_admin_setting("data_supplement_last_run", {"checked_at": datetime.now(timezone.utc).isoformat(),
            "execution_id": execution.execution_id, "status": summary["status"], "coverage": coverage,
            "failures": summary["failures"], "core_created": summary["core_created"], "core_reused": summary["core_reused"]},
            actor="data-supplement", audit_resource="data_supplement")
        return summary
    except Exception:
        if execution and not collection_finished:
            control.transition_execution(execution.execution_id, ExecutionStatus.FAILED, error_code="SUPPLEMENT_FAILED")
        raise
    finally:
        if core is not None:
            core.close()
        control.close()
