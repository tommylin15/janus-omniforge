"""Run existing Janus Risk baseline/challenger directly on month-directory inputs."""
from __future__ import annotations

import argparse
import json
import pandas as pd
from pathlib import Path

from monthly_folder_io import load_monthly_folders
from risk_pilot import make_risk_panel, evaluate_risk_pilot


def main() -> None:
    parser = argparse.ArgumentParser(description='Research-only Risk OOS on immutable Drive monthly folders')
    parser.add_argument('month_folders', nargs='+', help='YYYY-MM folders with a single archived revision')
    parser.add_argument('--cutoff', required=True, help='train label-maturity cutoff YYYY-MM-DD')
    parser.add_argument('--result', default='risk_pilot_oos.json')
    args = parser.parse_args()
    prices, sources = load_monthly_folders(args.month_folders)
    # Manifest evidence is the calendar authority; no next-observed-day
    # bridging for suspended stocks or absent source days.
    market_sessions = {
        market: sorted({date for source in sources for date in source['market_sessions'][market]})
        for market in ('twse', 'tpex')
    }
    panel = make_risk_panel(prices, market_sessions=market_sessions)
    result = evaluate_risk_pilot(panel, args.cutoff)
    screened = evaluate_risk_pilot(panel, args.cutoff, exclude_unverified_shocks=True)
    result['sensitivity_unverified_shock_screen'] = {
        'excluded_train_rows': result['train_rows'] - screened['train_rows'],
        'excluded_oos_rows': result['oos_rows'] - screened['oos_rows'],
        'metrics': screened['metrics'],
        'oos_by_market': screened['oos_by_market'],
        'oos_by_month': screened['oos_by_month'],
        'publication_allowed': False,
    }
    result['official_market_sessions'] = {market: len(dates) for market, dates in market_sessions.items()}
    # Diagnostic walk-forward quarters: fixed cutoffs, no test-period tuning.
    # These are retrospective diagnostics, not a never-observed holdout.
    fold_bounds = [('2025-09-30', '2025-12-31'),
                   ('2025-12-31', '2026-03-31'),
                   ('2026-03-31', '2026-06-30'),
                   ('2026-06-30', '2026-08-31')]
    result['walk_forward_diagnostic_folds'] = []
    for cutoff, end in fold_bounds:
        if panel['trade_date'].min() > pd.Timestamp(cutoff) or panel['trade_date'].max() < pd.Timestamp(end):
            continue
        fold = evaluate_risk_pilot(panel, cutoff, oos_end=end)
        result['walk_forward_diagnostic_folds'].append({
            'train_cutoff': fold['cutoff'], 'oos_end': end,
            'train_rows': fold['train_rows'], 'oos_rows': fold['oos_rows'],
            'oos_unique_dates': fold['oos_unique_dates'],
            'train_latest_label_maturity': fold['train_latest_label_maturity'],
            'oos_latest_label_maturity': fold['oos_latest_label_maturity'],
            'metrics': fold['metrics'], 'candidate_beats_baseline_mae': fold['candidate_beats_baseline_mae']})
    result['sources'] = sources
    result['historical_survivorship'] = 'CURRENT_MASTER_ONLY_NOT_PIT'
    result['publication_allowed'] = False
    Path(args.result).write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'oos_rows': result['oos_rows'],
                      'candidate_beats_baseline_mae': result['candidate_beats_baseline_mae']}))


if __name__ == '__main__':
    main()