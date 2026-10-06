from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ingestion_core import runtime_entrypoint


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


def test_private_operations_rollout_seeds_runtime_evidence_once_and_verifies_admin_manifest():
    private_job = WORKFLOW.split("  deploy-private-pipeline:\n", 1)[1].split("\n  migrate-operations:", 1)[0]
    assert "Seed Private Pipeline operations evidence" in private_job
    assert "needs.detect.outputs.private_ops_schema == 'true'" in private_job
    assert "gcloud run jobs execute janus-private-pipeline" in private_job
    assert "--wait" in private_job
    assert "/app/admin-manifest.json" in VERIFY
    assert 'manifest.get("id") != "/app/admin"' in VERIFY
    assert 'manifest.get("start_url") != "/app/admin"' in VERIFY
    assert 'href="/app/admin-manifest.json"' in VERIFY


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
    compile(INGESTION_ENTRYPOINT, str(ROOT / "jobs/ingestion-core" / "ingestion_core" / "runtime_entrypoint.py"), "exec")
    assert "032_liquid_500" in INGESTION_ENTRYPOINT
    assert "032_liquid_500" in INGESTION_WORKFLOW
    assert "CREATE TABLE IF NOT EXISTS control.liquid_500_versions" in INGESTION_ENTRYPOINT
    assert "CREATE TABLE IF NOT EXISTS control.liquid_500_members" in INGESTION_ENTRYPOINT
    assert "liquid_500_versions" in LIQUID_500_MIGRATION
    assert "liquid_500_members" in LIQUID_500_MIGRATION
    assert "rank BETWEEN 1 AND 500" in LIQUID_500_MIGRATION
    assert "janus_web_control" in LIQUID_500_MIGRATION
    assert "janus_private_api" in LIQUID_500_MIGRATION


def test_liquid_500_tpex_source_is_historical_only_and_not_rerunnable():
    assert "033_liquid_500_tpex_source" not in INGESTION_ENTRYPOINT
    assert "033_liquid_500_tpex_source" not in INGESTION_WORKFLOW
    assert "_apply_liquid_500_tpex_source" not in INGESTION_ENTRYPOINT
    assert "033_liquid_500_tpex_source" in LIQUID_500_TPEX_MIGRATION


def test_full_500_collection_uses_batched_default_sources_in_dev():
    assert '--remove-env-vars="INGESTION_DATASETS"' in DEPLOY
    assert "full-market-500|" in INGESTION_WORKFLOW
    assert 'dataset_selection=""' in INGESTION_WORKFLOW
    assert "twse-market-volume|taiex" in INGESTION_WORKFLOW
    assert "tpex-market-volume" not in INGESTION_WORKFLOW
    assert "tpex-benchmark" not in INGESTION_WORKFLOW
    assert "trap cleanup_job_env EXIT" in INGESTION_WORKFLOW
    assert 'MART_JOB=janus-intelligence-mart,GCP_REGION=${GCP_REGION},MART_OPERATION=queue' in INGESTION_WORKFLOW
    assert "tests/test_portfolio_deploy_contract.py" in WORKFLOW


def test_fact_pack_analysis_replay_disables_outer_cloud_run_retry_and_restores_default():
    analysis_branch = INGESTION_WORKFLOW.split("if [[ \"${OPERATION}\" == 'analysis' ]]", 1)[1].split("fi", 1)[0]
    cleanup = INGESTION_WORKFLOW.split("cleanup_job_env()", 1)[1].split("trap cleanup_job_env EXIT", 1)[0]
    assert "--max-retries=0" in analysis_branch
    assert "--max-retries=1" in cleanup


def test_private_stock_master_acl_has_bounded_control_owner_transport():
    compile(INGESTION_ENTRYPOINT, str(ROOT / "jobs/ingestion-core" / "ingestion_core" / "runtime_entrypoint.py"), "exec")
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


def test_fact_pack_analysis_replay_uses_control_generated_uuid_trace():
    compile(INGESTION_ENTRYPOINT, str(ROOT / "jobs/ingestion-core" / "ingestion_core" / "runtime_entrypoint.py"), "exec")
    assert "control.enqueue_analysis(config_id, symbols)" in INGESTION_ENTRYPOINT
    assert 'trace_id=f"fact-pack-acceptance:{config_id}"' not in INGESTION_ENTRYPOINT


def test_fact_pack_analysis_replay_retriggers_when_older_queue_work_claims_first():
    class FakeControl:
        def __init__(self):
            self.statuses = iter(("queued", "queued", "succeeded"))
            self.closed = False

        def enqueue_analysis(self, config_id, symbols):
            assert (config_id, symbols) == ("first-batch", ("2330",))
            return SimpleNamespace(execution_id="target-analysis")

        def get_execution(self, execution_id):
            assert execution_id == "target-analysis"
            return SimpleNamespace(status=SimpleNamespace(value=next(self.statuses)))

        def list_mart_reports(self, *, filters, limit):
            assert filters == {"execution_id": "target-analysis"}
            assert limit == 51
            return [{"analysis_outcome": "complete", "publication_status": "published"}]

        def close(self):
            self.closed = True

    control = FakeControl()
    clock = iter((0.0, 0.0, 61.0, 62.0))
    triggers = []

    def trigger(execution_id, *, delay_seconds):
        triggers.append((execution_id, delay_seconds))
        return {"status": "accepted", "analysis_execution_id": execution_id}

    with (
        patch.object(runtime_entrypoint, "_control_plane", return_value=control),
        patch.object(runtime_entrypoint, "_trigger_mart", side_effect=trigger),
        patch.object(runtime_entrypoint, "monotonic", side_effect=lambda: next(clock)),
        patch.object(runtime_entrypoint, "sleep"),
    ):
        result = runtime_entrypoint._run_analysis_replay(
            "first-batch", ("2330",), timeout_seconds=120
        )

    assert triggers == [("target-analysis", 0), ("target-analysis", 0)]
    assert result["analysis_execution_id"] == "target-analysis"
    assert result["mart_triggers"] == 2
    assert result["reports"] == 1
    assert control.closed


def test_fact_pack_analysis_replay_retries_same_target_after_mart_retrying():
    class FakeControl:
        def __init__(self):
            self.statuses = iter(("retrying", "succeeded"))
            self.enqueue_calls = 0
            self.closed = False

        def enqueue_analysis(self, config_id, symbols):
            self.enqueue_calls += 1
            assert (config_id, symbols) == ("first-batch", ("2330",))
            return SimpleNamespace(execution_id="target-analysis")

        def get_execution(self, execution_id):
            assert execution_id == "target-analysis"
            return SimpleNamespace(status=SimpleNamespace(value=next(self.statuses)))

        def list_mart_reports(self, *, filters, limit):
            assert filters == {"execution_id": "target-analysis"}
            assert limit == 51
            return [{"analysis_outcome": "complete", "publication_status": "published"}]

        def close(self):
            self.closed = True

    control = FakeControl()
    clock = iter((0.0, 61.0, 62.0))
    triggers = []

    def trigger(execution_id, *, delay_seconds):
        triggers.append((execution_id, delay_seconds))
        return {"status": "accepted", "analysis_execution_id": execution_id}

    with (
        patch.object(runtime_entrypoint, "_control_plane", return_value=control),
        patch.object(runtime_entrypoint, "_trigger_mart", side_effect=trigger),
        patch.object(runtime_entrypoint, "monotonic", side_effect=lambda: next(clock)),
        patch.object(runtime_entrypoint, "sleep"),
    ):
        result = runtime_entrypoint._run_analysis_replay(
            "first-batch", ("2330",), timeout_seconds=120
        )

    assert control.enqueue_calls == 1
    assert triggers == [("target-analysis", 0), ("target-analysis", 0)]
    assert result["analysis_execution_id"] == "target-analysis"
    assert result["mart_triggers"] == 2
    assert control.closed


def test_admin_runbook_is_in_runtime_and_retired_admin_redirect_is_verified():
    ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert "!doc/runbook-data-supplement.md" in ignored
    assert "url=/app/admin" in VERIFY
    assert "legacy static Admin rollback surface" not in VERIFY
