from pathlib import Path


ROOT = Path(__file__).parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "deploy-dev.yml").read_text(encoding="utf-8")
INGESTION_WORKFLOW = (ROOT / ".github" / "workflows" / "run-dev-ingestion.yml").read_text(encoding="utf-8")
VERIFY = (ROOT / "scripts" / "gcp" / "verify-dev.sh").read_text(encoding="utf-8")
MIGRATION_RUNNER = (ROOT / "scripts" / "gcp" / "apply-private-storage-postgres-migration.sh").read_text(encoding="utf-8")
MIGRATION = (ROOT / "infra" / "postgres" / "migrations" / "030_private_stock_master_read.sql").read_text(encoding="utf-8")
COVERAGE_MIGRATION = (ROOT / "infra" / "postgres" / "migrations" / "031_portfolio_market_coverage.sql").read_text(encoding="utf-8")
LIQUID_500_MIGRATION = (ROOT / "infra" / "postgres" / "migrations" / "032_liquid_500.sql").read_text(encoding="utf-8")
LIQUID_500_TPEX_MIGRATION = (ROOT / "infra" / "postgres" / "migrations" / "033_liquid_500_tpex_source.sql").read_text(encoding="utf-8")
INGESTION_ENTRYPOINT = (ROOT / "jobs" / "ingestion-core" / "ingestion_core" / "runtime_entrypoint.py").read_text(encoding="utf-8")
CLOUDBUILD = (ROOT / "cloudbuild.yaml").read_text(encoding="utf-8")
DEPLOY = (ROOT / "scripts" / "gcp" / "deploy-dev.sh").read_text(encoding="utf-8")


def test_api_source_changes_gate_private_portfolio_tests():
    for test_path in (
        "tests/test_private_pipeline.py",
        "tests/test_user_api.py",
        "tests/test_portfolio_completeness.py",
        "tests/test_portfolio_api_completeness.py",
        "tests/test_portfolio_revaluation.py",
    ):
        assert test_path in WORKFLOW


def test_api_source_changes_deploy_and_verify_private_pipeline():
    assert "private_pipeline_runtime:" in WORKFLOW
    assert "- 'services/api/**'" in WORKFLOW.split("private_pipeline_runtime:", 1)[1]
    assert "deploy-private-pipeline:" in WORKFLOW
    private_job = WORKFLOW.split("deploy-private-pipeline:", 1)[1]
    assert "bash scripts/gcp/deploy-dev.sh private-pipeline" in private_job
    assert "bash scripts/gcp/verify-dev.sh private-pipeline" in private_job
    assert "private-pipeline)" in VERIFY
    assert "verify_job janus-private-pipeline" in VERIFY


def test_private_pipeline_runtime_configuration_is_applied_by_cloud_build_identity():
    assert 'if [[ "${_RUNTIME_NAME}" == "janus-private-pipeline" ]]' in CLOUDBUILD
    for flag in (
        '--service-account="janus-private-pipeline@${PROJECT_ID}.iam.gserviceaccount.com"',
        '--tasks=1',
        '--parallelism=1',
        '--max-retries=1',
        '--task-timeout=30m',
        '--remove-env-vars="VALUATION_DATE"',
        '--update-secrets="JANUS_API_POSTGRES_BUNDLE=janus-runtime-bundle:latest"',
    ):
        assert flag in CLOUDBUILD
    private_branch = DEPLOY.split("  private-pipeline)", 1)[1].split("    ;;", 1)[0]
    assert "gcloud run jobs update" not in private_branch


def test_private_stock_master_acl_migration_is_in_dev_migration_runner():
    assert "/opt/janus/migrations/030_private_stock_master_read.sql" in MIGRATION_RUNNER
    assert "GRANT USAGE ON SCHEMA control TO janus_private_api, janus_private_pipeline" in MIGRATION
    assert "GRANT SELECT ON control.stock_master TO janus_private_api, janus_private_pipeline" in MIGRATION


def test_portfolio_market_coverage_bridge_is_bounded_and_in_migration_runner():
    assert "/opt/janus/migrations/031_portfolio_market_coverage.sql" in MIGRATION_RUNNER
    assert "SECURITY DEFINER" in COVERAGE_MIGRATION
    assert "SET search_path = pg_catalog, pg_temp" in COVERAGE_MIGRATION
    assert "cc.dataset_id = 'ohlcv'" in COVERAGE_MIGRATION
    assert "cc.batch_scope = 'symbol'" in COVERAGE_MIGRATION
    assert "cc.coverage_tier <> 'core_focus'" in COVERAGE_MIGRATION
    assert "cc.market = sm.market" in COVERAGE_MIGRATION
    assert "sm.enabled" in COVERAGE_MIGRATION
    assert "REVOKE ALL ON FUNCTION control.request_portfolio_market_coverage(text[]) FROM PUBLIC" in COVERAGE_MIGRATION
    assert "GRANT EXECUTE ON FUNCTION control.request_portfolio_market_coverage(text[]) TO janus_private_pipeline" in COVERAGE_MIGRATION
    assert "janus_private_api" not in COVERAGE_MIGRATION.split("GRANT EXECUTE", 1)[1]


def test_liquid_500_schema_is_in_bounded_dev_migration_runner():
    compile(INGESTION_ENTRYPOINT, str(ROOT / "jobs/ingestion-core/ingestion_core/runtime_entrypoint.py"), "exec")
    assert "032_liquid_500" in INGESTION_ENTRYPOINT
    assert "032_liquid_500" in INGESTION_WORKFLOW
    assert "CREATE TABLE IF NOT EXISTS control.liquid_500_versions" in INGESTION_ENTRYPOINT
    assert "CREATE TABLE IF NOT EXISTS control.liquid_500_members" in INGESTION_ENTRYPOINT
    assert "liquid_500_versions" in LIQUID_500_MIGRATION
    assert "liquid_500_members" in LIQUID_500_MIGRATION
    assert "rank BETWEEN 1 AND 500" in LIQUID_500_MIGRATION
    assert "janus_web_control" in LIQUID_500_MIGRATION
    assert "janus_private_api" in LIQUID_500_MIGRATION


def test_liquid_500_tpex_source_is_enabled_and_rerunnable():
    assert "033_liquid_500_tpex_source" in INGESTION_ENTRYPOINT
    assert "033_liquid_500_tpex_source" in INGESTION_WORKFLOW
    assert "source_ids ? 'tpex'" in INGESTION_ENTRYPOINT
    assert "jsonb_array_elements_text" in LIQUID_500_TPEX_MIGRATION
    assert "033_liquid_500_tpex_source" in LIQUID_500_TPEX_MIGRATION


def test_private_stock_master_acl_has_bounded_control_owner_transport():
    compile(INGESTION_ENTRYPOINT, str(ROOT / "jobs/ingestion-core/ingestion_core/runtime_entrypoint.py"), "exec")
    assert 'CONTROL_MIGRATION_PRIVATE_STOCK_MASTER_READ = "030_private_stock_master_read"' in INGESTION_ENTRYPOINT
    assert 'CONTROL_MIGRATION_PORTFOLIO_MARKET_COVERAGE = "031_portfolio_market_coverage"' in INGESTION_ENTRYPOINT
    assert 'raise ValueError("unsupported control migration")' in INGESTION_ENTRYPOINT
    assert "SET LOCAL ROLE janus_control" in INGESTION_ENTRYPOINT
    assert "has_schema_privilege('janus_private_api', 'control', 'USAGE')" in INGESTION_ENTRYPOINT
    assert "has_table_privilege('janus_private_pipeline', 'control.stock_master', 'SELECT')" in INGESTION_ENTRYPOINT
    assert "has_function_privilege(" in INGESTION_ENTRYPOINT
    assert "operation=control-migration" in INGESTION_WORKFLOW
    assert "030_private_stock_master_read|031_portfolio_market_coverage" in INGESTION_WORKFLOW
    assert "JANUS_CONTROL_MIGRATION=${MIGRATION}" in INGESTION_WORKFLOW
    assert "gcloud run jobs execute janus-ingestion-core" in INGESTION_WORKFLOW
