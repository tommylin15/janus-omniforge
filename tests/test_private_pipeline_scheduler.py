from pathlib import Path


ROOT=Path(__file__).parents[1]


def test_direct_private_pipeline_scheduler_apply_is_retired_after_controller_cutover():
    script=(ROOT/"scripts/gcp/apply-private-pipeline-schedulers-dev.sh").read_text(encoding="utf-8")
    assert "Retired: direct janus-private-pipeline Cloud Scheduler jobs" in script
    assert "janus-batch-controller" in script
    assert "batch_controller.py" in script
    assert "exit 1" in script
    assert "gcloud scheduler jobs create" not in script
    assert "gcloud scheduler jobs update" not in script
    assert "gcloud run jobs add-iam-policy-binding" not in script
    assert "janus-ingestion-scheduler@" not in script


def test_private_pipeline_deploy_removes_fixed_valuation_default():
    build=(ROOT/"cloudbuild.yaml").read_text(encoding="utf-8")
    private=build.split('if [[ "${_RUNTIME_NAME}" == "janus-private-pipeline" ]]; then',1)[1].split("\n        fi",1)[0]
    assert '--remove-env-vars="VALUATION_DATE,PRIVATE_RECALC_QUEUE_MODE"' in private
    assert "--tasks=1" in private
    assert "--parallelism=8" in private
    assert '--remove-secrets="CORE_CATALOG_PASSWORD,PRIVATE_DATABASE_URL,PRIVATE_CATALOG_PASSWORD,JANUS_PIPELINE_POSTGRES_BUNDLE"' in private
    assert 'JANUS_API_POSTGRES_BUNDLE=janus-runtime-bundle:latest' in private


def test_janus_deploy_and_database_migration_use_one_secret_bundle():
    deploy=(ROOT/"scripts/gcp/deploy-dev.sh").read_text(encoding="utf-8")
    for name in (
        "JANUS_INGESTION_POSTGRES_BUNDLE",
        "JANUS_MART_POSTGRES_BUNDLE",
        "JANUS_API_POSTGRES_BUNDLE",
    ):
        assert f"{name}=janus-runtime-bundle:latest" in deploy
    assert "janus-postgres-api-bundle:latest" not in deploy
    assert "janus-agent-provider-bundle:latest" not in deploy

    migration=(ROOT/"scripts/gcp/cloudbuild-postgres-migration.yaml").read_text(encoding="utf-8")
    vm_migration=(ROOT/"scripts/gcp/apply-web-postgres-migration.sh").read_text(encoding="utf-8")
    assert "apply secret-manager '${PROJECT_ID}'" in migration
    assert "secrets/janus-runtime-bundle/versions/latest:access" in vm_migration
