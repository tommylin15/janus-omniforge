"""Research Risk v1 tests: prior-only factors, matched cohorts, no publication."""
import numpy as np
import pandas as pd
import pytest

from research.colab.risk_v1 import add_v1_features, compare_risk_models


def example_panel(n=400):
    dates = pd.bdate_range('2025-01-02', periods=n)
    rows = []
    for market, symbol, scale in [('twse', '1101', 1.), ('tpex', '6488', 1.4)]:
        ret = np.sin(np.arange(n) / 12.) * .02 * scale + np.cos(np.arange(n) / 7.) * .004
        close = 100 * np.exp(np.cumsum(ret))
        for i, day in enumerate(dates):
            c = float(close[i])
            rows.append({
                'symbol': symbol, 'market': market, 'trade_date': day,
                'close': c, 'open': c * .997, 'high': c * 1.012,
                'low': c * .985, 'turnover': 1000000 + i * 1000,
                'vol20': .3, 'vol60': .3, 'drawdown60': -.1,
                'abs_return5': .05, 'volume_ratio20': 1.2,
                'target_fwd_vol20': .4,
                'label_matures_on': dates[i + 20] if i + 20 < n else pd.NaT,
                'unverified_shock_feature': 0., 'unverified_shock_label': 0.,
            })
    return pd.DataFrame(rows)


def test_v1_features_use_no_future_prices():
    raw = example_panel()
    baseline = add_v1_features(raw)
    day = raw.trade_date.iloc[80]
    changed = raw.copy()
    changed.loc[(changed.symbol == '1101') & (changed.trade_date > day), 'high'] *= 1.3
    changed = add_v1_features(changed)
    old = baseline[(baseline.symbol == '1101') & (baseline.trade_date == day)].iloc[0]
    new = changed[(changed.symbol == '1101') & (changed.trade_date == day)].iloc[0]
    for col in ('atr14_pct', 'abs_overnight_gap5', 'log_turnover20'):
        assert old[col] == pytest.approx(new[col])


def test_v1_factors_dont_bridge_missing_stock_session():
    raw = example_panel()
    day = raw.trade_date.iloc[90]
    raw.loc[(raw.symbol == '1101') & (raw.trade_date == day),
            ['open', 'high', 'low', 'close', 'turnover']] = np.nan
    panel = add_v1_features(raw)
    stock = panel[panel.symbol == '1101'].reset_index(drop=True)
    assert np.isnan(stock.loc[93, 'atr14_pct'])
    assert np.isnan(stock.loc[93, 'abs_overnight_gap5'])
    assert np.isnan(stock.loc[94, 'log_turnover20'])
    assert pd.notna(stock.loc[120, 'atr14_pct'])


def test_v1_comparison_same_train_test_and_mature_labels():
    panel = add_v1_features(example_panel())
    report = compare_risk_models(panel, '2025-08-01')
    assert report['train_rows'] > 100
    assert report['oos_rows'] > 50
    assert report['latest_train_label_maturity'] <= '2025-08-01'
    assert report['publication_allowed'] is False
    assert set(report['metrics']) == {'rolling20', 'ridge_v0_matched', 'ridge_v1_ohlcv'}
    assert set(report['by_market']) == {'tpex', 'twse'}
    assert report['status'] == 'RESEARCH_OOS_ONLY_NOT_PROMOTABLE'


def test_v1_rejects_impossible_ohlc():
    raw = example_panel()
    raw.loc[0, 'high'] = raw.loc[0, 'low'] * .1
    with pytest.raises(ValueError, match='invalid OHLC'):
        add_v1_features(raw)


def test_v1_rejects_missing_enrichment_and_immature_samples():
    raw = example_panel()
    with pytest.raises(ValueError, match='turnover'):
        add_v1_features(raw.drop(columns=['turnover']))
    enriched = add_v1_features(raw)
    with pytest.raises(ValueError, match='insufficient time-matured'):
        compare_risk_models(enriched, '2025-01-09')
