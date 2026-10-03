"""PIT evidence and comparable financial features."""

from __future__ import annotations

from datetime import date, datetime, time, timezone, timedelta
from hashlib import sha256
import json
from math import isfinite
from statistics import fmean
from typing import Any, Iterable
from urllib.parse import quote, urlparse


APPROVED_SOURCES = frozenset({"twse", "tpex", "mops", "taiex", "tpex-benchmark", "taifex", "tdcc", "finmind"})


def analysis_cutoff(as_of: date) -> datetime:
    return datetime.combine(as_of, time.max, timezone(timedelta(hours=8))).astimezone(timezone.utc)


def canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()


def _number(value: Any) -> float | None:
    try:
        result = float(str(value).replace(",", "")) if value not in (None, "") else None
        return result if result is not None and isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _instant(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.combine(date.fromisoformat(text[:10]), time.min)
        except ValueError:
            return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _row_time(row: dict[str, Any]) -> datetime | None:
    for field in ("published_at", "observed_at", "trade_date", "observed_date", "effective_date"):
        parsed = _instant(row.get(field))
        if parsed:
            return parsed
    return None


def _value_time(row: dict[str, Any]) -> datetime | None:
    for field in ("trade_date", "observed_date", "effective_date", "published_at", "observed_at"):
        parsed = _instant(row.get(field))
        if parsed:
            return parsed
    return None


def _financial_period_time(row: dict[str, Any]) -> datetime | None:
    explicit = _instant(row.get("fiscal_period_end"))
    if explicit:
        return explicit
    try:
        year = int(row.get("fiscal_year", 0))
        quarter = int(row.get("fiscal_quarter", 0))
    except (TypeError, ValueError):
        return None
    month_day = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}.get(quarter)
    if year <= 0 or month_day is None:
        return None
    return datetime(year, month_day[0], month_day[1], tzinfo=timezone.utc)


def _severity(value: Any) -> float | None:
    numeric = _number(value)
    if numeric is not None:
        return max(0, min(100, numeric))
    return {"low": 25.0, "medium": 50.0, "high": 75.0, "critical": 100.0}.get(str(value).strip().lower())


def _metric(row: dict[str, Any]) -> str:
    return str(row.get("metric") or row.get("event_type") or row.get("investor_type") or "observation")


def _evidence_id(dataset_id: str, row: dict[str, Any], core_snapshot_id: str) -> str:
    snapshot = str(row.get("__snapshot_id", core_snapshot_id))
    identity = canonical_json([dataset_id, row.get("symbol"), _metric(row), _row_time(row),
                               row.get("value", row.get("close", row.get("net_shares", row.get("pe_ratio", row.get("severity"))))),
                               row.get("provenance_id", ""), snapshot])
    return f"ev-{sha256(identity).hexdigest()[:24]}"


def evidence_from_rows(datasets: dict[str, list[dict[str, Any]]], core_snapshot_id: str) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for dataset_id, rows in sorted(datasets.items()):
        for row in rows:
            table = str(row.get("__table_identifier", f"core.{dataset_id.replace('-', '_')}_v1"))
            snapshot = str(row.get("__snapshot_id", core_snapshot_id))
            provenance = str(row.get("provenance_id", "")).strip()
            is_financial = dataset_id == "financials"
            availability = _instant(row.get("availability_at")) if is_financial else None
            publication_authoritative = not is_financial or row.get("publication_time_authoritative") is True
            published = _instant(row.get("published_at")) if publication_authoritative else None
            observed = availability if is_financial else _row_time(row)
            record = _financial_period_time(row) if is_financial else _value_time(row)
            metric = _metric(row)
            value = row.get("value")
            unit = row.get("unit")
            if value is None:
                for name, fallback_unit in (("close", "TWD_or_index_points"), ("net_shares", "shares"),
                                            ("pe_ratio", "ratio"), ("severity", "score_0_100")):
                    if row.get(name) is not None:
                        value, unit = row[name], fallback_unit
                        break
            evidence.append({
                "evidence_id": _evidence_id(dataset_id, row, core_snapshot_id),
                "dataset_id": dataset_id,
                "symbol": row.get("symbol"),
                "metric": metric,
                "value": value,
                "unit": unit or "not_applicable",
                "source_id": row.get("source_id"),
                "source_authorization": row.get("source_authorization", "official" if row.get("source_id") in APPROVED_SOURCES else "blocked"),
                "published_at": published.isoformat().replace("+00:00", "Z") if published else None,
                "availability_at": availability.isoformat().replace("+00:00", "Z") if availability else None,
                "publication_time_authoritative": publication_authoritative,
                "observed_at": observed.isoformat().replace("+00:00", "Z") if observed else None,
                "record_at": record.isoformat().replace("+00:00", "Z") if record else None,
                "quality_flag": row.get("quality_flag", "good"),
                "severity": _severity(row.get("severity")),
                "manual_review_required": row.get("manual_review_required") is True,
                "provenance_id": provenance,
                "core_snapshot_id": core_snapshot_id,
                "location": f"iceberg://{quote(table, safe='.') }?snapshot={quote(snapshot)}&provenance={quote(provenance)}",
            })
    return evidence


def validate_evidence(items: Iterable[dict[str, Any]], analysis_as_of: date) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[str]]:
    cutoff = analysis_cutoff(analysis_as_of)
    rows = list(items)
    newest: dict[str, datetime] = {}
    for item in rows:
        observed = _instant(item.get("observed_at"))
        if observed and observed <= cutoff:
            newest[item["dataset_id"]] = max(observed, newest.get(item["dataset_id"], observed))
    stale_days = {"ohlcv": 14, "valuation": 14, "institutional": 14, "benchmark": 14,
                  "market-activity": 14, "financials": 400, "events": 180}
    rejected: list[dict[str, str]] = []
    valid: list[dict[str, Any]] = []
    blockers: set[str] = set()
    seen: set[str] = set()
    claims: dict[tuple[Any, ...], Any] = {}
    for item in rows:
        reason = ""
        parsed = urlparse(str(item.get("location", "")))
        observed = _instant(item.get("observed_at"))
        if parsed.scheme not in {"https", "gs", "iceberg"} or not parsed.netloc:
            reason = "invalid_url"
        elif item.get("source_authorization") not in {"official", "approved_fallback"}:
            reason = "source_not_authorized"
        elif not item.get("provenance_id") or not item.get("core_snapshot_id"):
            reason = "missing_provenance"
        elif item.get("dataset_id") == "financials" and not item.get("availability_at"):
            reason = "missing_availability_time"
        elif item.get("dataset_id") == "events" and not item.get("published_at"):
            reason = "missing_publication_time"
        elif observed is None:
            reason = "missing_observation_time"
        elif observed > cutoff or (_instant(item.get("published_at")) or observed) > cutoff \
                or (_instant(item.get("record_at")) or observed) > cutoff:
            reason = "future_leakage"
        elif item.get("evidence_id") in seen:
            reason = "duplicate"
        elif newest.get(item["dataset_id"]) and (cutoff - newest[item["dataset_id"]]).days > stale_days.get(item["dataset_id"], 30):
            reason = "stale"
        elif _number(item.get("value")) is not None and not item.get("unit"):
            reason = "missing_unit"
        key = (item.get("dataset_id"), item.get("symbol"), item.get("metric"), item.get("record_at"))
        if not reason and key in claims:
            if claims[key] == item.get("value"):
                reason = "duplicate"
            else:
                reason = "conflict"
                blockers.add("manual_review")
        if reason:
            rejected.append({"evidence_id": str(item.get("evidence_id", "")), "reason": reason})
            if reason in {"invalid_url", "source_not_authorized", "future_leakage"}:
                blockers.add("invalid_evidence")
            continue
        seen.add(str(item["evidence_id"]))
        claims[key] = item.get("value")
        if item.get("quality_flag") == "critical":
            blockers.add("critical_data_quality")
        if item.get("manual_review_required") is True:
            blockers.add("manual_review")
        severity = _severity(item.get("severity"))
        if severity is not None and severity >= 75:
            blockers.add("high_event_risk")
        valid.append(item)
    if any(item.get("dataset_id") == "financials" for item in rows) and not any(
        item.get("dataset_id") == "financials" for item in valid
    ):
        blockers.add("invalid_evidence")
    return valid, rejected, sorted(blockers)


def _scope_rows(datasets: dict[str, list[dict[str, Any]]], symbols: frozenset[str]) -> dict[str, list[dict[str, Any]]]:
    if not symbols:
        return datasets
    return {name: [row for row in rows if not row.get("symbol") or str(row["symbol"]) in symbols]
            for name, rows in datasets.items()}


def _research_rows(datasets: dict[str, list[dict[str, Any]]], as_of: date) -> dict[str, list[dict[str, Any]]]:
    """Select PIT financial revisions and the matching market benchmark before feature calculation."""
    cutoff = analysis_cutoff(as_of)
    result = {name: list(rows) for name, rows in datasets.items()}
    latest, invalid = {}, []
    for row in result.get("financials", []):
        available = _instant(row.get("availability_at"))
        if available is None or available > cutoff:
            invalid.append(row)
            continue
        key = tuple(str(row.get(name)) for name in ("symbol", "fiscal_year", "fiscal_quarter", "statement_type", "metric", "source_id"))
        if key not in latest or available > _instant(latest[key]["availability_at"]):
            latest[key] = row
    if "financials" in result:
        result["financials"] = sorted(latest.values(), key=lambda row: (_financial_period_time(row) or datetime.min.replace(tzinfo=timezone.utc),
                                                                        str(row.get("metric")))) + invalid
    markets = {str(row.get("market", "TWSE")).upper() for row in result.get("ohlcv", [])}
    benchmark = "TPEx" if markets == {"TPEX"} else "TAIEX" if markets <= {"TWSE"} else None
    if benchmark and "benchmark" in result:
        result["benchmark"] = [row for row in result["benchmark"] if row.get("benchmark_id") == benchmark
                               and row.get("index_kind", "price") == "price"]
    symbols = {str(row["symbol"]) for rows in result.values() for row in rows if row.get("symbol")}
    if any(len(rows) > 5000 * max(1, len(symbols)) for rows in result.values()):
        raise ValueError("research scope exceeds bounded dataset row limit")
    return result


def _series(rows: Iterable[dict[str, Any]], field: str, *, total: bool = False) -> list[float]:
    grouped: dict[datetime, list[float]] = {}
    for row in rows:
        observed, number = _value_time(row), _number(row.get(field))
        if observed is not None and number is not None:
            grouped.setdefault(observed, []).append(number)
    return [sum(grouped[when]) if total else fmean(grouped[when]) for when in sorted(grouped)]


def _change(values: list[float], window: int) -> float | None:
    if len(values) <= window or values[-window - 1] == 0:
        return None
    return round((values[-1] / values[-window - 1] - 1) * 100, 6)


def _financial_features_v2(rows):
    """Compare one statement/period/unit/scope series; keep unproven EPS basis missing."""
    monthly = [r for r in rows if r.get("statement_type") == "monthly_revenue"]
    quarterly = [r for r in rows if r.get("metric", "").startswith("revenue_") and r.get("is_single_quarter")]
    legacy_revenue = [r for r in rows if str(r.get("metric", "")).lower() in {"revenue", "營業收入"}]
    eps = [r for r in rows if r.get("metric", "").startswith("eps_") and r.get("unit") == "TWD_per_share" and r.get("is_single_quarter")]

    def comparable(series):
        if any(r.get("source_id") == "mops" for r in series):
            series = [r for r in series if r.get("source_id") == "mops"]
        identities = {(r.get("symbol"), r.get("source_id"), r.get("report_scope"), r.get("unit"), r.get("currency")) for r in series}
        if len(identities) != 1:
            return []
        return sorted(series, key=lambda r: (_financial_period_time(r) or datetime.min.replace(tzinfo=timezone.utc)))

    revenue = comparable(monthly or quarterly or legacy_revenue)
    eps = comparable(eps)
    def trend(series):
        values = [_number(r.get("value")) for r in series]
        return round((values[-1]/values[0]-1)*100, 6) if len(values) > 1 and None not in values and values[0] else None

    eps_basis_known = bool(eps) and all(r.get("share_basis_status") == "comparable" for r in eps)
    history = [{"period_end": str(r.get("fiscal_period_end", "")), "value": _number(r.get("value")),
                "unit": r.get("unit"), "period_basis": r.get("period_basis"), "report_scope": r.get("report_scope")}
               for r in comparable(monthly)[-12:]]
    balances = {}
    for row in rows:
        if row.get("statement_type") == "balance" and row.get("metric") in {"total_liabilities_snapshot", "total_equity_snapshot"}:
            key = (row.get("symbol"), str(row.get("fiscal_period_end")), row.get("source_id"),
                   row.get("report_scope"), row.get("unit"), row.get("currency"))
            balances.setdefault(key, {})[row["metric"]] = _number(row.get("value"))
    matching = [(key, value) for key, value in balances.items() if key[-2:] == ("TWD", "TWD") and
                value.get("total_liabilities_snapshot") is not None and value.get("total_equity_snapshot")]
    latest = max(matching, key=lambda item: item[0][1])[1] if matching else None
    debt = round(latest["total_liabilities_snapshot"]/latest["total_equity_snapshot"], 6) if latest else None
    reasons = {}
    if trend(revenue) is None:
        reasons["revenue_trend_percent"] = "insufficient_comparable_revenue_series"
    if not eps_basis_known:
        reasons["eps_trend_percent"] = "historical_eps_share_basis_unknown"
    roe_rows = [r for r in rows if r.get("unit") == "percent" and r.get("metric") in {"roe", "權益報酬率", "權益報酬率(%)"}]
    roe_rows.sort(key=lambda r: _financial_period_time(r) or datetime.min.replace(tzinfo=timezone.utc))
    growth = {}
    for metric in ("eps_yoy_percent_same_filing", "net_income_parent_yoy_percent_same_filing"):
        observations = [row for row in rows if row.get("metric") == metric and row.get("unit") == "percent"
                        and row.get("financial_feature_version") == "same-filing-comparatives-v1"]
        observations.sort(key=lambda row: (str(row.get("fiscal_period_end", "")), str(row.get("availability_at", ""))))
        growth[metric] = _number(observations[-1]["value"]) if observations else None
    return {"fundamental": {**growth, "revenue_trend_percent": trend(revenue),
                            "revenue_trend_basis": "monthly" if monthly else "single_quarter" if quarterly else "legacy_reported",
                            "eps_trend_percent": trend(eps) if eps_basis_known else None,
                            "monthly_revenue_history_12": history, "missing_reasons": reasons},
            "valuation": {"debt_to_equity": debt, "roe": _number(roe_rows[-1].get("value")) if roe_rows else None}}


