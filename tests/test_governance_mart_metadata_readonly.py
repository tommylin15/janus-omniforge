"""Offline guards for Mart-only existing-identity metadata readback."""
import ast
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
import pytest

SCRIPT=Path(__file__).resolve().parents[1]/"scripts/gcp/governance_mart_metadata_readonly.py"
spec=spec_from_file_location("governance_mart_metadata_readonly",SCRIPT)
m=module_from_spec(spec)
spec.loader.exec_module(m)

def test_mart_probes_are_metadata_only():
    ast.parse(m.MART_PROBE)
    assert 'catalog.list_tables(("mart",))' in m.MART_PROBE
    assert "catalog.load_table(name)" in m.MART_PROBE
    for forbidden in ("table.scan(", ".to_arrow(", ".delete(", ".upsert(", "create_namespace(", "DELETE FROM", "DROP TABLE"):
        assert forbidden not in m.MART_PROBE

def test_mart_override_selects_one_existing_job():
    job={"template":{"template":{"containers":[{"name":"mart","command":[]} ]}}}
    out=m.override(job,"a"*40)
    assert out["name"]=="mart"
    assert out["args"]==["python","-c",m.MART_PROBE]
    assert out["env"]==[{"name":"JANUS_GOVERNANCE_SOURCE_SHA","value":"a"*40}]
    job["template"]["template"]["containers"][0]["command"]=["bash"]
    with pytest.raises(ValueError):
        m.override(job,"a"*40)
