"""Read-only current-snapshot file inventory, executed inside existing dev Jobs."""
from datetime import datetime, timedelta, timezone
import json
import os


def candidates(objects, protected, bucket, now):
    cutoff = now - timedelta(days=7)
    return [item for item in objects
            if item['name'].endswith(('.metadata.json', '.avro', '.parquet'))
            and 'gs://' + bucket + '/' + item['name'] not in protected
            and datetime.fromisoformat(item['updated'].replace('Z', '+00:00')) < cutoff]


def main(layer):
    from ingestion_core.stage import GcsObjectStore
    bucket = os.environ['CORE_BUCKET' if layer == 'core' else 'MART_BUCKET']
    if bucket != 'gen-lang-client-0593591102-dev-' + layer:
        raise ValueError('snapshot_plan_bucket_invalid')
    if layer == 'core':
        from ingestion_core.__main__ import _iceberg_core
        core = _iceberg_core(bucket, read_only=True)
        identifiers = ['ops.batch_events_v1'] + [core.table_identifier(key) for key in core.IDENTIFIERS]
    else:
        from packages.postgres_bundle import load_postgres_bundle
        from intelligence_mart.storage import MartMaintenanceStore, sql_catalog_from_environment
        load_postgres_bundle('JANUS_MART_POSTGRES_BUNDLE', {'CATALOG_DB_PASSWORD': ('mart_catalog_password', 'catalog_password')})
        core = MartMaintenanceStore(sql_catalog_from_environment(), 'gs://' + bucket + '/warehouse')
        identifiers = [core.table_identifier(key) for key in core.IDENTIFIERS]
    store = GcsObjectStore(bucket)
    now = datetime.now(timezone.utc)
    result = {'source': 'current_only_snapshot_plan', 'data_writes': 0, 'core_snapshot_ids': [],
              'layer': layer, 'observed_at': now.isoformat(), 'tables': [],
              'minimum_age_days': 7, 'holds_and_delete_permission_verified': False}
    from urllib.request import Request, urlopen
    endpoint = ('https://storage.googleapis.com/storage/v1/b/' + bucket
                + '/iam/testPermissions?permissions=storage.objects.delete&permissions=storage.objects.update')
    with urlopen(Request(endpoint, headers={'Authorization': 'Bearer ' + store._token()}), timeout=20) as response:
        result['runtime_cleanup_permissions'] = sorted(json.load(response).get('permissions', []))
    pointers = {}
    visible_count = visible_bytes = 0
    try:
        for identifier in identifiers:
            if not core.catalog.table_exists(identifier):
                continue
            table = core.catalog.load_table(identifier)
            pointers[identifier] = table.metadata_location
            protected = {table.metadata_location} | {entry.metadata_file for entry in table.metadata.metadata_log}
            current = table.current_snapshot()
            if current:
                protected.add(current.manifest_list)
                for manifest in current.manifests(table.io):
                    protected.add(manifest.manifest_path)
                    protected.update(entry.data_file.file_path for entry in manifest.fetch_manifest_entry(table.io, discard_deleted=True))
            objects = store.objects('warehouse/' + identifier.split('.')[1] + '/')
            visible_count += len(objects)
            visible_bytes += sum(int(item['size']) for item in objects)
            if visible_count > 25000 or visible_bytes > 1024 ** 3:
                raise RuntimeError('snapshot_plan_inventory_budget')
            eligible = candidates(objects, protected, bucket, now)
            small = [item for item in eligible if int(item['size']) < 1024 ** 2]
            result['tables'].append({'table': identifier,
                'snapshots_to_expire': sum(s.snapshot_id != (current.snapshot_id if current else None) for s in table.snapshots()),
                'eligible_objects': len(eligible), 'eligible_bytes': sum(int(item['size']) for item in eligible),
                'under_1mib_objects': len(small), 'under_1mib_bytes': sum(int(item['size']) for item in small)})
        for identifier, pointer in pointers.items():
            if core.catalog.load_table(identifier).metadata_location != pointer:
                raise RuntimeError('snapshot_plan_catalog_changed')
        for key in ('eligible_objects', 'eligible_bytes', 'under_1mib_objects', 'under_1mib_bytes', 'snapshots_to_expire'):
            result[key] = sum(table[key] for table in result['tables'])
        result.update(status='OBSERVED', visible_objects=visible_count, visible_bytes=visible_bytes)
        print('D06_REFERENCE_READBACK=' + json.dumps(result, sort_keys=True), flush=True)
    finally:
        core.close()
