"""SEQ-05: two verified TWSE instruments, one non-ML reference from pinned Mart rows.

No network fetching, owner positions, fifth Registry role or request-time Iceberg.
The temporary two-stock scope is evidence-backed; broader classification must
come from a verified company-industry reader, not symbol-prefix heuristics.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from ingestion_core.valuation_range_inputs import from_existing_rows
from packages.valuation_reference import project_reference_card

# Official TWSE company profiles; scope is deliberately NOT all four-digit stocks.
VERIFIED_REFERENCE_SCOPE = {
    "2330": {
        "market": "twse", "security_type": "ordinary_stock", "is_financial": False,
        "industry": "半導體業", "classification_source": "https://www.twse.com.tw/pdf/ch/2330_ch.pdf",
    },
    "2882": {
        "market": "twse", "security_type": "ordinary_stock", "is_financial": True,
        "industry": "金融保險業", "classification_source": "https://www.twse.com.tw/pdf/ch/2882_ch.pdf",
    },
}
# Baseline official approval only. Approved fallback sources need a live control
# source-review lookup, which this fixed Mart input path does not currently have.
OFFICIAL_SOURCE_IDS = frozenset({"twse", "tpex", "mops", "finmind", "yahoo-finance"})



def simple_reported_eps(rows: list[dict[str, Any]], *, as_of: date) -> list[dict[str, Any]]:
    """SEQ-05 research shortcut: sum last four *single-quarter* FinMind EPS.

    This is deliberately not share-restated EPS. Keep the distinct calculation
    label and avoid assuming financial basis comparison or fabricating values.
    Existing Core source receipts are used; no additional issuer download.
    """
    by_quarter: dict[tuple[int, int], set[Decimal]] = {}
    for row in rows:
        if (row.get("symbol") != "2330" or row.get("source_id") != "finmind"
                or row.get("metric") != "EPS" or not row.get("provenance_id")):
            continue
        try:
            y, q = int(row["fiscal_year"]), int(row["fiscal_quarter"])
            value = Decimal(str(row["value"]))
            if not 1 <= q <= 4 or not value.is_finite():
                continue
            period_end = date(y, q * 3, (31, 30, 30, 31)[q - 1])
            if period_end > as_of:
                continue
            first_seen = row.get("availability_at") or row.get("published_at")
            if first_seen and date.fromisoformat(str(first_seen)[:10]) > as_of:
                continue
        except (ValueError, KeyError, TypeError, InvalidOperation):
            continue
        by_quarter.setdefault((y, q), set()).add(value)
    ordered = sorted(by_quarter, reverse=True)
    if len(ordered) < 4:
        return []
    chosen = ordered[:4]
    end_index = chosen[0][0] * 4 + chosen[0][1] - 1
    if {y * 4 + q - 1 for y, q in chosen} != set(range(end_index - 3, end_index + 1)):
        return []
    if any(len(by_quarter[key]) != 1 for key in chosen):
        return []
    return [{
        "symbol": "2330", "metric": "eps_single_quarter",
        "fiscal_year": y, "fiscal_quarter": q,
        "fiscal_period_end": date(y, q * 3, (31, 30, 30, 31)[q - 1]).isoformat(),
        "period_basis": "single_quarter", "unit": "TWD_per_share",
        "value": str(next(iter(by_quarter[y, q]))),
        "share_basis": "unadjusted_reported_quarterly_simple_sum",
        "report_scope": "FinMind_single_quarter_reported",
        "source_id": "finmind",
        "provenance_id": "existing_core_finmind",
    } for y, q in sorted(chosen)]



def reference_from_core(
    datasets: Mapping[str, list[dict[str, Any]]], *, symbol: str,
    as_of: str, core_snapshot_id: str, market: str | None,
    latest_close: Any, latest_trade_date: str | None,
) -> dict[str, Any] | None:
    """Build one bounded price-reference result using the Mart's pinned Core rows.

    The permanent stock-master/sector adapter is still future work. This
    version only supports independent, evidence-reviewed company identities.
    Missing financials/valuation observations are returned as null-price cards.
    """
    scope = VERIFIED_REFERENCE_SCOPE.get(symbol)
    if scope is None:
        return None
    if not str(core_snapshot_id).isdigit():
        # The existing Mart test and legacy embedded manifests may use
        # nonnumeric synthetic IDs. Do not manufacture a reference card when
        # a real Core snapshot fence is unavailable.
        return None
    day = date.fromisoformat(as_of)
    if market is not None and market != scope["market"]:
        raise ValueError("valuation_reference_market_identity_conflict")
    valuation = [row for row in datasets.get("valuation", ()) if str(row.get("symbol")) == symbol]
    financial = [row for row in datasets.get("financials", ()) if str(row.get("symbol")) == symbol]
    quotes = [row for row in datasets.get("ohlcv", ()) if str(row.get("symbol")) == symbol]
    if any(
        row.get("market") not in (None, "", scope["market"])
        for row in (*valuation, *financial, *quotes)
    ):
        raise ValueError("valuation_reference_core_market_conflict")
    # User-approved research shortcut: for 2330 use four real historical
    # FinMind single-quarter Core values without expensive share-restatement.
    # Never mix these with the MOPS YTD/duplicate rows.
    eps = simple_reported_eps(financial, as_of=day) if symbol == "2330" else []
    if eps:
        financial = eps
    # Source whitelist remains scoped to existing approved Control sources.
    sources = {str(row.get("source_id")) for row in (*valuation, *financial)
               if row.get("source_id") and row.get("provenance_id")}
    rights = "approved" if sources and sources.issubset(OFFICIAL_SOURCE_IDS) else "unknown"
    calculated = from_existing_rows(
        symbol=symbol, market=scope["market"], security_type=scope["security_type"],
        is_financial=scope["is_financial"], as_of=day,
        valuation_rows=valuation, financial_rows=financial,
        rights_status=rights, price=latest_close, price_as_of=latest_trade_date,
    )
    # The financial facts came from pinned Core, not from a PostgreSQL serving
    # query; preserve this truthful source lineage.
    calculated["input_refs"].update({
        "multiple_source": "core.valuation_v1/pinned",
        "financial_source": "core.financials_v1/pinned",
        "price_source": "core.ohlcv_v1/pinned" if latest_close is not None else None,
        "core_snapshot_id": str(core_snapshot_id),
    })
    card = project_reference_card(
        calculated, symbol=symbol, as_of=as_of,
        core_snapshot_id=str(core_snapshot_id),
    )
    if eps:
        card["eps_aggregation"] = "last_four_reported_quarters_simple_sum"
        card["eps_quarter_values"] = [
            {"period": f"{row['fiscal_year']}Q{row['fiscal_quarter']}",
             "value": row["value"]} for row in eps]
        card["research_approximation"] = True
    card["classification"] = {
        "industry": scope["industry"],
        "source": scope["classification_source"],
        "security_type": scope["security_type"],
        "is_financial": scope["is_financial"],
        "scope": "seq05-two-stock-only",
    }
    return card
