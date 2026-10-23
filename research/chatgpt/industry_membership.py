"""PIT-aware historical stock-to-industry preflight for ChatGPT-side labeling.

Research-only: never infers historical memberships from current lists, never
converts sector index prices into security membership, and never publishes X.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

RELATIVE_DIR = Path('derived/factor_inputs/industry_membership')
FILE_NAME = 'industry_membership.parquet'
SCHEMA_VERSION = 'industry-membership-pit-v1'
REQUIRED = ('market', 'symbol', 'classification_system', 'industry_id',
            'membership_type', 'valid_from', 'valid_to', 'published_at',
            'source_id', 'source_url', 'source_sha256', 'evidence_status')
MEMBERSHIP_TYPES = {'primary', 'secondary', 'theme', 'supply_chain'}
OFFICIAL_SYSTEMS = {'TWSE_OFFICIAL', 'TPEX_OFFICIAL'}


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def _base(status: str, *, reason: str, path: str = '') -> dict:
    return {
        'contract': SCHEMA_VERSION, 'preflight_code_sha256': _sha(Path(__file__)),
        'status': status, 'reason': reason,
        'input_file': path, 'rows': 0, 'usable_primary_rows': 0,
        'primary_matched_stock_days': 0, 'total_stock_days': 0,
        'unmatched_stock_days': 0, 'overlapping_secondary_rows': 0,
        'industry_features_in_model_x': False,
        'industry_index_crosswalk': 'NOT_VERIFIED',
        'source_authorization': 'NOT_VERIFIED',
        'historical_pit': 'NOT_VERIFIED',
        'asof_cutoff': 'BEFORE_LOCAL_TRADE_DATE_START_ASIA_TAIPEI',
        'allow_overlapping_secondary_and_theme': True,
        'publication_allowed': False,
    }


def _check_table(df: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(set(REQUIRED) - set(df.columns))
    if missing:
        raise ValueError('MISSING_COLUMNS:' + ','.join(missing))
    if df.empty:
        raise ValueError('EMPTY_MEMBERSHIP')
    z = df[list(REQUIRED)].copy()
    for k in ('market', 'symbol', 'classification_system', 'industry_id',
              'membership_type', 'source_id', 'source_url', 'source_sha256', 'evidence_status'):
        if z[k].isna().any():
            raise ValueError('NULL_REQUIRED:' + k)
        z[k] = z[k].astype(str).str.strip()
        if z[k].eq('').any():
            raise ValueError('EMPTY_REQUIRED:' + k)
    z['market'] = z.market.str.lower()
    if not z.market.isin(('twse', 'tpex')).all():
        raise ValueError('UNRECOGNIZED_MARKET')
    if not z.symbol.str.fullmatch(r'[1-9][0-9]{3}').all():
        raise ValueError('UNRECOGNIZED_ORDINARY_STOCK_CODE')
    if not z.membership_type.isin(MEMBERSHIP_TYPES).all():
        raise ValueError('UNRECOGNIZED_MEMBERSHIP_TYPE')
    if not z.evidence_status.isin(('VERIFIED', 'UNVERIFIED', 'UNKNOWN')).all():
        raise ValueError('UNRECOGNIZED_EVIDENCE_STATUS')
    if not z.source_url.str.startswith('https://').all():
        raise ValueError('SOURCE_URL_REQUIRED')
    if not z.source_sha256.str.fullmatch(r'[0-9a-fA-F]{64}').all():
        raise ValueError('SOURCE_SHA256_REQUIRED')
    primary = z.membership_type.eq('primary')
    if (primary & ~z.classification_system.isin(OFFICIAL_SYSTEMS)).any():
        raise ValueError('PRIMARY_REQUIRES_OFFICIAL_CLASSIFICATION_SYSTEM')
    if (primary & ((z.market.eq('twse') & z.classification_system.ne('TWSE_OFFICIAL')) |
                  (z.market.eq('tpex') & z.classification_system.ne('TPEX_OFFICIAL')))).any():
        raise ValueError('PRIMARY_OFFICIAL_MARKET_MISMATCH')
    for col in ('valid_from', 'valid_to'):
        # Exclusive valid_to; missing valid_to is an open interval.
        if col == 'valid_from' and z[col].isna().any():
            raise ValueError('VALID_FROM_REQUIRED')
        s = z[col].astype('string')
        good = s.isna() | s.str.fullmatch(r'\d{4}-\d{2}-\d{2}').fillna(False)
        if not good.all():
            raise ValueError('INVALID_DATE_FORMAT:' + col)
        z[col] = pd.to_datetime(z[col], format='%Y-%m-%d', errors='coerce')
        if (s.notna() & z[col].isna()).any():
            raise ValueError('INVALID_DATE_VALUE:' + col)
    if (z.valid_to.notna() & z.valid_to.le(z.valid_from)).any():
        raise ValueError('INVALID_EFFECTIVE_INTERVAL')
    # Timestamps are source-publication evidence, not local fetched_at.
    # An unqualified date or timezone-naive timestamp cannot establish PIT.
    evidence_times = z.loc[z.evidence_status.eq('VERIFIED'), 'published_at'].dropna().astype(str)
    if not evidence_times.str.contains(r'(?:Z|[+-]\d{2}:?\d{2})$', regex=True).all():
        raise ValueError('PUBLISHED_AT_REQUIRES_EXPLICIT_TIMEZONE')
    z['published_at'] = pd.to_datetime(z.published_at, errors='coerce', utc=True, format='mixed')
    invalid_pub = z.evidence_status.eq('VERIFIED') & z.published_at.isna()
    if invalid_pub.any():
        raise ValueError('VERIFIED_REQUIRES_PUBLISHED_AT')
    if z.duplicated(['market', 'symbol', 'classification_system', 'industry_id',
                     'membership_type', 'valid_from', 'valid_to'], keep=False).any():
        raise ValueError('DUPLICATE_MEMBERSHIP_EFFECTIVE_RECORD')
    # Exactly one official PRIMARY per market/symbol at any instant. Secondary,
    # themes and supply-chain labels can overlap without forced weights.
    pp = z.loc[primary].sort_values(['market', 'symbol', 'valid_from'])
    for _, g in pp.groupby(['market', 'symbol'], sort=False):
        prev_end = None
        first = True
        for row in g.itertuples(index=False):
            if not first and (pd.isna(prev_end) or row.valid_from < prev_end):
                raise ValueError('OVERLAPPING_OFFICIAL_PRIMARY:' + row.market + ':' + row.symbol)
            prev_end = row.valid_to
            first = False
    return z


def _coverage(z: pd.DataFrame, prices: pd.DataFrame) -> dict:
    if prices is None or prices.empty:
        return {'total_stock_days': 0, 'primary_matched_stock_days': 0,
                'unmatched_stock_days': 0, 'unmatched_sample': [],
                'coverage': 'NOT_CHECKED_NO_OHLCV'}
    needed = {'market', 'symbol', 'trade_date'}
    if not needed.issubset(prices):
        raise ValueError('OHLCV_MARKET_SYMBOL_DATE_REQUIRED')
    days = prices[['market', 'symbol', 'trade_date']].copy()
    days['market'] = days.market.astype(str).str.lower()
    days['symbol'] = days.symbol.astype(str).str.strip()
    days['trade_date'] = pd.to_datetime(days.trade_date, errors='raise').dt.normalize()
    days = days.drop_duplicates().reset_index(drop=True)
    valid = z.loc[z.membership_type.eq('primary') & z.evidence_status.eq('VERIFIED')].copy()
    if valid.empty:
        matches = pd.Series(False, index=days.index)
    else:
        left = days.sort_values(['trade_date', 'market', 'symbol'])
        right = valid[['market', 'symbol', 'valid_from', 'valid_to', 'published_at']].sort_values('valid_from')
        joined = pd.merge_asof(left, right, by=['market', 'symbol'],
                               left_on='trade_date', right_on='valid_from', direction='backward')
        cutoff = joined.trade_date.dt.tz_localize('Asia/Taipei')
        good = (joined.valid_from.notna() &
                (joined.valid_to.isna() | joined.trade_date.lt(joined.valid_to)) &
                joined.published_at.lt(cutoff))
        hit_keys = pd.MultiIndex.from_frame(joined.loc[good, ['market', 'symbol', 'trade_date']])
        matches = pd.Series(pd.MultiIndex.from_frame(days).isin(hit_keys), index=days.index)
    pending = days.loc[~matches]
    return {'total_stock_days': int(len(days)),
            'primary_matched_stock_days': int(matches.sum()),
            'unmatched_stock_days': int((~matches).sum()),
            'unmatched_sample': pending.head(8).assign(trade_date=lambda t: t.trade_date.dt.strftime('%Y-%m-%d')).to_dict('records'),
            'coverage': 'COMPLETE' if matches.all() else 'PARTIAL'}


def check_industry_membership(dataset_root: Path, prices: pd.DataFrame | None = None) -> dict:
    """Mandatory pre-label check. Missing/invalid membership gates sector X, not non-sector X/Y.

    The expected manifest is research input metadata with keys: version, file,
    sha256, rows, status, historical_pit, source_authorization. Both PIT and
    authorization must explicitly be VERIFIED before any row can be trusted.
    """
    root = Path(dataset_root).expanduser().resolve()
    folder = root / RELATIVE_DIR
    infile = folder / FILE_NAME
    result = _base('MISSING', reason='HISTORICAL_MEMBERSHIP_NOT_COLLECTED', path=str(RELATIVE_DIR / FILE_NAME))
    if not infile.exists():
        return result
    manifest = folder / 'manifest.json'
    if not manifest.is_file():
        return {**result, 'status': 'BLOCKED', 'reason': 'IMMUTABLE_MEMBERSHIP_MANIFEST_MISSING'}
    try:
        if infile.is_symlink() or manifest.is_symlink():
            raise ValueError('SYMLINK_INPUT_FORBIDDEN')
        meta = json.loads(manifest.read_text(encoding='utf-8'))
        if (meta.get('version') != SCHEMA_VERSION or meta.get('file') != FILE_NAME or
                meta.get('status') != 'RESEARCH_DATA_ONLY' or meta.get('publication_allowed') is not False):
            raise ValueError('MEMBERSHIP_MANIFEST_CONTRACT')
        digest = _sha(infile)
        if digest != meta.get('sha256'):
            raise ValueError('MEMBERSHIP_HASH_MISMATCH')
        df = pd.read_parquet(infile)
        if len(df) != meta.get('rows'):
            raise ValueError('MEMBERSHIP_ROW_COUNT_MISMATCH')
        z = _check_table(df)
        # The sidecar binds each row to a reviewed source, not merely a
        # plausible-looking URL or 64-character digest in the Parquet table.
        sources = meta.get('sources')
        if not isinstance(sources, dict):
            raise ValueError('SOURCE_REGISTRY_MISSING')
        for rec in z[['source_id', 'source_url', 'source_sha256']].drop_duplicates().itertuples(index=False):
            src = sources.get(rec.source_id)
            if (not isinstance(src, dict) or src.get('url') != rec.source_url or
                    src.get('sha256') != rec.source_sha256 or
                    src.get('authorization_status') != 'VERIFIED' or
                    not str(src.get('rights_review_url', '')).startswith('https://') or
                    not {'COLLECT', 'RESEARCH_STORE', 'ML_TRAIN'}.issubset(
                        set(src.get('authorized_uses') or []))):
                raise ValueError('SOURCE_REGISTRY_NOT_AUTHORIZED_OR_MISMATCH:' + rec.source_id)
        result.update({'rows': len(z), 'input_sha256': digest,
                       'manifest_sha256': _sha(manifest),
                       'source_authorization': str(meta.get('source_authorization', 'NOT_VERIFIED')),
                       'historical_pit': str(meta.get('historical_pit', 'NOT_VERIFIED')),
                       'overlapping_secondary_rows': int(z.membership_type.ne('primary').sum()),
                       'usable_primary_rows': int((z.membership_type.eq('primary') & z.evidence_status.eq('VERIFIED')).sum())})
        if result['source_authorization'] != 'VERIFIED' or result['historical_pit'] != 'VERIFIED':
            return {**result, 'status': 'BLOCKED', 'reason': 'SOURCE_AUTHORIZATION_OR_HISTORICAL_PIT_UNVERIFIED'}
        coverage = _coverage(z, prices)
        result.update(coverage)
        if not result['usable_primary_rows']:
            return {**result, 'status': 'BLOCKED', 'reason': 'NO_VERIFIED_OFFICIAL_PRIMARY'}
        status = 'VERIFIED' if coverage['coverage'] == 'COMPLETE' else 'PARTIAL_COVERAGE'
        return {**result, 'status': status,
                'reason': 'PRIMARY_EFFECTIVE_DATED_ASOF_CONFIRMED' if status == 'VERIFIED' else 'MISSING_ASOF_PRIMARY_FOR_SOME_STOCK_DAYS'}
    except (ValueError, TypeError, KeyError, OSError, ImportError) as exc:
        return {**result, 'status': 'BLOCKED', 'reason': f'INVALID_MEMBERSHIP_INPUT:{exc}'}
