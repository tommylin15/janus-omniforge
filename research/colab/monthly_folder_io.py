"""Read Janus Colab-first immutable YYYY-MM research folders with content hashes."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from typing import Iterable

import pandas as pd


def load_monthly_folders(folders: Iterable[str | Path]) -> tuple[pd.DataFrame, list[dict]]:
    frames = []
    provenance = []
    seen_month = set()
    for directory in folders:
        directory = Path(directory)
        if not directory.is_dir() or not directory.name.startswith('20'):
            raise ValueError('expected YYYY-MM research folder')
        manifests = list(directory.glob('manifest-r[0-9]*.json'))
        if len(manifests) != 1:
            raise ValueError('select exactly one revision per monthly folder')
        manifest_path = manifests[0]
        manifest = json.loads(manifest_path.read_text('utf-8'))
        month, revision = manifest.get('month'), manifest.get('revision')
        if directory.name != month or month in seen_month:
            raise ValueError('duplicate month or mismatched directory')
        seen_month.add(month)
        if manifest.get('kind') != 'COLAB_RESEARCH_PROBE' or manifest.get('publication_allowed') is not False:
            raise ValueError('unexpected research manifest')
        declared = manifest.get('sha256', {})
        required = (f'ohlcv-{revision}.csv.gz', f'universe-{revision}.csv', f'quality-{revision}.json')
        for name in required:
            if name not in declared or '/' in name or '..' in name:
                raise ValueError('mandatory research hash absent')
            f = directory / name
            if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest() != declared[name]:
                raise ValueError(f'SHA256 mismatch: {name}')
        quality = json.loads((directory / required[2]).read_text('utf-8'))
        if quality.get('status') not in ('PROBE', 'PARTIAL', 'PASS'):
            raise ValueError('unrecognized research quality status')
        universe = pd.read_csv(directory / required[1], dtype={'symbol': 'string', 'market': 'string'})
        if universe.duplicated(['symbol']).any() or not universe['market'].isin(['twse', 'tpex']).all():
            raise ValueError('invalid research company roster')
        with gzip.open(directory / required[0], 'rb') as stream:
            df = pd.read_csv(stream, dtype={'symbol': 'string', 'market': 'string'})
        cols = {'symbol', 'market', 'trade_date', 'close', 'volume'}
        if not cols.issubset(df.columns):
            raise ValueError('research OHLCV fields missing')
        if not df.empty:
            if not df['trade_date'].str.startswith(month + '-').all():
                raise ValueError('research OHLCV dates do not match month')
            match = df.merge(universe[['symbol', 'market']], on=['symbol', 'market'], how='left', indicator=True)
            if not (match['_merge'] == 'both').all():
                raise ValueError('research row outside official company roster')
        df['source_month'] = month
        df['source_archive_sha256'] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        frames.append(df)
        provenance.append({'archive': str(directory), 'month': month,
                           'sha256': df['source_archive_sha256'].iloc[0] if not df.empty else hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                           'quality_status': quality['status'],
                           'historical_survivorship': quality.get('historical_survivorship', 'UNKNOWN')})
    if not frames:
        raise ValueError('no monthly research folders')
    combined = pd.concat(frames, ignore_index=True)
    combined['trade_date'] = pd.to_datetime(combined['trade_date'], format='%Y-%m-%d', errors='raise')
    if combined.duplicated(['symbol', 'trade_date']).any():
        raise ValueError('duplicate symbol/trade_date in monthly research data')
    return combined, provenance