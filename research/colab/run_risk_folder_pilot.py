"""Run existing Janus Risk baseline/challenger directly on month-directory inputs."""
from __future__ import annotations

import argparse
import json
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
    panel = make_risk_panel(prices)
    result = evaluate_risk_pilot(panel, args.cutoff)
    result['sources'] = sources
    result['historical_survivorship'] = 'CURRENT_MASTER_ONLY_NOT_PIT'
    result['publication_allowed'] = False
    Path(args.result).write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'oos_rows': result['oos_rows'],
                      'candidate_beats_baseline_mae': result['candidate_beats_baseline_mae']}))


if __name__ == '__main__':
    main()