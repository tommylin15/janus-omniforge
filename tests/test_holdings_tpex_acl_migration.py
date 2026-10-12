"""Scope and execution contract for additive 053 TPEx EOD ACL fix."""
from pathlib import Path
import ast
import base64
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "infra/postgres/migrations/053_tpex_owner_eod_quote_acl.sql"
RUNNER = ROOT / "scripts/gcp/holdings_tpex_acl_migration.py"
OLD_SQL = ROOT / "infra/postgres/migrations/044_quotes_broker_profile.sql"


def test_tpex_acl_migration_is_one_bounded_owner_table():
    text = SQL.read_text()
    assert text.startswith("\\set ON_ERROR_STOP on")
    assert "SET ROLE janus_control;" in text
    assert "BEGIN;" in text and "COMMIT;" in text
    assert "GRANT SELECT, INSERT, UPDATE ON control.operational_last_quotes TO janus_private_pipeline;" in text
    assert "control.operational_last_quotes" in text
    assert "CHECK (source IN ('twse_mis', 'tpex_openapi_eod'))" in text
    assert "CHECK (session IN ('regular', 'off_session', 'official_close'))" in text
    assert "source <> 'tpex_openapi_eod'" in text
    assert "route_version = 'latest-price.v2'" in text
    assert "NOT has_table_privilege('janus_public_api'" in text
    assert "053_tpex_owner_eod_quote_acl" in text
    assert text.index("-- PHASE: acceptance") < text.index("INSERT INTO control.schema_migrations")
    for bad in ("GRANT ALL", "ALL TABLES", "DROP TABLE", "DELETE FROM",
                "ALTER ROLE", "CREATE ROLE", "TRUNCATE"):
        assert bad not in text.upper()
    assert "GRANT SELECT, INSERT, UPDATE ON control.operational_last_quotes TO janus_private_api;" in OLD_SQL.read_text()


def test_existing_ingestion_sql_executor_is_valid_and_fails_closed():
    source=RUNNER.read_text()
    ast.parse(source)
    assert "ops/holdings-tpex-acl-migration.json" in source
    assert "EXPECTED_IMAGE = re.compile" in source
    assert "existing_deployed_source_mismatch" not in source  # image is runtime-verified
    assert "new_resources" in source and "ledger_mutation" in source
    assert "args=[\"-c\",source]" in source
    assert "cloud.job(JOB)" in source
    assert "if not already:" in source
    assert "all(v is True for v in result)" in source
    assert "other_gcp_or_owner_mutations" in source
    assert "cloud.cloud(f\"{cloud.ROOT}/jobs/{JOB}:run\"" in source
    assert "cloud.terminal(execution)" in source
    match=re.search(r'INSIDE = r\"\"\"(.*?)\"\"\"',source,re.DOTALL)
    assert match, "one isolated ingress Python script is required"
    inner=match.group(1) % base64.b64encode(SQL.read_bytes()).decode('ascii')
    ast.parse(inner)
    assert "SELECT current_user" in inner and "janus_control" in inner
    assert "053_tpex_owner_eod_quote_acl" in inner
    assert "INSERT INTO control.schema_migrations" in inner
