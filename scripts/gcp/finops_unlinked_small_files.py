"""User-approved old, unlinked Core small-object cleanup; no row/manifest retirement."""
from datetime import datetime, timedelta, timezone
import json
import inspect
import os
import re
import traceback
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from ingestion_core.stage import GcsObjectStore
from ingestion_core.iceberg_maintenance import maintain_financials
from ingestion_core.retention import clean_orphans

BUCKET='gen-lang-client-0593591102-dev-core'
COMPONENT='finops-unlinked-small-files'


class SmallStore(GcsObjectStore):
    def __init__(self, entries, now, prefixes):
        super().__init__(BUCKET, release_event_based_hold=True)
        self.initial={x['name']:x for x in entries}
        self.now=now
        self.prefixes=tuple(prefixes)
        self.deleted=[]
        self.delete_attempt=None

    def objects(self,prefix):
        items=super().objects(prefix)
        return tuple(x for x in items if int(x['size'])<1024*1024) if prefix.startswith('warehouse/') else items

    def delete(self,name,*,generation=None):
        item=self.initial.get(name)
        if (not item or generation!=item['generation'] or not name.startswith(self.prefixes)
                or not name.endswith(('.metadata.json','.avro','.parquet'))
                or int(item['size'])>=1024*1024
                or self.now-datetime.fromisoformat(item['updated'].replace('Z','+00:00'))<=timedelta(days=7)):
            raise ValueError('unlinked_small_file_delete_outside_approved_scope')
        if len(self.deleted)>=9000: raise RuntimeError('unlinked_cleanup_object_budget')
        self.delete_attempt={"name":name,"generation":generation}
        endpoint = ('https://storage.googleapis.com/storage/v1/b/' + BUCKET + '/o/'
                    + quote(name, safe='') + '?generation=' + quote(generation, safe=''))
        headers = {'Authorization': 'Bearer ' + self._token()}
        super().delete(name, generation=generation)
        try:
            with urlopen(Request(endpoint, headers=headers), timeout=self.timeout_seconds):
                raise RuntimeError('deleted_generation_still_exists')
        except HTTPError as error:
            if error.code != 404:
                raise
        self.deleted.append({'name':name,'generation':generation,'bytes':int(item['size'])})


def cleanup(core,store,now,tables):
    identifiers=['ops.batch_events_v1']+[core.table_identifier(key) for key in core.IDENTIFIERS]
    # Current-only snapshot policy; this operation never removes canonical rows.
    for identifier in identifiers:
        if not core.catalog.table_exists(identifier): continue
        report={'table':identifier,'phase':'PREFLIGHT'}
        tables.append(report)
        report['preflight']=maintain_financials(core=core,store=store,apply=False,now=now,identifier=identifier)
        report['orphan_preflight']=clean_orphans(core,store,identifier,apply=False,now=now)
    for report in tables:
        identifier=report['table']
        report['phase']='APPLYING'
        result=maintain_financials(core=core,store=store,apply=True,now=now,identifier=identifier)
        report['maintenance']=result
        report['orphans']=clean_orphans(core,store,identifier,apply=True,now=now)
        table=core.catalog.load_table(identifier)
        if result['row_count'] and table.scan(limit=1).to_arrow().num_rows!=1:
            raise RuntimeError('current_snapshot_readback_failed')
        report['phase']='READBACK_PASS'


def main():
    if os.environ.get('JANUS_APPROVED_UNLINKED_CLEANUP')!='true' or os.environ.get('CORE_BUCKET')!=BUCKET:
        raise ValueError('explicit_unlinked_cleanup_authorization_required')
    from ingestion_core.__main__ import _iceberg_core
    from ingestion_core import batch_controller
    core=None
    now=datetime.now(timezone.utc)
    raw=GcsObjectStore(BUCKET)
    store=None
    result={'component':COMPONENT,'mode':'user-approved-unlinked-small-files',
            'status':'PARTIAL','core_rows_deleted':0,'core_manifests_deleted':0,
            'iceberg_audit_disabled':not hasattr(batch_controller,'export_events') and '_iceberg_core' not in inspect.getsource(batch_controller.run),
            'private_changes':0,'deletion_fence_published':False,
            'reference_policy':'2026-10-18 user approved current-only snapshots; historical references grant no retention',
            'small_file_bytes_exclusive':1024*1024,'minimum_age_days':7}
    try:
        result['stage']='CORE_CATALOG_READ'
        core=_iceberg_core(BUCKET,read_only=True)
        with core.mutation_lock():
            result['stage']='METADATA_TOKEN_READ'
            raw._token()
            result['stage']='CORE_INVENTORY_READ'
            inventory=raw.bounded_inventory(max_pages=10)
            if not inventory.get('complete') or inventory['visible_objects']>9000 or inventory['visible_bytes']>256*1024*1024:
                raise RuntimeError('unlinked_cleanup_inventory_budget')
            entries=raw.objects('')
            if len(entries)>9000 or sum(int(x['size']) for x in entries)>256*1024*1024:
                raise RuntimeError('unlinked_cleanup_inventory_changed')
            prefixes=['warehouse/'+core.table_identifier(key).split('.')[1]+'/' for key in core.IDENTIFIERS]
            store=SmallStore(entries,now,prefixes+['warehouse/batch_events_v1/'])
            result['before']={'objects':len(entries),'bytes':sum(int(x['size']) for x in entries),
                              'under_1mib':sum(int(x['size'])<1024*1024 for x in entries)}
            result['tables']=[]
            result['stage']='UNLINKED_CLEANUP'
            cleanup(core,store,now,result['tables'])
            result['stage']='GENERATION_READBACK'
            remaining=raw.objects('')
            current={x['name']:x['generation'] for x in remaining}
            if any(current.get(x['name'])==x['generation'] for x in store.deleted):
                raise RuntimeError('deleted_generation_still_visible')
            result['after']={'objects':len(remaining),'bytes':sum(int(x['size']) for x in remaining),
                             'under_1mib':sum(int(x['size'])<1024*1024 for x in remaining)}
            result['status']='PASS' if result['after']['under_1mib']<result['before']['under_1mib'] else 'NO_REDUCTION'
            result['stage']='COMPLETE'
    except Exception as error:
        frame=traceback.extract_tb(error.__traceback__)[-1]
        result.update(error_type=type(error).__name__,http_status=error.code if isinstance(error,HTTPError) else None,
                      error_location=Path(frame.filename).name+':'+str(frame.lineno),
                      error_frames=[Path(x.filename).name+':'+x.name+':'+str(x.lineno) for x in traceback.extract_tb(error.__traceback__)],
                      delete_attempt=store.delete_attempt if store else None)
        if isinstance(error,HTTPError):
            try:
                message=json.loads(error.read(16384)).get('error',{})
                safe_message=re.sub(r'[\w.+-]+@[\w.-]+','<identity>',str(message.get('message',''))[:512])
                safe_message=re.sub(r'(?i)(bearer\s+)\S+',r'\1<redacted>',safe_message)
                result['http_message']=re.sub(r'(?i)(access_token[=: ]+)\S+',r'\1<redacted>',safe_message)
                result['http_reasons']=[x['reason'] for x in message.get('errors',[]) if re.fullmatch(r'[A-Za-z_]{1,80}',x.get('reason',''))]
                result['denied_storage_permissions']=sorted(set(re.findall(r'storage\.[a-zA-Z]+\.[a-zA-Z]+',message.get('message',''))))
            except Exception: pass
    finally:
        try:
            if core is not None: core.close()
        except Exception:
            result.update(status='PARTIAL',close_error=True)
        deleted=store.deleted if store else []
        result.update(deleted_objects=len(deleted),deleted_bytes=sum(x['bytes'] for x in deleted),
                      generation_chunks=(len(deleted)+99)//100)
        for index in range(0,len(deleted),100):
            print(json.dumps({'component':COMPONENT+'-generations','chunk':index//100,'objects':deleted[index:index+100]},sort_keys=True),flush=True)
        print(json.dumps(result,sort_keys=True),flush=True)
    # Prevent automatic Cloud Run retries after partial deletes; the caller
    # requires the structured business status to be PASS independently.
    return 0


if __name__=='__main__': raise SystemExit(main())
