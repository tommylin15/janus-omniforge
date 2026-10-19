"""Bounded, explicitly requested Yahoo single-quarter EPS supplement."""
from calendar import monthrange
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re

SYMBOLS = ('1513', '2327', '2382', '3231', '3711', '5876')
SOURCE = 'yahoo-finance'


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


def parse_eps(raw: bytes, symbol: str, *, year: int, quarter: int, received_at: str):
    """Read a displayed provider value; never calculate EPS or infer publication."""
    if symbol not in SYMBOLS or (year, quarter) != (2025, 4):
        raise ValueError('unapproved_eps_scope')
    return parse_reported_quarter(raw, symbol, year=year, quarter=quarter, received_at=received_at)


def parse_reported_quarter(raw: bytes, symbol: str, *, year: int, quarter: int,
                           received_at: str, suffix: str = 'TW'):
    if not re.fullmatch(r'[1-9][0-9]{3}', symbol) or suffix not in {'TW', 'TWO'} or not 1 <= quarter <= 4:
        raise ValueError('invalid_eps_identity')
    html = raw.decode('utf-8')
    title = re.search(r'<title[^>]*>(.*?)</title>', html, re.S)
    if not title or f'({symbol}.{suffix})' not in title[1] or '每股盈餘' not in title[1]:
        raise ValueError('yahoo_stock_identity_mismatch')
    parser = _Text()
    parser.feed(html)
    text = ' '.join(parser.parts)
    section = text.split('單季每股盈餘', 1)
    if len(section) != 2 or '年度/季別' not in section[1]:
        raise ValueError('missing_single_quarter_table')
    table = section[1].split('單季每股盈餘', 1)[0]
    matches = re.findall(rf'{year}\s+Q{quarter}\s+(-?\s*\d[\d,]*(?:\.\d+)?)', table)
    if len(matches) != 1:
        raise ValueError('missing_or_ambiguous_quarter')
    try:
        amount = Decimal(matches[0].replace(' ', '').replace(',', ''))
        received = datetime.fromisoformat(received_at.replace('Z', '+00:00'))
        if not amount.is_finite() or received.tzinfo is None:
            raise ValueError('invalid_eps_or_receipt')
    except (InvalidOperation, TypeError) as error:
        raise ValueError('invalid_eps_or_receipt') from error
    return {
        'symbol': symbol, 'fiscal_year': year, 'fiscal_quarter': quarter,
        'fiscal_period_end': date(year, quarter * 3, monthrange(year, quarter * 3)[1]).isoformat(),
        'statement_type': 'income', 'metric': 'eps_single_quarter',
        'period_basis': 'single_quarter', 'unit': 'TWD_per_share', 'currency': 'TWD',
        'value': str(amount), 'source_id': SOURCE,
        'availability_at': received.isoformat(), 'observed_at': received.isoformat(),
        'published_at': None, 'publication_time_authoritative': False,
        'availability_basis': 'source_response_receipt',
        'report_scope': 'provider_reported', 'share_basis_status': 'provider_reported_unspecified',
        'historical_publication_status': 'unknown',
        'financial_feature_version': 'yahoo-reported-single-quarter-v1',
        'source_document_sha256': sha256(raw).hexdigest(),
    }


def run():
    import os
    from uuid import uuid4
    from packages.provenance import Provenance
    from pyiceberg.expressions import And, EqualTo
    from .__main__ import _control_plane, _iceberg_core
    from .control import ExecutionStatus
    from .data_supplement import _fetch
    from .serving_projection import StockServingProjection
    from .stage import GcsObjectStore, StageWriter

    control = core = execution = None
    report = {'component': 'drl01_yahoo_eps', 'status': 'PARTIAL', 'source_id': SOURCE,
              'owner_mutation': False, 'period': '2025Q4', 'items': []}
    try:
        if os.environ.get('DRL01_YAHOO_EPS_APPROVED') != '2025Q4-six-symbols':
            raise ValueError('explicit_supplement_request_required')
        control = _control_plane()
        if not control.source_is_approved(SOURCE):
            raise ValueError('source_not_approved')
        with control.connection.cursor() as cur:
            cur.execute("SELECT symbol FROM control.stock_master WHERE enabled AND market='TWSE' AND symbol=ANY(%s)", (list(SYMBOLS),))
            if {row[0] for row in cur.fetchall()} != set(SYMBOLS):
                raise ValueError('current_stock_scope_mismatch')
        writer = StageWriter(GcsObjectStore(os.environ['STAGE_BUCKET']))
        core = _iceberg_core(os.environ['CORE_BUCKET'])
        execution = control.enqueue_collection('first-batch', SYMBOLS, request_options={'operation': 'yahoo-eps-2025Q4'})
        control.transition_execution(execution.execution_id, ExecutionStatus.RUNNING)
        prepared = []
        for symbol in SYMBOLS:
            url = f'https://tw.stock.yahoo.com/quote/{symbol}.TW/eps'
            raw, _ = _fetch(url)
            received = datetime.now(timezone.utc)
            row = parse_eps(raw, symbol, year=2025, quarter=4, received_at=received.isoformat())
            provenance = Provenance(str(uuid4()), SOURCE, url, 'financials', received, None, received,
                'sha256:' + sha256(raw).hexdigest(), False,
                quality_details={'period': '2025Q4', 'source_kind': 'third_party',
                                 'share_basis': 'provider_reported_unspecified'})
            staged = writer.write_raw(payload=raw, media_type='text/html', extension='html',
                execution_id=execution.execution_id, provenance=provenance, execution_scoped=True)
            prepared.append((row, staged))
        migration = Path('/app/infra/postgres/migrations/065_yahoo_eps_serving.sql')
        with core.mutation_lock(), control.connection.cursor() as cur:
            cur.execute(migration.read_text())
        projection = StockServingProjection.from_env()
        for row, staged in prepared:
            table = core.catalog.load_table(core.table_identifier('financials'))
            snapshot = table.current_snapshot()
            scope = And(
                And(EqualTo('symbol', row['symbol']), EqualTo('source_id', SOURCE)),
                And(EqualTo('fiscal_year', 2025), EqualTo('fiscal_quarter', 4)))
            candidates = table.scan(snapshot_id=snapshot.snapshot_id, row_filter=scope, limit=50).to_arrow().to_pylist()
            persisted = max(candidates, key=lambda r: str(r['availability_at']), default=None)
            reused = (persisted is not None and persisted.get('metric') == row['metric']
                      and persisted.get('unit') == row['unit'] and persisted.get('period_basis') == row['period_basis']
                      and Decimal(str(persisted['value'])) == Decimal(row['value']))
            if not reused:
                core.write(dataset_id='financials', rows=[row], execution_id=execution.execution_id,
                    provenance_id=staged.idempotency_key, source_id=SOURCE, partition_date=date.today())
                table = core.catalog.load_table(core.table_identifier('financials'))
                snapshot = table.current_snapshot()
                persisted = max(table.scan(snapshot_id=snapshot.snapshot_id, row_filter=scope, limit=50)
                    .to_arrow().to_pylist(), key=lambda r: str(r['availability_at']))
            # Publish the persisted row, including original lineage when a retry reused it.
            if Decimal(str(persisted['value'])) != Decimal(row['value']):
                raise ValueError('persisted_eps_mismatch')
            count = projection.publish('financials', [persisted], execution_id=str(persisted['execution_id']),
                provenance_id=persisted['provenance_id'], source_id=SOURCE, core_snapshot_id=snapshot.snapshot_id)
            report['items'].append({'symbol': row['symbol'], 'value': row['value'],
                'inserted': int(not reused), 'reused': int(reused), 'published': count,
                'core_snapshot_id': str(snapshot.snapshot_id)})
        writer.mark_core_committed(execution.execution_id, stage_results=[item[1] for item in prepared])
        control.complete_collection(execution.execution_id, None, partial=False)
        report['status'] = 'PASS' if len(report['items']) == 6 and all(x['published'] == 1 for x in report['items']) else 'PARTIAL'
    except Exception as error:
        report['error_type'] = type(error).__name__
        if control and execution:
            control.transition_execution(execution.execution_id, ExecutionStatus.FAILED, error_code='YAHOO_EPS_SUPPLEMENT_FAILED')
        raise
    finally:
        print(json.dumps(report, sort_keys=True), flush=True)
        if core:
            core.close()
        if control:
            control.close()


if __name__ == '__main__':
    run()
