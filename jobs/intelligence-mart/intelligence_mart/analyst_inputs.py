"""Target-only analysis Mart: real Core X values, never training or publication."""
from __future__ import annotations

from datetime import date, timedelta

from .specialists import digest, number, validated_inputs

VERSION = "analyst-inputs-v1"
ROLES = ("quant", "risk", "fundamental", "valuation")


def bounded_inputs(core, as_of):
    end = date.fromisoformat(as_of)
    windows = {"ohlcv": ("trade_date", 400), "benchmark": ("trade_date", 400),
               "valuation": ("observed_date", 1850), "events": ("effective_date", 365)}
    tables = core.get("iceberg_tables", {})
    bounds = {f"core.{name}_v1": (field, (end - timedelta(days=days)).isoformat(), as_of)
              for name, (field, days) in windows.items() if f"core.{name}_v1" in tables}
    return bounds


def revenue_rows(rows, symbol, market):
    """Collapse identical amounts across units; conflicting monthly facts stay missing."""
    grouped = {}
    for row in rows:
        if (str(row.get("symbol")) != symbol or row.get("period_basis") != "monthly"
                or not str(row.get("metric", "")).startswith("monthly_revenue")):
            continue
        value = number(row.get("value"))
        scale = {"TWD": 1, "TWD_thousands": 1000}.get(row.get("unit"))
        try:
            period = date(int(row["fiscal_year"]), int(row["fiscal_month"]), 1).strftime("%Y-%m")
        except (ValueError, TypeError, KeyError):
            continue
        if value is None or value < 0 or scale is None:
            continue
        grouped.setdefault(period, []).append((value * scale, row.get("published_at")))
    output = []
    for period, records in sorted(grouped.items()):
        values = {v for v, _ in records}
        output.append({"symbol": symbol, "market": market, "fiscal_month": period,
                       "revenue_twd": next(iter(values)) if len(values) == 1 else float("nan"),
                       "published_at": max((str(t) for _, t in records if t), default=None)})
    return output


def _features(order, values, *, input_as_of, version, reasons=()):
    clean = {key: number(values.get(key)) for key in order}
    missing = [key for key, value in clean.items() if value is None]
    return {"feature_order": list(order), "values": clean, "missing_features": missing,
            "input_as_of": input_as_of, "feature_version": version,
            "feature_ready": not missing, "model_compatible": "NOT_VERIFIED",
            "reasons": list(reasons), "publication_authority": False}


def build(datasets, symbols, as_of, snapshot):
    """Materialize reference feature contracts; model schemas must be matched before serving."""
    import pandas as pd
    from research.chatgpt import janus_precision as precision
    from research.colab.risk_pilot import make_risk_panel
    from research.colab.risk_v1 import V1_FEATURES, add_v1_features
    from .risk_shadow import _eligible_price_rows, FEATURE_VERSION as RISK_FEATURE_VERSION

    date.fromisoformat(as_of)
    result = []
    selected = tuple(sorted(set(symbols)))
    # All inputs are bounded by the reader; this guard also covers injected readers.
    if sum(map(len, datasets.values())) > 250000:
        raise ValueError("analyst input row budget exceeded")
    for symbol in selected:
        own = {name: [r for r in rows if name == "benchmark" or not r.get("symbol") or str(r["symbol"]) == symbol]
               for name, rows in datasets.items()}
        valid, _, rejected = validated_inputs(own, symbol, as_of, snapshot, preserve_financial_basis=True)
        prices, excluded = _eligible_price_rows(valid.get("ohlcv", []), as_of)
        roles = {}
        market = None
        latest_day, latest_close = None, None
        if not prices.empty and prices.market.nunique() == 1:
            market = str(prices.market.iloc[0])
            latest = prices.sort_values("trade_date").iloc[-1]
            latest_day, latest_close = str(latest.trade_date)[:10], number(latest.close)
            # Include observed benchmark sessions to expose gaps, never forward fill stock prices.
            benchmark_id = "TAIEX" if market == "twse" else "TPEx"
            sessions = sorted(set(prices.trade_date) | {
                str(r["trade_date"])[:10] for r in datasets.get("benchmark", [])
                if r.get("benchmark_id") == benchmark_id and r.get("trade_date")
                and str(r["trade_date"])[:10] <= as_of})
            for role, order, version in (
                ("quant", precision.QUANT, "janus-precision-" + precision.VERSION),
                ("risk", V1_FEATURES, RISK_FEATURE_VERSION)):
                values, reasons = {}, []
                try:
                    if role == "quant":
                        frame, _, _ = precision.daily(prices, sessions={market: sessions})
                    else:
                        frame = add_v1_features(make_risk_panel(prices, market_sessions={market: sessions}))
                    current = frame.loc[frame.trade_date.eq(pd.Timestamp(as_of))]
                    if len(current) == 1:
                        values = current.iloc[0].to_dict()
                    else:
                        reasons.append("no_current_trade_observation")
                except ValueError:
                    reasons.append("invalid_or_incomplete_price_window")
                roles[role] = _features(order, values, input_as_of=latest_day, version=version, reasons=reasons)
        for role, order, version in (("quant", precision.QUANT, "janus-precision-" + precision.VERSION),
                                     ("risk", V1_FEATURES, RISK_FEATURE_VERSION)):
            roles.setdefault(role, _features(order, {}, input_as_of=None, version=version,
                                             reasons=["no_accepted_ohlcv"]))
        revenues = revenue_rows(valid.get("financials", []), symbol, market) if market else []
        fund_values, period, reasons = {}, None, []
        if revenues:
            try:
                frame, _ = precision.monthly(pd.DataFrame(revenues))
                last = frame.sort_values("fiscal_month").iloc[-1]
                fund_values, period = last.to_dict(), str(last.fiscal_month)
            except ValueError:
                reasons.append("invalid_revenue_window")
        else:
            reasons.append("monthly_revenue_or_market_missing")
        roles["fundamental"] = _features(precision.FUND, fund_values, input_as_of=period,
                                         version="janus-precision-" + precision.VERSION, reasons=reasons)
        # Accounting basis must match the published model. Never substitute debt/equity for debt/assets,
        # infer ROE from a different quarter, or feed PE/PB (the target) back into model X.
        roles["valuation"] = _features(precision.VAL,
            {"market_code": {"twse": 0., "tpex": 1.}.get(market)}, input_as_of=None,
            version="valuation-mapping-pending", reasons=["model_accounting_mapping_required"])
        financial_identity = [{"fiscal_year": r.get("fiscal_year"), "fiscal_quarter": r.get("fiscal_quarter"),
            "fiscal_month": r.get("fiscal_month"), "metric": r.get("metric"), "value": r.get("value"),
            "unit": r.get("unit"), "period_basis": r.get("period_basis"), "report_scope": r.get("report_scope")}
            for r in valid.get("financials", [])]
        financial_identity.sort(key=lambda x: str(sorted(x.items())))
        result.append({"symbol": symbol, "market": market, "analysis_as_of": as_of,
            "latest_trade_date": latest_day, "latest_close": latest_close,
            "roles": roles, "financial_input_hash": digest(financial_identity),
            "revenue_month_count": len(revenues),
            "rejected_input_count": len(rejected) + len(excluded)})
    artifact = {"artifact_kind": "mart_analyst_inputs_v1", "schema_version": VERSION,
        "analysis_as_of": as_of, "core_snapshot_id": snapshot, "rows": result,
        "calendar_basis": "OBSERVED_CORE_BENCHMARK_AND_TARGET_SESSIONS",
        "owner_fields_exposed": False, "publication_authority": False}
    artifact["output_hash"] = digest(artifact)
    return artifact
