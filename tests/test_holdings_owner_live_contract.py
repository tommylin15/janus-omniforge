"""Owner EOD live probe must read its correctly separated Private Mart schemas."""
import ast
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT / 'scripts/gcp/holdings_p0_owner_live_probe.py'

def test_exact_owner_pnl_acceptance_uses_unrealized_mart():
    text=SCRIPT.read_text(encoding='utf-8')
    ast.parse(text)
    m=re.search(r'OWNER_CODE = r"""(.*?)"""',text,re.DOTALL)
    assert m is not None
    source=m.group(1)
    ast.parse(source)
    assert "SELECT DISTINCT user_id FROM private.current_positions WHERE symbol=%s" in source
    assert "len(owners)!=1" in source
    assert "store.mart('mart_user_positions',owner)" in source
    assert "store.mart('mart_user_unrealized_pnl',owner)" in source
    assert "pnl_row.get('unrealized_pnl') is None" in source
    assert "pnl_row.get('unrealized_return') is None" in source
    assert "current_version=int(repo.latest_ledger_version(owner))" in source
    assert "repo.private_mart_write_lock" in source
    assert "tpex_openapi_eod" in source
    assert "ledger_mutation" in text
    assert "write_limit" in text
    assert "no_ledger_mutation" in text
    assert "janus-private-pipeline" in text
    assert "DELETE FROM" not in source.upper()
    assert "INSERT INTO private.ledger_events" not in source


def test_official_00719b_identity_reconciliation_is_source_scoped_and_no_ledger_mutation():
    script=SCRIPT.read_text(encoding='utf-8')
    assert 'EXPECTED_SOURCE = "1e9c31d148db540ee06cac5ccccd8fac8d619511"' in script
    assert 'sha256:d06ffd5a56439d00780af8e9908a060f154c53a69768915ebd5581d3a58cb95e' in script
    assert "identity.get('name')!='元大美債1-3'" in script
    assert "row.get('stock_name')!='元大美債1-3'" in script
    assert "row.get('identity_status')!='available'" in script
    assert "official_etf_identity_available" in script
    assert "private_mart_write_lock" in script
    assert "SELECT DISTINCT user_id FROM private.current_positions" in script
    assert "UPDATE private.ledger_events" not in script
    assert "INSERT INTO private.ledger_events" not in script
    assert "DELETE FROM private.ledger_events" not in script
