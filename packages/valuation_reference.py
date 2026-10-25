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


def validate_published_card(
    card: Mapping[str, Any], *, symbol: str, as_of: str,
    core_snapshot_id: str,
) -> dict[str, Any]:
    """Reject cross-symbol, stale-shape or falsely complete Mart/API cards.

    This is a validation of one materialized card, not a way to recompute its
    numbers from LLM narrative, stock prices or UI data.
    """
    if (not isinstance(card, Mapping) or card.get("schema_version") != CARD_VERSION
            or card.get("role") != "valuation" or card.get("symbol") != symbol
            or card.get("as_of") != as_of
            or str(card.get("core_snapshot_id")) != str(core_snapshot_id)
            or card.get("method_version") != METHOD_VERSION
            or card.get("window_months") != WINDOW_MONTHS
            or card.get("minimum_valid_months") != MIN_MONTHS
            or card.get("is_ml_forecast") is not False
            or card.get("is_trading_signal") is not False):
        raise ValueError("valuation_reference_published_identity_invalid")
    try:
        date.fromisoformat(as_of)
        stamp = card.get("price_as_of")
        if stamp is not None and date.fromisoformat(stamp) > date.fromisoformat(as_of):
            raise ValueError()
    except (TypeError, ValueError):
        raise ValueError("valuation_reference_published_date_invalid") from None
    months = card.get("valid_month_count")
    if (isinstance(months, bool) or not isinstance(months, int)
            or not 0 <= months <= WINDOW_MONTHS):
        raise ValueError("valuation_reference_published_month_count_invalid")
    if (not isinstance(card.get("input_hash"), str)
            or len(card["input_hash"]) != 64
            or any(c not in "0123456789abcdef" for c in card["input_hash"])):
        raise ValueError("valuation_reference_published_hash_invalid")
    refs = card.get("input_refs")
    if (not isinstance(refs, Mapping)
            or str(refs.get("core_snapshot_id")) != str(core_snapshot_id)):
        raise ValueError("valuation_reference_published_source_snapshot_invalid")
    status = card.get("status")
    if status not in STATUSES:
        raise ValueError("valuation_reference_published_status_invalid")
    prices = (card.get("lower"), card.get("mid"), card.get("upper"))
    if status == "available":
        numeric = tuple(_positive(value) for value in prices)
        if (months < MIN_MONTHS or any(value is None for value in numeric)
                or not numeric[0] <= numeric[1] <= numeric[2]):
            raise ValueError("valuation_reference_published_price_invalid")
    elif any(card.get(key) is not None for key in (
        "lower", "mid", "upper", "price_gap_to_reference_mid_pct"
    )):
        raise ValueError("valuation_reference_published_missing_price_invalid")
    classification = card.get("classification")
    if not isinstance(classification, Mapping) or classification.get("scope") != "seq05-two-stock-only":
        raise ValueError("valuation_reference_published_classification_missing")
    return dict(card)
