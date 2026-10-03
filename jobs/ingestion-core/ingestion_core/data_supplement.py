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
from .financial_publication import FilingIndex, normalise_xbrl_financials, parse_filing_index
from .first_batch import effective_trading_day, normalise_benchmark, normalise_valuation
from .sources import parse_twse
from .stage import GcsObjectStore, StageWriter


def months_ending(year, month, count):
    if not 1 <= month <= 12 or not 1 <= count <= 36:
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


class MonthlyRevenueTable(FilingIndex):
    def __init__(self):
        super().__init__()
        self.entries = []

    def handle_endtag(self, tag):
        super().handle_endtag(tag)
        if tag == "tr":
            self.entries.append(list(self.cells))


def normalise_monthly_archive(raw, symbol, year, month, *, received_at, expected_name):
    html = raw.decode("cp950")
    if f"上市公司{year-1911}年{month}月份" not in html or "單位：千元" not in html:
        raise ValueError("monthly archive period or unit mismatch")
    table = MonthlyRevenueTable()
    table.feed(html)
    if not {"公司代號", "公司名稱", "當月營收"}.issubset(table.headers):
        raise ValueError("monthly archive headers changed")
    entries = [row for row in table.entries if len(row) == 11 and row[0] == symbol]
    if len(entries) != 1:
        raise ValueError("monthly archive company missing or ambiguous")
    row = entries[0]
    return normalise_monthly({"code": 200, "result": {"yymm": f"{year-1911}{month:02d}",
        "companyAbbreviation": row[1], "data": [["本月", row[2]]]}}, symbol, year, month,
        received_at=received_at, expected_name=expected_name)


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



def _rows(core, dataset, symbols):
    if not core.table_exists(dataset):
        return []
    from pyiceberg.expressions import In
    table = core.catalog.load_table(core.table_identifier(dataset))
    options = {"limit": 100001}
    if "symbol" in {field.name for field in table.schema().fields}:
        options["row_filter"] = In("symbol", set(symbols))
    rows = table.scan(**options).to_arrow().to_pylist()
    if len(rows) > 100000:
        raise ValueError("supplement read limit exceeded")
    return rows


def coverage_summary(financial_rows, price_rows, symbols, target):
    result = {}
    today = target+timedelta(days=1)
    latest = today.replace(day=1)-timedelta(days=1)
    if today.day <= 10:
        latest = latest.replace(day=1)-timedelta(days=1)
    required_months = {(year, month+1) for year, month in months_ending(latest.year, latest.month, 12)}
    for symbol in symbols:
        financial = [r for r in financial_rows if r["symbol"] == symbol and r.get("availability_at") and
                     r.get("source_id") == "mops" and r.get("source_document_sha256")]

        quarters = {(r["fiscal_year"], r["fiscal_quarter"]) for r in financial if r["statement_type"] != "monthly_revenue" and r["fiscal_year"] >= today.year-3}
        months = {(r["fiscal_year"], r.get("fiscal_month")) for r in financial if r["statement_type"] == "monthly_revenue" and (r["fiscal_year"], r.get("fiscal_month")) in required_months}
        dates = {str(r["trade_date"]) for r in price_rows if r["symbol"] == symbol and (target-timedelta(days=365)).isoformat() <= str(r["trade_date"]) <= target.isoformat()}
        result[symbol] = {"financial_quarters": len(quarters), "revenue_months": len(months), "price_trading_dates": len(dates),
                          "history_complete": len(quarters) >= 12 and len(months) >= 12 and len(dates) >= 121,
                          "historical_publication_status": "unknown", "original_numeric_revision_status": "unknown"}
    return result

def supplement_symbols(control):
    """Reuse ingestion's approved focus and de-identified portfolio coverage."""
    return tuple(sorted(set(control.config_symbols("first-batch")) | set(control.portfolio_coverage_symbols())))


def parse_valuation_month(raw, symbol, year, month, expected_name):
    """Official per-stock month, with fiscal/date/field fences and nullable PE."""
    document = json.loads(raw)
    fields = ["日期", "殖利率(%)", "股利年度", "本益比", "股價淨值比", "財報年/季"]
    title = re.sub(r"[\s*]", "", document.get("title", ""))
    if document.get("stat") != "OK" or document.get("fields") != fields or not title.startswith(
            f"{year-1911}年{month:02d}月" + re.sub(r"[\s*]", "", expected_name)):
        raise ValueError("valuation response identity or schema mismatch")
    values, days = [], set()
    for cells in document.get("data", []):
        if len(cells) != len(fields):
            raise ValueError("valuation row width mismatch")
        match = re.fullmatch(r"([0-9]{3})年([0-9]{2})月([0-9]{2})日", cells[0])
        if not match or (int(match[1])+1911, int(match[2])) != (year, month):
            raise ValueError("valuation row outside requested month")
        day = date(year, month, int(match[3])).isoformat()
        if day in days:
            raise ValueError("duplicate valuation date")
        days.add(day)
        row = dict(zip(fields, cells)) | {"symbol": symbol, "observed_date": day}
        value = normalise_valuation([row])[0]
        for key in ("pe_ratio", "pb_ratio", "dividend_yield_percent"):
            if value[key] is not None and (not Decimal(value[key]).is_finite() or Decimal(value[key]) < 0):
                raise ValueError("invalid official valuation ratio")
        values.append({**value, "observed_at": day+"T00:00:00Z"})
    if not values:
        raise ValueError("valuation month contains no observations")
    return values


def run_backfill(*, incremental=False, valuation_only=False):
    from .__main__ import _control_plane, _core_ready_event, _current_core_fences, _iceberg_core, TAIPEI
    today = datetime.now(TAIPEI).date()
    control = _control_plane()
    core = None
    stage_results = []
    execution = None
    collection_finished = False
    summary = {"operation": "data_supplement_daily" if incremental else "data_supplement_backfill", "analysis_as_of": today.isoformat(),
               "core_created": 0, "core_updated": 0, "core_reused": 0, "failures": [], "symbols": [], "items": [], "skipped": 0}
    if valuation_only:
        summary["operation"] = "valuation_history"
    try:
        core = _iceberg_core(os.environ["CORE_BUCKET"])
        writer = StageWriter(GcsObjectStore(os.environ["STAGE_BUCKET"]))
        supplied = os.environ.get("JANUS_DATA_SUPPLEMENT_SYMBOLS", "").strip()
        if supplied:
            symbols = tuple(sorted(set(supplied.split(","))))
        else:
            symbols = supplement_symbols(control)
        if not symbols or len(symbols) > 50 or any(not re.fullmatch(r"[1-9][0-9]{3}", s) for s in symbols):
            raise ValueError("supplement requires 1..50 bounded stock symbols")
        with control.connection.cursor() as cursor:
            cursor.execute("SELECT symbol,name,market FROM control.stock_master WHERE enabled AND symbol=ANY(%s)", (list(symbols),))
            stocks = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
        if set(stocks) != set(symbols) or any(market != "TWSE" for _, market in stocks.values()):
            raise ValueError("supplement currently supports verified TWSE stocks only")
        if not control.source_is_approved("mops") or not control.source_is_approved("twse"):
            raise ValueError("official supplement sources are not approved")
        execution = control.enqueue_collection("first-batch", symbols, request_options={"operation": summary["operation"]})
        control.transition_execution(execution.execution_id, ExecutionStatus.RUNNING)
        summary.update(execution_id=execution.execution_id, symbols=list(symbols))
        prior = _rows(core, "financials", symbols) if incremental else []
        quality = control.get_admin_setting("data_supplement_quality") if incremental else None
        repairs = {(item.get("symbol"), item.get("dataset"), item.get("period"))
                   for item in (quality[0].get("issues", []) if quality and isinstance(quality[0], dict) else [])}

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
            summary["core_updated"] += result.updated
            summary["core_reused"] += result.reused
            summary["items"].append({**item, "dataset": dataset, "rows": len(rows),
                                     "inserted": result.inserted, "reused": result.reused})

        def failure(dataset, symbol, period, error):
            summary["failures"].append({"dataset": dataset, "symbol": symbol, "period": period,
                                        "reason": type(error).__name__})

        monthly_archives = {}
        for symbol in (() if valuation_only else symbols):
            financial_batch = []
            filings = []
            known_quarters = {(r["fiscal_year"], r["fiscal_quarter"]) for r in prior if r["symbol"] == symbol and r.get("statement_type") != "monthly_revenue" and r.get("source_document_sha256")}
            start_year = today.year-1 if incremental and len(known_quarters) >= 12 else today.year-3
            repair_years = [int(period[:4]) for stock, dataset, period in repairs if stock == symbol and dataset == "financials" and re.fullmatch(r"[0-9]{4}Q[1-4]", period or "")]
            if repair_years:
                start_year = min(start_year, min(repair_years))
            for year in range(start_year, today.year+1):
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
                period = f"{year}Q{quarter}"
                existing = [r for r in prior if r["symbol"] == symbol and r.get("fiscal_year") == year and
                            r.get("fiscal_quarter") == quarter and r.get("statement_type") != "monthly_revenue"]
                if existing and any(r.get("official_filing_uploaded_at") == filing["official_uploaded_at"] and
                    r.get("financial_feature_version") == "same-filing-comparatives-v1" for r in existing) and (symbol, "financials", period) not in repairs:
                    summary["skipped"] += 1
                    continue
                url = "https://mopsov.twse.com.tw/server-java/t164sb01?"+urlencode({"step": "1", "CO_ID": symbol, "SYEAR": year, "SSEASON": quarter, "REPORT_ID": "C"})
                try:
                    raw, _ = _fetch(url)
                    provenance, received = stage(raw, url, "mops", "financials", "html", {"symbol": symbol, "year": year, "quarter": quarter})
                    rows = normalise_xbrl_financials(raw.decode("latin-1"), symbol, year, quarter, received_at=received)
                    for row in rows:
                        row.update(source_document_sha256=sha256(raw).hexdigest(), official_filing_uploaded_at=filing["official_uploaded_at"],
                                   filing_filename=filing["filename"], source_id="mops", provenance_id=provenance)
                    financial_batch.extend(rows)
                except Exception as error:
                    failure("financials", symbol, f"{year}Q{quarter}", error)
            # The latest not-yet-due month is not a historical coverage failure.
            latest = today.replace(day=1) - timedelta(days=1)
            if today.day <= 10:
                latest = latest.replace(day=1) - timedelta(days=1)
            for year, zero_month in months_ending(latest.year, latest.month, 12):
                month = zero_month+1
                period = f"{year}-{month:02d}"
                existing = [r for r in prior if r["symbol"] == symbol and r.get("fiscal_year") == year and r.get("fiscal_month") == month]
                if existing and (year, month) < (latest.year, latest.month) and (symbol, "monthly-revenue", period) not in repairs:
                    summary["skipped"] += 1
                    continue
                category = int("-KY" in stocks[symbol][0].upper())
                url = f"https://mopsov.twse.com.tw/nas/t21/sii/t21sc03_{year-1911}_{month}_{category}.html"
                try:
                    if (year, month, category) not in monthly_archives:
                        raw, _ = _fetch(url)
                        provenance, received = stage(raw, url, "mops", "financials", "html", {"year": year, "month": month, "kind": "monthly_archive"})
                        monthly_archives[year, month, category] = raw, provenance, received
                    raw, provenance, received = monthly_archives[year, month, category]
                    rows = normalise_monthly_archive(raw, symbol, year, month, received_at=received, expected_name=stocks[symbol][0])
                    for row in rows:
                        row.update(source_id="mops", source_document_sha256=sha256(raw).hexdigest(), provenance_id=provenance)
                    financial_batch.extend(rows)
                except Exception as error:
                    failure("monthly-revenue", symbol, f"{year}-{month:02d}", error)
            if financial_batch:
                commit(financial_batch, financial_batch[0]["provenance_id"], "mops", "financials", {"symbol": symbol, "period": "history"})
            print(json.dumps({"operation": summary["operation"], "symbol": symbol, "phase": "financials_committed",
                              "core_created": summary["core_created"], "failures": len(summary["failures"])}), flush=True)

        schedule_setting = control.get_admin_setting("schedule")
        schedule = schedule_setting[0] if schedule_setting and isinstance(schedule_setting[0], dict) else {}
        holidays = {date.fromisoformat(day) for day in schedule.get("holiday_overrides", ())}
        holidays.update(date.fromisoformat(day.strip()) for day in os.environ.get("MARKET_HOLIDAYS", "").split(",") if day.strip())
        target = effective_trading_day(today-timedelta(days=1), holidays=holidays)
        price_months = int(os.environ.get("JANUS_DATA_SUPPLEMENT_PRICE_MONTHS", "8"))
        market_months = [(year, month+1) for year, month in months_ending(target.year, target.month, price_months)]
        prior_valuation = _rows(core, "valuation", symbols)
        for symbol in symbols:
            valuation_batch = []
            for year, month in ([(target.year, target.month)] if incremental else market_months):
                known = {str(row["observed_date"]) for row in prior_valuation if row["symbol"] == symbol}
                if incremental and target.isoformat() in known:
                    summary["skipped"] += 1
                    continue
                url = "https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU?"+urlencode(
                    {"date": f"{year}{month:02d}01", "stockNo": symbol, "response": "json"})
                try:
                    raw, _ = _fetch(url)
                    provenance, _ = stage(raw, url, "twse", "valuation", "json", {"symbol": symbol, "year": year, "month": month})
                    observations = parse_valuation_month(raw, symbol, year, month, stocks[symbol][0])
                    valuation_batch.extend({**row, "source_id": "twse", "provenance_id": provenance}
                        for row in observations if row["observed_date"] <= target.isoformat())
                except Exception as error:
                    failure("valuation", symbol, f"{year}-{month:02d}", error)
            if valuation_batch:
                commit(valuation_batch, valuation_batch[0]["provenance_id"], "twse", "valuation", {"symbol": symbol, "period": "history"})
        missing_months, benchmark_months = {}, set(market_months)
        if incremental:
            required, day = set(), target
            while len(required) < 121:
                if day.weekday() < 5 and day not in holidays:
                    required.add(day.isoformat())
                day -= timedelta(days=1)
            prices = _rows(core, "ohlcv", symbols)
            for symbol in symbols:
                available = {str(r["trade_date"]) for r in prices if r["symbol"] == symbol}
                missing_months[symbol] = {(int(day[:4]), int(day[5:7])) for day in required-available}
                missing_months[symbol].update((int(period[:4]), int(period[5:7])) for stock, dataset, period in repairs
                    if stock == symbol and dataset == "ohlcv" and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", period or ""))
            available = {str(r["trade_date"]) for r in _rows(core, "benchmark", ())}
            benchmark_months = {(int(day[:4]), int(day[5:7])) for day in required-available}
        for year, month in (() if valuation_only else market_months):
            for symbol in symbols:
                if incremental and (year, month) not in missing_months[symbol]:
                    summary["skipped"] += 1
                    continue
                url = "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?"+urlencode({"date": f"{year}{month:02d}01", "stockNo": symbol, "response": "json"})
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
            if incremental and (year, month) not in benchmark_months:
                summary["skipped"] += 1
                continue
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

        tables = _current_core_fences(core)
        coverage = coverage_summary(_rows(core, "financials", symbols), _rows(core, "ohlcv", symbols), symbols, target)
        summary["coverage"] = coverage
        if not summary["core_created"] and not summary["core_reused"] and not (incremental and tables):
            raise RuntimeError(json.dumps({"failures": [{"dataset": f["dataset"], "date": f["period"], "error": f["reason"]}
                                                         for f in summary["failures"]]}))
        ready = _core_ready_event(core_bucket=os.environ["CORE_BUCKET"], execution_id=execution.execution_id,
                                  config_id="first-batch", analysis_as_of=today.isoformat(), iceberg_tables=tables,
                                  symbols=symbols, market="TWSE")
        ready["featureVersion"] = "2"
        publish_ready = ready if not incremental or summary["core_created"] or summary["core_updated"] else None
        completed, analysis = control.complete_collection(execution.execution_id, publish_ready,
            partial=bool(summary["failures"]) or not all(row["history_complete"] for row in coverage.values()))
        collection_finished = True
        if not summary["failures"]:
            writer.mark_core_committed(execution.execution_id, stage_results=stage_results)
        summary.update(status=completed.status.value, analysis_execution_id=analysis.execution_id if analysis else None,
                       core_snapshot_id=ready["coreSnapshotId"])
        control.put_admin_setting("data_supplement_last_run", {"checked_at": datetime.now(timezone.utc).isoformat(),
            "execution_id": execution.execution_id, "status": summary["status"], "coverage": coverage,
            "failures": summary["failures"], "core_created": summary["core_created"], "core_updated": summary["core_updated"], "core_reused": summary["core_reused"], "skipped": summary["skipped"], "operation": summary["operation"]},
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
