"""SEQ-05 / RV-04: one read-only valuation-reference card from a verified RV-02 row.

This is a projection contract, not a data reader or independent price authority.
Only a batch caller that has pinned the Core snapshot and verified the RV-03
source may attach it to an existing immutable analysis product. No model role,
API-time Iceberg scan, deployment, or owner data is created here.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from packages.valuation_range import METHOD_VERSION, MIN_MONTHS, SCHEMA_VERSION, WINDOW_MONTHS

CARD_VERSION = "valuation-reference-card.v1"
STATUSES = frozenset({
    "available", "limited", "missing", "stale",
    "not_applicable", "blocked_basis", "blocked_rights", "error",
})


def _positive(value: Any) -> Decimal | None:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return number if number.is_finite() and number > 0 else None


def project_reference_card(
    result: Mapping[str, Any], *, symbol: str, as_of: str, core_snapshot_id: str
) -> dict[str, Any]:
    """Validate a real computed reference before exposing its single price band.

    Incomplete input always yields null price fields; never infer a stock kind,
    accounting basis, a source authorization, or an instrument's last price.
    """
    if (result.get("schema_version") != SCHEMA_VERSION
            or result.get("method_version") != METHOD_VERSION
            or result.get("symbol") != symbol
            or result.get("as_of") != as_of
            or not symbol or not core_snapshot_id or
            not str(core_snapshot_id).isdigit()):
        raise ValueError("valuation_reference_source_identity_mismatch")
    try:
        if date.fromisoformat(as_of).isoformat() != as_of:
            raise ValueError()
        observation_date = result.get("price_as_of")
        if observation_date and date.fromisoformat(str(observation_date)) > date.fromisoformat(as_of):
            raise ValueError()
    except (TypeError, ValueError):
        raise ValueError("valuation_reference_date_invalid") from None
    status = result.get("status")
    if status not in STATUSES:
        raise ValueError("valuation_reference_status_invalid")
    months = result.get("valid_month_count")
    if isinstance(months, bool) or not isinstance(months, int) or not 0 <= months <= WINDOW_MONTHS:
        raise ValueError("valuation_reference_month_count_invalid")
    input_hash = result.get("input_hash")
    if not isinstance(input_hash, str) or len(input_hash) != 64 or any(
            c not in "0123456789abcdef" for c in input_hash):
        raise ValueError("valuation_reference_input_hash_invalid")
    lows = tuple(result.get(name) for name in ("lower", "mid", "upper"))
    gap = result.get("price_gap_to_reference_mid_pct")
    if status == "available":
        parsed = tuple(_positive(value) for value in lows)
        if (result.get("security_type") != "ordinary_stock"
                or result.get("rights_status") not in {"approved", "allowed"}
                or result.get("basis_type") not in {"ttm_eps", "bvps"}
                or months < MIN_MONTHS
                or _positive(result.get("basis")) is None
                or any(value is None for value in parsed)
                or not parsed[0] <= parsed[1] <= parsed[2]):
            raise ValueError("valuation_reference_price_unverified")
    elif any(value is not None for value in (*lows, gap)):
        raise ValueError("valuation_reference_missing_must_have_null_prices")

    return {
        "schema_version": CARD_VERSION,
        "role": "valuation",
        "symbol": symbol,
        "as_of": as_of,
        "core_snapshot_id": str(core_snapshot_id),
        "status": status,
        "basis_type": result.get("basis_type"),
        "financial_period": result.get("financial_period"),
        "window_months": WINDOW_MONTHS,
        "minimum_valid_months": MIN_MONTHS,
        "valid_month_count": months,
        "lower": lows[0],
        "mid": lows[1],
        "upper": lows[2],
        "price_gap_to_reference_mid_pct": gap,
        "price_as_of": result.get("price_as_of"),
        "method": result.get("method"),
        "method_version": METHOD_VERSION,
        "historical_pit_status": result.get("historical_pit_status"),
        "excluded_reasons": list(result.get("excluded_reasons") or ()),
        "input_hash": input_hash,
        "input_refs": dict(result.get("input_refs") or {}),
        "is_ml_forecast": False,
        "is_trading_signal": False,
    }
