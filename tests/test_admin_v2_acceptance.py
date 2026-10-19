import importlib.util
from pathlib import Path
import sys
import pytest


def test_synthetic_acceptance_is_exact_source_and_uses_no_financial_tables():
    path=Path(__file__).parents[1]/'scripts/gcp/admin_v2_acceptance.py'
    sys.path.insert(0,str(path.parent))
    spec=importlib.util.spec_from_file_location('admin_v2_acceptance',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert module.checked_source('a'*40,True)=='a'*40
    for source,approved in [('main',True),('a'*40,False)]:
        with pytest.raises(ValueError):module.checked_source(source,approved)
    compile(module.CANARY,'admin-v2-canary','exec')
    assert 'ledger_events' not in module.CANARY and 'current_positions' not in module.CANARY
    assert 'synthetic_cleanup_verified' in module.CANARY
