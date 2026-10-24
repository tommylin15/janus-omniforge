"""C1-A live evidence hard bounds; no table DELETE, data scan or secret output."""
from pathlib import Path
import ast
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts/gcp"))
import governance_c1a_live_proof as m

def test_fixed_scope_and_explicit_nonpublication():
    ast.parse((ROOT/"scripts/gcp/governance_c1a_live_proof.py").read_text())
    assert len(m.CORE)==2 and len(m.MART)==11
    assert len(set(m.CORE+m.MART))==13
    assert m.MAX_LOG_ENTRIES==300
    assert m.WINDOW_DAYS==7
    assert "to_arrow(" not in m.PROBE and ".scan(" not in m.PROBE
    assert "delete(" not in m.PROBE and "UPDATE " not in m.PROBE
    assert "independent_recovery_verified=False" in m.PROBE
    assert "read_only=True" in m.PROBE

def test_guard_rejects_legacy_57_and_any_permission_expansion():
    base=dict(audit_focus="c1a-live-table-reader-recovery-20261024",
              scope="existing-dev",read_only=True,no_data_mutation=True,
              no_template_mutation=True,no_private_row_data=True,
              no_new_resources=True,no_iam_expansion=True,execution_count=1)
    m.request_guard(base)
    for k in base:
        req=base.copy();req[k]=None
        with pytest.raises(ValueError):
            m.request_guard(req)

def test_fail_closed_job_overrides_and_fingerprint_preserving(monkeypatch):
    template={"template":{"template":{"containers":[{"name":"job","command":[]}]}}}
    override=m.overrides(template,"a"*40,"core")
    assert override["args"][0]=="python" and override["args"][1]=="-c"
    assert override["env"][-1]=={"name":"JANUS_C1A_LAYER","value":"core"}
    assert "image" not in override
    assert "secrets" not in str(override).lower()
    template["template"]["template"]["containers"][0]["command"]=["bash"]
    with pytest.raises(ValueError,match="entrypoint_drift"):
        m.overrides(template,"a"*40,"core")

def test_recovery_and_reader_evidence_never_promoted_by_log_mentions():
    cores={"tables":[{"name":n,"status":"READABLE","current_snapshot_id":"1"}
                     for n in m.CORE]}
    marts={"tables":[{"name":n,"status":"READABLE","current_snapshot_id":"2"}
                     for n in m.MART]}
    evidence=m.decide(cores,marts,[{"name":"janus-api",
        "table_mentions":{m.MART[0]:10}}])
    assert len(evidence)==13
    assert evidence[m.MART[0]]["log_mentions"][0]["count"]==10
    assert all(x["actual_business_reader"]=="UNKNOWN_NO_TABLE_LEVEL_RUNTIME_TRACE"
               for x in evidence.values())
    assert all(not x["independent_recovery_verified"] for x in evidence.values())
