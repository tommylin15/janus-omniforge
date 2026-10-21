"""Risk OHLCV-enriched challenger v1 (RESEARCH ONLY, never auto-promote).

Adds ATR14/close, mean absolute overnight gap (5 trading sessions), and
log(1 + 20-day average turnover in TWD). Requires official-market session
reindexed bars from make_risk_panel; missing stock sessions stay NaN.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

V0_FEATURES = ('vol20', 'vol60', 'drawdown60', 'abs_return5', 'volume_ratio20')
V1_EXTRA = ('atr14_pct', 'abs_overnight_gap5', 'log_turnover20')
V1_FEATURES = V0_FEATURES + V1_EXTRA


def add_v1_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Create time-t features only, with no market/company-action substitution."""
    for col in ('symbol', 'market', 'trade_date', 'open', 'high', 'low', 'close', 'turnover', *V0_FEATURES):
        if col not in panel:
            raise ValueError(f'missing OHLCV input field: {col}')
    out = panel.copy()
    for col in ('open', 'high', 'low', 'close', 'turnover'):
        out[col] = pd.to_numeric(out[col], errors='raise')
    observed = out['close'].notna()
    if ((out.loc[observed, ['open', 'high', 'low', 'close']] <= 0).any().any()
            or (out.loc[observed, 'high'] < out.loc[observed, ['open', 'low', 'close']].max(axis=1)).any()
            or (out.loc[observed, 'low'] > out.loc[observed, ['open', 'close']].min(axis=1)).any()
            or (out.loc[observed, 'turnover'] < 0).any()
            or out.loc[observed, ['open', 'high', 'low', 'turnover']].isna().any().any()):
        raise ValueError('invalid OHLC/turnover; do not fabricate missing values')
    out = out.sort_values(['market', 'symbol', 'trade_date']).reset_index(drop=True)
    grouped = out.groupby(['market', 'symbol'], sort=False)
    prior_close = grouped['close'].shift(1)
    true_range = pd.concat([(out['high'] - out['low']),
                            (out['high'] - prior_close).abs(),
                            (out['low'] - prior_close).abs()], axis=1).max(axis=1, skipna=False)
    key = [out['market'], out['symbol']]
    out['atr14_pct'] = (true_range.groupby(key, sort=False).transform(
        lambda s: s.rolling(14, min_periods=14).mean()) / out['close'])
    overnight_abs = (out['open'] / prior_close - 1).abs()
    out['abs_overnight_gap5'] = overnight_abs.groupby(key, sort=False).transform(
        lambda s: s.rolling(5, min_periods=5).mean())
    avg_turnover = grouped['turnover'].transform(lambda s: s.rolling(20, min_periods=20).mean())
    out['log_turnover20'] = np.log1p(avg_turnover)
    return out


def compare_risk_models(panel: pd.DataFrame, cutoff: str,
                        *, oos_end: str | None = None,
                        exclude_unverified_shocks: bool = True) -> dict:
    """Matched samples, label-maturity purge, train-only scaling.

    Retrospective fixed-cutoff diagnostic; no independent pristine holdout.
    """
    cutoff_ts = pd.Timestamp(cutoff)
    end_ts = pd.Timestamp(oos_end) if oos_end else None
    as_of = panel['trade_date'].max()
    columns = list(V1_FEATURES) + ['target_fwd_vol20', 'label_matures_on']
    eligible = panel.dropna(subset=columns).copy()
    eligible = eligible.loc[eligible['label_matures_on'] <= as_of]
    if exclude_unverified_shocks:
        for col in ('unverified_shock_feature', 'unverified_shock_label'):
            if col not in eligible:
                raise ValueError('shock sensitivity flag missing')
        eligible = eligible.loc[(eligible['unverified_shock_feature'] == 0)
                                & (eligible['unverified_shock_label'] == 0)]
    train = eligible.loc[(eligible['trade_date'] <= cutoff_ts)
                         & (eligible['label_matures_on'] <= cutoff_ts)]
    test = eligible.loc[(eligible['trade_date'] > cutoff_ts)
                        & (eligible['label_matures_on'] <= as_of)]
    if end_ts is not None:
        test = test.loc[test['trade_date'] <= end_ts]
    if (len(train) < 100 or len(test) < 20
            or train['trade_date'].nunique() < 30 or test['trade_date'].nunique() < 5):
        raise ValueError(f'insufficient time-matured panel: train={len(train)} test={len(test)}')
    baseline = test['vol20'].to_numpy()
    actual = test['target_fwd_vol20'].to_numpy()
    preds = {'rolling20': baseline}
    for name, cols in [('ridge_v0_matched', V0_FEATURES),
                       ('ridge_v1_ohlcv', V1_FEATURES)]:
        estimator = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
        estimator.fit(train[list(cols)], train['target_fwd_vol20'])
        preds[name] = np.clip(estimator.predict(test[list(cols)]), 0, None)

    def scored(indices):
        y = actual[indices]
        return {name: {'mae': float(np.mean(np.abs(y - val[indices]))),
                       'rmse': float(np.sqrt(np.mean((y - val[indices]) ** 2)))}
                for name, val in preds.items()}

    months = test['trade_date'].dt.to_period('M').astype(str)
    month_metrics = {
        str(m): {'rows': int((months == m).sum()),
                 'metrics': scored((months == m).to_numpy())}
        for m in sorted(months.unique())
    }
    market_metrics = {
        str(m): {'rows': int((test['market'] == m).sum()),
                 'metrics': scored((test['market'] == m).to_numpy())}
        for m in sorted(test['market'].unique())
    }
    metric = scored(slice(None))
    return {
        'status': 'RESEARCH_OOS_ONLY_NOT_PROMOTABLE',
        'publication_allowed': False,
        'cutoff': cutoff_ts.strftime('%Y-%m-%d'),
        'oos_end': end_ts.strftime('%Y-%m-%d') if end_ts is not None else None,
        'last_available_date': as_of.strftime('%Y-%m-%d'),
        'train_rows': int(len(train)), 'oos_rows': int(len(test)),
        'train_unique_dates': int(train['trade_date'].nunique()),
        'oos_unique_dates': int(test['trade_date'].nunique()),
        'latest_train_label_maturity': train['label_matures_on'].max().strftime('%Y-%m-%d'),
        'latest_oos_label_maturity': test['label_matures_on'].max().strftime('%Y-%m-%d'),
        'features_v0': list(V0_FEATURES), 'features_v1': list(V1_FEATURES),
        'candidate_data_basis': 'RAW_UNADJUSTED_OHLCV_AND_CURRENT_MASTER_ONLY',
        'shock_screen': bool(exclude_unverified_shocks),
        'metrics': metric, 'by_month': month_metrics, 'by_market': market_metrics,
        'v1_beats_v0_mae': bool(metric['ridge_v1_ohlcv']['mae'] < metric['ridge_v0_matched']['mae']),
        'v1_beats_rolling_mae': bool(metric['ridge_v1_ohlcv']['mae'] < metric['rolling20']['mae']),
    }
