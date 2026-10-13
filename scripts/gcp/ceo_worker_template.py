"""Prepare a dedicated bounded CEO Job from the existing Mart template.

This command writes a private local template only. Creation and Job-scoped IAM
remain blocked until the plan is explicitly approved; it never changes traffic.
"""
from copy import deepcopy
import argparse
import json
import os
from pathlib import Path
import re

PROJECT = 'gen-lang-client-0593591102'
REGION = 'us-central1'
JOB = 'janus-ceo-analysis'


def template(source, image, sha):
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise ValueError('full tested SHA required')
    if not re.fullmatch(r'ghcr.io/tommylin15/janus-intelligence-mart@sha256:[0-9a-f]{64}', image):
        raise ValueError('public immutable CEO digest required')
    if source.get('name') != f'projects/{PROJECT}/locations/{REGION}/jobs/janus-intelligence-mart':
        raise ValueError('existing dev Mart required')
    result = deepcopy(source['template'])
    task = result['template']
    if len(task['containers']) != 1:
        raise ValueError('single Mart container required')
    if task['serviceAccount'] != f'intelligence-mart@{PROJECT}.iam.gserviceaccount.com':
        raise ValueError('existing Mart identity required')
    container = task['containers'][0]
    container['name'] = 'ceo'
    container['image'] = image
    container['resources'] = {'limits': {'cpu': '1', 'memory': '1Gi'}}
    container['command'], container['args'] = ['python'], ['-m', 'intelligence_mart.__main__']
    overrides = {'MART_OPERATION': 'ceo-request', 'MART_CEO_GEMINI_ONLY': 'true',
                 'MART_GEMINI_MODEL': 'gemini-3.5-flash-lite', 'MART_GEMINI_FREE_TIER_CONFIRMED': 'true',
                 'MART_CEO_GEMINI_VIA_OMNIAGENT': 'true',
                 # Pilot Gateway is 0%-traffic. Never point at disabled formal serving URL.
                 'MART_OMNI_GATEWAY_URL': 'https://gemini-p0v-b03e5f55---omniagent-agent-gateway-2oo7qbkd5q-uc.a.run.app',
                 'GCP_PROJECT_ID': PROJECT, 'MART_CODEX_TIMEOUT_SECONDS': '120', 'MART_CODEX_MAX_ATTEMPTS': '1'}
    container['env'] = [e for e in container.get('env', []) if e['name'] not in overrides and
                        e['name'] not in {'CEO_REQUEST_ID', 'MART_CODEX_AUTH_SECRET', 'MART_CODEX_AUTH_JSON', 'CODEX_ACCESS_TOKEN'}]
    container['env'] += [{'name': key, 'value': value} for key, value in overrides.items()]
    task['timeout'], task['maxRetries'] = '480s', 0
    result['taskCount'], result['parallelism'] = 1, 1
    return {'name': f'projects/{PROJECT}/locations/{REGION}/jobs/{JOB}',
            'labels': {'janus-component': 'manual-ceo', 'janus-git-sha': sha}, 'template': result}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', required=True)
    parser.add_argument('--sha', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from ghcr_jobs_rollout import job
    value = template(job('janus-intelligence-mart'), args.image, args.sha)
    args.output.write_text(json.dumps(value), encoding='utf-8')
    os.chmod(args.output, 0o600)
    print(json.dumps({'status': 'prepared_only', 'job': JOB, 'cpu': '1', 'memory': '1Gi',
                      'timeout_seconds': 480, 'max_retries': 0, 'scheduler': False,
                      'cloud_mutation': False, 'approval_required': True}))


if __name__ == '__main__':
    main()
