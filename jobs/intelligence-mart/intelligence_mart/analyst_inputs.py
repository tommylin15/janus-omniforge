"""Target-only analysis Mart: real Core X values, never training or publication."""
from __future__ import annotations

from datetime import date, timedelta

from .specialists import digest, number, validated_inputs

VERSION = "analyst-inputs-v3-seq08-core-market-aligned"
QUANT15 = ("ret5","ret20","ret60","ma20_distance","ma60_distance","vol20","vol60","drawdown60","volume_ratio20","log_turnover20","market_code","ret10","ret120","bollinger_z20","ret20_market_rank")
RISK12 = ("vol20","vol60","drawdown60","abs_return5","volume_ratio20","atr14_pct","abs_overnight_gap5","log_turnover20","downside_vol20","worst_daily_ret20","amihud_illiquidity","drawdown_from_high120")
FUND15 = ("yoy_m","yoy_3m","yoy_change1","growth_acceleration","mom_m","log_revenue","season_sin","season_cos","revenue_vol3","market_code","revenue_sum6m","revenue_mean12m","revenue_growth_6m","base_log_twd","base_to_recent_log")
SEQ08_FEATURE_VERSION = {"quant":"quant-xgb15-factor-factory-v1","risk":"risk-xgb12-original-factory-v1","fundamental":"fundamental-rc1-xgb15-v1"}
FUND_ABSTAIN = {"base_twd_below":3266999.83471632,"mean12_over_base_above":3.1528768314559463,"absolute_yoy_above":246.93646766061153}
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



def latest_eligible_market_session(latest_trade_date, sessions, analysis_as_of, *, max_age_days=7):
    """Allow a market holiday without treating a halted/stale symbol as fresh.

    Exact last observed Core session must equal the stock's latest bar. A newer
    benchmark session blocks stale individual stocks; no forward filling.
    """
    if not latest_trade_date or not sessions:
        return None
    try:
        cutoff = date.fromisoformat(analysis_as_of)
        actual = date.fromisoformat(str(latest_trade_date)[:10])
        observed = max(date.fromisoformat(str(day)[:10]) for day in sessions)
    except (ValueError, TypeError):
        return None
    if actual != observed:
        return None
    age = (cutoff - actual).days
    return actual.isoformat() if 0 <= age <= max_age_days else None


def verified_market_rank(info, *, market, latest_day, as_of, snapshot):
    """Only full-market rank can establish a target's Core cohort day."""
    if not isinstance(info, dict):
        return False
    value = number(info.get("value"))
    return (info.get("market") == market
            and info.get("analysis_as_of") == as_of
            and info.get("source_trade_date") == latest_day
            and str(info.get("core_snapshot_id")) == str(snapshot)
            and info.get("source") == "full_market_core_same_day_pct_rank"
            and isinstance(info.get("cohort_size"), int)
            and not isinstance(info.get("cohort_size"), bool)
            and info["cohort_size"] >= 100
            and value is not None and 0 < value <= 1)


def build(datasets, symbols, as_of, snapshot, *, market_rank=None):
    """Materialize reference feature contracts; model schemas must be matched before serving."""
    import pandas as pd
    from research.chatgpt import janus_precision as precision
    from .risk_shadow import _eligible_price_rows
    import math

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
            # Stock bars are not a market calendar. Use accepted same-market
            # Core benchmark sessions only; never forward-fill missing OHLCV.
            benchmark_id = "TAIEX" if market == "twse" else "TPEx"
            benchmark_days = sorted({
                str(r["trade_date"])[:10] for r in valid.get("benchmark", [])
                if str(r.get("benchmark_id", "")).casefold() == benchmark_id.casefold()
                and str(r.get("index_kind") or "price").lower() == "price"
                and r.get("trade_date") and str(r["trade_date"])[:10] <= as_of
            })
            info = (market_rank or {}).get(symbol)
            ranked_day = verified_market_rank(
                info, market=market, latest_day=latest_day, as_of=as_of,
                snapshot=snapshot)
            # Only a proven complete public Core cohort lets Risk use the last
            # observed Core day when the index alone has newer observations.
            # Otherwise the newer market session still blocks a halted stock.
            sessions = ([day for day in benchmark_days if day <= latest_day]
                        if ranked_day and latest_day in benchmark_days
                        else benchmark_days)
            daily_values, day_reasons = {}, []
            if not benchmark_days:
                day_reasons.append("market_benchmark_sessions_missing")
            try:
                # Original research factor factory is shared by Quant15 and Risk12.
                market_day = latest_eligible_market_session(latest_day, sessions, as_of)
                if market_day is None:
                    day_reasons.append("latest_market_session_missing_or_stale")
                else:
                    frame, _, _ = precision.daily(prices, sessions={market: sessions})
                    current = frame.loc[frame.trade_date.eq(pd.Timestamp(market_day))]
                    if len(current) == 1:
                        daily_values = current.iloc[0].to_dict()
                    else:
                        day_reasons.append("no_eligible_trade_observation")
            except (ValueError, KeyError):
                day_reasons.append("invalid_or_incomplete_price_window")
            for role, order in (("quant", QUANT15), ("risk", RISK12)):
                values = dict(daily_values)
                reasons = list(day_reasons)
                if role == "quant":
                    # Factory.rank(pct=True) is all-market, same-day; running it on
                    # one Owner's stock silently gives 1.0. Never expose that value.
                    values["ret20_market_rank"] = None
                    if ranked_day:
                        values["ret20_market_rank"] = number(info["value"])
                    else:
                        reasons.append("full_market_same_day_percent_rank_missing")
                roles[role] = _features(order, values, input_as_of=latest_day,
                                         version=SEQ08_FEATURE_VERSION[role], reasons=reasons)
        for role, order in (("quant", QUANT15), ("risk", RISK12)):
            roles.setdefault(role, _features(order, {}, input_as_of=None,
                       version=SEQ08_FEATURE_VERSION[role], reasons=["no_accepted_ohlcv"]))
        revenues = revenue_rows(valid.get("financials", []), symbol, market) if market else []
        fund_values, period, reasons = {}, None, []
        if revenues:
            try:
                frame, _ = precision.monthly(pd.DataFrame(revenues))
                last = frame.sort_values("fiscal_month").iloc[-1]
                fund_values, period = last.to_dict(), str(last.fiscal_month)
                previous_month = str(pd.Period(period, freq="M") - 11)
                prior = frame.loc[frame.fiscal_month.eq(previous_month)]
                base = number(prior.iloc[0].revenue_twd) if len(prior) == 1 else None
                mean12 = number(fund_values.get("revenue_mean12m"))
                # 5%-policy X values must use research's previous-year base.
                if base is not None and base > 0 and mean12 is not None and mean12 > 0:
                    fund_values["base_log_twd"] = math.log1p(base)
                    fund_values["base_to_recent_log"] = max(-16., min(16., math.log(max(mean12, 1.) / max(base, 1.))))
                    fund_values["_research_base_twd"] = base
                else:
                    reasons.append("prior_year_target_base_missing")
            except (ValueError, KeyError, TypeError, OverflowError):
                reasons.append("invalid_revenue_window")
        else:
            reasons.append("monthly_revenue_or_market_missing")
        if revenues and any(number(fund_values.get(key)) is None for key in FUND15):
            reasons.append("monthly_revenue_comparison_window_incomplete")
        roles["fundamental"] = _features(FUND15, fund_values, input_as_of=period,
                                         version=SEQ08_FEATURE_VERSION["fundamental"], reasons=reasons)
        base_twd = number(fund_values.get("_research_base_twd"))
        mean12 = number(fund_values.get("revenue_mean12m"))
        yoy = number(fund_values.get("yoy_m"))
        abstain = []
        if base_twd is None or base_twd <= 0 or mean12 is None or yoy is None:
            abstain.append("BASE_OR_MONTHLY_INPUT_MISSING")
        else:
            if base_twd <= FUND_ABSTAIN["base_twd_below"]:
                abstain.append("LOW_BASE_TWD")
            if mean12 / base_twd >= FUND_ABSTAIN["mean12_over_base_above"]:
                abstain.append("UNSTABLE_BASE_RATIO")
            if abs(yoy) >= FUND_ABSTAIN["absolute_yoy_above"]:
                abstain.append("EXTREME_YOY")
        roles["fundamental"]["abstention_reasons"] = abstain
        roles["fundamental"]["abstention_policy_version"] = "fundamental-rc1-xonly-5pct-v1"
        # Accounting basis must match the published model. Never substitute debt/equity for debt/assets,
        # infer ROE from a different quarter, or feed PE/PB (the target) back into model X.
        from .valuation_ml_mapping import build_v26_features
        roles["valuation"] = build_v26_features(
            valid.get("financials", []), symbol=symbol, market=market, as_of=as_of)
        financial_identity = [{"fiscal_year": r.get("fiscal_year"), "fiscal_quarter": r.get("fiscal_quarter"),
            "fiscal_month": r.get("fiscal_month"), "metric": r.get("metric"), "value": r.get("value"),
            "unit": r.get("unit"), "period_basis": r.get("period_basis"), "report_scope": r.get("report_scope")}
            for r in valid.get("financials", [])]
        financial_identity.sort(key=lambda x: str(sorted(x.items())))
        item = {"symbol": symbol, "market": market, "analysis_as_of": as_of,
            "latest_trade_date": latest_day, "latest_close": latest_close,
            "roles": roles, "financial_input_hash": digest(financial_identity),
            "revenue_month_count": len(revenues),
            "rejected_input_count": len(rejected) + len(excluded)}
        # The two scope-reviewed Valuation reference cases reuse this already
        # snapshot-fenced Core input. The official price-reference function
        # emits null prices when four-quarter EPS/BVPS or 24 months are missing.
        from .valuation_reference import reference_from_core
        reference = reference_from_core(
            valid, symbol=symbol, as_of=as_of, core_snapshot_id=str(snapshot),
            market=market, latest_close=latest_close,
            latest_trade_date=latest_day)
        if reference is not None:
            item["valuation_reference"] = reference
        result.append(item)
    artifact = {"artifact_kind": "mart_analyst_inputs_v1", "schema_version": VERSION,
        "analysis_as_of": as_of, "core_snapshot_id": snapshot, "rows": result,
        "calendar_basis": "ACCEPTED_SAME_MARKET_BENCHMARK_SESSIONS_WITH_FULL_CORE_COHORT_PROOF",
        "owner_fields_exposed": False, "publication_authority": False}
    artifact["output_hash"] = digest(artifact)
    return artifact
