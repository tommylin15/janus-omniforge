from pathlib import Path


ROOT = Path(__file__).parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "deploy-dev.yml").read_text(encoding="utf-8")
INGESTION_WORKFLOW = (ROOT / ".github" / "workflows" / "run-dev-ingestion.yml").read_text(encoding="utf-8")
VERIFY = (ROOT / "scripts" / "gcp" / "verify-dev.sh").read_text(encoding="utf-8")
MIGRATION_RUNNER = (ROOT / "scripts" / "gcp" / "apply-private-storage-postgres-migration.sh").read_text(encoding="utf-8")
MIGRATION = (ROOT / "infra" / "postgres" / "migrations" / "030_private_stock_master_read.sql").read_text(encoding="utf-8")
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


def test_private_stock_master_acl_has_bounded_control_owner_transport():
    compile(INGESTION_ENTRYPOINT, str(ROOT / "jobs/ingestion-core/ingestion_core/runtime_entrypoint.py"), "exec")
    assert 'CONTROL_MIGRATION_PRIVATE_STOCK_MASTER_READ = "030_private_stock_master_read"' in INGESTION_ENTRYPOINT
    assert 'raise ValueError("unsupported control migration")' in INGESTION_ENTRYPOINT
    assert "has_schema_privilege('janus_private_api', 'control', 'USAGE')" in INGESTION_ENTRYPOINT
    assert "has_table_privilege('janus_private_pipeline', 'control.stock_master', 'SELECT')" in INGESTION_ENTRYPOINT
    assert "operation=control-migration" in INGESTION_WORKFLOW
    assert "[[ \"${migration}\" == '030_private_stock_master_read' ]]" in INGESTION_WORKFLOW
    assert "JANUS_CONTROL_MIGRATION=${MIGRATION}" in INGESTION_WORKFLOW
    assert "gcloud run jobs execute janus-ingestion-core" in INGESTION_WORKFLOW
