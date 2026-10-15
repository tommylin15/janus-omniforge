"""Restore one exact failed rollout under a newly acquired, audited lease.

No force unlock or owner impersonation. A failed acquisition leaves Scheduler
paused; a failed restore retains the new run's lease and its recovery receipt.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

import ghcr_terminal_lease_recovery as terminal
import ghcr_jobs_rollout as rollout

RECEIPT_HASH = '1926ca5aef8cb79dcfec96c402ec3ab581674890e855ef206258fe1768f3d330'
SOURCE = '4d058c47ac62ad7328f9f7c0e9fcd4ef4f1ac7b1'
BASELINE = 'c8e8a7415be48b291a347dcc115d7834db6696a8'


def verify_receipt(raw):
    if sha256(raw).hexdigest() != RECEIPT_HASH:
        raise ValueError('failed_rollout_receipt_hash_mismatch')
    journal = json.loads(raw)
    if (journal.get('source_sha') != SOURCE or journal.get('phase') != 'RECOVERY_REQUIRED'
            or journal.get('rollback_mode') != 'reversible_ghcr'
            or journal.get('rollback_baseline_sha') != BASELINE
            or journal.get('rollback_baseline_verified') is not True
            or set(journal.get('snapshots', {})) != set(rollout.REQUIRED_JOBS)
            or set(journal.get('targets', {})) != {name for name, _ in rollout.JOB_COMPONENT}):
        raise ValueError('failed_rollout_receipt_identity_mismatch')
    return journal


def validate_paused_state(journal):
    rollout.legacy_writers()
    rollout.fence()
    schedule = rollout.scheduler()
    if schedule.get('state') != 'PAUSED' or rollout.scheduler_fingerprint(schedule) != journal['scheduler_hash']:
        raise ValueError('paused_scheduler_baseline_drift')
    for name in rollout.REQUIRED_JOBS:
        snap = journal['snapshots'][name]
        current = rollout.job(name)
        allowed = {snap['image']}
        if name in journal['targets']:
            allowed.add(journal['targets'][name])
        if rollout.image(current) not in allowed or rollout.fingerprint(current) != snap['configuration_hash']:
            raise ValueError('failed_rollout_runtime_drift')


def main():
    if os.environ.get('GITHUB_REPOSITORY') != terminal.REPO or os.environ.get('GITHUB_REF') != 'refs/heads/main':
        raise ValueError('wrong_repository_or_branch')
    request = json.loads(Path('ops/ghcr-stale-lease-recovery-request.json').read_text())
    if (request.get('intent') != 'restore-exact-abandoned-ghcr-rollout' or request.get('approved') is not True
            or request.get('owner_run') != terminal.OWNER_RUN
            or request.get('owner_source_sha') != terminal.OWNER_SHA
            or request.get('tag_sha') != terminal.TAG_SHA
            or request.get('restore_previous_images_and_scheduler') is not True):
        raise ValueError('rollout_restore_authorization_missing')
    terminal.verify_owner(terminal._gh(f'repos/{terminal.REPO}/actions/runs/{terminal.OWNER_RUN}'))
    terminal.verify_lease(terminal._gh(terminal.LEASE_REF), terminal._gh(terminal.LEASE_TAG))
    directory = Path('/tmp/abandoned-rollout-original')
    subprocess.run(['gh', 'run', 'download', str(terminal.OWNER_RUN), '--name',
                    'ghcr-jobs-rollout-receipt', '--dir', str(directory)], check=True, timeout=90)
    journal = verify_receipt((directory/'ghcr-jobs-rollout.json').read_bytes())
    before = terminal.service_identity(terminal._service())
    rollout.wait_for_terminal_executions()
    validate_paused_state(journal)
    rollout.job_update_permissions()
    for image in sorted({journal['snapshots'][name]['image'] for name, _ in rollout.JOB_COMPONENT}):
        manifest = json.loads(rollout.command(['skopeo', 'inspect', '--no-creds', 'docker://'+image]))
        if manifest.get('Digest') != image.rsplit('@', 1)[1] or manifest.get('Labels', {}).get('org.opencontainers.image.revision') != BASELINE:
            raise ValueError('rollback_registry_identity_unverified')
    # Re-check the exact abandoned owner immediately before the transfer.
    terminal.verify_owner(terminal._gh(f'repos/{terminal.REPO}/actions/runs/{terminal.OWNER_RUN}'))
    terminal.verify_lease(terminal._gh(terminal.LEASE_REF), terminal._gh(terminal.LEASE_TAG))
    validate_paused_state(journal)
    if before != terminal.service_identity(terminal._service()):
        raise ValueError('api_traffic_drift_before_restore')
    terminal._gh('-X', 'DELETE', f'repos/{terminal.REPO}/git/refs/tags/{terminal.TAG}')
    # Acquire our own normal lease. Never substitute the old run's identity.
    rollout.command(rollout.LEASE + ['acquire'])
    receipt = Path('/tmp/abandoned-rollout-recovery.json')
    def save():
        receipt.write_text(json.dumps(journal, sort_keys=True))
    save()
    rollout.recover(journal, save)
    rollout.fence()
    if before != terminal.service_identity(terminal._service()):
        raise ValueError('api_traffic_drift_during_restore')
    if journal['phase'] != 'RESTORED' or rollout.scheduler()['state'] != 'ENABLED':
        raise ValueError('rollout_restore_not_verified')
    rollout.command(rollout.LEASE + ['release', '--safe-to-release'])
    print(json.dumps({'status': 'PASS', 'operation': 'exact_abandoned_rollout_restore',
                      'original_run': terminal.OWNER_RUN, 'baseline_source_sha': BASELINE,
                      'scheduler_restored': True, 'canonical_ledger_writes': 0,
                      'api_traffic_unchanged': True}))


if __name__ == '__main__':
    main()
