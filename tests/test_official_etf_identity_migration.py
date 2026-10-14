"""Official TPEx bond ETF identity is a provenance-audited, one-symbol dev fix."""
from pathlib import Path

from scripts.gcp.analysis_schema_bootstrap import payload

ROOT = Path(__file__).parents[1]
MIGRATION = "058_official_held_etf_identity"


def test_00719b_migration_is_source_authorized_idempotent_and_not_portfolio_mutation():
    sql = (ROOT / "infra/postgres/migrations" / (MIGRATION + ".sql")).read_text()
    assert "00719B" in sql and "元大美債1-3" in sql
    assert "https://wwwov.tpex.org.tw/web/etf/etf_specification_bond_detail.php?code=00719B&l=zh-tw" in sql
    assert "DATE '2018-02-01'" in sql
    assert "tpex_official_bond_etf" in sql and "'BOND_ETF'" in sql
    assert "control.official_instrument_identity_provenance" in sql
    assert "ON CONFLICT (symbol) DO NOTHING" in sql
    assert "NOT EXISTS (" in sql and "control.market_universe_members WHERE symbol='00719B'" in sql
    assert "NOT has_table_privilege('janus_public_api'" in sql
    assert sql.index("-- PHASE: acceptance") < sql.index("INSERT INTO control.schema_migrations")
    upper = sql.upper()
    assert "DELETE FROM " not in upper
    assert "UPDATE PRIVATE." not in upper
    assert "INSERT INTO PRIVATE." not in upper
    assert "UPDATE CONTROL.STOCK_MASTER" not in upper


def test_058_migration_bounded_existing_job_override():
    sql = (ROOT / "infra/postgres/migrations" / (MIGRATION + ".sql")).read_bytes()
    source = {
        "etag": "existing-ready-job",
        "template": {"template": {"containers": [{"name": "ingestion", "command": ["python"]}]}}
    }
    p = payload(source, sql, MIGRATION)
    assert set(p) == {"etag", "overrides"}
    assert p["etag"] == "existing-ready-job"
    override = p["overrides"]
    assert override["taskCount"] == 1
    assert override["timeout"] == "300s"
    assert len(override["containerOverrides"]) == 1
    env = {x["name"]: x["value"] for x in override["containerOverrides"][0]["env"]}
    assert env["JANUS_ANALYSIS_MIGRATION_NAME"] == MIGRATION
    assert len(env["JANUS_ANALYSIS_MIGRATION_HASH"]) == 64
    assert "cpu" not in override and "memory" not in override


def test_new_migration_uses_existing_dev_procedure_without_new_iam():
    workflow = (ROOT / ".github/workflows/serving-schema-migration-dev.yml").read_text()
    assert "058_official_held_etf_identity" in workflow
    assert "analysis_schema_bootstrap.py" in workflow
    assert "ops/serving-schema-migration" in workflow
    assert "janus-ingestion-core" in workflow
    assert "add-iam-policy-binding" not in workflow
