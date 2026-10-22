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
    if result.duplicated(["symbol", "trade_date"]).any():
        raise ValueError("duplicate admitted Core bar; fail closed")
    if result.groupby("symbol")["market"].nunique().gt(1).any():
        raise ValueError("symbol changed market inside inference window")
    return result, excluded


def predict_core_shadow(rows: list[dict], as_of: str, model, *, core_snapshot_id: str) -> dict:
    """Full-market chunk, eight-factor deterministic input and XGB prediction.

    Trading calendar comes from accepted market bars IN THE SAME pinned Core
    snapshot. This is only a provisional observation calendar, not certified
    official sessions: output must remain shadow and publication_allowed=false.
    """
    prices, excluded = _eligible_price_rows(rows, as_of)
    if prices.empty:
        return {"status": "INSUFFICIENT_OHLCV", "predictions": [],
                "excluded_input_rows": len(excluded), "publication_allowed": False}
    grids = {market: sorted(prices.loc[prices.market.eq(market), "trade_date"].unique())
             for market in sorted(prices.market.unique())}
    panel = add_v1_features(make_risk_panel(prices, market_sessions=grids))
    latest = panel.loc[panel.trade_date.eq(pd.Timestamp(as_of))].copy()
    valid = latest.dropna(subset=list(V1_FEATURES))
    valid = valid.loc[valid["unverified_shock_feature"].eq(0)]
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
            "eligible_symbols": int(len(predictions)),
            "excluded_input_rows": len(excluded),
            "calendar_evidence": "PINNED_CORE_OBSERVED_MARKET_DATES_NOT_OFFICIAL_CERTIFIED",
            "source_status": RISK_MODEL_SOURCE_STATUS,
            "publication_allowed": False,
            "model_version": MODEL_VERSION, "model_sha256": MODEL_SHA256}
