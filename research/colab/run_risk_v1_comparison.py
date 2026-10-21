"""Colab-only Risk v0/v1 matched-sample OOS on 21 immutable Drive months.

Usage: python research/colab/run_risk_v1_comparison.py --result PATH \
    /content/drive/MyDrive/給ai專用/janusChatGPT/資料源/2025-*/ \
    /content/drive/MyDrive/給ai專用/janusChatGPT/資料源/2026-*/
Never promotes, uploads to GCS, or changes Janus runtime.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from monthly_folder_io import load_monthly_folders
from risk_pilot import make_risk_panel
from risk_v1 import add_v1_features, compare_risk_models


def main():
    parser = argparse.ArgumentParser(description="Risk 8-factor research-only matched OOS")
    parser.add_argument('month_folders', nargs='+', help='Existing YYYY-MM research folders')
    parser.add_argument('--cutoff', default='2026-03-31', help='Training label-maturity cutoff')
    parser.add_argument('--result', default='risk_v1_comparison.json')
    args = parser.parse_args()
    prices, sources = load_monthly_folders(args.month_folders)
    sessions = {market: sorted({
        day for source in sources for day in source['market_sessions'][market]
    }) for market in ('twse', 'tpex')}
    panel = add_v1_features(make_risk_panel(prices, market_sessions=sessions))
    report = compare_risk_models(panel, args.cutoff)
    bounds = [('2025-09-30', '2025-12-31'),
              ('2025-12-31', '2026-03-31'),
              ('2026-03-31', '2026-06-30'),
              ('2026-06-30', '2026-08-31')]
    report['fixed_diagnostic_folds'] = []
    for train_cutoff, oos_end in bounds:
        if panel['trade_date'].min() > pd.Timestamp(train_cutoff):
            continue
        if panel['trade_date'].max() < pd.Timestamp(oos_end):
            continue
        fold = compare_risk_models(panel, train_cutoff, oos_end=oos_end)
        report['fixed_diagnostic_folds'].append(fold)
    report.update({
        'official_market_sessions': {market: len(days) for market, days in sessions.items()},
        'source_provenance': sources,
        'historical_pit': 'NOT_VERIFIED',
        'corporate_actions': 'UNADJUSTED',
        'official_benchmark': 'UNAVAILABLE',
        'untouched_holdout': False,
        'publication_allowed': False,
    })
    destination = Path(args.result)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({
        'status': report['status'], 'train_rows': report['train_rows'],
        'oos_rows': report['oos_rows'],
        'v1_beats_v0_mae': report['v1_beats_v0_mae'],
        'publication_allowed': False,
    }))


if __name__ == '__main__':
    main()
