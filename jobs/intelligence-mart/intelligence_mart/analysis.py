"""Deterministic PIT features, five roles, evidence validation and aggregation."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from hashlib import sha256
import json
from math import tanh
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable
from urllib.parse import quote, urlparse


ROLE_WEIGHTS = {
    "fundamental": 0.25,
    "valuation": 0.20,
    "positioning": 0.20,
    "quant": 0.25,
    "event_risk": 0.10,
}
APPROVED_SOURCES = frozenset({"twse", "tpex", "mops", "taiex", "tpex-benchmark", "taifex", "tdcc", "finmind"})
ROLE_DATASETS = {
    "fundamental": frozenset({"financials"}),
    "valuation": frozenset({"valuation", "financials"}),
    "positioning": frozenset({"institutional", "ohlcv"}),
    "quant": frozenset({"ohlcv", "benchmark", "market-activity"}),
    "event_risk": frozenset({"events"}),
}
FACT_PACK_VERSION = "1.0.0"


def canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()


def prompt_bundle(path: Path | None = None) -> tuple[dict[str, Any], str]:
    target = path or Path(__file__).parents[1] / "prompts" / "five_roles.v1.json"
    payload = target.read_bytes()
    document = json.loads(payload)
    if set(document.get("roles", {})) != set(ROLE_WEIGHTS):
        raise ValueError("five-role prompt bundle is incomplete")
    return document, f"sha256:{sha256(payload).hexdigest()}"


def governance_bundle(path: Path | None = None) -> tuple[dict[str, Any], str]:
    target = path or Path(__file__).parents[3] / "packages" / "governance" / "policy.json"
    payload = target.read_bytes()
    document = json.loads(payload)
    if set(document.get("roleWeights", {})) != set(ROLE_WEIGHTS):
        raise ValueError("governance role weights are incomplete")
    return document, f"sha256:{sha256(payload).hexdigest()}"


def _number(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", "")) if value not in (None, "") else None
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
    cutoff = datetime.combine(analysis_as_of, time.max, timezone.utc)
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
    cutoff = datetime.combine(as_of, time.max, tzinfo=timezone.utc)
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
    eps = [r for r in rows if r.get("metric", "").startswith("eps_") and r.get("is_single_quarter")]

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
    return {"fundamental": {"revenue_trend_percent": trend(revenue),
                            "revenue_trend_basis": "monthly" if monthly else "single_quarter" if quarterly else "legacy_reported",
                            "eps_trend_percent": trend(eps) if eps_basis_known else None,
                            "monthly_revenue_history_12": history, "missing_reasons": reasons},
            "valuation": {"debt_to_equity": debt, "roe": _number(roe_rows[-1].get("value")) if roe_rows else None}}


def _features(datasets: dict[str, list[dict[str, Any]]], *, feature_version="1") -> dict[str, Any]:
    ohlcv = datasets.get("ohlcv", [])
    close = _series(ohlcv, "close")
    volume = _series(ohlcv, "volume_shares")
    turnover = _series(ohlcv, "turnover_twd")
    recent_high = max(close[-21:-1]) if len(close) >= 21 else None
    volume_mean = fmean(volume[-20:]) if volume else None
    latest_volume = volume[-1] if volume else None
    screening = {
        "breakout_20d": bool(recent_high is not None and close[-1] >= recent_high),
        "volume_ratio_20d": round(latest_volume / volume_mean, 6) if latest_volume is not None and volume_mean else None,
        "liquidity_turnover_20d": round(fmean(turnover[-20:]), 2) if turnover else None,
        "return_anomaly": abs(_change(close, 1) or 0) >= 11,
    }
    financials = sorted(datasets.get("financials", []), key=lambda row: (
        int(row.get("fiscal_year", 0)), int(row.get("fiscal_quarter", 0)), _row_time(row) or datetime.min.replace(tzinfo=timezone.utc)
    ))
    metric_values: dict[str, list[float]] = {}
    metric_history: dict[str, list[dict[str, Any]]] = {}
    for row in financials:
        number = _number(row.get("value"))
        if number is not None:
            metric_name = str(row.get("metric", "unknown")).lower()
            metric_values.setdefault(metric_name, []).append(number)
            metric_history.setdefault(metric_name, []).append({
                "fiscal_year": row.get("fiscal_year"), "fiscal_quarter": row.get("fiscal_quarter"),
                "value": number, "unit": row.get("unit"),
            })
    def trend(tokens: tuple[str, ...]) -> float | None:
        values = [value for metric, numbers in metric_values.items() if any(token in metric for token in tokens) for value in numbers]
        return round((values[-1] / values[0] - 1) * 100, 6) if len(values) > 1 and values[0] else None
    valuation_rows = sorted(datasets.get("valuation", []), key=lambda row: _value_time(row) or datetime.min.replace(tzinfo=timezone.utc))
    valuation = valuation_rows[-1] if valuation_rows else {}
    def latest_metric(tokens: tuple[str, ...]) -> float | None:
        values = [numbers[-1] for metric, numbers in metric_values.items() if any(token in metric for token in tokens)]
        return values[-1] if values else None
    institutional = datasets.get("institutional", [])
    net = _series(institutional, "net_shares", total=True)
    benchmark = _series(datasets.get("benchmark", []), "close")
    returns = [(close[i] / close[i - 1] - 1) for i in range(1, len(close)) if close[i - 1]]
    bench_returns = [(benchmark[i] / benchmark[i - 1] - 1) for i in range(1, len(benchmark)) if benchmark[i - 1]]
    paired = min(len(returns), len(bench_returns), 120)
    beta = None
    if paired >= 20:
        xs, ys = bench_returns[-paired:], returns[-paired:]
        xm, ym = fmean(xs), fmean(ys)
        variance = sum((x - xm) ** 2 for x in xs)
        beta = round(sum((x - xm) * (y - ym) for x, y in zip(xs, ys)) / variance, 6) if variance else None
    true_ranges = []
    ordered_ohlcv = sorted(ohlcv, key=lambda row: _value_time(row) or datetime.min.replace(tzinfo=timezone.utc))
    for previous, row in zip(ordered_ohlcv, ordered_ohlcv[1:]):
        high, low, previous_close = _number(row.get("high")), _number(row.get("low")), _number(previous.get("close"))
        if None not in (high, low, previous_close):
            true_ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    atr_14 = round(fmean(true_ranges[-14:]), 6) if true_ranges else None
    stock_20, benchmark_20 = _change(close, 20), _change(benchmark, 20)
    peak = close[0] if close else None
    drawdowns = []
    for value in close[-120:]:
        peak = max(peak, value) if peak is not None else value
        if peak:
            drawdowns.append((value / peak - 1) * 100)
    events = datasets.get("events", [])
    severities = [_severity(row.get("severity")) for row in events]
    result = {
        "screening": screening,
        "fundamental": {"revenue_trend_percent": trend(("revenue", "營業收入")), "eps_trend_percent": trend(("eps", "每股盈餘")),
                        "observations": len(financials), "history_12": {key: values[-12:] for key, values in metric_history.items()}},
        "valuation": {"pe_ratio": _number(valuation.get("pe_ratio")), "pb_ratio": _number(valuation.get("pb_ratio")),
                      "dividend_yield_percent": _number(valuation.get("dividend_yield_percent")),
                      "roe": latest_metric(("roe", "權益報酬率")),
                      "debt_to_equity": latest_metric(("debt_to_equity", "d/e", "負債權益比", "負債比率"))},
        "positioning": ({f"net_shares_{window}d": round(sum(net[-window:]), 2) if net else None for window in (5, 20, 60)}
                        | {f"net_volume_ratio_{window}d": round(sum(net[-window:]) / sum(volume[-window:]) * 100, 6)
                           if net and sum(volume[-window:]) else None for window in (5, 20, 60)}
                        | {"net_shares_previous_5d": round(sum(net[-10:-5]), 2) if len(net) >= 10 else None,
                           "net_volume_ratio_previous_5d": round(sum(net[-10:-5]) / sum(volume[-10:-5]) * 100, 6)
                           if len(net) >= 10 and sum(volume[-10:-5]) else None}),
        "quant": {"return_20d": stock_20, "return_60d": _change(close, 60), "return_120d": _change(close, 120),
                  "relative_strength_20d": round(stock_20 - benchmark_20, 6) if stock_20 is not None and benchmark_20 is not None else None,
                  "max_drawdown_120d": round(min(drawdowns), 6) if drawdowns else None,
                  "beta_120d": beta, "atr_14d": atr_14,
                  "reference_stop": round(close[-1] - 2 * atr_14, 6) if close and atr_14 is not None else None,
                  "turnover_20d": screening["liquidity_turnover_20d"]},
        "event_risk": {"dataset_available": "events" in datasets, "event_count": len(events),
                       "max_severity": max((value for value in severities if value is not None), default=None)},
    }
    if feature_version == "2":
        for role, values in _financial_features_v2(financials).items():
            result[role].update(values)
        price_days = {str(r.get("trade_date")): _number(r.get("close")) for r in ohlcv}
        bench_days = {str(r.get("trade_date")): _number(r.get("close")) for r in datasets.get("benchmark", [])}
        def dated_returns(values):
            ordered = sorted(values)
            return {(first, last): values[last]/values[first]-1 for first, last in zip(ordered, ordered[1:])
                    if values[first] and values[last] is not None}
        stock_returns, index_returns = dated_returns(price_days), dated_returns(bench_days)
        periods = sorted(set(stock_returns) & set(index_returns))[-120:]
        aligned_beta = None
        if len(periods) >= 20:
            xs, ys = [index_returns[p] for p in periods], [stock_returns[p] for p in periods]
            xm, ym = fmean(xs), fmean(ys)
            variance = sum((x-xm)**2 for x in xs)
            aligned_beta = round(sum((x-xm)*(y-ym) for x, y in zip(xs, ys))/variance, 6) if variance else None
        result["quant"].update(beta_120d=aligned_beta, beta_aligned_intervals=len(periods))
        nets = {}
        for row in institutional:
            value = _number(row.get("net_shares"))
            if value is not None:
                day = str(row.get("trade_date"))
                nets[day] = nets.get(day, 0)+value
        volumes = {str(r.get("trade_date")): _number(r.get("volume_shares")) for r in ohlcv}
        joined = sorted(day for day in set(nets) & set(volumes) if volumes[day] is not None)
        for window in (5, 20, 60):
            days = joined[-window:]
            denominator = sum(volumes[d] for d in days)
            result["positioning"][f"net_shares_{window}d"] = round(sum(nets[d] for d in days), 2) if len(days) == window else None
            result["positioning"][f"net_volume_ratio_{window}d"] = round(sum(nets[d] for d in days)/denominator*100, 6) if len(days) == window and denominator else None
        previous = joined[-10:-5]
        denominator = sum(volumes[d] for d in previous)
        result["positioning"].update(net_shares_previous_5d=round(sum(nets[d] for d in previous), 2) if len(previous) == 5 else None,
            net_volume_ratio_previous_5d=round(sum(nets[d] for d in previous)/denominator*100, 6) if len(previous) == 5 and denominator else None,
            aligned_trading_days=len(joined), denominator_basis="same-date TWSE volume_shares; full requested trading-day window")
    return result


def _role(name: str, features: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    values = features[name]
    score: float | None
    if name == "fundamental":
        trends = [values[key] for key in ("revenue_trend_percent", "eps_trend_percent") if values[key] is not None]
        score = round(max(0, min(100, 50 + fmean(trends))), 4) if trends else None
    elif name == "valuation":
        parts = ([max(0, min(100, (30 - values["pe_ratio"]) / 30 * 100))] if values["pe_ratio"] not in (None, 0) else [])
        parts += [max(0, min(100, (5 - values["pb_ratio"]) / 5 * 100))] if values["pb_ratio"] is not None else []
        parts += [max(0, min(100, values["roe"] * 4))] if values["roe"] is not None else []
        parts += [max(0, min(100, (2 - values["debt_to_equity"]) / 2 * 100))] if values["debt_to_equity"] is not None else []
        score = round(fmean(parts), 4) if parts else None
    elif name == "positioning":
        ratios = [values[f"net_volume_ratio_{window}d"] for window in (5, 20, 60)
                  if values[f"net_volume_ratio_{window}d"] is not None]
        score = round(50 + 50 * tanh(fmean(ratios) / 10), 4) if ratios else None
    elif name == "quant":
        returns = [values[key] for key in ("return_20d", "return_60d", "return_120d") if values[key] is not None]
        score = round(max(0, min(100, 50 + fmean(returns))), 4) if returns else None
    else:
        score = round(100 - min(100, values["max_severity"]), 4) if values["max_severity"] is not None else (100.0 if values["dataset_available"] else None)
    refs = [item["evidence_id"] for item in evidence if item["dataset_id"] in ROLE_DATASETS[name]]
    completeness = round(sum(value is not None for value in values.values()) / len(values), 4) if score is not None else 0.0
    return {"role": name, "score": score, "completeness": completeness,
            "confidence": round(min(1.0, len(refs) / 12), 4) if score is not None else 0.0,
            "missing_data": [key for key, value in values.items() if value is None], "evidence_ids": refs, "features": values}


def _fact_packs(*, roles: list[dict[str, Any]], evidence: list[dict[str, Any]], analysis_as_of: str,
                core_snapshot_id: str, feature_version: object) -> list[dict[str, Any]]:
    evidence_by_id = {item["evidence_id"]: item for item in evidence}
    packs: list[dict[str, Any]] = []
    for role in roles:
        selected = [evidence_by_id[evidence_id] for evidence_id in role["evidence_ids"] if evidence_id in evidence_by_id]
        selected.sort(key=lambda item: item["evidence_id"])
        evidence_hash = f"sha256:{sha256(canonical_json(selected)).hexdigest()}"
        payload = {
            "fact_pack_version": FACT_PACK_VERSION,
            "pack_type": role["role"],
            "analysis_as_of": analysis_as_of,
            "core_snapshot_id": core_snapshot_id,
            "feature_version": str(feature_version),
            "facts": role["features"],
            "missing_data": role["missing_data"],
            "evidence_ids": role["evidence_ids"],
            "provenance_ids": sorted({item["provenance_id"] for item in selected}),
            "evidence_hash": evidence_hash,
            "baseline": {
                "role": role["role"],
                "score": role["score"],
                "completeness": role["completeness"],
                "confidence": role["confidence"],
                "score_semantics": "deterministic_regression_baseline_not_full_research_analysis",
            },
        }
        payload["fact_pack_hash"] = f"sha256:{sha256(canonical_json(payload)).hexdigest()}"
        packs.append(payload)
    return packs


def _aggregate(roles: list[dict[str, Any]], blockers: list[str], weights: dict[str, float], data_quality: str,
               completeness_gate: float) -> dict[str, Any]:
    scored = [role for role in roles if role["score"] is not None]
    completeness = round(sum(role["completeness"] for role in roles) / len(weights), 4)
    quality_factor = {"good": 1.0, "warning": 0.5, "critical": 0.0, "unknown": 0.0}[data_quality]
    raw_weights = {role["role"]: weights[role["role"]] * role["completeness"] * role["confidence"] * quality_factor for role in scored}
    available_weight = sum(raw_weights.values())
    contributions = [{"role": role["role"], "initial_weight": weights[role["role"]],
                      "effective_weight": round(raw_weights[role["role"]] / available_weight, 6),
                      "contribution": round(role["score"] * raw_weights[role["role"]] / available_weight, 6)}
                     for role in scored] if available_weight else []
    score = round(sum(item["contribution"] for item in contributions), 6) if contributions else None
    if "invalid_evidence" in blockers or "critical_data_quality" in blockers:
        outcome, status, reason = "invalid", "blocked", ",".join(blockers)
    elif "manual_review" in blockers:
        outcome, status, reason = "review_required", "blocked", ",".join(blockers)
    elif "high_event_risk" in blockers:
        outcome, status, reason = "risk_blocked", "blocked", ",".join(blockers)
    elif completeness < completeness_gate or score is None:
        outcome, status, reason = "insufficient_data", "blocked", "completeness_below_30_percent"
    else:
        outcome, status, reason = "complete", "publishable", None
    positive = [role["role"] for role in scored if role["score"] >= 60]
    negative = [role["role"] for role in scored if role["score"] <= 40]
    return {"aggregate_score": score, "completeness": completeness,
            "confidence": round(fmean(role["confidence"] for role in scored), 4) if scored else 0.0,
            "bull": positive, "bear": negative,
            "contradictions": [f"{bull}_positive_vs_{bear}_negative" for bull in positive for bear in negative],
            "contributions": contributions,
            "devils_advocate": {"counter_roles": negative if score is not None and score >= 50 else positive,
                                 "evidence_ids": [evidence for role in scored if (role["score"] < 50) == (score is not None and score >= 50) for evidence in role["evidence_ids"][:3]]},
            "confidence_semantics": "data_and_analysis_confidence_not_profit_probability",
            "analysis_outcome": outcome, "publication_status": status, "reason": reason}


def scopes(options: dict[str, Any], requested_symbols: tuple[str, ...]) -> list[dict[str, Any]]:
    configured = options.get("scopes")
    if configured is None:
        if not requested_symbols:
            raise ValueError("analysis execution requires requested symbols or explicit scopes")
        return [{"type": "symbol", "id": symbol, "name": symbol, "coverage": "symbol", "symbols": [symbol]}
                for symbol in requested_symbols]
    if not isinstance(configured, list) or not configured:
        raise ValueError("scopes must be a non-empty array")
    result = []
    for item in configured:
        if not isinstance(item, dict) or item.get("type") not in {"market", "industry", "symbol"} or not str(item.get("id", "")).strip():
            raise ValueError("invalid analysis scope")
        members = item.get("symbols", [])
        if item["type"] == "symbol":
            members = [item["id"]]
        if item["type"] == "industry" and not members:
            raise ValueError("industry scope requires immutable membership symbols")
        result.append({"type": item["type"], "id": str(item["id"]), "name": str(item.get("name", item["id"])),
                       "coverage": str(item.get("coverage", {"market": "market_wide", "industry": "industry_membership", "symbol": "symbol"}[item["type"]])),
                       "symbols": sorted(set(map(str, members)))})
    return result


def analyze(*, execution_id: str, analysis_as_of: str, core_snapshot_id: str, requested_symbols: tuple[str, ...],
            options: dict[str, Any], datasets: dict[str, list[dict[str, Any]]], prompts: dict[str, Any],
            prompt_hash: str) -> list[dict[str, Any]]:
    if options.get("prompt_version") not in (None, prompts["version"]) or options.get("prompt_hash") not in (None, prompt_hash):
        raise ValueError("execution prompt fence does not match repository prompt")
    policy, policy_hash = governance_bundle()
    if options.get("governance_policy_hash") not in (None, policy_hash):
        raise ValueError("execution governance fence does not match repository policy")
    weights = {name: float(value) for name, value in options.get("role_weights", policy["roleWeights"]).items()}
    if set(weights) != set(ROLE_WEIGHTS) or any(value <= 0 for value in weights.values()) or abs(sum(weights.values()) - 1) > 1e-9:
        raise ValueError("immutable governance role weights must be positive and sum to one")
    components = options.get("published_components", [])
    if not isinstance(components, list) or any(
        not isinstance(item, dict) or item.get("publication_status") != "published"
        or item.get("analysis_as_of") != analysis_as_of or not str(item.get("artifact_uri", "")).startswith("gs://")
        for item in components
    ):
        raise ValueError("daily brief sources must be published artifacts from the same analysis_as_of")
    reports = []
    for scope in scopes(options, requested_symbols):
        selected = _research_rows(_scope_rows(datasets, frozenset(scope["symbols"])), date.fromisoformat(analysis_as_of))
        evidence, rejected, blockers = validate_evidence(evidence_from_rows(selected, core_snapshot_id), date.fromisoformat(analysis_as_of))
        required_datasets = set(map(str, options.get("required_datasets", ())))
        if required_datasets - set(selected):
            blockers = sorted(set(blockers) | {"invalid_evidence"})
        if options.get("manual_review_required") is True:
            blockers = sorted(set(blockers) | {"manual_review"})
        valid_ids = {item["evidence_id"] for item in evidence}
        validated = {name: [row for row in rows if _evidence_id(name, row, core_snapshot_id) in valid_ids]
                     for name, rows in selected.items() if not rows or any(_evidence_id(name, row, core_snapshot_id) in valid_ids for row in rows)}
        features = _features(validated, feature_version=options["feature_version"])
        roles = [_role(name, features, evidence) for name in ROLE_WEIGHTS]
        fact_packs = _fact_packs(roles=roles, evidence=evidence, analysis_as_of=analysis_as_of,
                                 core_snapshot_id=core_snapshot_id, feature_version=options["feature_version"])
        data_quality = "critical" if "critical_data_quality" in blockers else ("warning" if rejected else "good")
        aggregate = _aggregate(roles, blockers, weights, data_quality, float(policy["developmentCompletenessGate"]))
        aggregate.update({
            "screening_summary": features["screening"],
            "risk_summary": {"event_risk": features["event_risk"], "quant": features["quant"]},
            "sentiment_summary": {"status": "unavailable", "reason": "no_approved_text_features"},
            "cio_summary": {"stance": ("bullish" if aggregate["aggregate_score"] is not None and aggregate["aggregate_score"] >= 60
                                        else "bearish" if aggregate["aggregate_score"] is not None and aggregate["aggregate_score"] <= 40
                                        else "neutral"),
                            "score": aggregate["aggregate_score"], "confidence": aggregate["confidence"]},
        })
        report = {
            "schema_version": options["schema_version"], "feature_version": options["feature_version"],
            "model_version": options["model_version"], "governance_snapshot_version": options["governance_snapshot_version"],
            "execution_id": execution_id, "analysis_as_of": analysis_as_of, "core_snapshot_id": core_snapshot_id,
            "scope": scope, "membership_snapshot": scope["symbols"],
            "membership_snapshot_hash": f"sha256:{sha256(canonical_json(scope)).hexdigest()}",
            "prompt_version": prompts["version"], "prompt_hash": prompt_hash,
            "governance": {"policy_version": policy["version"], "policy_hash": policy_hash,
                           "role_weights": weights, "completeness_gate": policy["developmentCompletenessGate"],
                           "high_event_risk_threshold": policy["blocking"]["highRiskScoreAtLeast"],
                           "manual_review_required": options.get("manual_review_required") is True},
            "features": features, "roles": roles, "fact_packs": fact_packs,
            "evidence": evidence, "rejected_evidence": rejected,
            "data_quality": data_quality, "aggregate": aggregate,
        }
        if scope["type"] == "market" and components:
            report["published_components"] = components
        # Execution identity is audit metadata, not analytical input. Exclude
        # it so rebuilding the same immutable snapshot/as-of is comparable.
        hash_payload = {key: value for key, value in report.items() if key != "execution_id"}
        report["deterministic_hash"] = f"sha256:{sha256(canonical_json(hash_payload)).hexdigest()}"
        reports.append(report)
    return reports
