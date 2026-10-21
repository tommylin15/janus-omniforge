import hashlib
import io
import json
from zipfile import ZipFile

import numpy as np
import pandas as pd
import pytest

from research.colab.risk_pilot import evaluate_risk_pilot, load_monthly_zips, make_risk_panel


def make_prices(n=500):
    days = pd.bdate_range('2024-01-02', periods=n)
    out = []
    for symbol, market, scale in [('2330','twse',1), ('6488','tpex',3)]:
        ret = np.sin(np.arange(n) / 16) * .01 * scale + .002*np.cos(np.arange(n)/9)
        price = 100*np.exp(np.cumsum(ret))
        out.extend({'symbol':symbol,'market':market,'trade_date':dt,'close':float(x),'volume':10000+idx*10} for idx, (dt,x) in enumerate(zip(days,price)))
    return pd.DataFrame(out)


def test_prior_features_and_future_target():
    data = make_prices(360)
    panel = make_risk_panel(data)
    rows = panel[panel.symbol == '2330'].reset_index(drop=True)
    assert pd.isna(rows.loc[30, 'vol60'])
    assert pd.notna(rows.loc[61, 'vol60'])
    assert rows.loc[61, 'label_matures_on'] == rows.loc[81, 'trade_date']
    # Replacing any future close after day 120 must not change day 100's features.
    changed = data.copy()
    changed.loc[(changed.symbol == '2330') & (changed.trade_date > rows.loc[120, 'trade_date']), 'close'] *= 3
    newer = make_risk_panel(changed)
    a = rows.loc[100]
    b = newer[newer.symbol == '2330'].reset_index(drop=True).loc[100]
    for feature in ['vol20','vol60','drawdown60','abs_return5','volume_ratio20']:
        assert a[feature] == pytest.approx(b[feature])
    assert rows.loc[355, 'target_fwd_vol20'] != rows.loc[355, 'target_fwd_vol20']  # NaN


def test_purged_train_labels_and_oos():
    panel = make_risk_panel(make_prices())
    report = evaluate_risk_pilot(panel, '2025-04-01')
    assert report['train_rows'] > 100
    assert report['oos_rows'] > 20
    assert report['train_latest_label_maturity'] <= '2025-04-01'
    assert report['publication_allowed'] is False
    assert report['status'] == 'RESEARCH_OOS_ONLY_NOT_PROMOTABLE'


def test_duplicate_and_nonordinary_rejected():
    df = make_prices(200)
    with pytest.raises(ValueError, match='duplicate'):
        make_risk_panel(pd.concat([df,df.head(1)]))
    df.loc[0,'market'] = 'unknown'
    with pytest.raises(ValueError, match='ordinary'):
        make_risk_panel(df)


def test_verified_zip_read_and_tampering(tmp_path):
    df = make_prices(80).copy()
    df['trade_date'] = df.trade_date.dt.strftime('%Y-%m-%d')
    df = df[df.trade_date.str.startswith('2024-01')]
    bars = df.to_csv(index=False).encode()
    universe = b'symbol,market\n2330,twse\n6488,tpex\n'
    quality = json.dumps({'status': 'PROBE'}).encode()
    manifest = {'month':'2024-01','sha256': {p:hashlib.sha256(b).hexdigest() for p,b in [('ohlcv.csv',bars),('universe.csv',universe),('quality.json',quality)]}}
    path = tmp_path/'2024-01.zip'
    with ZipFile(path,'w') as z:
        z.writestr('ohlcv.csv',bars); z.writestr('universe.csv',universe)
        z.writestr('quality.json',quality); z.writestr('manifest.json',json.dumps(manifest))
    merged, prov = load_monthly_zips([path])
    assert len(merged) == len(df)
    assert prov[0]['month'] == '2024-01'
    with ZipFile(path,'a') as z:
        z.writestr('ohlcv.csv','corrupt')
    with pytest.raises(ValueError, match='duplicate ZIP'):
        load_monthly_zips([path])


def test_missing_stock_sessions_never_bridge_feature_or_future_label():
    """A stock suspension is not a market holiday and must not be forward-filled."""
    data = make_prices(180)
    sessions = list(pd.bdate_range('2024-01-02', periods=180))
    gap_day = sessions[90]
    data = data[~((data.symbol == '2330') & (data.trade_date == gap_day))]
    panel = make_risk_panel(data, market_sessions={'twse': sessions, 'tpex': sessions})
    stock = panel[panel.symbol == '2330'].set_index('trade_date')
    assert pd.isna(stock.loc[gap_day, 'close'])
    assert pd.isna(stock.loc[sessions[120], 'vol60'])
    assert pd.isna(stock.loc[sessions[75], 'target_fwd_vol20'])
    assert pd.notna(stock.loc[sessions[155], 'vol60'])
    other = panel[panel.symbol == '6488'].set_index('trade_date')
    assert pd.notna(other.loc[sessions[120], 'vol60'])


def test_official_market_session_missing_for_all_symbols_is_not_skipped():
    """The manifest calendar, not data presence, defines elapsed sessions."""
    data = make_prices(180)
    sessions = list(pd.bdate_range('2024-01-02', periods=180))
    whole_day = sessions[90]
    without = data[data.trade_date != whole_day]
    panel = make_risk_panel(without, market_sessions={'twse': sessions, 'tpex': sessions})
    assert panel[panel.trade_date == whole_day]['close'].isna().all()
    row = panel[(panel.symbol == '2330') & (panel.trade_date == sessions[75])]
    assert row['target_fwd_vol20'].isna().all()
    with pytest.raises(ValueError, match='outside evidenced trading sessions'):
        make_risk_panel(data, market_sessions={'twse': sessions[:-1], 'tpex': sessions[:-1]})


def test_oos_month_market_and_research_only_shock_sensitivity():
    data = make_prices(480)
    # Inject a deliberately unadjusted event; test the screen contract, not
    # a factual claim that this event is a real stock split.
    day = data[data.symbol == '2330'].trade_date.iloc[290]
    data.loc[(data.symbol == '2330') & (data.trade_date >= day), 'close'] *= 2
    panel = make_risk_panel(data)
    result = evaluate_risk_pilot(panel, '2025-02-03')
    screened = evaluate_risk_pilot(panel, '2025-02-03', exclude_unverified_shocks=True)
    assert result['publication_allowed'] is False
    assert result['oos_unique_dates'] > 20
    assert result['train_latest_label_maturity'] <= '2025-02-03'
    assert set(result['oos_by_market']) == {'twse', 'tpex'}
    assert result['oos_by_month']
    assert screened['oos_rows'] < result['oos_rows']
    assert screened['sensitivity_exclude_unverified_gt35pct_shocks']
    for month in result['oos_by_month']:
        assert result['oos_by_month'][month]['metrics']['ridge_challenger']['mae'] >= 0
