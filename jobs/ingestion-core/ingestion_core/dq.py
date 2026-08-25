"""Deterministic Core data-quality validation and safe merge rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable


ALLOWED_COLUMNS = frozenset(
    {
        "symbol", "market", "trade_date", "open", "high", "low", "close", "volume_shares",
        "turnover_twd", "change_percent", "is_corporate_action", "source_id", "observed_at",
    }
)
REQUIRED_COLUMNS = frozenset({"symbol", "market", "trade_date", "close", "source_id", "observed_at"})
PRICE_COLUMNS = frozenset({"open", "high", "low", "close"})
ZERO_IS_VALID = frozenset({"volume_shares", "turnover_twd", "change_percent"})
MARKETS = frozenset({"TWSE", "TPEX"})


@dataclass(frozen=True)
class Violation:
    code: str
    field: str
    message: str
    severity: str = "critical"

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "field": self.field, "message": self.message, "severity": self.severity}


@dataclass(frozen=True)
class DqResult:
    accepted: tuple[dict[str, Any], ...]
    quarantined: tuple[tuple[dict[str, Any], tuple[Violation, ...]], ...]
    warnings: tuple[tuple[int, Violation], ...]


def validate_ohlcv(rows: Iterable[dict[str, Any]], *, analysis_as_of: date) -> DqResult:
    accepted: list[dict[str, Any]] = []
    quarantined: list[tuple[dict[str, Any], tuple[Violation, ...]]] = []
    warnings: list[tuple[int, Violation]] = []
    seen: set[tuple[str, str, str]] = set()

    for index, original in enumerate(rows):
        row = dict(original)
        violations: list[Violation] = []
        missing = sorted(REQUIRED_COLUMNS - row.keys())
        violations.extend(Violation("REQUIRED_KEY", field, "required field is missing") for field in missing)
        drift = sorted(row.keys() - ALLOWED_COLUMNS)
        violations.extend(Violation("SCHEMA_DRIFT", field, "unexpected field") for field in drift)

        trade_date = _date(row.get("trade_date"), "trade_date", violations)
        observed = _datetime(row.get("observed_at"), "observed_at", violations)
        if trade_date and trade_date > analysis_as_of:
            violations.append(Violation("FUTURE_DATE", "trade_date", "trade date exceeds analysis_as_of"))
        if observed and observed.date() < trade_date if observed and trade_date else False:
            violations.append(Violation("DATE_ORDER", "observed_at", "observed_at precedes trade_date"))

        if row.get("market") not in MARKETS:
            violations.append(Violation("INVALID_MARKET", "market", "market must be TWSE or TPEX"))
        if row.get("source_id") not in {"twse", "tpex", "finmind"}:
            violations.append(Violation("INVALID_SOURCE", "source_id", "source is not approved for OHLCV"))

        for field in PRICE_COLUMNS:
            if field in row:
                value = _decimal(row[field], field, violations)
                if value is not None and value <= 0:
                    violations.append(Violation("INVALID_PRICE", field, "price must be greater than zero"))
                row[field] = value
        for field in ("volume_shares", "turnover_twd", "change_percent"):
            if field in row:
                value = _decimal(row[field], field, violations)
                if value is not None and field != "change_percent" and value < 0:
                    violations.append(Violation("INVALID_UNIT", field, "share/TWD units cannot be negative"))
                row[field] = value

        prices = [row.get(field) for field in PRICE_COLUMNS]
        numeric_prices = [value for value in prices if isinstance(value, Decimal)]
        if row.get("high") is not None and numeric_prices and row["high"] != max(numeric_prices):
            violations.append(Violation("PRICE_RANGE", "high", "high must be the maximum OHLC value"))
        if row.get("low") is not None and numeric_prices and row["low"] != min(numeric_prices):
            violations.append(Violation("PRICE_RANGE", "low", "low must be the minimum OHLC value"))

        key = (str(row.get("symbol")), str(row.get("market")), str(row.get("trade_date")))
        if key in seen:
            violations.append(Violation("DUPLICATE", "symbol,market,trade_date", "duplicate Core natural key"))
        seen.add(key)

        change = row.get("change_percent")
        if isinstance(change, Decimal) and abs(change) > Decimal("11"):
            warnings.append(
                (index, Violation("EXTREME_MOVE_REVIEW", "change_percent", "retained; verify limits, corporate action, and cross-source data", "warning"))
            )

        if violations:
            quarantined.append((original, tuple(violations)))
        else:
            accepted.append(row)
    return DqResult(tuple(accepted), tuple(quarantined), tuple(warnings))


def merge_without_null_overwrite(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Merge an incremental row without replacing valid values with nulls."""
    result = dict(existing)
    result.update({key: value for key, value in incoming.items() if value is not None})
    return result


def semantic_zero(value: Any, field: str) -> Any:
    """Preserve valid zeroes; reject zero only where field semantics forbid it."""
    if value != 0 and value != Decimal("0"):
        return value
    if field in ZERO_IS_VALID:
        return value
    if field in PRICE_COLUMNS:
        raise ValueError(f"zero is invalid for {field}")
    return value


def _decimal(value: Any, field: str, violations: list[Violation]) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).replace(",", ""))
    except InvalidOperation:
        violations.append(Violation("TYPE", field, "expected decimal-compatible value"))
        return None


def _date(value: Any, field: str, violations: list[Violation]) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        violations.append(Violation("DATE", field, "expected ISO date"))
        return None


def _datetime(value: Any, field: str, violations: list[Violation]) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed
    except (TypeError, ValueError):
        violations.append(Violation("DATE", field, "expected timezone-aware ISO datetime"))
        return None
