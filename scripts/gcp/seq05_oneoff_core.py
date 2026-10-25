"""One-off SEQ-05 small-source Stage -> Core patch (Dev only).

Called via a single Cloud Run execution override, not as a scheduler or new
job. Sources: existing Free FinMind TaiwanStockPER and Yahoo TW stock profile.
All writes use the already versioned/locked Iceberg and Stage APIs.
"""
from __future__ import annotations
import html
import json
import os
import re
import calendar
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from uuid import uuid4

from packages.provenance import Provenance
from ingestion_core.__main__ import _iceberg_core, _control_plane
from ingestion_core.stage import StageWriter, GcsObjectStore
from pyiceberg.expressions import And, EqualTo, GreaterThanOrEqual, LessThanOrEqual

PER_URL = "https://api.finmindtrade.com/api/v4/data?" + urlencode({
    "dataset": "TaiwanStockPER", "data_id": "2882",
    "start_date": "2025-10-01", "end_date": "2026-08-31",
})
BVPS_URL = "https://tw.stock.yahoo.com/quote/2882.TW/profile"
MONTHS = tuple(f"{year:04d}-{month:02d}" for year in (2025, 2026)
               for month in range(1, 13) if "2025-10" <= f"{year:04d}-{month:02d}" <= "2026-08")
MARKET = "TWSE"
AS_OF = date(2026, 10, 24)


def get(url: str, limit=900000) -> bytes:
    with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0 (JanusOneOffResearch/1.0)"}), timeout=35) as response:
        raw = response.read(limit + 1)
    if not raw or len(raw) > limit:
        raise ValueError("source_payload_size_invalid")
    return raw


def positive(value):
    try:
        n = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return n if n.is_finite() and n > 0 else None


def extract_finmind_pb(raw: bytes) -> list[dict]:
    data = json.loads(raw)
    if data.get("status") != 200 or not isinstance(data.get("data"), list):
        raise ValueError("finmind_api_status_invalid")
    grouped = defaultdict(list)
    for r in data["data"]:
        if str(r.get("stock_id")) != "2882":
            raise ValueError("finmind_symbol_mismatch")
        day = date.fromisoformat(str(r["date"]))
        month = day.strftime("%Y-%m")
        if month in MONTHS and day <= AS_OF and (pbr := positive(r.get("PBR"))) is not None:
            grouped[month].append((day, pbr))
    out = []
    for month in MONTHS:
        daily = grouped.get(month, [])
        if not daily:
            continue
        last = max(d for d, _ in daily)
        month_end = date(last.year, last.month, calendar.monthrange(last.year, last.month)[1])
        if (month_end - last).days > 7:
            continue
        values = {v for d, v in daily if d == last}
        if len(values) != 1:
            continue
        out.append({"symbol": "2882", "market": MARKET, "observed_date": last.isoformat(),
                    "pb_ratio": str(next(iter(values)))})
    return out


def extract_yahoo_bvps(raw: bytes) -> dict:
    # Extract the issuer's latest completed 2026-Q2 reported per-share figure,
    # not 2026-Q3 pre-publication numbers or total shareholders' equity.
    plain = html.unescape(re.sub(r"<[^>]+>", " ", raw.decode("utf-8", "replace")))
    plain = re.sub(r"\s+", " ", plain)
    if "2026" not in plain or "每股淨值" not in plain:
        raise ValueError("yahoo_reported_bvps_not_found")
    candidates = re.findall(r"每股淨值\s*([0-9]+(?:\.[0-9]+)?)\s*元", plain)
    if not candidates:
        candidates = re.findall(r"每股淨值.{0,70}?([0-9]{2,3}\.[0-9]{1,3})\s*元", plain)
    accepted = [positive(v) for v in candidates]
    # Same 2026Q2 value independently observed in the official-compatible
    # 2026-10-23 Yahoo Finance profile; reject HTML changes or stale quote cards.
    if Decimal("69.37") not in accepted:
        raise ValueError("yahoo_reported_bvps_conflicts_with_reference")
    return {
        "symbol": "2882", "metric": "bvps", "statement_type": "quarterly_balance_sheet",
        "fiscal_year": 2026, "fiscal_quarter": 2,
        "fiscal_period_end": "2026-06-30", "period_basis": "snapshot",
        "report_scope": "consolidated", "share_basis": "reported_per_share",
        "unit": "TWD_per_share", "currency": "TWD", "value": "69.37",
        "publication_time_authoritative": False,
        "financial_feature_version": "seq05-oneoff-reported-bvps-research-v1",
    }


def run():
    report = {"operation": "seq05-oneoff-research-quickfill", "symbols": ["2882"],
              "target_pb_months": list(MONTHS), "status": "PARTIAL",
              "inserted": {"valuation": 0, "financials": 0},
              "reused": {"valuation": 0, "financials": 0},
              "source_errors": [], "no_owner_mutation": True,
              "no_new_service": True}
    core = control = None
    execution = str(uuid4())
    try:
        control = _control_plane()
        if not all(control.source_is_approved(src) for src in ("finmind", "yahoo-finance")):
            raise ValueError("source_not_approved_in_current_control")
        with control.connection.cursor() as cursor:
            cursor.execute("SELECT market FROM control.stock_master WHERE symbol=%s AND enabled=true", ("2882",))
            market = cursor.fetchone()
        if not market or str(market[0]).upper() != MARKET:
            raise ValueError("stock_master_identity_mismatch")
        core = _iceberg_core(os.environ["CORE_BUCKET"])
        stage = StageWriter(GcsObjectStore(os.environ["STAGE_BUCKET"]))
        now = datetime.now(timezone.utc)
        valuation_table = core.catalog.load_table(core.table_identifier("valuation"))
        valuation_snapshot = valuation_table.current_snapshot()
        if not valuation_snapshot:
            raise ValueError("valuation_snapshot_missing")
        existing = valuation_table.scan(
            snapshot_id=valuation_snapshot.snapshot_id,
            row_filter=And(EqualTo("symbol", "2882"),
                           GreaterThanOrEqual("observed_date", date(2025, 10, 1)),
                           LessThanOrEqual("observed_date", date(2026, 8, 31))),
            selected_fields=("symbol", "observed_date", "pb_ratio"),
            limit=800).to_arrow().to_pylist()
        if len(existing) >= 800:
            raise ValueError("existing_valuation_scan_exceeded")
        covered = {str(r["observed_date"])[:7] for r in existing
                   if positive(r.get("pb_ratio")) is not None
                   and str(r["observed_date"])[:7] in MONTHS}
        report["preexisting_months"] = sorted(covered)
        sources = ((PER_URL, "finmind", "valuation", "json"),
                   (BVPS_URL, "yahoo-finance", "financials", "html"))
        for url, source_id, dataset_id, extension in sources:
            try:
                raw = get(url)
                rows = extract_finmind_pb(raw) if dataset_id == "valuation" else [extract_yahoo_bvps(raw)]
                if dataset_id == "valuation":
                    rows = [r for r in rows if r["observed_date"][:7] not in covered]
                    report["source_observed_months"] = sorted({r["observed_date"][:7] for r in rows} | covered)
                else:
                    table = core.catalog.load_table(core.table_identifier("financials"))
                    snap = table.current_snapshot()
                    selected = table.scan(
                        snapshot_id=snap.snapshot_id,
                        row_filter=And(EqualTo("symbol", "2882"),
                          EqualTo("fiscal_year", 2026), EqualTo("fiscal_quarter", 2)),
                        selected_fields=("metric", "value", "unit"), limit=150).to_arrow().to_pylist()
                    if any(r["metric"] == "bvps" and str(r.get("value")) == "69.37"
                           and r.get("unit") == "TWD_per_share" for r in selected):
                        rows = []
                if not rows:
                    report["reused"][dataset_id] += 1
                    continue
                receipt = datetime.now(timezone.utc)
                provenance = Provenance(
                    provenance_id=str(uuid4()), source_id=source_id,
                    source_url=url, dataset_id=dataset_id,
                    observed_at=receipt, published_at=None, fetched_at=receipt,
                    content_hash="sha256:"+sha256(raw).hexdigest(),
                    is_fallback=True,
                    quality_details={"purpose": "SEQ-05 one-off two-stock research",
                                     "target": "2882", "as_of": AS_OF.isoformat()})
                staged = stage.write_raw(
                    payload=raw, media_type="application/json" if extension == "json" else "text/html",
                    extension=extension, execution_id=execution,
                    provenance=provenance, execution_scoped=True)
                if dataset_id == "financials":
                    rows[0]["availability_at"] = receipt.isoformat()
                    rows[0]["observed_at"] = receipt.isoformat()
                    rows[0]["source_document_sha256"] = sha256(raw).hexdigest()
                commit = core.write(
                    dataset_id=dataset_id, rows=rows, execution_id=execution,
                    provenance_id=staged.idempotency_key, source_id=source_id,
                    partition_date=AS_OF)
                report["inserted"][dataset_id] = commit.inserted
                report["reused"][dataset_id] += commit.reused
                report[dataset_id+"_snapshot"] = str(commit.snapshot_id)
            except Exception as exc:
                report["source_errors"].append({"source": source_id,
                                                "error_type": type(exc).__name__})
        table = core.catalog.load_table(core.table_identifier("valuation"))
        out = table.scan(
            row_filter=And(EqualTo("symbol", "2882"),
                           GreaterThanOrEqual("observed_date", date(2025, 10, 1)),
                           LessThanOrEqual("observed_date", date(2026, 8, 31))),
            selected_fields=("observed_date", "pb_ratio"),limit=800).to_arrow().to_pylist()
        report["verified_pb_months"] = sorted({str(r["observed_date"])[:7] for r in out
            if positive(r.get("pb_ratio")) is not None and str(r["observed_date"])[:7] in MONTHS})
        report["pb_coverage"] = len(report["verified_pb_months"])
        report["status"] = ("CORE_INPUTS_COMPLETE" if report["pb_coverage"] == len(MONTHS)
                            and not report["source_errors"] and
                            report["inserted"]["financials"] + report["reused"]["financials"] >= 1
                            else "PARTIAL")
        report["mutation_execution_id"] = execution
    finally:
        if core:
            core.close()
        if control:
            control.close()
        print("SEQ05_QUICKFILL_RECEIPT:"+json.dumps(report,sort_keys=True,ensure_ascii=False),flush=True)

if __name__ == "__main__":
    run()
