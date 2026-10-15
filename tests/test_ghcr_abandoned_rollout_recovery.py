from hashlib import sha256
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]/'scripts/gcp'))
import ghcr_abandoned_rollout_recovery as recovery


def journal():
    return {'source_sha': recovery.SOURCE, 'phase': 'RECOVERY_REQUIRED',
            'rollback_mode': 'reversible_ghcr', 'rollback_baseline_sha': recovery.BASELINE,
            'rollback_baseline_verified': True, 'scheduler_hash': 'original-schedule',
            'snapshots': {name: {'image': 'old-'+name, 'configuration_hash': 'config-'+name}
                          for name in recovery.rollout.REQUIRED_JOBS},
            'targets': {name: 'new-'+name for name, _ in recovery.rollout.JOB_COMPONENT}}


def test_only_exact_receipt_bytes_and_verified_baseline_are_accepted(monkeypatch):
    value = journal()
    raw = json.dumps(value).encode()
    monkeypatch.setattr(recovery, 'RECEIPT_HASH', sha256(raw).hexdigest())
    assert recovery.verify_receipt(raw) == value
    with pytest.raises(ValueError, match='hash_mismatch'):
        recovery.verify_receipt(raw+b' ')
    for key, bad in [('rollback_baseline_verified', False), ('phase', 'PASS'),
                     ('source_sha', '0'*40), ('rollback_mode', 'user_authorized_forward_only'),
                     ('snapshots', {}), ('targets', {})]:
        changed = json.dumps({**value, key: bad}).encode()
        monkeypatch.setattr(recovery, 'RECEIPT_HASH', sha256(changed).hexdigest())
        with pytest.raises(ValueError, match='identity_mismatch'):
            recovery.verify_receipt(changed)


def test_paused_recovery_rejects_running_jobs_config_drift_and_unrelated_images(monkeypatch):
    value = journal()
    rollout = recovery.rollout
    monkeypatch.setattr(rollout, 'legacy_writers', lambda: None)
    monkeypatch.setattr(rollout, 'fence', lambda: None)
    monkeypatch.setattr(rollout, 'scheduler', lambda: {'state': 'PAUSED'})
    monkeypatch.setattr(rollout, 'scheduler_fingerprint', lambda _: 'original-schedule')
    monkeypatch.setattr(rollout, 'job', lambda name: {'name': name})
    monkeypatch.setattr(rollout, 'image', lambda row: 'new-'+row['name'] if row['name'] in value['targets'] else 'old-'+row['name'])
    monkeypatch.setattr(rollout, 'fingerprint', lambda row: 'config-'+row['name'])
    recovery.validate_paused_state(value)
    monkeypatch.setattr(rollout, 'image', lambda _: 'unrelated-image')
    with pytest.raises(ValueError, match='runtime_drift'):
        recovery.validate_paused_state(value)
    monkeypatch.setattr(rollout, 'scheduler', lambda: {'state': 'ENABLED'})
    with pytest.raises(ValueError, match='scheduler_baseline_drift'):
        recovery.validate_paused_state(value)
    def active():
        raise ValueError('execution_not_terminal')
    monkeypatch.setattr(rollout, 'fence', active)
    with pytest.raises(ValueError, match='execution_not_terminal'):
        recovery.validate_paused_state(value)
