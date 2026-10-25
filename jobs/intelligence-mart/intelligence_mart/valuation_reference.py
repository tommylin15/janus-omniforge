"""SEQ-05: two verified TWSE instruments, one non-ML reference from pinned Mart rows.

No network fetching, owner positions, fifth Registry role or request-time Iceberg.
The temporary two-stock scope is evidence-backed; broader classification must
come from a verified company-industry reader, not symbol-prefix heuristics.
"""
from __future__ import annotations

from datetime import date
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
OFFICIAL_SOURCE_IDS = frozenset({"twse", "tpex", "mops"})


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
        raise ValueError("valuation_reference_core_snapshot_required")
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
    # Do not silently omit disallowed sources and then treat remaining rows as
    # a source-approved, publishable price. All eligible inputs must be official.
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
    card["classification"] = {
        "industry": scope["industry"],
        "source": scope["classification_source"],
        "security_type": scope["security_type"],
        "is_financial": scope["is_financial"],
        "scope": "seq05-two-stock-only",
    }
    return card
