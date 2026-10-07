"""Public-only, PIT deterministic specialist baselines; never invokes a provider."""

from __future__ import annotations

from datetime import date
from hashlib import sha256
from math import isfinite, sqrt
from statistics import fmean, pstdev
from typing import Any

from .facts import (analysis_cutoff, canonical_json, _change, _evidence_id, _financial_features_v2, _instant, _severity,
                       _research_rows, evidence_from_rows, validate_evidence)

VERSION = "specialist-rules-v2"
FEATURE_VERSION = "2"
MODEL_VERSION = "deterministic-unpromoted-v1"
DEPENDENCIES = {
    "fundamental": ("financials",),
    "valuation": ("financials", "valuation", "ohlcv"),
    "quant": ("ohlcv", "benchmark"),
    "risk": ("ohlcv", "benchmark"),
    "event": ("events",),
}
TITLES = {"fundamental": "基本面", "valuation": "估值", "quant": "量化",
          "risk": "風險", "event": "事件"}
METRIC_LABELS = {"revenue_trend_percent": "可比較營收期間變化（%）", "eps_trend_percent": "可比較每股盈餘期間變化（%）",
                 "eps_yoy_percent_same_filing": "同份財報每股盈餘年增率（%）",
                 "net_income_parent_yoy_percent_same_filing": "同份財報歸屬母公司獲利年增率（%）",
                 "pe_ratio": "本益比", "pb_ratio": "股價淨值比", "dividend_yield_percent": "殖利率（%）",
                 "debt_to_equity": "負債／權益", "roe": "權益報酬率（%）",
                 "volatility_annualized": "年化歷史波動（比率）", "historical_cvar_95_daily": "最差 5% 日報酬平均（比率）",
                 "max_drawdown_120d": "120 日最大回撤（比率）", "beta_120d": "相對市場敏感度",
                 "aligned_intervals": "與市場對齊的報酬區間數", "event_count": "已驗證事件筆數", "max_severity": "事件最高嚴重度",
                 "dcf_value_per_share": "DCF 價值", "reverse_dcf_growth": "價格隱含成長率",
                 "expected_excess_return": "樣本外驗證超額報酬預測", "outperform_probability": "經校準勝過市場機率",
                 "regime_probability": "市場狀態模型", "classifier_probability": "本機事件分類模型"}
METRIC_LABELS.update({f"return_{w}d_percent": f"{w} 個交易日歷史報酬（%）" for w in (5, 20, 60, 120)})


def digest(value: object) -> str:
    return "sha256:" + sha256(canonical_json(value)).hexdigest()


def number(value: Any) -> float | None:
    try:
        result = float(str(value).replace(",", ""))
        return result if isfinite(result) else None
    except (ValueError, TypeError):
        return None


def validated_inputs(datasets, symbol, as_of, snapshot):
    """Reuse source validation, with availability and every timestamp fenced before features."""
    cutoff = analysis_cutoff(date.fromisoformat(as_of))
    scoped = {name: [r for r in rows if not r.get("symbol") or r.get("symbol") == symbol]
              for name, rows in datasets.items()}
    selected = _research_rows(scoped, date.fromisoformat(as_of))
    valid, rejected, _ = validate_evidence(evidence_from_rows(selected, snapshot), date.fromisoformat(as_of))
    accepted = {item["evidence_id"] for item in valid}
    result = {}
    for name, rows in selected.items():
        result[name] = []
        for row in rows:
            identity = _evidence_id(name, row, snapshot)
            if identity not in accepted:
                continue
            times = [row.get(k) for k in ("published_at", "availability_at", "observed_at", "record_at",
                                         "trade_date", "observed_date", "effective_date") if row.get(k) is not None]
            if any(_instant(t) is None or _instant(t) > cutoff for t in times):
                rejected.append({"evidence_id": identity, "reason": "future_or_invalid_time"})
                accepted.discard(identity)
                continue
            if row.get("quality_flag") == "critical":
                rejected.append({"evidence_id": identity, "reason": "critical_data_quality"})
                accepted.discard(identity)
                continue
            result[name].append(row)
    return result, [item for item in valid if item["evidence_id"] in accepted], rejected


def price_series(rows):
    """Never average contradictory prices or interpret missing dates as aligned returns."""
    days = {}
    for row in rows:
        day, close = str(row.get("trade_date", "")), number(row.get("close"))
        if not day or close is None or close <= 0:
            continue
        if day in days and days[day] != close:
            raise ValueError("conflicting daily close")
        days[day] = close
    return dict(sorted(days.items()))


def risk_metrics(prices, benchmark):
    values = list(prices.values())[-121:]
    returns = [b / a - 1 for a, b in zip(values, values[1:])]
    peak, drawdown = None, None
    for value in values:
        peak = max(peak or value, value)
        drawdown = min(drawdown or 0, value / peak - 1)
    def intervals(series):
        days = list(series)
        return {(a, b): series[b] / series[a] - 1 for a, b in zip(days, days[1:])}
    xs, ys = intervals(benchmark), intervals(prices)
    common = sorted(xs.keys() & ys.keys())[-120:]
    beta = None
    if len(common) >= 20:
        xm, ym = fmean(xs[k] for k in common), fmean(ys[k] for k in common)
        variance = sum((xs[k] - xm) ** 2 for k in common)
        if variance:
            beta = sum((xs[k] - xm) * (ys[k] - ym) for k in common) / variance
    cvar = None
    if len(returns) >= 60:
        import numpy as np
        from riskfolio.src.RiskFunctions import CVaR_Hist
        cvar = -float(CVaR_Hist(np.asarray(returns), alpha=.05))
    return {"volatility_annualized": pstdev(returns) * sqrt(252) if len(returns) >= 20 else None,
            "historical_cvar_95_daily": cvar,
            "max_drawdown_120d": drawdown if len(returns) >= 120 else None,
            "beta_120d": beta, "aligned_intervals": len(common)}


def discounted_cash_flow(fcf_per_share, discount_rate, terminal_growth, growth, years=5):
    """Scenario calculator; all inputs must be explicit, never invented from missing Core fields."""
    inputs = (fcf_per_share, discount_rate, terminal_growth, growth)
    if any(number(v) is None for v in inputs) or fcf_per_share <= 0 or discount_rate <= terminal_growth \
            or discount_rate <= 0 or terminal_growth <= -1 or growth <= -1 or not 1 <= years <= 20:
        raise ValueError("invalid DCF assumptions")
    flows = [fcf_per_share * (1 + growth) ** t for t in range(1, years + 1)]
    return sum(v / (1 + discount_rate) ** t for t, v in enumerate(flows, 1)) \
        + flows[-1] * (1 + terminal_growth) / (discount_rate - terminal_growth) / (1 + discount_rate) ** years


def reverse_dcf(price, fcf_per_share, discount_rate, terminal_growth, years=5):
    if number(price) is None or price <= 0:
        raise ValueError("invalid price")
    low, high = -.95, 2.
    if not discounted_cash_flow(fcf_per_share, discount_rate, terminal_growth, low, years) <= price \
            <= discounted_cash_flow(fcf_per_share, discount_rate, terminal_growth, high, years):
        return None
    for _ in range(80):
        mid = (low + high) / 2
        if discounted_cash_flow(fcf_per_share, discount_rate, terminal_growth, mid, years) < price:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def screening(datasets, symbols, as_of, snapshot):
    output = []
    for symbol in sorted(set(symbols)):
        rows, evidence, rejected = validated_inputs({"ohlcv": datasets.get("ohlcv", [])}, symbol, as_of, snapshot)
        prices = price_series(rows.get("ohlcv", []))
        values = list(prices.values())
        latest_day = max(prices, default=None)
        latest = next((r for r in reversed(rows.get("ohlcv", [])) if str(r.get("trade_date")) == latest_day), {})
        metrics = {f"return_{w}d_percent": _change(values, w) for w in (5, 20, 60, 120)}
        signals = [v for v in metrics.values() if v is not None]
        output.append({"symbol": symbol, "metrics": metrics,
                       "latest_trade_date": latest_day, "latest_close": prices.get(latest_day),
                       "latest_volume_shares": number(latest.get("volume_shares")),
                       "latest_turnover_twd": number(latest.get("turnover_twd")),
                       "screening_score": max(0, min(100, 50 + metrics["return_5d_percent"]))
                           if metrics["return_5d_percent"] is not None else None,
                       "anomaly_flags": ["daily_return_above_11_percent"] if abs(_change(values, 1) or 0) >= 11 else [],
                       "status": "partial" if rejected or len(signals) < 4 else "ready",
                       "analysis_as_of": as_of, "core_snapshot_id": snapshot,
                       "input_hash": digest(evidence), "engine_version": VERSION,
                       "llm_api_tokens": 0})
    ranked = sorted((r for r in output if r["screening_score"] is not None),
                    key=lambda r: (-r["screening_score"], r["symbol"]))
    ranks = {r["symbol"]: i for i, r in enumerate(ranked, 1)}
    return [dict(r, candidate_rank=ranks.get(r["symbol"])) for r in output]


def screening_quality(rows):
    """10% inclusive tolerance; poor coverage requests discussion without failing execution."""
    total = len(rows)
    day = max((r["latest_trade_date"] for r in rows if r["latest_trade_date"]), default=None)
    missing = sum(r["latest_trade_date"] != day or r["latest_close"] is None
                  or any(number(r.get(k)) is None or r[k] < 0
                         for k in ("latest_volume_shares", "latest_turnover_twd")) for r in rows)
    def coverage(count):
        return {"missing_symbols": count, "total_symbols": total,
                "missing_ratio": count / total if total else None,
                "status": "accepted" if total and count * 10 <= total else "discussion_required"}
    return {"tolerance": 0.1, "latest_market_date": day, "eod": coverage(missing),
            "history": {str(w): coverage(sum(r["metrics"][f"return_{w}d_percent"] is None for r in rows))
                        for w in (5, 20, 60, 120)},
            "auto_fail": False, "model_validation_counted_as_missing": False}


def _role_dependency_state(rows, rejected, datasets, symbol, snapshot, role):
    dependencies = DEPENDENCIES[role]
    rejected_ids = {item["evidence_id"] for item in rejected}
    dependency_ids = {
        _evidence_id(dataset, row, snapshot)
        for dataset in dependencies
        for row in datasets.get(dataset, [])
        if not row.get("symbol") or row.get("symbol") == symbol
    }
    errors = [item for item in rejected if item["evidence_id"] in dependency_ids & rejected_ids]
    input_hash = digest({
        "accepted": {dataset: rows.get(dataset) for dataset in dependencies},
        "rejected": errors,
    })
    return errors, input_hash


def specialist_input_hashes(datasets, symbol, as_of, snapshot):
    """Hash every output-affecting accepted/rejected dependency for each specialist."""
    rows, _, rejected = validated_inputs(datasets, symbol, as_of, snapshot)
    return {
        role: _role_dependency_state(rows, rejected, datasets, symbol, snapshot, role)[1]
        for role in DEPENDENCIES
    }


def analyze_specialists(datasets, symbol, as_of, snapshot, *, roles=None):
    selected_roles = tuple(DEPENDENCIES) if roles is None else tuple(dict.fromkeys(roles))
    unknown = sorted(set(selected_roles) - set(DEPENDENCIES))
    if unknown:
        raise ValueError(f"unknown specialist roles: {','.join(unknown)}")
    rows, evidence, rejected = validated_inputs(datasets, symbol, as_of, snapshot)
    metrics = {}
    selected = set(selected_roles)

    if {"fundamental", "valuation"} & selected:
        features = _financial_features_v2(rows.get("financials", []))
    if "fundamental" in selected:
        metrics["fundamental"] = {k: features["fundamental"].get(k) for k in (
            "revenue_trend_percent", "eps_trend_percent",
            "net_income_parent_yoy_percent_same_filing", "eps_yoy_percent_same_filing")}
    if "valuation" in selected:
        valuations = sorted(rows.get("valuation", []),
                            key=lambda r: str(r.get("observed_date", r.get("observed_at", ""))))
        latest = valuations[-1] if valuations else {}
        features["valuation"].update(
            {k: number(latest.get(k)) for k in ("pe_ratio", "pb_ratio", "dividend_yield_percent")})
        metrics["valuation"] = {k: features["valuation"].get(k) for k in (
            "pe_ratio", "pb_ratio", "dividend_yield_percent", "debt_to_equity", "roe")}
        metrics["valuation"].update(dcf_value_per_share=None, reverse_dcf_growth=None)

    if {"quant", "risk"} & selected:
        prices = price_series(rows.get("ohlcv", []))
    if "quant" in selected:
        metrics["quant"] = {f"return_{w}d_percent": _change(list(prices.values()), w)
                            for w in (5, 20, 60, 120)}
        metrics["quant"].update(expected_excess_return=None, outperform_probability=None)
    if "risk" in selected:
        benchmark = price_series(rows.get("benchmark", []))
        metrics["risk"] = risk_metrics(prices, benchmark)
        metrics["risk"]["regime_probability"] = None
    if "event" in selected:
        metrics["event"] = {
            "event_count": len(rows["events"]) if "events" in rows else None,
            "max_severity": max((_severity(r.get("severity")) for r in rows.get("events", [])
                                 if _severity(r.get("severity")) is not None), default=None),
            "classifier_probability": None,
        }

    artifacts = []
    for role in selected_roles:
        dependencies = DEPENDENCIES[role]
        role_evidence = [e for e in evidence if e["dataset_id"] in dependencies]
        errors, input_hash = _role_dependency_state(rows, rejected, datasets, symbol, snapshot, role)
        missing = sorted(k for k, v in metrics[role].items() if v is None)
        contributions = [{"feature": k, "value": v, "method": "observed_metric_not_shap"}
                         for k, v in metrics[role].items() if v is not None]
        payload = {"artifact_kind": "mart_specialist_v1", "schema_version": "1.0.0",
                   "symbol": symbol, "role": role, "analysis_as_of": as_of, "core_snapshot_id": snapshot,
                   "feature_version": FEATURE_VERSION, "engine_version": VERSION, "model_version": MODEL_VERSION,
                   "model_status": "oos_not_validated", "status": "blocked" if errors else "partial" if missing else "ready",
                   "input_hash": input_hash, "metrics": metrics[role],
                   "missing_data": missing, "rejected_evidence": errors,
                   "evidence_ids": sorted(e["evidence_id"] for e in role_evidence),
                   "provenance_ids": sorted({e["provenance_id"] for e in role_evidence}),
                   "feature_contributions": contributions, "publication_authority": False,
                   "llm_api_tokens": 0, "ceo_triggered": False,
                   "plain_language": f"{TITLES[role]}：" + ("；".join(
                       f"{METRIC_LABELS.get(k, k)} {v:.4g}" for k, v in metrics[role].items() if v is not None)
                       or "目前沒有可用的合格數值")
                       + ("。資料或模型尚未齊備：" + "、".join(
                           METRIC_LABELS.get(k, k) for k in missing) if missing else "")
                       + "。此為確定性基準，尚未通過台灣樣本外模型驗證。"}
        payload["output_hash"] = digest(payload)
        from .specialist_contract import MartSpecialistV1
        MartSpecialistV1.model_validate(payload)
        artifacts.append(payload)
    return artifacts
