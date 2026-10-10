"""Purged Taiwan walk-forward evaluation. No synthetic history or automatic promotion."""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from math import ceil, sqrt
from statistics import correlation, fmean, pstdev

from .specialists import digest, number
from .facts import _instant, _financial_period_time


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
        for horizon, outcome in row.get("future_outcomes", {}).items():
            if horizon not in {"5", "20", "60", "120"} or number(outcome.get("excess_return")) is None \
                    or _instant(outcome.get("outcome_as_of")) is None \
                    or _instant(outcome["outcome_as_of"]) <= _instant(row["analysis_as_of"]):
                raise ValueError("invalid OOS decay outcome")
        groups[row["analysis_as_of"]].append(row)
    ics, spreads, pnl, turnovers = [], [], [], []
    hits = [float((r["prediction"] > 0) == (r["excess_return"] > 0)) for r in predictions]
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
    wealth, peak, drawdown = 1., 1., 0.
    for value in pnl:
        wealth *= 1 + value
        peak = max(peak, wealth)
        drawdown = min(drawdown, wealth / peak - 1)
    probabilities = [r for r in predictions if r.get("probability") is not None]
    if any(number(r["probability"]) is None or not 0 <= r["probability"] <= 1 for r in probabilities):
        raise ValueError("invalid probability")
    bins = []
    for index in range(10):
        selected = [r for r in probabilities if min(int(r["probability"]*10), 9) == index]
        if selected:
            bins.append({"count": len(selected), "predicted": fmean(r["probability"] for r in selected),
                         "observed": fmean(float(r["excess_return"] > 0) for r in selected)})
    time_series = {}
    for symbol in sorted({r["symbol"] for r in predictions}):
        rows = [r for r in predictions if r["symbol"] == symbol]
        x, y = ranks([r["prediction"] for r in rows]), ranks([r["excess_return"] for r in rows])
        time_series[symbol] = {"predictions": len(rows), "rank_ic": correlation(x, y)
            if len(rows) >= 20 and pstdev(x) and pstdev(y) else None,
            "hit_rate": fmean(float((r["prediction"] > 0) == (r["excess_return"] > 0)) for r in rows)}
    decay = {}
    for horizon in (5, 20, 60, 120):
        temporal = {}
        for symbol in time_series:
            rows = [row for row in predictions if row["symbol"] == symbol and
                    str(horizon) in row.get("future_outcomes", {})]
            x = ranks([row["prediction"] for row in rows])
            y = ranks([row["future_outcomes"][str(horizon)]["excess_return"] for row in rows])
            temporal[symbol] = {"samples": len(rows), "rank_ic": correlation(x, y)
                if len(rows) >= 20 and pstdev(x) and pstdev(y) else None}
        decay[str(horizon)] = {"time_series_by_symbol": temporal,
            "semantics": "same_oos_signal_future_horizons_overlapping_outcomes_not_independent_returns"}
    return {"rank_ic": fmean(ics) if ics else None,
            "icir": fmean(ics) / pstdev(ics) if len(ics) > 1 and pstdev(ics) else None,
            "top_decile_spread": fmean(spreads) if spreads else None,
            "hit_rate": fmean(hits) if hits else None,
            "brier": fmean((r["probability"] - float(r["excess_return"] > 0)) ** 2 for r in probabilities) if probabilities else None,
            "sharpe": fmean(pnl) / pstdev(pnl) * sqrt(annual_periods) if len(pnl) > 1 and pstdev(pnl) else None,
            "max_drawdown": drawdown if pnl else None, "turnover": fmean(turnovers) if turnovers else None,
            "after_cost_return": wealth - 1 if pnl else None, "cross_sections": len(pnl),
            "cost_bps": cost_bps, "time_series_by_symbol": time_series,
            "probability_calibration": {"status": "evaluated" if len(probabilities) >= 30 else "insufficient_oos_predictions",
                "samples": len(probabilities), "bins": bins, "expected_calibration_error":
                sum(r["count"]*abs(r["predicted"]-r["observed"]) for r in bins)/len(probabilities)
                if len(probabilities) >= 30 else None} if probabilities else "not_evaluated",
            "ic_decay": decay, "regime_stability": "not_evaluated", "promotion_eligible": False}


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
        # Reserve matured months for calibration; never calibrate on the OOS block.
        calibration_months = set(sorted({r["analysis_as_of"][:7] for r in train})[-3:])
        calibration = [r for r in train if r["analysis_as_of"][:7] in calibration_months]
        fitting = [r for r in train if r["analysis_as_of"][:7] not in calibration_months]
        if len(fitting) >= 100 and len({r["analysis_as_of"][:7] for r in fitting}) >= 3 and len(calibration) >= 30:
            train = fitting
        else:
            calibration = []
        test = [r for r in test if r.get("is_oos_entry", True)]
        if not test:
            continue
        x, y = np.array([[r[k] for k in features] for r in train]), np.array([r["excess_return"] for r in train])
        xt = np.array([[r[k] for k in features] for r in test])
        if model_name == "linear":
            mean, scale = x.mean(axis=0), x.std(axis=0)
            scale[scale == 0] = 1
            coefficients = np.linalg.lstsq(np.column_stack([np.ones(len(x)), (x - mean) / scale]), y, rcond=None)[0]
            contributions = (xt - mean) / scale * coefficients[1:]
            bases = np.repeat(coefficients[0], len(xt))
            pred = bases + contributions.sum(axis=1)
            predict = lambda values: np.column_stack([np.ones(len(values)), (values-mean)/scale]) @ coefficients
        elif model_name == "lightgbm":
            from lightgbm import LGBMRegressor
            model = LGBMRegressor(n_estimators=50, max_depth=3, num_leaves=7, n_jobs=1, random_state=17, verbosity=-1)
            model.fit(x, y)
            pred = model.predict(xt)
            explained = model.booster_.predict(xt, pred_contrib=True)
            contributions, bases = explained[:, :-1], explained[:, -1]
            predict = model.predict
        elif model_name == "catboost":
            from catboost import CatBoostRegressor
            model = CatBoostRegressor(iterations=50, depth=3, thread_count=1, random_seed=17, verbose=False, allow_writing_files=False)
            model.fit(x, y)
            pred = model.predict(xt)
            from catboost import Pool
            explained = model.get_feature_importance(Pool(xt), type="ShapValues")
            contributions, bases = explained[:, :-1], explained[:, -1]
            predict = model.predict
        elif model_name == "qlib_double_ensemble":
            from .qlib_double_ensemble.adapter import fit, predict_explained
            model = fit(x, y, features)
            pred, contributions, bases = predict_explained(model, xt, features)
            predict = lambda values: predict_explained(model, values, features)[0]
        else:
            raise ValueError("unsupported evaluated model")
        if not np.allclose(bases + contributions.sum(axis=1), pred, rtol=1e-5, atol=1e-8):
            raise ValueError("model contribution does not reconstruct its prediction")
        probabilities = [None]*len(test)
        if calibration and len({r["excess_return"] > 0 for r in calibration}) == 2:
            from sklearn.linear_model import LogisticRegression
            scores = predict(np.array([[r[k] for k in features] for r in calibration]))
            calibrator = LogisticRegression(random_state=17).fit(np.asarray(scores).reshape(-1, 1),
                np.array([r["excess_return"] > 0 for r in calibration]))
            probabilities = calibrator.predict_proba(np.asarray(pred).reshape(-1, 1))[:, 1].tolist()
        cutoff = max(r["label_available_at"] for r in train+calibration)
        predictions.extend({"symbol": r["symbol"], "analysis_as_of": r["analysis_as_of"],
                            "outcome_as_of": r["outcome_as_of"], "excess_return": r["excess_return"],
                            "prediction": float(p), "probability": probability, "training_label_cutoff": cutoff,
                            "sample_source_authorization": r["source_authorization"],
                            "sample_provenance_id": r["provenance_id"],
                            "feature_available_at": r["feature_available_at"],
                            "label_available_at": r["label_available_at"],
                            "future_outcomes": r.get("future_outcomes", {}),
                            "feature_contributions": dict(zip(features, map(float, values), strict=True)),
                            "explanation_base_value": float(base),
                            "explanation_method": "linear_additive" if model_name == "linear" else "native_tree_shap"}
                           for r, p, probability, values, base in zip(test, pred, probabilities, contributions, bases, strict=True))
        folds.append({"month": month, "training_samples": len(train), "calibration_samples": len(calibration),
                      "test_samples": len(test), "label_cutoff": cutoff})
    payload = {"artifact_kind": "mart_oos_evaluation_v1", "protocol_version": "taiwan-purged-monthly-v5",
               "model_name": model_name, "features": features, "horizon_days": horizon_days,
               "input_hash": digest(samples), "folds": folds, "predictions": predictions,
               "status": "evaluated" if folds else "insufficient_history", "promotion_eligible": False,
               "metrics": evaluate_predictions(predictions, cost_bps=cost_bps, annual_periods=252 / horizon_days)}
    payload["output_hash"] = digest(payload)
    return payload


def build_quant_samples(datasets, symbols, as_of, snapshot, horizon_days):
    """Non-overlapping entry cohorts, exact market-day benchmark and strict row PIT fences."""
    from .specialists import validated_inputs, price_series
    from .facts import evidence_from_rows
    datasets = {name: datasets.get(name, []) for name in ("ohlcv", "benchmark")}
    samples, exclusions = [], defaultdict(int)
    for symbol in sorted(set(symbols)):
        current, _, _ = validated_inputs(datasets, symbol, as_of, snapshot)
        prices = price_series(current.get("ohlcv", []))
        benchmark = price_series(current.get("benchmark", []))
        days = list(benchmark)
        # Matured overlapping training labels are allowed; only held-out entries are non-overlapping.
        for i in range(60, len(days) - horizon_days, 5):
            entry, outcome = days[i], days[i + horizon_days]
            if entry not in prices or outcome not in prices:
                exclusions["missing_aligned_price_endpoint"] += 1
                continue
            history, _, rejected = validated_inputs(datasets, symbol, entry, snapshot)
            known = price_series(history.get("ohlcv", []))
            if entry not in known or entry not in benchmark or outcome not in benchmark:
                exclusions["missing_pit_price_or_aligned_benchmark"] += 1
                continue
            features = {f"momentum_{w}d": (known[entry]/known[days[i-w]]-1)*100
                        if days[i-w] in known else None for w in (5, 20, 60)}
            if any(v is None for v in features.values()):
                exclusions["insufficient_feature_history"] += 1
                continue
            # Label availability includes actual source observation/publication, not a guessed historical date.
            label_rows = [r for r in current.get("ohlcv", []) if str(r.get("trade_date")) == outcome]
            label_rows += [r for r in current.get("benchmark", []) if str(r.get("trade_date")) == outcome]
            times = [str(r.get(k))[:10] for r in label_rows for k in ("availability_at", "published_at", "observed_at") if r.get(k)]
            available = max([outcome, *times])
            future_outcomes = {str(window): {"outcome_as_of": days[i + window],
                "excess_return": prices[days[i + window]] / prices[entry] - benchmark[days[i + window]] / benchmark[entry]}
                for window in (5, 20, 60, 120) if i + window < len(days) and days[i + window] in prices}
            samples.append({"symbol": symbol, "analysis_as_of": entry, "outcome_as_of": outcome,
                            "is_oos_entry": i % horizon_days == 0,
                            "feature_available_at": entry, "label_available_at": available,
                            "excess_return": prices[outcome] / prices[entry] - benchmark[outcome] / benchmark[entry],
                            "source_authorization": "official" if all(r["source_authorization"] == "official"
                                for r in evidence_from_rows({"labels": label_rows}, snapshot)) else "approved_fallback",
                            "provenance_id": digest([label_rows, future_outcomes]), "future_outcomes": future_outcomes, **features})
        if len(prices) <= 60 + horizon_days:
            exclusions["insufficient_price_history"] += 1
    return samples, dict(exclusions)


ROLE_FEATURES = {"fundamental": ["net_income_parent_yoy_percent_same_filing", "eps_yoy_percent_same_filing"],
                 "valuation": ["pe_ratio", "pb_ratio", "dividend_yield_percent"]}

FINANCIAL_HISTORY_POLICY = {"version": "current-official-revision-v1", "strict_pit": False,
    "revision_semantics": "current_collected_official_version_may_include_later_revisions",
    "time_preference": "authoritative_publication_then_official_filing_upload_then_period_end_plus_90_days",
    "assumed_publication_lag_days": 90, "user_authorized": "2026-10-03"}


def financial_training_history(rows):
    """User-approved current-version historical replay; canonical Core rows stay intact."""
    latest = {}
    for row in sorted(rows, key=lambda row: str(row.get("version_at") or row.get("availability_at") or row.get("observed_at") or "")):
        key = tuple(str(row.get(name)) for name in ("symbol", "fiscal_year", "fiscal_quarter", "statement_type", "metric", "source_id"))
        latest[key] = row
    output = []
    for row in latest.values():
        available = _instant(row.get("published_at")) if row.get("publication_time_authoritative") is True else None
        basis = "authoritative_publication"
        if available is None:
            available, basis = _instant(row.get("official_filing_uploaded_at")), "official_filing_upload_current_revision"
        if available is None:
            period = _financial_period_time(row)
            available, basis = period + timedelta(days=90) if period else None, "period_end_plus_90_days_assumption"
        if available is None:
            output.append(dict(row))
            continue
        clock = available.isoformat()
        output.append({**row, "published_at": None, "publication_time_authoritative": False,
            "availability_at": clock, "observed_at": clock, "record_at": None,
            "financial_training_time_basis": basis, "original_receipt_at": row.get("availability_at")})
    return output


def build_financial_samples(datasets, symbols, as_of, snapshot, horizon_days, role):
    """Replay financials using the approved reported/assumed time policy; price labels stay purged."""
    from .specialists import validated_inputs
    from .facts import _financial_features_v2
    base, exclusions = build_quant_samples(datasets, symbols, as_of, snapshot, horizon_days)
    if role == "fundamental":
        datasets = {**datasets, "financials": financial_training_history(datasets.get("financials", []))}
    exclusions = defaultdict(int, exclusions)
    output = []
    for sample in base:
        inputs, evidence, _ = validated_inputs({name: datasets.get(name, []) for name in ("financials", "valuation")},
            sample["symbol"], sample["analysis_as_of"], snapshot)
        if role == "fundamental":
            values = _financial_features_v2(inputs.get("financials", []))["fundamental"]
        elif role == "valuation":
            observations = sorted(inputs.get("valuation", []), key=lambda row: str(row.get("observed_date", row.get("observed_at", ""))))
            values = observations[-1] if observations else {}
        else:
            raise ValueError("unsupported financial specialist")
        features = {name: number(values.get(name)) for name in ROLE_FEATURES[role]}
        if any(value is None for value in features.values()):
            exclusions["insufficient_financial_features" if role == "fundamental" else "insufficient_pit_financial_features"] += 1
            continue
        output.append({**sample, **features, "provenance_id": digest([sample["provenance_id"], evidence])})
    return output, dict(exclusions)


def evaluate_core_history(datasets, symbols, as_of, snapshot):
    results = []
    for horizon in (5, 20, 60, 120):
        samples, exclusions = build_quant_samples(datasets, symbols, as_of, snapshot, horizon)
        for model in ("linear", "lightgbm", "catboost", "qlib_double_ensemble"):
            evaluation = walk_forward(samples, model_name=model, features=["momentum_5d", "momentum_20d", "momentum_60d"],
                                      cost_bps=30, horizon_days=horizon)
            evaluation.pop("output_hash")
            evaluation.update(core_snapshot_id=snapshot, analysis_as_of=as_of, exclusions=exclusions,
                              cost_semantics="research_sensitivity_30bps_not_actual_broker_cost",
                              cohort_semantics="current_deep_coverage_research_cohort_not_historical_population",
                              missing_evaluations=["historical_membership_replay", "ic_decay", "calibration", "regime_stability", "qlib_double_ensemble"])
            if model == "qlib_double_ensemble":
                evaluation["upstream_version"] = "microsoft/qlib-v0.9.7-bounded-adapter"
                evaluation["missing_evaluations"].remove("qlib_double_ensemble")
            if any(item["rank_ic"] is not None for value in evaluation["metrics"]["ic_decay"].values()
                   for item in value["time_series_by_symbol"].values()):
                evaluation["missing_evaluations"].remove("ic_decay")
            calibration = evaluation["metrics"]["probability_calibration"]
            if isinstance(calibration, dict) and calibration["status"] == "evaluated":
                evaluation["missing_evaluations"].remove("calibration")
            evaluation["output_hash"] = digest(evaluation)
            results.append(evaluation)
        for role, models in (("fundamental", ("lightgbm",)), ("valuation", ("lightgbm", "catboost"))):
            financial_samples, financial_exclusions = build_financial_samples(datasets, symbols, as_of, snapshot, horizon, role)
            for model in models:
                evaluation = walk_forward(financial_samples, model_name=model, features=ROLE_FEATURES[role],
                                          cost_bps=30, horizon_days=horizon)
                evaluation.pop("output_hash")
                evaluation.update(specialist_role=role, core_snapshot_id=snapshot, analysis_as_of=as_of,
                    exclusions=financial_exclusions, cost_semantics="research_sensitivity_30bps_not_actual_broker_cost",
                    cohort_semantics="current_deep_coverage_research_cohort_not_historical_population")
                if role == "fundamental":
                    history = financial_training_history(datasets.get("financials", []))
                    bases = defaultdict(int)
                    for row in history:
                        if row.get("metric") in ROLE_FEATURES[role]:
                            bases[row.get("financial_training_time_basis", "unknown")] += 1
                    evaluation["financial_history_policy"] = {**FINANCIAL_HISTORY_POLICY, "feature_time_basis_counts": dict(bases)}
                evaluation["output_hash"] = digest(evaluation)
                results.append(evaluation)
    from .specialists import validated_inputs, price_series
    benchmark_rows, _, _ = validated_inputs(datasets, sorted(symbols)[0], as_of, snapshot) if symbols else ({}, [], [])
    series = price_series(benchmark_rows.get("benchmark", []))
    values = list(series.values())
    returns = [b / a - 1 for a, b in zip(values, values[1:])]
    results.append({"model_name": "statsmodels_markov_regime", "core_snapshot_id": snapshot,
                    "analysis_as_of": as_of, **fit_regime_challenger(returns, dates=list(series)[1:])})
    return results


def fit_regime_challenger(returns, *, dates=None):
    """Monthly research fit only; filtered final-state probability has no promotion authority."""
    if dates is not None and (len(dates) != len(returns) or dates != sorted(set(dates))):
        raise ValueError("regime returns require unique chronological market dates")
    if len(returns) < 252 or any(number(r) is None for r in returns) or not pstdev(returns):
        return {"status": "insufficient_history", "required_returns": 252, "available_returns": len(returns),
                "high_vol_probability": None, "promotion_eligible": False}
    import numpy as np
    from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression
    model = MarkovRegression(np.asarray(returns), k_regimes=2, trend="c", switching_variance=True)
    try:
        result = model.fit(disp=False, maxiter=100, em_iter=5, search_reps=0)
    except (np.linalg.LinAlgError, ValueError, FloatingPointError):
        return {"status": "fit_numerical_error", "high_vol_probability": None, "promotion_eligible": False}
    if not result.mle_retvals.get("converged") or not np.isfinite(result.params).all():
        return {"status": "fit_not_converged", "high_vol_probability": None, "promotion_eligible": False}
    variances = [result.params[model.parameters[i, "variance"]][0] for i in range(2)]
    regime = int(np.argmax(variances))
    payload = {"status": "research_fit_oos_pending", "high_vol_probability": float(result.filtered_marginal_probabilities[-1, regime]),
               "promotion_eligible": False, "parameters": result.params.tolist(), "model_version": "statsmodels-markov-2-v2"}
    if dates is None:
        return payload
    from scipy.stats import norm
    folds, skipped = [], []
    for month in sorted({day[:7] for day in dates}):
        indices = [i for i, day in enumerate(dates) if day.startswith(month)]
        first, last = indices[0], indices[-1]+1
        history = np.asarray(returns[:first])
        if first < 252 or not np.std(history):
            continue
        try:
            trained = MarkovRegression(history, k_regimes=2, trend="c", switching_variance=True).fit(
                disp=False, maxiter=100, em_iter=5, search_reps=0)
        except (np.linalg.LinAlgError, ValueError, FloatingPointError):
            skipped.append({"month": month, "reason": "fit_numerical_error"})
            continue
        if not trained.mle_retvals.get("converged") or not np.isfinite(trained.params).all():
            skipped.append({"month": month, "reason": "fit_not_converged"})
            continue
        # Fixed pre-month parameters, forward filtering only; no smoothed probabilities.
        filtered = MarkovRegression(np.asarray(returns[:last]), k_regimes=2, trend="c", switching_variance=True).filter(trained.params)
        markov = filtered.llf_obs[first:last]
        gaussian = norm.logpdf(returns[first:last], loc=float(history.mean()), scale=float(history.std()))
        if np.isfinite(markov).all() and np.isfinite(gaussian).all():
            folds.append({"month": month, "training_end": dates[first-1], "test_start": dates[first],
                          "test_end": dates[last-1], "test_returns": last-first,
                          "markov_log_score_sum": float(markov.sum()), "gaussian_log_score_sum": float(gaussian.sum())})
        else:
            skipped.append({"month": month, "reason": "invalid_predictive_density"})
    count = sum(f["test_returns"] for f in folds)
    payload.update(status="research_oos_evaluated" if count >= 30 else "research_fit_oos_pending", oos_folds=folds,
        skipped_folds=skipped, oos_returns=count,
        average_log_score_improvement=sum(f["markov_log_score_sum"]-f["gaussian_log_score_sum"] for f in folds)/count if count else None)
    return payload
