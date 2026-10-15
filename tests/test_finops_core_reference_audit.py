import importlib.util
from pathlib import Path
import pytest

p=Path("scripts/gcp/finops_core_reference_audit.py")
spec=importlib.util.spec_from_file_location("finops_core_reference_audit",p)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def test_recursive_known_core_identity_keys_not_plain_hashes():
    good="sha256:"+"a"*64
    value={"core_snapshot_id":good,"specialists":[{"other_hash":good}],
           "nested":{"core_snapshot_ids":[good,None]}}
    assert module.references(value)=={good}
    assert module.references({"hash":good})==set()

def test_bad_identity_ref_fails_closed():
    with pytest.raises(ValueError,match="INVALID_CORE_REFERENCE_CONTRACT"):
        module.references({"core_snapshot_id":"not-a-core-snapshot"})

def test_approved_artifacts_only():
    assert module.relevant_mart("executions/test/specialist-manifest.json")
    assert module.relevant_mart("ml-oos-data/v1/abc/manifest.json")
    assert not module.relevant_mart("private/users/trades.json")
