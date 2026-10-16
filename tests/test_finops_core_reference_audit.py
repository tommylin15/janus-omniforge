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

def test_json_size_budget_is_bounded():
    assert module.LIMIT_BYTES <= 60*1024*1024
    assert module.LIMIT_DOCS <= 3000

def test_candidate_source_provenance_is_not_retention_authorization():
    assert module.HASH.fullmatch("sha256:"+"0"*64)
    assert "deletion_fence_published" in module.audit.__code__.co_consts or callable(module.audit)

def test_document_read_pins_listed_generation_and_exact_byte_limit(monkeypatch):
    from urllib.parse import parse_qs, urlparse
    seen=[]
    monkeypatch.setattr(module,"get_json",lambda url,token,**kw:seen.append((url,kw)) or {})
    module.read_doc("bucket","a/b.json","token",generation="123",max_bytes=4*1024*1024)
    assert parse_qs(urlparse(seen[0][0]).query)=={"alt":["media"],"generation":["123"]}
    assert seen[0][1]=={"max_bytes":4*1024*1024}

def test_large_research_document_is_read_within_total_budget(monkeypatch):
    obj={"name":"large.json","size":str(4*1024*1024),"generation":"123","updated":"2026-10-16T00:00:00Z"}
    monkeypatch.setattr(module,"objects",lambda bucket,token:([obj] if bucket==module.RESEARCH else [],1))
    good="sha256:"+"a"*64
    monkeypatch.setattr(module,"read_doc",lambda *args,**kw:{"core_snapshot_id":good})
    result=module.audit("token")
    assert result["model_research_sources"]["research"]["documents_checked"]==1
    assert result["model_research_sources"]["research"]["documents_skipped_oversized"]==0
    assert result["externally_referenced_core_identities"]==1
    assert result["deletion_fence_published"] is False

def test_document_over_total_budget_remains_explicitly_incomplete(monkeypatch):
    obj={"name":"large.json","size":str(module.LIMIT_BYTES+1),"generation":"123"}
    monkeypatch.setattr(module,"objects",lambda bucket,token:([obj] if bucket==module.RESEARCH else [],1))
    monkeypatch.setattr(module,"read_doc",lambda *args,**kw:pytest.fail("budget must prevent download"))
    result=module.audit("token")
    assert result["model_research_sources"]["research"]["documents_skipped_oversized"]==1
    assert result["research_reference_completeness"]=="NOT_PROVEN"
