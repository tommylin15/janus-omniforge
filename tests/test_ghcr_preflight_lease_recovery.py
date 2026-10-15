from hashlib import sha256
import json
from pathlib import Path
import sys
from unittest.mock import patch
import pytest

sys.path.insert(0,str(Path(__file__).parents[1] / "scripts/gcp"))
import ghcr_preflight_lease_recovery as fix


def sample():
    return {"source_sha":fix.SOURCE_SHA,"rollback_mode":"reversible_ghcr",
            "phase":"RECOVERY_REQUIRED","failed_stage":"preflight",
            "operations":[],"canaries":[],"snapshots":{},
            "scheduler_hash":"a"*64,
            "targets":{name:"digest" for name,_ in fix.rollout.JOB_COMPONENT}}


def test_receipt_exact_bytes_and_zero_mutation(monkeypatch):
    body=sample()
    raw=json.dumps(body).encode()
    monkeypatch.setattr(fix,"RECEIPT_SHA256",sha256(raw).hexdigest())
    assert fix.verify_receipt(raw)==body
    with pytest.raises(ValueError,match="hash_mismatch"):
        fix.verify_receipt(raw+b" ")
    for key,bad in (("phase","PASS"),("failed_stage","update_core"),("operations",[{}]),
                    ("snapshots",{"a":{}}),("canaries",[{}]),("source_sha","0"*40),
                    ("scheduler_hash","bad")):
        changed=json.dumps({**body,key:bad}).encode()
        monkeypatch.setattr(fix,"RECEIPT_SHA256",sha256(changed).hexdigest())
        with pytest.raises(ValueError,match="identity_mismatch"):
            fix.verify_receipt(changed)


def test_preflight_lease_release_rejects_original_runtime_drift():
    targets=[name for name,_ in fix.rollout.JOB_COMPONENT]
    req={"expected_images":{name:"old" for name in targets},
         "expected_config_hashes":{name:"hash" for name in targets}}
    journal={"scheduler_hash":"expected"}
    with patch.object(fix.rollout,"legacy_writers"), \
         patch.object(fix.rollout,"scheduler",return_value={"state":"ENABLED"}), \
         patch.object(fix.rollout,"scheduler_fingerprint",return_value="expected"), \
         patch.object(fix.rollout,"job",return_value={"name":"job"}), \
         patch.object(fix.rollout,"image",return_value="old"), \
         patch.object(fix.rollout,"fingerprint",return_value="hash"):
        fix.verify_original_runtime(req,journal)
        with patch.object(fix.rollout,"image",return_value="changed"):
            with pytest.raises(ValueError,match="preflight_original_job_drift"):
                fix.verify_original_runtime(req,journal)
        with patch.object(fix.rollout,"scheduler",return_value={"state":"PAUSED"}):
            with pytest.raises(ValueError,match="preflight_original_scheduler_drift"):
                fix.verify_original_runtime(req,journal)
        with patch.object(fix.rollout,"scheduler_fingerprint",return_value="drift"):
            with pytest.raises(ValueError,match="preflight_original_scheduler_drift"):
                fix.verify_original_runtime(req,journal)
