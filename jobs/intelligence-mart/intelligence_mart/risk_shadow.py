"""Read-only Risk XGBoost inference on accepted pinned Core bars.

Research candidate cannot upgrade risk specialist publication. The caller
persists immutable shadow-only results with source/model hashes separately.
Never fit, download an untrusted URL, update canonical values, or write owner data.
"""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import math

import numpy as np
import pandas as pd

from research.colab.risk_pilot import make_risk_panel
from research.colab.risk_v1 import V1_FEATURES, add_v1_features

MODEL_VERSION = "risk-xgboost8-2025h2-v1"
MODEL_SHA256 = "36c77d0168a1d667223ab915c9b08fd2c1c6608f9f7db2fc046204e922854044"
MODEL_NAME = "risk-models/candidates/2026Q3-20261022/risk-xgboost8-2025h2-v1.ubj"
FEATURE_VERSION = "risk-ohlcv8-market-session-v1"
RISK_MODEL_SOURCE_STATUS = "CURRENT_MASTER_ONLY_UNADJUSTED_RESEARCH"


def load_model_from_pinned_store(store, *, expected_sha256=MODEL_SHA256):
    """Allow only the reviewed hash in an existing Mart dev bucket."""
    raw = store.read(MODEL_NAME)
    if sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("risk model sha256 mismatch")
    # Late import keeps deterministic screening independent of XGBoost startup.
    from xgboost import XGBRegressor
    model = XGBRegressor()
    model.load_model(bytearray(raw))
    if getattr(model, "n_features_in_", None) != len(V1_FEATURES):
        raise ValueError("risk model feature count mismatch")
    return model


def _eligible_price_rows(rows, as_of: str) -> tuple[pd.DataFrame, list[str]]:
    """Core names/units mapped without guessing, and quality/source guards."""
    needed = ("symbol", "market", "trade_date", "open", "high", "low", "close",
              "volume_shares", "turnover_twd", "source_id", "provenance_id")
    accepted = []
    excluded = []
    for row in rows:
        sym = str(row.get("symbol", ""))
        if not sym:
            continue
        if any(row.get(key) is None for key in needed):
            excluded.append(sym)
            continue
        market = str(row["market"]).lower()
        if market not in ("twse", "tpex"):
            excluded.append(sym)
            continue
        day = str(row["trade_date"])[:10]
        if day > as_of:
            raise ValueError("risk input contains future session")
        if str(row.get("source_authorization", "")).lower() in ("blocked", "denied", "unauthorized"):
            excluded.append(sym)
            continue
        # Do not treat fetched_at as historical first publication.
        # Explicit later-published revisions are unavailable at cutoff.
        for time_field in ("published_at", "availability_at"):
            stamp = row.get(time_field)
            if stamp is not None and str(stamp).strip():
                stamp_day = str(stamp)[:10]
                try:
                    from datetime import date
                    known_day = date.fromisoformat(stamp_day)
                except ValueError as exc:
                    raise ValueError("risk invalid publication metadata") from exc
                if known_day.isoformat() > as_of:
                    raise ValueError("risk future-available source revision")

        if row.get("quality_flag") == "critical":
            excluded.append(sym)
            continue
        # Explicit corporate-action rows have no comparable return scale;
        # don't change prices or invent a split ratio.
        if row.get("is_corporate_action") is True:
            excluded.append(sym)
            continue
        accepted.append({
            "symbol": sym, "market": market, "trade_date": day,
            "open": row["open"], "high": row["high"], "low": row["low"],
            "close": row["close"], "volume": row["volume_shares"],
            "turnover": row["turnover_twd"],
        })
    result = pd.DataFrame(accepted)
    if result.empty:
        return result, excluded
    # Core's pinned Iceberg snapshot can include revisions with the same
    # (symbol, market, trade_date). Revisions are NOT interchangeable merely
    # because their timestamps differ. Collapse only numerically identical
    # eligible OHLCV/turnover rows; conflicting evidence quarantines the
    # *entire affected stock*, not the other stocks in this market chunk.
    # No as-of-max revision selection, price averaging, or forward fill.
    bars = ("open", "high", "low", "close", "volume", "turnover")
    result = result.sort_values(["symbol", "trade_date", "market"], kind="stable")
    ambiguous = set()
    duplicate_rows = 0
    duplicates = result.loc[result.duplicated(["symbol", "trade_date"], keep=False)]
    for (sym, day), group in duplicates.groupby(["symbol", "trade_date"], sort=False):
        comparable = group[list(bars)].apply(pd.to_numeric, errors="coerce")
        if (comparable.isna().any().any()
                or not np.isfinite(comparable.to_numpy(dtype=float)).all()
                or group["market"].nunique() != 1
                or any(comparable[c].nunique(dropna=False) != 1 for c in bars)):
            ambiguous.add(sym)
        else:
            duplicate_rows += len(group) - 1
    if ambiguous:
        # Do not allow the feature engine to bridge a disputed historic day.
        excluded.extend(sorted(ambiguous))
        result = result.loc[~result["symbol"].isin(ambiguous)]
    result = result.drop_duplicates(["symbol", "trade_date"], keep="first")
    # Conflicting historical TWSE/TPEx membership is not an inferred transfer.
    # Quarantine the affected symbol, not the unrelated 250-symbol batch.
    mixed_market = set(result.groupby("symbol")["market"].nunique().loc[lambda n: n > 1].index)
    if mixed_market:
        ambiguous.update(mixed_market)
        excluded.extend(sorted(mixed_market))
        result = result.loc[~result["symbol"].isin(mixed_market)].copy()
    # Counts are carried with the DataFrame for the non-public shadow receipt.
    result.attrs["ambiguous_core_symbols"] = len(ambiguous)
    result.attrs["identical_core_duplicates_collapsed"] = duplicate_rows
    return result, excluded


def predict_core_shadow(rows: list[dict], as_of: str, model, *, core_snapshot_id: str,
                        target_symbols: set[str] | frozenset[str] | None = None) -> dict:
    """Selected ordinary shares, eight-factor deterministic XGB risk prediction.

    Trading calendar comes from accepted market bars IN THE SAME pinned Core
    snapshot. This is only a provisional observation calendar, not certified
    official sessions: output must remain shadow and publication_allowed=false.
    """
    prices, excluded = _eligible_price_rows(rows, as_of)
    quarantined = prices.attrs.get("ambiguous_core_symbols", 0)
    collapsed = prices.attrs.get("identical_core_duplicates_collapsed", 0)
    if prices.empty:
        count = len(target_symbols) if target_symbols is not None else len(set(excluded))
        return {"status": "INSUFFICIENT_OHLCV", "predictions": [],
                "excluded_input_rows": len(excluded),
                "ambiguous_core_symbols": quarantined,
                "identical_core_duplicates_collapsed": collapsed,
                "target_symbols_count": count, "excluded_target_symbols_count": count,
                "excluded_target_reasons": {"NO_ACCEPTED_CORE_HISTORY_OR_ACTION_OR_SOURCE": count},
                "publication_allowed": False}
    # Core does not expose a certified per-market trading-session calendar
    # here. Use the union of all accepted cohort dates for BOTH markets:
    # conservative across asymmetric closure and missing-market days, so
    # a day seen in either market cannot silently bridge a missing stock day.
    # This stays shadow until a verified per-market calendar is available.
    evidenced_days = sorted(prices["trade_date"].unique())
    grids = {market: evidenced_days for market in sorted(prices.market.unique())}
    # Preserve the observed session calendar from the whole accepted chunk,
    # but compute expensive features and predictions for watchlist/held shares
    # only. Never infer owner holdings from prices or the public universe.
    if target_symbols is not None:
        prices = prices.loc[prices.symbol.isin(target_symbols)].copy()
        if prices.empty:
            return {"status": "NO_ELIGIBLE_TARGETS", "predictions": [],
                    "eligible_symbols": 0,
                    "target_symbols_count": len(target_symbols),
                    "excluded_target_symbols_count": len(target_symbols),
                    "excluded_target_reasons": {
                        "NO_ACCEPTED_CORE_HISTORY_OR_ACTION_OR_SOURCE": len(target_symbols)},
                    "publication_allowed": False}
    panel = add_v1_features(make_risk_panel(prices, market_sessions=grids))
    latest = panel.loc[panel.trade_date.eq(pd.Timestamp(as_of))].copy()
    valid = latest.dropna(subset=list(V1_FEATURES))
    valid = valid.loc[valid["unverified_shock_feature"].eq(0)]
    target_pool = set(target_symbols) if target_symbols is not None else set(prices.symbol)
    with_usable_bars = set(prices.symbol)
    with_complete_features = set(latest.dropna(subset=list(V1_FEATURES)).symbol)
    valid_set = set(valid.symbol)
    exclusion_reasons = {
        "NO_ACCEPTED_CORE_HISTORY_OR_ACTION_OR_SOURCE": len(target_pool - with_usable_bars),
        "MISSING_REQUIRED_8_FEATURE_WINDOW": len((target_pool & with_usable_bars) - with_complete_features),
        "UNVERIFIED_EXTREME_RETURN_WINDOW": len(with_complete_features - valid_set),
    }
    predictions = []
    if not valid.empty:
        x = valid[list(V1_FEATURES)].to_numpy(dtype=np.float32)
        y = np.asarray(model.predict(x), dtype=float)
        if len(y) != len(valid) or not np.isfinite(y).all():
            raise ValueError("risk nonfinite or mismatched model output")
        for (_, row), value in zip(valid.iterrows(), y):
            annual = max(float(value), 0.)
            recent = float(row["vol20"])
            if not all(math.isfinite(n) and n >= 0 for n in (annual, recent)):
                raise ValueError("risk invalid current volatility")
            predictions.append({
                "symbol": str(row["symbol"]), "market": str(row["market"]),
                "analysis_as_of": as_of, "core_snapshot_id": core_snapshot_id,
                "future_20d_volatility_annualized": annual,
                "recent_20d_volatility_annualized": recent,
                "model_version": MODEL_VERSION, "feature_version": FEATURE_VERSION,
                "model_sha256": MODEL_SHA256,
                "quality": "SHADOW_UNVALIDATED", "publication_allowed": False,
            })
    return {"status": "SHADOW_ONLY", "predictions": predictions,
            "input_symbols": int(prices.symbol.nunique()),
            "ambiguous_core_symbols": quarantined,
            "identical_core_duplicates_collapsed": collapsed,
            "eligible_symbols": int(len(predictions)),
            "excluded_input_rows": len(excluded),
            "target_symbols_count": len(target_pool),
            "excluded_target_symbols_count": len(target_pool - valid_set),
            "excluded_target_reasons": exclusion_reasons,
            "calendar_evidence": "PINNED_CORE_COHORT_UNION_SESSIONS_NOT_OFFICIAL_CERTIFIED",
            "source_status": RISK_MODEL_SOURCE_STATUS,
            "publication_allowed": False,
            "model_version": MODEL_VERSION, "model_sha256": MODEL_SHA256}
