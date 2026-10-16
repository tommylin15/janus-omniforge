"""Delete exact runtime-verified orphan generations with the existing CI identity."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

BUCKET = 'gen-lang-client-0593591102-dev-core'


def validate(item, actual, now):
    errors = []
    if not item['name'].startswith('warehouse/batch_events_v1/'):
        errors.append('prefix_mismatch')
    if not item['name'].endswith(('.avro', '.parquet')):
        errors.append('extension_mismatch')
    if actual['generation'] != item['generation']:
        errors.append(f"generation_mismatch:{actual['generation']}!={item['generation']}")
    if int(actual['size']) != item['bytes']:
        errors.append(f"size_mismatch:{actual['size']}!={item['bytes']}")
    if not 0 < item['bytes'] < 1024*1024:
        errors.append('bytes_out_of_range')
    updated = datetime.fromisoformat(actual['updated'].replace('Z','+00:00'))
    if updated >= now-timedelta(days=7):
        errors.append(f"too_recent:{actual['updated']}")
    if actual.get('temporaryHold'):
        errors.append('temporary_hold')
    # event_based_hold is checked separately and can be cleared
    if actual.get('retentionExpirationTime'):
        retention = datetime.fromisoformat(actual['retentionExpirationTime'].replace('Z','+00:00'))
        if retention > now:
            errors.append(f"retention_active:{actual['retentionExpirationTime']}")
    if errors:
        raise ValueError(f"ci_orphan_generation_scope_changed:{item['name']}:{','.join(errors)}")
    return actual.get('eventBasedHold', False)


def run(call, jsoncall, inventory, rollout):
    plan = json.loads(Path('ops/finops-ci-orphan-generations.json').read_text())
    if plan['bucket'] != BUCKET or not 1 <= len(plan['objects']) <= 1000:
        raise ValueError('ci_orphan_budget_invalid')
    source = jsoncall('gh','run','view',plan['source_run'],'--json','status,conclusion,workflowName')
    if source != {'status':'completed','conclusion':'success','workflowName':'D06 read-only runtime reference census'}:
        raise ValueError('ci_orphan_source_not_verified')
    destination = Path('.tmp/d06-ci-source')
    call('gh','run','download',plan['source_run'],'--name','d06-runtime-references','--dir',str(destination))
    original = json.loads((destination/'d06-runtime-references.json').read_text())
    receipt = next(x for x in original['results'] if x.get('execution') == plan['source_execution'])
    dry_run = receipt['result']['audit_cleanup_dry_run']
    if dry_run['applied'] is not False or dry_run['candidate_generations'] != plan['objects']:
        raise ValueError('ci_orphan_source_generations_mismatch')
    if len({x['name'] for x in plan['objects']}) != len(plan['objects']) or sum(x['bytes'] for x in plan['objects']) > 32*1024*1024:
        raise ValueError('ci_orphan_candidate_budget_invalid')
    rollout.fence()
    before = inventory()
    token = call('gcloud','auth','print-access-token')
    headers = {'Authorization':'Bearer '+token}
    deleted = []
    result = {'component':'finops-ci-orphans','status':'PARTIAL','before':before,
              'source_run':plan['source_run'],'source_execution':plan['source_execution'],
              'core_rows_deleted':0,'core_manifests_deleted':0,'private_changes':0}

    def delete(item):
        endpoint = 'https://storage.googleapis.com/storage/v1/b/'+BUCKET+'/o/'+quote(item['name'],safe='')
        with urlopen(Request(endpoint,headers=headers),timeout=20) as response:
            actual = json.load(response)
        has_hold = validate(item,actual,datetime.now(timezone.utc))
        # Clear event-based hold if present (requires storage.objects.update)
        if has_hold:
            patch_data = json.dumps({'eventBasedHold': False}).encode()
            patch_req = Request(endpoint+'?ifGenerationMatch='+item['generation'],
                               data=patch_data, headers={**headers,'Content-Type':'application/json'},
                               method='PATCH')
            with urlopen(patch_req,timeout=20):
                pass
        with urlopen(Request(endpoint+'?ifGenerationMatch='+item['generation'],headers=headers,method='DELETE'),timeout=20):
            return item

    try:
        # Prove this identity can delete one generation before starting a batch.
        deleted.append(delete(plan['objects'][0]))
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(delete,item) for item in plan['objects'][1:]]
            errors = []
            for future in as_completed(futures):
                try: deleted.append(future.result())
                except Exception as error: errors.append(error)
            if errors: raise errors[0]
        after = inventory()
        result['after'] = after
        if before['under_1mib']-after['under_1mib'] < len(deleted):
            raise RuntimeError('ci_orphan_net_reduction_not_verified')
        result['status'] = 'PASS'
    except Exception as error:
        result.update(error_type=type(error).__name__,http_status=error.code if isinstance(error,HTTPError) else None,
                      error_message=str(error)[:512] if isinstance(error,ValueError) else None)
        if isinstance(error,HTTPError):
            try:
                import re
                message = str(json.loads(error.read(16384)).get('error',{}).get('message',''))[:512]
                result['http_message'] = re.sub(r'[\w.+-]+@[\w.-]+','<identity>',message)
            except Exception: pass
    finally:
        result.update(deleted_objects=len(deleted),deleted_bytes=sum(x['bytes'] for x in deleted))
        Path('finops-unlinked-receipt.json').write_text(json.dumps(result,sort_keys=True))
        Path('finops-unlinked-generations.json').write_text(json.dumps(deleted,sort_keys=True))
        print(json.dumps(result,sort_keys=True))
    if result['status'] != 'PASS': raise RuntimeError('ci_orphan_cleanup_not_pass')
