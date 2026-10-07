"""Bounded dev probe/row canary; credentials remain in memory."""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'jobs/intelligence-mart'))
from google.cloud import bigquery
from google.oauth2.credentials import Credentials
from pyiceberg.io.pyarrow import PyArrowFileIO
from pyiceberg.table import StaticTable
from pyiceberg.expressions import And, In, GreaterThanOrEqual, LessThan, LessThanOrEqual
from intelligence_mart.bigquery_reader import BigQueryAnalyticsReader

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--manifest', type=Path, required=True)
parser.add_argument('--config', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--execute', action='store_true')
args = parser.parse_args()
config = json.loads(args.config.read_text())
if config['project'] != 'gen-lang-client-0593591102' or config['location'] != 'us-central1':
    raise ValueError('only existing authorized dev project/region supported')
raw = args.manifest.read_bytes()
if hashlib.sha256(raw).hexdigest() != config['manifest_sha256']:
    raise ValueError('immutable manifest hash mismatch')
manifest = json.loads(raw)
token = subprocess.run(['gcloud.cmd' if sys.platform == 'win32' else 'gcloud', 'auth', 'print-access-token'],
                       capture_output=True, text=True, check=True).stdout.strip()
properties = {'gcs.oauth2.token': token, 'gcs.oauth2.token-expires-at': str(int((time.time() + 3000) * 1000))}
io = PyArrowFileIO(properties)
client = bigquery.Client(project=config['project'], credentials=Credentials(token), location='us-central1')
reader = BigQueryAnalyticsReader(client, SimpleNamespace(load_table=lambda _: SimpleNamespace(io=io)),
    config['tables'], location='us-central1', maximum_bytes_billed=config['maximum_bytes_billed'], date_bounds=config['date_bounds'])
def encode(row):
    return json.dumps(row, sort_keys=True, default=lambda v: v.isoformat() if isinstance(v, (date, datetime)) else str(v))
try:
    result = reader.probe(manifest, tuple(config['symbols']), core_snapshot_id=config['core_snapshot_id'], row_limit=config['row_limit'],
        table_scope=tuple(config['tables']), dry_run=not args.execute)
    evidence = result.telemetry
    evidence['comparison'] = {}
    for identifier in (config['tables'] if args.execute else []):
        fence = manifest['iceberg_tables'][identifier]
        table = StaticTable.from_metadata(fence['metadata_location'], properties=properties)
        column, start, end = config['date_bounds'][identifier]
        if column == 'trade_date':
            predicate = And(GreaterThanOrEqual(column, start), LessThanOrEqual(column, end))
        else:
            predicate = And(GreaterThanOrEqual(column, start + 'T00:00:00+00:00'),
                LessThan(column, (date.fromisoformat(end) + timedelta(days=1)).isoformat() + 'T00:00:00+00:00'))
        if config['symbols'] and 'symbol' in [f.name for f in table.schema().fields]:
            predicate = And(predicate, In('symbol', config['symbols']))
        started = time.monotonic()
        reference = table.scan(snapshot_id=fence['snapshot_id'], row_filter=predicate, limit=config['row_limit'] + 1).to_arrow().to_pylist()
        dataset = identifier.split('.')[1][:-3].replace('_', '-')
        candidate = [{k: v for k, v in row.items() if not k.startswith('__')} for row in result.datasets[dataset]]
        match = Counter(map(encode, reference)) == Counter(map(encode, candidate))
        evidence['comparison'][dataset] = {'reference_rows': len(reference), 'bigquery_rows': len(candidate),
            'row_multiset_equal': match, 'pyiceberg_elapsed_seconds': time.monotonic() - started,
            'output_hash': hashlib.sha256('\n'.join(sorted(map(encode, candidate))).encode()).hexdigest(),
            'null_cells': sum(v is None for row in candidate for v in row.values())}
        if not match:
            evidence['status'] = 'fidelity-failed'
            args.output.write_text(json.dumps(evidence, indent=2))
            raise ValueError('row fidelity mismatch: ' + dataset)
    evidence['status'] = 'bounded-live-pass' if args.execute else 'dry-run-only'
    args.output.write_text(json.dumps(evidence, indent=2))
    print(json.dumps({'status': evidence['status'], 'comparison': evidence['comparison'],
        'scan': {k: {n: v[n] for n in ('processed_bytes', 'billed_bytes', 'elapsed_seconds')} for k, v in evidence['scan_evidence'].items()}}))
finally:
    client.close()
