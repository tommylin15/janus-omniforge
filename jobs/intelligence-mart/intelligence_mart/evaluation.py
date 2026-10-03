"""Purged Taiwan walk-forward evaluation. No synthetic history or automatic promotion."""
from __future__ import annotations

from collections import defaultdict
from math import ceil, sqrt
from statistics import correlation, fmean, pstdev

from .specialists import digest, number
from .facts import _instant


def ranks(values):
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    result = [0.] * len(values)
    i = 0
    while i < len(ordered):
        j = i + 1
        while j < len(ordered) and ordered[j][1] == ordered[i][1]:
            j += 1
        for index, _ in ordered[i:j]:
            result[index] = (i + j - 1) / 2
        i = j
    return result


def evaluate_predictions(predictions, *, cost_bps, annual_periods):
    if number(cost_bps) is None or cost_bps < 0 or annual_periods <= 0:
        raise ValueError("explicit nonnegative cost and evaluation cadence required")
    groups = defaultdict(list)
    for row in predictions:
        if not row["training_label_cutoff"] < row["analysis_as_of"] < row["outcome_as_of"]:
            raise ValueError("walk-forward label leakage")
        if any(number(row.get(k)) is None for k in ("prediction", "excess_return")):
            raise ValueError("invalid OOS prediction")
        groups[row["analysis_as_of"]].append(row)
    ics, spreads, pnl, turnovers, hits = [], [], [], [], []
    previous = set()
    for day, rows in sorted(groups.items()):
        if len({r["symbol"] for r in rows}) != len(rows):
            raise ValueError("duplicate OOS symbol/date")
        rows = sorted(rows, key=lambda r: (-r["prediction"], r["symbol"]))
        if len(rows) < 10:
            continue
        x, y = ranks([r["prediction"] for r in rows]), ranks([r["excess_return"] for r in rows])
        if pstdev(x) and pstdev(y):
            ics.append(correlation(x, y))
        n = ceil(len(rows) / 10)
        selected = {r["symbol"] for r in rows[:n]}
        turnover = len(selected - previous) / len(selected) if previous else 1.
        previous = selected
        turnovers.append(turnover)
        top = fmean(r["excess_return"] for r in rows[:n])
        spreads.append(top - fmean(r["excess_return"] for r in rows[-n:]))
        pnl.append(top - turnover * cost_bps / 10000)
        hits += [float((r["prediction"] > 0) == (r["excess_return"] > 0)) for r in rows]
    wealth, peak, drawdown = 1., 1., 0.
    for value in pnl:
        wealth *= 1 + value
        peak = max(peak, wealth)
        drawdown = min(drawdown, wealth / peak - 1)
    probabilities = [r for r in predictions if r.get("probability") is not None]
    if any(number(r["probability"]) is None or not 0 <= r["probability"] <= 1 for r in probabilities):
        raise ValueError("invalid probability")
    return {"rank_ic": fmean(ics) if ics else None,
            "icir": fmean(ics) / pstdev(ics) if len(ics) > 1 and pstdev(ics) else None,
            "top_decile_spread": fmean(spreads) if spreads else None,
            "hit_rate": fmean(hits) if hits else None,
            "brier": fmean((r["probability"] - float(r["excess_return"] > 0)) ** 2 for r in probabilities) if probabilities else None,
            "sharpe": fmean(pnl) / pstdev(pnl) * sqrt(annual_periods) if len(pnl) > 1 and pstdev(pnl) else None,
            "max_drawdown": drawdown if pnl else None, "turnover": fmean(turnovers) if turnovers else None,
            "after_cost_return": wealth - 1 if pnl else None, "cross_sections": len(pnl),
            "cost_bps": cost_bps, "probability_calibration": "not_evaluated",
            "regime_stability": "not_evaluated", "promotion_eligible": False}


def walk_forward(samples, *, model_name, features, cost_bps, horizon_days):
    """Monthly expanding fit; only matured labels strictly before each OOS block enter training."""
    import numpy as np
    valid = []
    for row in samples:
        if row.get("source_authorization") not in {"official", "approved_fallback"} or not row.get("provenance_id"):
            raise ValueError("benchmark requires authorized PIT provenance")
        dates = {k: _instant(row.get(k)) for k in ("feature_available_at", "analysis_as_of", "label_available_at", "outcome_as_of")}
        if any(v is None for v in dates.values()) or dates["feature_available_at"] > dates["analysis_as_of"] \
                or dates["label_available_at"] < dates["outcome_as_of"]:
            raise ValueError("invalid PIT feature/label availability")
        if all(number(row.get(k)) is not None for k in (*features, "excess_return")):
            valid.append(row)
    if horizon_days not in {5, 20, 60, 120}:
        raise ValueError("unsupported forecast horizon")
    predictions, folds = [], []
    for month in sorted({r["analysis_as_of"][:7] for r in valid}):
        test = [r for r in valid if r["analysis_as_of"].startswith(month)]
        start = min(r["analysis_as_of"] for r in test)
        train = [r for r in valid if r["label_available_at"] < start and r["analysis_as_of"] < start]
        if len(train) < 100 or len({r["analysis_as_of"][:7] for r in train}) < 3:
            continue
        x, y = np.array([[r[k] for k in features] for r in train]), np.array([r["excess_return"] for r in train])
        xt = np.array([[r[k] for k in features] for r in test])
        if model_name == "linear":
            mean, scale = x.mean(axis=0), x.std(axis=0)
            scale[scale == 0] = 1
            coefficients = np.linalg.lstsq(np.column_stack([np.ones(len(x)), (x - mean) / scale]), y, rcond=None)[0]
            pred = np.column_stack([np.ones(len(xt)), (xt - mean) / scale]) @ coefficients
        elif model_name == "lightgbm":
            from lightgbm import LGBMRegressor
            model = LGBMRegressor(n_estimators=50, max_depth=3, num_leaves=7, n_jobs=1, random_state=17, verbosity=-1)
            model.fit(x, y)
            pred = model.predict(xt)
        elif model_name == "catboost":
            from catboost import CatBoostRegressor
            model = CatBoostRegressor(iterations=50, depth=3, thread_count=1, random_seed=17, verbose=False, allow_writing_files=False)
            model.fit(x, y)
            pred = model.predict(xt)
        else:
            raise ValueError("unsupported evaluated model")
        cutoff = max(r["label_available_at"] for r in train)
        predictions.extend({"symbol": r["symbol"], "analysis_as_of": r["analysis_as_of"],
                            "outcome_as_of": r["outcome_as_of"], "excess_return": r["excess_return"],
                            "prediction": float(p), "training_label_cutoff": cutoff}
                           for r, p in zip(test, pred, strict=True))
        folds.append({"month": month, "training_samples": len(train), "test_samples": len(test), "label_cutoff": cutoff})
    payload = {"artifact_kind": "mart_oos_evaluation_v1", "protocol_version": "taiwan-purged-monthly-v1",
               "model_name": model_name, "features": features, "horizon_days": horizon_days,
               "input_hash": digest(samples), "folds": folds, "predictions": predictions,
               "status": "evaluated" if folds else "insufficient_history", "promotion_eligible": False,
               "metrics": evaluate_predictions(predictions, cost_bps=cost_bps, annual_periods=252 / horizon_days)}
    payload["output_hash"] = digest(payload)
    return payload


def build_quant_samples(datasets, symbols, as_of, snapshot, horizon_days):
    """Non-overlapping entry cohorts, exact market-day benchmark and strict row PIT fences."""
    from .specialists import validated_inputs, price_series
    from .facts import _change, evidence_from_rows
    datasets = {name: datasets.get(name, []) for name in ("ohlcv", "benchmark")}
    samples, exclusions = [], defaultdict(int)
    for symbol in sorted(set(symbols)):
        current, _, _ = validated_inputs(datasets, symbol, as_of, snapshot)
        prices = price_series(current.get("ohlcv", []))
        benchmark = price_series(current.get("benchmark", []))
        days = list(prices)
        for i in range(60, len(days) - horizon_days, horizon_days):
            entry, outcome = days[i], days[i + horizon_days]
            history, _, rejected = validated_inputs(datasets, symbol, entry, snapshot)
            known = price_series(history.get("ohlcv", []))
            if entry not in known or entry not in benchmark or outcome not in benchmark:
                exclusions["missing_pit_price_or_aligned_benchmark"] += 1
                continue
            features = {f"momentum_{w}d": _change(list(known.values()), w) for w in (5, 20, 60)}
            if any(v is None for v in features.values()):
                exclusions["insufficient_feature_history"] += 1
                continue
            # Label availability includes actual source observation/publication, not a guessed historical date.
            label_rows = [r for r in current.get("ohlcv", []) if str(r.get("trade_date")) == outcome]
            label_rows += [r for r in current.get("benchmark", []) if str(r.get("trade_date")) == outcome]
            times = [str(r.get(k))[:10] for r in label_rows for k in ("availability_at", "published_at", "observed_at") if r.get(k)]
            available = max([outcome, *times])
            samples.append({"symbol": symbol, "analysis_as_of": entry, "outcome_as_of": outcome,
                            "feature_available_at": entry, "label_available_at": available,
                            "excess_return": prices[outcome] / prices[entry] - benchmark[outcome] / benchmark[entry],
                            "source_authorization": "official" if all(r["source_authorization"] == "official"
                                for r in evidence_from_rows({"labels": label_rows}, snapshot)) else "approved_fallback",
                            "provenance_id": digest(label_rows), **features})
        if len(days) <= 60 + horizon_days:
            exclusions["insufficient_price_history"] += 1
    return samples, dict(exclusions)


def evaluate_core_history(datasets, symbols, as_of, snapshot):
    results = []
    for horizon in (5, 20, 60, 120):
        samples, exclusions = build_quant_samples(datasets, symbols, as_of, snapshot, horizon)
        for model in ("linear", "lightgbm", "catboost"):
            evaluation = walk_forward(samples, model_name=model, features=["momentum_5d", "momentum_20d", "momentum_60d"],
                                      cost_bps=30, horizon_days=horizon)
            evaluation.pop("output_hash")
            evaluation.update(core_snapshot_id=snapshot, analysis_as_of=as_of, exclusions=exclusions,
                              cost_semantics="research_sensitivity_30bps_not_actual_broker_cost",
                              cohort_semantics="current_membership_research_cohort_not_historical_population",
                              missing_evaluations=["historical_membership_replay", "ic_decay", "calibration", "regime_stability", "qlib_double_ensemble"])
            evaluation["output_hash"] = digest(evaluation)
            results.append(evaluation)
    from .specialists import validated_inputs, price_series
    benchmark_rows, _, _ = validated_inputs(datasets, sorted(symbols)[0], as_of, snapshot) if symbols else ({}, [], [])
    values = list(price_series(benchmark_rows.get("benchmark", [])).values())
    returns = [b / a - 1 for a, b in zip(values, values[1:])]
    results.append({"model_name": "statsmodels_markov_regime", "core_snapshot_id": snapshot,
                    "analysis_as_of": as_of, **fit_regime_challenger(returns)})
    return results


def fit_regime_challenger(returns):
    """Monthly research fit only; filtered final-state probability has no promotion authority."""
    if len(returns) < 252 or any(number(r) is None for r in returns) or not pstdev(returns):
        return {"status": "insufficient_history", "required_returns": 252, "available_returns": len(returns),
                "high_vol_probability": None, "promotion_eligible": False}
    import numpy as np
    from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression
    model = MarkovRegression(np.asarray(returns), k_regimes=2, trend="c", switching_variance=True)
    result = model.fit(disp=False, maxiter=100, em_iter=5, search_reps=0)
    if not result.mle_retvals.get("converged") or not np.isfinite(result.params).all():
        return {"status": "fit_not_converged", "high_vol_probability": None, "promotion_eligible": False}
    variances = [result.params[model.parameters[i, "variance"]][0] for i in range(2)]
    regime = int(np.argmax(variances))
    return {"status": "research_fit_oos_pending", "high_vol_probability": float(result.filtered_marginal_probabilities[-1, regime]),
            "promotion_eligible": False, "parameters": result.params.tolist(), "model_version": "statsmodels-markov-2-v1"}
