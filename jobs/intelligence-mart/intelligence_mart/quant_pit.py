"""B9 research-only historical PIT universe reconstructed from authorized public OHLCV.

This is NOT an official index-constituent history, a current-500 replay, or
permission to publish/promote any model. It uses only prices/turnover OBSERVED
by the selection date, and trades on the following exchange session.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from hashlib import sha256
import json
from math import ceil, isfinite
from statistics import correlation, fmean, pstdev


MODELS = ("linear", "lightgbm", "catboost", "qlib_double_ensemble")


def _day(value):
    if not isinstance(value, str):
        raise ValueError("historical PIT timestamp missing")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError as exc:
        raise ValueError("invalid historical PIT timestamp") from exc


def _hash(data):
    return "sha256:" + sha256(json.dumps(data, sort_keys=True, separators=(",", ":"),
                                          ensure_ascii=False).encode()).hexdigest()


def historical_liquid_universe(rows, sessions, *, core_snapshot_id, lookback=20,
                               limit=500, minimum=10):
    """Reconstruct an as-known prior-session liquidity universe.

    'observed_at' is intentionally required. A later-received historical row
    cannot be silently backdated into an earlier investment decision.
    'published_at' cannot override an actual later receipt; such history is
    research-only until the as-known evidence is independently established.
    """
    if not core_snapshot_id or lookback < 2 or not 10 <= minimum <= limit <= 500:
        raise ValueError("invalid immutable universe bounds")
    days = tuple(sessions)
    if len(days) != len(set(days)) or list(days) != sorted(days):
        raise ValueError("sessions must be unique chronological market dates")
    for day in days:
        date.fromisoformat(day)
    indexed, rejections = defaultdict(dict), Counter()
    for row in rows:
        if row.get("source_authorization") != "official" or not row.get("provenance_id"):
            rejections["unauthorized_or_unproven"] += 1
            continue
        symbol, trade_date = row.get("symbol"), row.get("trade_date")
        if not isinstance(symbol, str) or not symbol.isdigit() or not 4 <= len(symbol) <= 6:
            rejections["invalid_symbol"] += 1
            continue
        if trade_date not in days:
            rejections["outside_market_calendar"] += 1
            continue
        try:
            observed = _day(row.get("observed_at"))
            available = _day(row.get("availability_at"))
            published = _day(row.get("published_at"))
            amount = float(row.get("turnover_twd"))
        except (TypeError, ValueError, OverflowError):
            rejections["invalid_time_or_turnover"] += 1
            continue
        if not isfinite(amount) or amount <= 0:
            rejections["invalid_time_or_turnover"] += 1
            continue
        # No current-membership selection. Historical data can only enter at
        # its real observation/publication/availability date, whichever latest.
        known_on = max(observed, available, published)
        if known_on < date.fromisoformat(trade_date):
            rejections["inconsistent_history_time"] += 1
            continue
        existing = indexed[symbol].get(trade_date)
        if existing is not None:
            if existing != (amount, known_on, row["provenance_id"]):
                raise ValueError("conflicting duplicate official source row")
            continue
        indexed[symbol][trade_date] = (amount, known_on, row["provenance_id"])
    output, coverage = {}, []
    for ix in range(lookback, len(days)):
        entry, selection = days[ix], days[ix-1]
        prior = days[ix-lookback:ix]
        scores = []
        for symbol, history in indexed.items():
            window = [history.get(day) for day in prior]
            if any(item is None for item in window):
                continue
            if any(item[1] > date.fromisoformat(selection) for item in window):
                rejections["not_known_before_entry"] += 1
                continue
            scores.append((symbol, fmean(item[0] for item in window),
                           [item[2] for item in window]))
        scores.sort(key=lambda item: (-item[1], item[0]))
        chosen = scores[:limit]
        valid = len(chosen) >= minimum
        provenance = [(symbol, sources) for symbol, _, sources in chosen]
        membership = {
            "entry_as_of": entry, "selection_as_of": selection,
            "symbols": [symbol for symbol, _, _ in chosen],
            "universe_version": f"prior-session-{lookback}d-liquid-research-v1",
            "core_snapshot_id": core_snapshot_id,
            "source_authorization": "official",
            "source_provenance_hash": _hash(provenance),
            "membership_semantics": "reconstructed_as_known_not_official_index_history",
            "quality": "candidate" if valid else "insufficient_cross_section",
        }
        membership["membership_hash"] = _hash(membership)
        coverage.append({"entry_as_of": entry, "eligible_symbols": len(scores),
                         "selected_symbols": len(chosen), "quality": membership["quality"]})
        if valid:
            output[entry] = membership
    return {"schema_version": "b9-quant-pit-cohort-v1",
            "source_core_snapshot_id": core_snapshot_id, "historical_universe": output,
            "coverage": coverage, "source_rejections": dict(rejections),
            "research_only": True, "promotion_eligible": False,
            "source_replay_readback": "not_verified"}


def _ranks(values):
    pairs = sorted(enumerate(values), key=lambda v: v[1])
    ranks = [0.0] * len(pairs)
    start = 0
    while start < len(pairs):
        stop = start + 1
        while stop < len(pairs) and pairs[stop][1] == pairs[start][1]:
            stop += 1
        for idx, _ in pairs[start:stop]:
            ranks[idx] = (start + stop - 1) / 2
        start = stop
    return ranks


def _score(rows, *, cost_bps):
    """One-way traded notional: entry buys and later buys+sales pay side costs."""
    daily_ic, gross, net, turnover = [], [], [], []
    previous = {}
    for day, block in rows:
        ordered = sorted(block, key=lambda r: (-r["score"], r["symbol"]))
        if len(ordered) < 10:
            raise ValueError("too small for a cross-sectional decile")
        x = _ranks([row["score"] for row in ordered])
        y = _ranks([row["excess_return"] for row in ordered])
        if pstdev(x) and pstdev(y):
            daily_ic.append(correlation(x, y))
        n = ceil(len(ordered) / 10)
        current = {row["symbol"] for row in ordered[:n]}
        # Equal weights. L1 traded notional includes sales AND purchases,
        # first observation enters from cash and pays one side.
        weights = {symbol: 1 / n for symbol in current}
        traded = sum(abs(weights.get(symbol, 0) - previous.get(symbol, 0))
                     for symbol in set(weights) | set(previous))
        previous = weights
        ret = fmean(row["excess_return"] for row in ordered[:n])
        turnover.append(traded)
        gross.append(ret)
        net.append(ret - traded * cost_bps / 10000)
    def compound(values):
        wealth = 1.0
        for value in values:
            wealth *= 1 + value
        return wealth-1
    return {"rank_ic": fmean(daily_ic) if daily_ic else None,
            "icir": fmean(daily_ic)/pstdev(daily_ic) if len(daily_ic) > 1 and pstdev(daily_ic) else None,
            "gross_return": compound(gross), "after_cost_return": compound(net),
            "mean_one_way_traded_notional": fmean(turnover) if turnover else None,
            "cross_sections": len(rows), "ic_cross_sections": len(daily_ic)}


def compare_four_models(predictions, cohort, sessions, *, horizon_days=5,
                        cost_bps=30, minimum=10):
    """Matched-panel descriptive research. Never a champion/promotion PASS.

    predictions: mapping of four model IDs to prediction rows; a separate
    'momentum_5d' ex-ante score must accompany each common prediction.
    A missing member or mismatched label blocks the whole date rather than
    cherry-picking a different cohort for each challenger.
    """
    if set(predictions) != set(MODELS) or horizon_days not in (5, 20, 60, 120) or cost_bps < 0:
        raise ValueError("four fixed models, valid horizon and cost required")
    universe = cohort["historical_universe"]
    calendar = {day: index for index, day in enumerate(sessions)}
    if len(calendar) != len(sessions):
        raise ValueError("duplicate market session")
    keyed, reasons = {}, Counter()
    for model in MODELS:
        entries = {}
        for row in predictions[model]:
            key = (row.get("analysis_as_of"), row.get("symbol"))
            if key in entries:
                raise ValueError("duplicate model prediction")
            entries[key] = row
        keyed[model] = entries
    blocks = []
    previous_index = None
    for day, membership in sorted(universe.items()):
        if (day not in calendar or membership.get("quality") != "candidate" or
                membership.get("core_snapshot_id") != cohort.get("source_core_snapshot_id") or
                membership.get("membership_hash") != _hash({k: v for k, v in membership.items()
                                                           if k != "membership_hash"})) :
            reasons["invalid_historical_membership"] += 1
            continue
        if previous_index is not None and calendar[day]-previous_index < horizon_days:
            reasons["overlapping_oos_outcomes"] += 1
            continue
        eligible = []
        for symbol in membership["symbols"]:
            rows = [keyed[model].get((day, symbol)) for model in MODELS]
            if any(row is None for row in rows):
                reasons["missing_matched_model_prediction"] += 1
                continue
            labels = {row.get("excess_return") for row in rows}
            outcomes = {row.get("outcome_as_of") for row in rows}
            momentum = {row.get("momentum_5d") for row in rows}
            if len(labels) != 1 or len(outcomes) != 1 or len(momentum) != 1:
                raise ValueError("mismatched future label or ex-ante momentum")
            try:
                label = float(rows[0]["excess_return"])
                m = float(rows[0]["momentum_5d"])
                scores = [float(row["prediction"]) for row in rows]
                if any(not isfinite(v) for v in (label, m, *scores)):
                    raise ValueError("invalid score")
            except (ValueError, TypeError, OverflowError):
                reasons["invalid_matched_number"] += 1
                continue
            if any(row.get("outcome_as_of") not in calendar or
                   calendar.get(row.get("outcome_as_of"), -1) - calendar[day] != horizon_days or
                   row.get("label_available_at", "~") > sessions[-1] or
                   row.get("sample_source_authorization") != "official" or
                   not row.get("sample_provenance_id") or
                   not row.get("training_label_cutoff", "~") < day < row.get("outcome_as_of", "") or
                   row.get("feature_available_at", "~") > day or
                   row.get("label_available_at", "") < row.get("outcome_as_of", "")
                   for row in rows):
                reasons["invalid_prediction_lineage_or_leakage"] += 1
                continue
            eligible.append((symbol, label, m, scores))
        if len(eligible) < minimum:
            reasons["insufficient_matched_cross_section"] += 1
            continue
        blocks.append((day, eligible))
        previous_index = calendar[day]
    panel = {}
    for index, model in enumerate((*MODELS, "momentum_rule")):
        per_day = []
        for day, block in blocks:
            per_day.append((day, [{"symbol": symbol, "excess_return": label,
                                   "score": scores[index] if index < 4 else m}
                                  for symbol, label, m, scores in block]))
        panel[model] = _score(per_day, cost_bps=cost_bps)
    return {"schema_version": "b9-quant-matched-oos-v1",
            "models": panel, "sessions": len(blocks),
            "min_symbols_per_session": min((len(block) for _, block in blocks), default=0),
            "max_symbols_per_session": max((len(block) for _, block in blocks), default=0),
            "horizon_days": horizon_days, "research_cost_bps_per_side": cost_bps,
            "excluded": dict(reasons), "matched_panel": True,
            "baseline": "prior_only_momentum_5d_rule",
            "status": "descriptive_only" if len(blocks) >= 3 else "insufficient_oos_cross_sections",
            "champion_promotion": False, "historical_source_readback": cohort.get("source_replay_readback"),
            "quality_pass": False}
